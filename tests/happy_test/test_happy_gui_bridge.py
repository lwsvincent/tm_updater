"""Happy path tests for GUI bridge (Api class) - no pywebview dependency needed."""
from pathlib import Path
from unittest.mock import MagicMock, patch

from updater.config import GuiConfig, LauncherConfig, UpdaterConfig
from updater.gui.app import Api


class TestApiGetConfig:
    def test_returns_flat_config_dict(self) -> None:
        """get_config() returns a flat dict suitable for JS consumption."""
        config = UpdaterConfig(
            launcher=LauncherConfig(
                enabled=True,
                executable="app.py",
                auto_launch=True,
                auto_update=False,
            ),
            gui=GuiConfig(theme="blueprint"),
        )
        api = Api(config, python_exe=None)
        result = api.get_config()

        assert result["launcher_enabled"] is True
        assert result["launcher_executable"] == "app.py"
        assert result["auto_launch"] is True
        assert result["auto_update"] is False
        assert result["theme"] == "blueprint"

    def test_disabled_launcher_config(self) -> None:
        """Default config returns disabled launcher."""
        config = UpdaterConfig()
        api = Api(config, python_exe=None)
        result = api.get_config()

        assert result["launcher_enabled"] is False
        assert result["launcher_executable"] == ""


class TestApiGetPackages:
    def test_no_python_exe_returns_empty(self) -> None:
        """Without a venv, get_packages returns empty list."""
        config = UpdaterConfig()
        api = Api(config, python_exe=None)
        assert api.get_packages() == []

    def test_returns_package_list_with_status(self) -> None:
        """With mocked pip, returns structured package data."""
        config = UpdaterConfig(packages=["pkg-a", "pkg-b"])
        api = Api(config, python_exe=Path("python.exe"))

        mock_versions = {"pkg-a": "1.0.0", "pkg-b": None}
        with patch("updater.gui.app.get_installed_versions_batch", return_value=mock_versions):
            packages = api.get_packages()

        assert len(packages) == 2
        pkg_a = next(p for p in packages if p["name"] == "pkg-a")
        pkg_b = next(p for p in packages if p["name"] == "pkg-b")

        assert pkg_a["installed"] == "1.0.0"
        assert pkg_a["status"] == "up_to_date"
        assert pkg_b["installed"] is None
        assert pkg_b["status"] == "not_installed"


class TestApiLaunchApp:
    def test_launch_without_python_returns_error(self) -> None:
        """launch_app() without python_exe returns error dict."""
        config = UpdaterConfig(
            launcher=LauncherConfig(enabled=True, executable="app.py"),
        )
        api = Api(config, python_exe=None)
        result = api.launch_app()

        assert result["success"] is False
        assert "No venv" in str(result["error"])
        assert result["pid"] is None

    def test_launch_success_returns_pid(self, tmp_path: Path) -> None:
        """Successful launch returns PID."""
        script = tmp_path / "app.py"
        script.write_text("import time; time.sleep(0.1)")

        config = UpdaterConfig(
            launcher=LauncherConfig(enabled=True, executable=str(script)),
            config_dir=tmp_path,
        )
        api = Api(config, python_exe=Path("python.exe"))

        mock_proc = MagicMock()
        mock_proc.pid = 12345

        with patch("updater.gui.app.launch_executable", return_value=mock_proc):
            result = api.launch_app()

        assert result["success"] is True
        assert result["pid"] == 12345

    def test_launch_error_returns_failure(self, tmp_path: Path) -> None:
        """LauncherError is caught and returned as error dict."""
        from updater.launcher import LauncherError

        config = UpdaterConfig(
            launcher=LauncherConfig(enabled=True, executable="missing.py"),
            config_dir=tmp_path,
        )
        api = Api(config, python_exe=Path("python.exe"))

        with patch(
            "updater.gui.app.launch_executable",
            side_effect=LauncherError("not found"),
        ):
            result = api.launch_app()

        assert result["success"] is False
        assert "not found" in str(result["error"])


class TestApiRunUpdateReentrancy:
    def test_concurrent_update_blocked(self) -> None:
        """Second run_update call is silently ignored while first is running."""
        config = UpdaterConfig()
        api = Api(config, python_exe=None)

        api._update_lock.acquire()
        api.run_update()
        assert api._update_lock.locked()

        api._update_lock.release()
