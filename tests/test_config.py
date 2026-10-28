from pathlib import Path

import pytest

from updater.config import (
    read_toml_text,
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


class TestTomlEncoding:
    """updater.toml is edited by hand on zh-TW Windows; encoding must not break it."""

    CONTENT_TPL = "[updater]\nsource = '{path}'\npackages = [\"test-matrix\"]\n"

    def _write_bytes(self, tmp_path: Path, payload: bytes) -> Path:
        toml_file = tmp_path / "updater.toml"
        toml_file.write_bytes(payload)
        return toml_file

    def test_plain_utf8_is_fine(self, tmp_path: Path) -> None:
        toml_file = _write_toml(
            tmp_path, self.CONTENT_TPL.format(path=r"\\pnt52\packages")
        )
        cfg = load_config(toml_file)
        assert cfg.encoding == "utf-8"
        assert cfg.parse_error == ""

    def test_utf8_bom_is_accepted(self, tmp_path: Path) -> None:
        payload = "﻿" + self.CONTENT_TPL.format(path=r"\\pnt52\packages")
        toml_file = self._write_bytes(tmp_path, payload.encode("utf-8"))
        cfg = load_config(toml_file)
        assert cfg.parse_error == ""
        assert cfg.source == r"\\pnt52\packages"
        assert cfg.encoding == "utf-8-sig"

    def test_big5_ansi_with_chinese_path_is_accepted(self, tmp_path: Path) -> None:
        zh_path = r"\\pnt52\研發本部_技術服務處\packages"
        payload = self.CONTENT_TPL.format(path=zh_path).encode("cp950")
        toml_file = self._write_bytes(tmp_path, payload)
        cfg = load_config(toml_file)
        assert cfg.parse_error == ""
        assert cfg.source == zh_path
        assert cfg.encoding == "cp950"

    def test_utf16_file_is_accepted(self, tmp_path: Path) -> None:
        payload = self.CONTENT_TPL.format(path=r"\\pnt52\packages").encode("utf-16")
        toml_file = self._write_bytes(tmp_path, payload)
        cfg = load_config(toml_file)
        assert cfg.parse_error == ""
        assert cfg.source == r"\\pnt52\packages"

    def test_syntax_error_keeps_defaults_and_reports(self, tmp_path: Path) -> None:
        toml_file = self._write_bytes(tmp_path, b"[updater\nsource = broken")
        cfg = load_config(toml_file)
        assert cfg.parse_error != ""
        assert cfg.source.startswith(r"\\pnt52")  # built-in default survived

    def test_undecodable_bytes_report_error_not_crash(self, tmp_path: Path) -> None:
        toml_file = self._write_bytes(tmp_path, b"[updater]\nsource = '\x81\x81'\n")
        cfg = load_config(toml_file)
        assert "編碼不支援" in cfg.parse_error
        assert cfg.packages  # defaults still applied

    def test_read_toml_text_returns_encoding_used(self, tmp_path: Path) -> None:
        zh = "研發本部_技術服務處"
        toml_file = self._write_bytes(
            tmp_path, self.CONTENT_TPL.format(path=zh).encode("cp950")
        )
        text, encoding = read_toml_text(toml_file)
        assert encoding == "cp950"
        assert zh in text
