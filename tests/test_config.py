from pathlib import Path

import pytest

from updater.config import (
    GuiConfig,
    LauncherConfig,
    UpdaterConfig,
    load_config,
)


def _write_toml(tmp_path: Path, content: str) -> Path:
    toml_file = tmp_path / "updater.toml"
    toml_file.write_text(content, encoding="utf-8")
    return toml_file


class TestLauncherConfigDefaults:
    def test_enabled_defaults_false(self) -> None:
        cfg = LauncherConfig()
        assert cfg.enabled is False

    def test_executable_defaults_empty(self) -> None:
        cfg = LauncherConfig()
        assert cfg.executable == ""

    def test_args_defaults_empty_list(self) -> None:
        cfg = LauncherConfig()
        assert cfg.args == []

    def test_mode_defaults_on_success(self) -> None:
        cfg = LauncherConfig()
        assert cfg.mode == "on_success"

    def test_auto_launch_defaults_false(self) -> None:
        cfg = LauncherConfig()
        assert cfg.auto_launch is False

    def test_auto_update_defaults_false(self) -> None:
        cfg = LauncherConfig()
        assert cfg.auto_update is False


class TestGuiConfigDefaults:
    def test_theme_defaults_blueprint(self) -> None:
        cfg = GuiConfig()
        assert cfg.theme == "blueprint"


class TestLoadConfig:
    def test_load_full_config(self, tmp_path: Path) -> None:
        toml_file = _write_toml(tmp_path, """
[updater]
source = 'C:\\packages'
packages = ["pkg-a", "pkg-b"]

[launcher]
enabled = true
executable = "start.py"
args = ["--port", "5000"]
mode = "on_complete"
auto_launch = true
auto_update = true

[gui]
theme = "dark"
""")
        cfg = load_config(toml_file)
        assert cfg.source == "C:\\packages"
        assert cfg.packages == ["pkg-a", "pkg-b"]
        assert cfg.launcher.enabled is True
        assert cfg.launcher.executable == "start.py"
        assert cfg.launcher.args == ["--port", "5000"]
        assert cfg.launcher.mode == "on_complete"
        assert cfg.launcher.auto_launch is True
        assert cfg.launcher.auto_update is True
        assert cfg.gui.theme == "dark"

    def test_load_updater_only(self, tmp_path: Path) -> None:
        toml_file = _write_toml(tmp_path, """
[updater]
source = 'C:\\packages'
packages = ["pkg-a"]
""")
        cfg = load_config(toml_file)
        assert cfg.source == "C:\\packages"
        assert cfg.launcher.enabled is False
        assert cfg.launcher.executable == ""
        assert cfg.gui.theme == "blueprint"

    def test_load_missing_file_returns_defaults(self) -> None:
        cfg = load_config(Path("nonexistent/updater.toml"))
        assert cfg.launcher.enabled is False
        assert cfg.gui.theme == "blueprint"
        assert len(cfg.packages) > 0  # builtin defaults

    def test_config_dir_property(self, tmp_path: Path) -> None:
        toml_file = _write_toml(tmp_path, "[updater]\n")
        cfg = load_config(toml_file)
        assert cfg.config_dir == tmp_path
