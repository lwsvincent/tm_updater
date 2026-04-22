"""Happy path tests for core module - end-to-end scan, compare, install flow."""
from pathlib import Path
from unittest.mock import patch

from updater.core import (
    PackageStatus,
    UpdateResult,
    check_updates,
    clear_pip_cache,
    find_venv_python,
    get_installed_versions_batch,
    install_updates,
    normalize_name,
    scan_packages,
)


class TestScanAndCompareFlow:
    """Simulate the full scan -> compare -> report cycle with fake whl files."""

    def test_full_scan_compare_cycle(self, tmp_path: Path) -> None:
        """Create whl files, scan them, compare against installed versions."""
        (tmp_path / "pkg_a-1.0.0-py3-none-any.whl").write_bytes(b"fake")
        (tmp_path / "pkg_a-2.0.0-py3-none-any.whl").write_bytes(b"fake")
        (tmp_path / "pkg_b-1.5.0-py3-none-any.whl").write_bytes(b"fake")
        (tmp_path / "pkg_c-3.0.0-py3-none-any.whl").write_bytes(b"fake")

        available = scan_packages(tmp_path)

        assert "pkg-a" in available
        assert available["pkg-a"][0] == "2.0.0"
        assert "pkg-b" in available
        assert "pkg-c" in available

        installed = {"pkg-a": "1.0.0", "pkg-b": "1.5.0", "pkg-c": None}
        statuses = check_updates(["pkg-a", "pkg-b", "pkg-c"], installed, available)

        status_map = {s.name: s for s in statuses}
        assert status_map["pkg-a"].status == "update_available"
        assert status_map["pkg-b"].status == "up_to_date"
        assert status_map["pkg-c"].status == "not_installed"

    def test_scan_ignores_non_whl_files(self, tmp_path: Path) -> None:
        """Only .whl files are picked up by scan."""
        (tmp_path / "pkg_a-1.0.0-py3-none-any.whl").write_bytes(b"whl")
        (tmp_path / "README.md").write_text("docs")
        (tmp_path / "pkg_b-1.0.0.tar.gz").write_bytes(b"tar")

        available = scan_packages(tmp_path)
        assert len(available) == 1
        assert "pkg-a" in available

    def test_all_up_to_date_produces_empty_update_list(self, tmp_path: Path) -> None:
        """When everything is current, no updates are flagged."""
        (tmp_path / "alpha-1.0.0-py3-none-any.whl").write_bytes(b"x")
        (tmp_path / "beta-2.0.0-py3-none-any.whl").write_bytes(b"x")

        available = scan_packages(tmp_path)
        installed = {"alpha": "1.0.0", "beta": "2.0.0"}
        statuses = check_updates(["alpha", "beta"], installed, available)

        to_update = [s for s in statuses if s.status in ("update_available", "not_installed")]
        assert len(to_update) == 0

    def test_package_not_in_source_is_skipped(self, tmp_path: Path) -> None:
        """A managed package not found in the source directory gets 'not_in_source'."""
        available = scan_packages(tmp_path)
        installed = {"missing-pkg": "1.0.0"}
        statuses = check_updates(["missing-pkg"], installed, available)

        assert statuses[0].status == "not_in_source"


class TestNormalizationEdgeCases:
    """Verify PEP 503 normalization handles real-world package names."""

    def test_underscore_to_hyphen(self) -> None:
        assert normalize_name("scope_driver") == "scope-driver"

    def test_mixed_case_and_separators(self) -> None:
        assert normalize_name("Am_Report.Generator") == "am-report-generator"

    def test_already_normalized(self) -> None:
        assert normalize_name("test-matrix") == "test-matrix"


class TestInstallUpdatesWithMock:
    """Test install flow with mocked subprocess to avoid real pip calls."""

    def test_install_success_flow(self, tmp_path: Path) -> None:
        """Successful install reports correct counts and calls progress."""
        whl = tmp_path / "pkg_a-2.0.0-py3-none-any.whl"
        whl.write_bytes(b"fake")

        statuses = [
            PackageStatus(
                name="pkg-a",
                installed="1.0.0",
                available="2.0.0",
                status="update_available",
                whl_path=whl,
            ),
        ]

        progress_log: list[tuple[str, str]] = []

        def on_progress(level: str, message: str) -> None:
            progress_log.append((level, message))

        with patch("updater.core.install_whl", return_value=(True, None)):
            result = install_updates(statuses, Path("python.exe"), on_progress=on_progress)

        assert result.total == 1
        assert result.updated == 1
        assert result.failed == 0
        assert result.all_success is True
        assert any("installing" in msg for _, msg in progress_log)
        assert any(level == "success" for level, _ in progress_log)

    def test_install_failure_reports_correctly(self, tmp_path: Path) -> None:
        """Failed install is counted and reported via progress callback."""
        whl = tmp_path / "pkg_x-1.0.0-py3-none-any.whl"
        whl.write_bytes(b"fake")

        statuses = [
            PackageStatus(
                name="pkg-x",
                installed=None,
                available="1.0.0",
                status="not_installed",
                whl_path=whl,
            ),
        ]

        progress_log: list[tuple[str, str]] = []

        with patch("updater.core.install_whl", return_value=(False, "pip error")):
            result = install_updates(
                statuses, Path("python.exe"), on_progress=lambda l, m: progress_log.append((l, m))
            )

        assert result.total == 1
        assert result.updated == 0
        assert result.failed == 1
        assert result.all_success is False
        assert "pkg-x" in result.failures
        assert any(level == "error" for level, _ in progress_log)

    def test_mixed_success_and_failure(self, tmp_path: Path) -> None:
        """Batch with both successes and failures reports mixed results."""
        whl_a = tmp_path / "a-2.0.0-py3-none-any.whl"
        whl_b = tmp_path / "b-1.0.0-py3-none-any.whl"
        whl_a.write_bytes(b"x")
        whl_b.write_bytes(b"x")

        statuses = [
            PackageStatus(name="a", installed="1.0.0", available="2.0.0", status="update_available", whl_path=whl_a),
            PackageStatus(name="b", installed=None, available="1.0.0", status="not_installed", whl_path=whl_b),
        ]

        call_count = 0

        def mock_install(whl_path: Path, python_exe: Path) -> tuple[bool, str | None]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return True, None
            return False, "network error"

        with patch("updater.core.install_whl", side_effect=mock_install):
            result = install_updates(statuses, Path("python.exe"))

        assert result.total == 2
        assert result.updated == 1
        assert result.failed == 1

    def test_no_updates_needed(self) -> None:
        """When all packages are up to date, install_updates is a no-op."""
        statuses = [
            PackageStatus(name="ok", installed="1.0.0", available="1.0.0", status="up_to_date"),
        ]
        result = install_updates(statuses, Path("python.exe"))

        assert result.total == 0
        assert result.updated == 0
        assert result.failed == 0
        assert result.all_success is True


class TestFindVenvPython:
    """Verify venv discovery logic with real filesystem."""

    def test_finds_venv_in_cwd(self, tmp_path: Path) -> None:
        """Discovers .venv/Scripts/python.exe relative to exe_dir."""
        venv_python = tmp_path / ".venv" / "Scripts" / "python.exe"
        venv_python.parent.mkdir(parents=True)
        venv_python.write_bytes(b"fake")

        result = find_venv_python(None, tmp_path)
        assert result is not None
        assert result.name == "python.exe"

    def test_explicit_venv_arg_wins(self, tmp_path: Path) -> None:
        """--venv argument takes priority over auto-discovery."""
        explicit_venv = tmp_path / "my_env"
        python_path = explicit_venv / "Scripts" / "python.exe"
        python_path.parent.mkdir(parents=True)
        python_path.write_bytes(b"fake")

        result = find_venv_python(str(explicit_venv), tmp_path)
        assert result is not None
        assert "my_env" in str(result)

    def test_returns_none_when_no_venv(self, tmp_path: Path) -> None:
        """Returns None when no venv can be found."""
        isolated = tmp_path / "isolated"
        isolated.mkdir()
        with patch("updater.core.Path") as MockPath:
            MockPath.cwd.return_value = isolated
            MockPath.side_effect = Path
            result = find_venv_python(None, tmp_path / "empty")
        assert result is None


class TestUpdateResult:
    """Verify UpdateResult semantics in realistic scenarios."""

    def test_all_success_property(self) -> None:
        r = UpdateResult(total=5, updated=5, failed=0, failures=[])
        assert r.all_success is True

    def test_partial_failure(self) -> None:
        r = UpdateResult(total=5, updated=3, failed=2, failures=["x", "y"])
        assert r.all_success is False

    def test_zero_total_is_success(self) -> None:
        """Nothing to update counts as success (important for launcher logic)."""
        r = UpdateResult(total=0, updated=0, failed=0, failures=[])
        assert r.all_success is True
