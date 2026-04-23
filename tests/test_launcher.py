import sys
from pathlib import Path

import pytest

from updater.core import UpdateResult
from updater.config import LauncherConfig, UpdaterConfig
from updater.launcher import (
    LauncherError,
    launch_executable,
    resolve_executable_path,
    should_launch,
)


class TestShouldLaunch:
    def test_on_success_all_ok(self) -> None:
        result = UpdateResult(total=3, updated=3, failed=0)
        assert should_launch("on_success", result) is True

    def test_on_success_nothing_to_update(self) -> None:
        result = UpdateResult(total=0, updated=0, failed=0)
        assert should_launch("on_success", result) is True

    def test_on_success_with_failures(self) -> None:
        result = UpdateResult(total=3, updated=2, failed=1, failures=["x"])
        assert should_launch("on_success", result) is False

    def test_on_complete_all_ok(self) -> None:
        result = UpdateResult(total=3, updated=3, failed=0)
        assert should_launch("on_complete", result) is True

    def test_on_complete_with_failures(self) -> None:
        result = UpdateResult(total=3, updated=2, failed=1, failures=["x"])
        assert should_launch("on_complete", result) is True


class TestResolveExecutablePath:
    def test_relative_path(self, tmp_path: Path) -> None:
        script = tmp_path / "start.py"
        script.write_text("pass")
        resolved = resolve_executable_path("start.py", tmp_path)
        assert resolved == script

    def test_absolute_path(self, tmp_path: Path) -> None:
        script = tmp_path / "start.py"
        script.write_text("pass")
        resolved = resolve_executable_path(str(script), tmp_path)
        assert resolved == script

    def test_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(LauncherError, match="not found"):
            resolve_executable_path("missing.py", tmp_path)


class TestLaunchExecutable:
    def test_launch_py_file(self, tmp_path: Path) -> None:
        mock_script = Path(__file__).parent / "mock_app.py"
        config = UpdaterConfig(
            launcher=LauncherConfig(
                enabled=True,
                executable=str(mock_script),
                args=["--test", "hello"],
            ),
            config_dir=tmp_path,
        )
        python_exe = Path(sys.executable)
        proc = launch_executable(config, python_exe)
        assert proc.pid > 0
        proc.terminate()
        proc.wait(timeout=5)

    def test_launch_missing_exe(self, tmp_path: Path) -> None:
        config = UpdaterConfig(
            launcher=LauncherConfig(
                enabled=True,
                executable="nonexistent.exe",
            ),
            config_dir=tmp_path,
        )
        with pytest.raises(LauncherError):
            launch_executable(config, Path("python.exe"))
