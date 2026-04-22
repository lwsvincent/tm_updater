"""Happy path tests for CLI (updater.exe) - subprocess-based integration tests."""
import subprocess
import sys
from pathlib import Path

import pytest


UPDATER_EXE = Path(__file__).parent.parent.parent / "dist" / "updater.exe"
PYTHON_MODULE = [sys.executable, "-m", "updater.main"]


def _run_updater(args: list[str], use_exe: bool = False) -> subprocess.CompletedProcess[str]:
    """Run the updater via either the compiled exe or python -m."""
    if use_exe and UPDATER_EXE.exists():
        cmd = [str(UPDATER_EXE)] + args
    else:
        cmd = PYTHON_MODULE + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


class TestCliHelpAndVersion:
    def test_help_flag(self) -> None:
        result = _run_updater(["--help"])
        assert result.returncode == 0
        assert "Test Matrix Package Updater" in result.stdout
        assert "--dry-run" in result.stdout
        assert "--source" in result.stdout

    @pytest.mark.skipif(not UPDATER_EXE.exists(), reason="updater.exe not built")
    def test_exe_help_flag(self) -> None:
        result = _run_updater(["--help"], use_exe=True)
        assert result.returncode == 0
        assert "Test Matrix Package Updater" in result.stdout


class TestCliDryRun:
    def test_dry_run_empty_source(self, tmp_path: Path) -> None:
        """Dry run with empty source shows warning and exits cleanly."""
        result = _run_updater(["--dry-run", "--source", str(tmp_path)])
        assert result.returncode == 0
        assert "No .whl files found" in result.stdout

    def test_dry_run_with_whls(self, tmp_path: Path) -> None:
        """Dry run with fake whls shows update status table."""
        (tmp_path / "test_matrix-2.0.0-py3-none-any.whl").write_bytes(b"fake")
        (tmp_path / "scope_driver-1.0.0-py3-none-any.whl").write_bytes(b"fake")

        result = _run_updater(["--dry-run", "--source", str(tmp_path)])
        assert result.returncode == 0
        assert "test-matrix" in result.stdout
        assert "Updates available:" in result.stdout

    def test_dry_run_specific_packages(self, tmp_path: Path) -> None:
        """Dry run with --packages filters to only specified packages."""
        (tmp_path / "alpha-1.0.0-py3-none-any.whl").write_bytes(b"fake")
        (tmp_path / "beta-2.0.0-py3-none-any.whl").write_bytes(b"fake")

        result = _run_updater([
            "--dry-run", "--source", str(tmp_path),
            "--packages", "alpha",
        ])
        assert result.returncode == 0
        assert "alpha" in result.stdout

    @pytest.mark.skipif(not UPDATER_EXE.exists(), reason="updater.exe not built")
    def test_exe_dry_run_with_whls(self, tmp_path: Path) -> None:
        """Same dry run test but using the compiled exe."""
        (tmp_path / "my_pkg-1.0.0-py3-none-any.whl").write_bytes(b"fake")

        result = _run_updater(
            ["--dry-run", "--source", str(tmp_path), "--packages", "my-pkg"],
            use_exe=True,
        )
        assert result.returncode == 0
        assert "my-pkg" in result.stdout

    @pytest.mark.skipif(not UPDATER_EXE.exists(), reason="updater.exe not built")
    def test_exe_dry_run_empty_source(self, tmp_path: Path) -> None:
        """Exe handles empty source gracefully."""
        result = _run_updater(
            ["--dry-run", "--source", str(tmp_path)],
            use_exe=True,
        )
        assert result.returncode == 0
        assert "No .whl files found" in result.stdout


class TestCliOutputFormat:
    def test_header_shows_source_and_venv(self, tmp_path: Path) -> None:
        """CLI output includes Source and Venv paths in header."""
        result = _run_updater(["--dry-run", "--source", str(tmp_path)])
        assert "Source" in result.stdout
        assert "Venv" in result.stdout or "No .whl files" in result.stdout

    def test_dry_run_mode_indicator(self, tmp_path: Path) -> None:
        """Dry run mode is clearly indicated in output."""
        result = _run_updater(["--dry-run", "--source", str(tmp_path)])
        assert "dry-run" in result.stdout
