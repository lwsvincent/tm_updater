from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

from updater.core import (
    PackageStatus,
    UpdateResult,
    normalize_name,
    scan_packages,
    check_updates,
    install_updates,
)


class TestNormalizeName:
    def test_hyphen(self) -> None:
        assert normalize_name("my-package") == "my-package"

    def test_underscore(self) -> None:
        assert normalize_name("my_package") == "my-package"

    def test_dot(self) -> None:
        assert normalize_name("my.package") == "my-package"

    def test_mixed(self) -> None:
        assert normalize_name("My_Package.Name") == "my-package-name"

    def test_uppercase(self) -> None:
        assert normalize_name("MyPackage") == "mypackage"


class TestPackageStatus:
    def test_up_to_date(self) -> None:
        ps = PackageStatus(
            name="pkg", installed="1.0.0", available="1.0.0", status="up_to_date"
        )
        assert ps.status == "up_to_date"

    def test_update_available(self) -> None:
        ps = PackageStatus(
            name="pkg", installed="1.0.0", available="2.0.0", status="update_available"
        )
        assert ps.status == "update_available"

    def test_not_installed(self) -> None:
        ps = PackageStatus(
            name="pkg", installed=None, available="1.0.0", status="not_installed"
        )
        assert ps.installed is None


class TestScanPackages:
    def test_scan_empty_dir(self, tmp_path: Path) -> None:
        result = scan_packages(tmp_path)
        assert result == {}

    def test_scan_nonexistent_dir(self) -> None:
        result = scan_packages(Path("/nonexistent"))
        assert result == {}

    def test_scan_finds_whl(self, tmp_path: Path) -> None:
        whl = tmp_path / "my_package-1.2.3-py3-none-any.whl"
        whl.write_bytes(b"fake")
        result = scan_packages(tmp_path)
        assert "my-package" in result
        assert result["my-package"][0] == "1.2.3"

    def test_scan_keeps_latest_version(self, tmp_path: Path) -> None:
        (tmp_path / "pkg-1.0.0-py3-none-any.whl").write_bytes(b"old")
        (tmp_path / "pkg-2.0.0-py3-none-any.whl").write_bytes(b"new")
        result = scan_packages(tmp_path)
        assert result["pkg"][0] == "2.0.0"


class TestCheckUpdates:
    def test_up_to_date(self) -> None:
        available = {"pkg-a": ("1.0.0", Path("pkg_a-1.0.0.whl"))}
        installed = {"pkg-a": "1.0.0"}
        statuses = check_updates(["pkg-a"], installed, available)
        assert statuses[0].status == "up_to_date"

    def test_update_available(self) -> None:
        available = {"pkg-a": ("2.0.0", Path("pkg_a-2.0.0.whl"))}
        installed = {"pkg-a": "1.0.0"}
        statuses = check_updates(["pkg-a"], installed, available)
        assert statuses[0].status == "update_available"

    def test_not_in_source(self) -> None:
        available: dict[str, tuple[str, Path]] = {}
        installed = {"pkg-a": "1.0.0"}
        statuses = check_updates(["pkg-a"], installed, available)
        assert statuses[0].status == "not_in_source"

    def test_not_installed(self) -> None:
        available = {"pkg-a": ("1.0.0", Path("pkg_a-1.0.0.whl"))}
        installed: dict[str, str | None] = {"pkg-a": None}
        statuses = check_updates(["pkg-a"], installed, available)
        assert statuses[0].status == "not_installed"


class TestUpdateResult:
    def test_all_success(self) -> None:
        r = UpdateResult(total=3, updated=3, failed=0, failures=[])
        assert r.all_success is True

    def test_has_failures(self) -> None:
        r = UpdateResult(total=3, updated=2, failed=1, failures=["pkg-x"])
        assert r.all_success is False


@pytest.fixture(scope="function")
def mock_subprocess() -> Generator[MagicMock, None, None]:
    """Patch updater.core.subprocess so all subprocess.run calls are intercepted."""
    with patch("updater.core.subprocess") as mock_sp:
        yield mock_sp


def test_install_updates_with_target_version(mock_subprocess: MagicMock) -> None:
    """Test that install_updates with target_version runs uninstall then install from local wheel."""
    python_exe = Path("C:\\venv\\Scripts\\python.exe")

    # Mock subprocess calls
    mock_subprocess.run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    # Call install_updates with target version and local whl_path
    result = install_updates(
        [
            PackageStatus(
                name="test-pkg",
                installed="1.0.0",
                available="3.0.0",
                status="update_available",
                whl_path=Path("test-pkg-2.5.0-py3-none-any.whl"),
            )
        ],
        python_exe,
        target_version="2.5.0",
    )

    # Assert: should call pip uninstall then pip install with local wheel
    calls = mock_subprocess.run.call_args_list
    assert len(calls) >= 2

    # First call: uninstall
    uninstall_call = calls[0]
    uninstall_cmd = uninstall_call[0][0]  # Extract positional arg
    assert isinstance(uninstall_cmd, list)
    uninstall_cmd_str = " ".join(map(str, uninstall_cmd))
    assert "uninstall" in uninstall_cmd_str
    assert "test-pkg" in uninstall_cmd_str

    # Second call: install with local wheel file (not PyPI version)
    install_call = calls[1]
    install_cmd = install_call[0][0]  # Extract positional arg
    assert isinstance(install_cmd, list)
    install_cmd_str = " ".join(map(str, install_cmd))
    assert "install" in install_cmd_str
    # Should use the local wheel file, not pip install from PyPI
    assert "test-pkg-2.5.0-py3-none-any.whl" in install_cmd_str
    assert "--no-deps" in install_cmd_str
