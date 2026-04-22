"""Happy path tests for launcher module - end-to-end launch scenarios."""
import subprocess
import sys
import time
from pathlib import Path

from updater.config import LauncherConfig, UpdaterConfig
from updater.core import UpdateResult
from updater.launcher import LauncherError, launch_executable, resolve_executable_path, should_launch

import pytest


class TestShouldLaunchDecisions:
    """Verify launch decision logic for all mode + result combinations."""

    def test_on_success_all_pass(self) -> None:
        result = UpdateResult(total=3, updated=3, failed=0, failures=[])
        assert should_launch("on_success", result) is True

    def test_on_success_with_failures(self) -> None:
        result = UpdateResult(total=3, updated=2, failed=1, failures=["x"])
        assert should_launch("on_success", result) is False

    def test_on_success_nothing_to_update(self) -> None:
        """Zero updates still counts as success."""
        result = UpdateResult(total=0, updated=0, failed=0, failures=[])
        assert should_launch("on_success", result) is True

    def test_on_complete_always_launches(self) -> None:
        result = UpdateResult(total=3, updated=1, failed=2, failures=["a", "b"])
        assert should_launch("on_complete", result) is True

    def test_on_complete_no_updates(self) -> None:
        result = UpdateResult(total=0, updated=0, failed=0, failures=[])
        assert should_launch("on_complete", result) is True


class TestResolveExecutablePath:
    """Verify path resolution with relative and absolute paths."""

    def test_relative_path_resolved_from_config_dir(self, tmp_path: Path) -> None:
        script = tmp_path / "start.py"
        script.write_text("print('hello')")

        resolved = resolve_executable_path("start.py", tmp_path)
        assert resolved.exists()
        assert resolved.name == "start.py"

    def test_absolute_path_used_directly(self, tmp_path: Path) -> None:
        script = tmp_path / "app.exe"
        script.write_bytes(b"MZ")

        resolved = resolve_executable_path(str(script), tmp_path)
        assert resolved == script.resolve()

    def test_missing_file_raises_launcher_error(self, tmp_path: Path) -> None:
        with pytest.raises(LauncherError, match="not found"):
            resolve_executable_path("nonexistent.py", tmp_path)

    def test_nested_relative_path(self, tmp_path: Path) -> None:
        nested = tmp_path / "scripts" / "run.py"
        nested.parent.mkdir()
        nested.write_text("print('nested')")

        resolved = resolve_executable_path("scripts/run.py", tmp_path)
        assert resolved.exists()


class TestLaunchExecutable:
    """Test actual process launching with a real Python script."""

    def test_launch_py_file_creates_process(self, tmp_path: Path) -> None:
        """Launch a .py script and verify a real process is created."""
        script = tmp_path / "hello.py"
        script.write_text("import sys; print('hello from launched app'); sys.exit(0)")

        config = UpdaterConfig(
            launcher=LauncherConfig(
                enabled=True,
                executable=str(script),
            ),
            config_dir=tmp_path,
        )

        proc = launch_executable(config, Path(sys.executable))
        assert proc.pid > 0
        proc.wait(timeout=10)

    def test_launch_py_with_args(self, tmp_path: Path) -> None:
        """Arguments are passed through to the launched script."""
        script = tmp_path / "echo_args.py"
        script.write_text(
            "import sys\n"
            "with open(sys.argv[1], 'w') as f:\n"
            "    f.write(' '.join(sys.argv[2:]))\n"
        )
        output_file = tmp_path / "output.txt"

        config = UpdaterConfig(
            launcher=LauncherConfig(
                enabled=True,
                executable=str(script),
                args=[str(output_file), "arg1", "arg2"],
            ),
            config_dir=tmp_path,
        )

        proc = launch_executable(config, Path(sys.executable))
        proc.wait(timeout=10)

        assert output_file.exists()
        assert output_file.read_text() == "arg1 arg2"

    def test_launch_missing_exe_raises(self, tmp_path: Path) -> None:
        """Attempting to launch a nonexistent file raises LauncherError."""
        config = UpdaterConfig(
            launcher=LauncherConfig(
                enabled=True,
                executable="does_not_exist.py",
            ),
            config_dir=tmp_path,
        )

        with pytest.raises(LauncherError):
            launch_executable(config, Path(sys.executable))


class TestEndToEndLaunchDecision:
    """Full flow: check update result -> decide launch -> resolve path."""

    def test_success_triggers_launch_resolution(self, tmp_path: Path) -> None:
        """After a successful update, the launcher resolves and is ready."""
        result = UpdateResult(total=2, updated=2, failed=0, failures=[])

        config = UpdaterConfig(
            launcher=LauncherConfig(
                enabled=True,
                executable="app.py",
                mode="on_success",
            ),
            config_dir=tmp_path,
        )

        assert should_launch(config.launcher.mode, result) is True

        script = tmp_path / "app.py"
        script.write_text("print('launched')")
        resolved = resolve_executable_path(config.launcher.executable, config.config_dir)
        assert resolved.exists()

    def test_failure_blocks_on_success_launch(self) -> None:
        """Failed update with on_success mode blocks the launch."""
        result = UpdateResult(total=2, updated=1, failed=1, failures=["broken"])

        assert should_launch("on_success", result) is False

    def test_failure_allows_on_complete_launch(self, tmp_path: Path) -> None:
        """Failed update with on_complete mode still allows launch."""
        result = UpdateResult(total=2, updated=1, failed=1, failures=["broken"])

        assert should_launch("on_complete", result) is True
