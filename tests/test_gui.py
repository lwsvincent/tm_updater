from pathlib import Path

import pytest

from updater.config import UpdaterConfig, LauncherConfig, GuiConfig
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
        (source_path / "test_pkg-1.0.0-py3-none-any.whl").write_bytes(b"fake")

        # Call the API
        result = api.get_versions("test-pkg")

        # Assert
        assert result == ["3.0.0", "2.5.0", "1.0.0"]  # newest first
        assert isinstance(result, list)
