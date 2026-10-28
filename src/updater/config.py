"""
Typed configuration dataclasses and TOML loader for the Updater microservice.

Provides structured access to updater.toml sections:
  [updater]  -> UpdaterConfig.source / .packages
  [launcher] -> UpdaterConfig.launcher (LauncherConfig)
  [gui]      -> UpdaterConfig.gui (GuiConfig)
"""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# Fallbacks for updater.toml written by Windows editors: Notepad's "ANSI" on a
# zh-TW machine is cp950 (Big5), and "UTF-8" from some editors carries a BOM
# which tomllib rejects.  Order matters - UTF-8 first, then the locale default.
_ENCODING_FALLBACKS = ("cp950", "cp1252")
_BOM_ENCODINGS = (
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
    (b"\xef\xbb\xbf", "utf-8-sig"),
)

_BUILTIN_SOURCE = r"\\pnt52\研發本部_技術服務處\技術服務處\DS-TA\Test_Matrix\packages"

_BUILTIN_PACKAGES = [
    "test-matrix",
    "scope_driver",
    "source_driver",
    "load_driver",
    "meter_driver",
    "daq_driver",
    "chamber_driver",
    "gpio_driver",
    "i2c_driver",
    "dc_power_supply_driver",
    "multi_driver",
    "subdevice",
    "usb_hid",
    "acbel_r90000",
    "am_shared",
    "am_report_generator",
    "visa_bundle",
]

CONFIG_FILENAME = "updater.toml"


@dataclass
class LauncherConfig:
    """Configuration for the post-update launcher feature."""

    enabled: bool = False
    executable: str = ""
    args: list[str] = field(default_factory=list)
    mode: str = "on_success"
    auto_launch: bool = False
    auto_update: bool = False
    auto_launch_enable: bool = False
    auto_update_enable: bool = False


@dataclass
class GuiConfig:
    """Configuration for the GUI appearance."""

    theme: str = "blueprint"


@dataclass
class UpdaterConfig:
    """Root configuration loaded from updater.toml."""

    source: str = _BUILTIN_SOURCE
    packages: list[str] = field(default_factory=lambda: list(_BUILTIN_PACKAGES))
    venv_names: list[str] = field(default_factory=lambda: ["venv", ".venv"])
    launcher: LauncherConfig = field(default_factory=LauncherConfig)
    gui: GuiConfig = field(default_factory=GuiConfig)
    config_dir: Path = field(default_factory=lambda: Path("."))
    # Non-empty when updater.toml could not be decoded/parsed; the updater then
    # runs on built-in defaults instead of dying (a GUI exe has no console).
    parse_error: str = ""
    encoding: str = ""


def read_toml_text(toml_path: Path) -> tuple[str, str]:
    """
    Decode updater.toml to text, returning (text, encoding_used).

    Handles BOM-prefixed UTF-8/UTF-16/UTF-32 and the zh-TW ANSI (cp950/Big5)
    files Notepad produces.  Raises ValueError when nothing decodes.
    """
    raw = toml_path.read_bytes()
    for bom, encoding in _BOM_ENCODINGS:
        if raw.startswith(bom):
            # Strip the BOM bytes: utf-16/utf-32 codecs would otherwise keep
            # U+FEFF as the first character, which tomllib rejects.
            return raw[len(bom):].decode(encoding), encoding
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    for encoding in _ENCODING_FALLBACKS:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise ValueError(
        f"updater.toml 編碼不支援（已試 UTF-8/BOM/{'/'.join(_ENCODING_FALLBACKS)}）"
    )


def load_config(toml_path: Path) -> UpdaterConfig:
    """
    Load UpdaterConfig from a TOML file.

    A malformed or undecodable file does not abort the run: it is reported
    (stderr + UpdaterConfig.parse_error) and built-in defaults are used.
    """
    if not toml_path.exists():
        print(f"[DEBUG] Config not found at: {toml_path}, using defaults")
        return UpdaterConfig(config_dir=toml_path.parent.resolve())

    print(f"[DEBUG] Loading config from: {toml_path.resolve()}")
    parse_error = ""
    encoding = ""
    try:
        text, encoding = read_toml_text(toml_path)
        if encoding != "utf-8":
            print(f"[DEBUG] updater.toml decoded as {encoding}")
        raw = tomllib.loads(text)
    except (ValueError, tomllib.TOMLDecodeError, OSError) as exc:
        parse_error = (
            f"updater.toml 無法解析，已改用內建預設值：{exc}（檔案：{toml_path}）"
        )
        print(f"[ERROR] {parse_error}", file=sys.stderr)
        raw = {}

    updater_raw = raw.get("updater", {})
    launcher_raw = raw.get("launcher", {})
    gui_raw = raw.get("gui", {})

    # Handle venv_names: can be a string or a list in TOML
    raw_venv_names = updater_raw.get("venv_name") or updater_raw.get("venv_names")
    if isinstance(raw_venv_names, str):
        venv_names = [raw_venv_names]
    elif isinstance(raw_venv_names, list):
        venv_names = raw_venv_names
    else:
        venv_names = ["venv", ".venv"]

    # Ensure defaults are included if not present
    for default in ["venv", ".venv"]:
        if default not in venv_names:
            venv_names.append(default)

    launcher = LauncherConfig(
        enabled=launcher_raw.get("enabled", False),
        executable=launcher_raw.get("executable", ""),
        args=launcher_raw.get("args", []),
        mode=launcher_raw.get("mode", "on_success"),
        auto_launch=launcher_raw.get("auto_launch", False),
        auto_update=launcher_raw.get("auto_update", False),
        auto_launch_enable=launcher_raw.get("auto_launch_enable", False),
        auto_update_enable=launcher_raw.get("auto_update_enable", False),
    )

    gui = GuiConfig(
        theme=gui_raw.get("theme", "blueprint"),
    )

    return UpdaterConfig(
        source=updater_raw.get("source", _BUILTIN_SOURCE),
        packages=updater_raw.get("packages", list(_BUILTIN_PACKAGES)),
        venv_names=venv_names,
        launcher=launcher,
        gui=gui,
        config_dir=toml_path.parent.resolve(),
        parse_error=parse_error,
        encoding=encoding,
    )


def find_config() -> Path:
    """
    Locate updater.toml beside the running executable or in parent directories.
    
    Searches in:
    1. The directory of the script/executable.
    2. One level up (e.g., if running from a sub-package).
    3. Two levels up (e.g., if running from src/updater/gui).
    """
    start_dir = Path(sys.argv[0]).resolve().parent
    
    # Check current, parent, and grandparent directories
    for dir_path in [start_dir, start_dir.parent, start_dir.parent.parent]:
        candidate = dir_path / CONFIG_FILENAME
        if candidate.exists():
            return candidate
            
    # Fallback to the original behavior (beside executable) if not found
    return start_dir / CONFIG_FILENAME
