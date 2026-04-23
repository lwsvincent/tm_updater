"""Happy path tests for config module - end-to-end config loading scenarios."""
from pathlib import Path

from updater.config import (
    GuiConfig,
    LauncherConfig,
    UpdaterConfig,
    find_config,
    load_config,
)


def _write_toml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "updater.toml"
    p.write_text(content, encoding="utf-8")
    return p


class TestConfigHappyPath:
    def test_full_production_config(self, tmp_path: Path) -> None:
        """Load a config that mirrors the real updater.toml structure."""
        toml_path = _write_toml(
            tmp_path,
            """\
[updater]
source = '\\\\server\\share\\packages'
packages = ["test-matrix", "scope_driver", "am_shared"]

[launcher]
enabled = true
executable = "start_app.py"
args = ["--port", "8080"]
mode = "on_success"
auto_launch = true
auto_update = false

[gui]
theme = "blueprint"
""",
        )
        cfg = load_config(toml_path)

        assert cfg.source == "\\\\server\\share\\packages"
        assert cfg.packages == ["test-matrix", "scope_driver", "am_shared"]
        assert cfg.launcher.enabled is True
        assert cfg.launcher.executable == "start_app.py"
        assert cfg.launcher.args == ["--port", "8080"]
        assert cfg.launcher.mode == "on_success"
        assert cfg.launcher.auto_launch is True
        assert cfg.launcher.auto_update is False
        assert cfg.gui.theme == "blueprint"
        assert cfg.config_dir == tmp_path.resolve()

    def test_minimal_config_uses_defaults(self, tmp_path: Path) -> None:
        """A config with only [updater] still provides usable launcher/gui defaults."""
        toml_path = _write_toml(
            tmp_path,
            """\
[updater]
source = 'C:\\packages'
packages = ["pkg-a"]
""",
        )
        cfg = load_config(toml_path)

        assert cfg.source == "C:\\packages"
        assert cfg.packages == ["pkg-a"]
        assert cfg.launcher == LauncherConfig()
        assert cfg.gui == GuiConfig()

    def test_missing_config_still_returns_usable_object(self, tmp_path: Path) -> None:
        """Application boots even without a config file."""
        cfg = load_config(tmp_path / "nonexistent.toml")

        assert isinstance(cfg, UpdaterConfig)
        assert isinstance(cfg.launcher, LauncherConfig)
        assert isinstance(cfg.gui, GuiConfig)
        assert cfg.launcher.enabled is False
        assert cfg.gui.theme == "blueprint"

    def test_on_complete_launcher_mode(self, tmp_path: Path) -> None:
        """Launcher with on_complete mode - launches even if updates fail."""
        toml_path = _write_toml(
            tmp_path,
            """\
[updater]
source = '.'
packages = []

[launcher]
enabled = true
executable = "app.exe"
mode = "on_complete"
""",
        )
        cfg = load_config(toml_path)

        assert cfg.launcher.mode == "on_complete"
        assert cfg.launcher.enabled is True

    def test_find_config_returns_path(self) -> None:
        """find_config() returns a Path regardless of whether file exists."""
        result = find_config()
        assert isinstance(result, Path)
        assert result.name == "updater.toml"
