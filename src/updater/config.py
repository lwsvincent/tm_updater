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


@dataclass
class GuiConfig:
    """Configuration for the GUI appearance."""

    theme: str = "blueprint"


@dataclass
class UpdaterConfig:
    """Root configuration loaded from updater.toml."""

    source: str = _BUILTIN_SOURCE
    packages: list[str] = field(default_factory=lambda: list(_BUILTIN_PACKAGES))
    launcher: LauncherConfig = field(default_factory=LauncherConfig)
    gui: GuiConfig = field(default_factory=GuiConfig)
    config_dir: Path = field(default_factory=lambda: Path("."))


def load_config(toml_path: Path) -> UpdaterConfig:
    """
    Load UpdaterConfig from a TOML file.

    If the file does not exist, returns an UpdaterConfig with all built-in defaults.
    Sections omitted from the TOML file fall back to their dataclass defaults.

    Args:
        toml_path: Absolute or relative path to updater.toml.

    Returns:
        Populated UpdaterConfig instance.
    """
    if not toml_path.exists():
        return UpdaterConfig(config_dir=toml_path.parent)

    with open(toml_path, "rb") as f:
        raw = tomllib.load(f)

    updater_raw = raw.get("updater", {})
    launcher_raw = raw.get("launcher", {})
    gui_raw = raw.get("gui", {})

    launcher = LauncherConfig(
        enabled=launcher_raw.get("enabled", False),
        executable=launcher_raw.get("executable", ""),
        args=launcher_raw.get("args", []),
        mode=launcher_raw.get("mode", "on_success"),
        auto_launch=launcher_raw.get("auto_launch", False),
        auto_update=launcher_raw.get("auto_update", False),
    )

    gui = GuiConfig(
        theme=gui_raw.get("theme", "blueprint"),
    )

    return UpdaterConfig(
        source=updater_raw.get("source", _BUILTIN_SOURCE),
        packages=updater_raw.get("packages", list(_BUILTIN_PACKAGES)),
        launcher=launcher,
        gui=gui,
        config_dir=toml_path.parent.resolve(),
    )


def find_config() -> Path:
    """
    Locate updater.toml beside the running executable.

    Returns the expected path whether or not it exists.
    """
    exe_dir = Path(sys.argv[0]).resolve().parent
    return exe_dir / CONFIG_FILENAME
