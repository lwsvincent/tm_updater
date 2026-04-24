from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from updater.config import GuiConfig, LauncherConfig, UpdaterConfig
from updater.core import UpdateResult
from updater.gui.app import Api


@pytest.fixture
def sample_config(tmp_path: Path) -> UpdaterConfig:
    """Create a sample config for testing."""
    return UpdaterConfig(
        packages=["test-pkg"],
        source=str(tmp_path),
        launcher=LauncherConfig(
            enabled=False,
            executable="",
            auto_launch=False,
            auto_update=False,
            auto_launch_enable=False,
            auto_update_enable=False,
            mode="on_success",
        ),
        gui=GuiConfig(theme="light"),
    )


@pytest.fixture
def api(sample_config: UpdaterConfig) -> Api:
    """Create an Api instance for testing."""
    return Api(sample_config, None)


@pytest.fixture
def api_with_python(sample_config: UpdaterConfig) -> Api:
    """Create an Api instance with a mock python_exe for testing."""
    return Api(sample_config, Path("python.exe"))


class TestGetVersions:
    def test_get_versions_returns_all_available_versions(
        self, api: Api, sample_config: UpdaterConfig, tmp_path: Path
    ) -> None:
        """Test that get_versions returns all versions sorted newest-first."""
        # Setup: Create multiple wheel files with different versions
        source_path = Path(sample_config.source)
        source_path.mkdir(exist_ok=True)

        # Create test wheel files
        (source_path / "test_pkg-3.0.0-py3-none-any.whl").write_bytes(b"fake")
        (source_path / "test_pkg-2.5.0-py3-none-any.whl").write_bytes(b"fake")

        # Call the API
        result = api.get_versions("test-pkg")

        # Assert
        assert result == ["3.0.0", "2.5.0"]  # newest first
        assert isinstance(result, list)


class TestInstallVersionedPackageSetsFlag:
    def test_install_versioned_package_sets_flag(
        self, api_with_python: Api, tmp_path: Path, sample_config: UpdaterConfig
    ) -> None:
        """Verify _auto_update_disabled is set to True after
        install_versioned_package.
        """
        # Create a fake wheel in the source directory so scan_packages finds it
        source_path = Path(sample_config.source)
        source_path.mkdir(exist_ok=True)
        (source_path / "test_pkg-2.5.0-py3-none-any.whl").write_bytes(b"fake")

        mock_result = UpdateResult(total=1, updated=1, failed=0, failures=[])

        # Patch _run_with_lock to run synchronously so flag is set before we assert
        api_with_python._run_with_lock = lambda fn: fn()  # type: ignore[assignment]

        with patch("updater.gui.app.install_updates", return_value=mock_result):
            with patch(
                "updater.gui.app.get_installed_versions_batch",
                return_value={"test-pkg": "1.0.0"},
            ):
                api_with_python.install_versioned_package("test-pkg", "2.5.0")

        assert api_with_python._auto_update_disabled is True


class TestCheckUpdatesRespectsAutoUpdateDisabled:
    def test_do_scan_returns_early_when_flag_set(self, api_with_python: Api) -> None:
        """_do_scan must return early without scanning when
        _auto_update_disabled is True.
        """
        api_with_python._auto_update_disabled = True

        mock_window = MagicMock()
        api_with_python._window = mock_window

        with patch("updater.gui.app.scan_packages") as mock_scan:
            with patch("updater.gui.app.check_updates") as mock_check:
                api_with_python._do_scan()

        # scan_packages and check_updates must NOT have been called
        mock_scan.assert_not_called()
        mock_check.assert_not_called()

        # onScanComplete must NOT have been called on the window
        for call in mock_window.evaluate_js.call_args_list:
            args = call[0]
            assert "onScanComplete" not in str(
                args
            ), "onScanComplete should not be called when auto-update is disabled"


class TestInstallVersionedPackageCallsInstallUpdates:
    def test_install_versioned_package_calls_install_updates_with_correct_args(
        self, api_with_python: Api, sample_config: UpdaterConfig
    ) -> None:
        """install_versioned_package must call install_updates with matching
        package and target_version."""
        source_path = Path(sample_config.source)
        source_path.mkdir(exist_ok=True)
        (source_path / "test_pkg-2.5.0-py3-none-any.whl").write_bytes(b"fake")

        mock_result = UpdateResult(total=1, updated=1, failed=0, failures=[])

        # Run synchronously so we can inspect the captured call
        api_with_python._run_with_lock = lambda fn: fn()  # type: ignore[assignment]

        with patch(
            "updater.gui.app.install_updates", return_value=mock_result
        ) as mock_install:
            with patch(
                "updater.gui.app.get_installed_versions_batch",
                return_value={"test-pkg": "1.0.0"},
            ):
                api_with_python.install_versioned_package("test-pkg", "2.5.0")

        mock_install.assert_called_once()
        call_kwargs = mock_install.call_args

        # Verify target_version was passed as "2.5.0"
        assert call_kwargs.kwargs.get("target_version") == "2.5.0" or (
            len(call_kwargs.args) >= 4 and call_kwargs.args[3] == "2.5.0"
        ), f"Expected target_version='2.5.0' in call, got: {call_kwargs}"

        # Verify the statuses list contains the correct package name
        statuses_arg = (
            call_kwargs.args[0]
            if call_kwargs.args
            else call_kwargs.kwargs.get("statuses")
        )
        assert statuses_arg is not None
        assert any(s.name == "test-pkg" for s in statuses_arg)
