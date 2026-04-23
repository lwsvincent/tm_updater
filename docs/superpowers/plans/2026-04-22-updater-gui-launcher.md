# Updater GUI & Post-Update Launcher Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a post-update launcher and an industrial-style GUI (PyWebView + Vue) to the Updater microservice, while refactoring the existing CLI into a shared core library.

**Architecture:** Extract scan/compare/install logic from `main.py` into `core.py`, add a typed `config.py` for toml loading, and a `launcher.py` for post-update execution. The GUI lives in `gui/app.py` (PyWebView bridge) backed by a Vite+Vue frontend. Two Nuitka builds: `updater.exe` (CLI) and `updater_gui.exe` (GUI).

**Tech Stack:** Python 3.11, PyWebView (WebView2), Vue 3, Vite, Nuitka, TOML config

**Spec:** `docs/superpowers/specs/2026-04-22-updater-gui-launcher-design.md`

---

## File Structure

### New files

| File | Responsibility |
|------|---------------|
| `src/updater/config.py` | Typed dataclasses + toml loading for all config sections |
| `src/updater/core.py` | Extracted scan, compare, install logic with callback-based progress |
| `src/updater/launcher.py` | Post-update executable launcher (py/exe dispatch) |
| `src/updater/gui/__init__.py` | GUI package marker |
| `src/updater/gui/app.py` | PyWebView window creation + Python-JS bridge API |
| `src/updater/gui/frontend/package.json` | Vue+Vite project config |
| `src/updater/gui/frontend/vite.config.js` | Vite config (port 15173) |
| `src/updater/gui/frontend/index.html` | HTML entry point |
| `src/updater/gui/frontend/src/main.js` | Vue mount + global bridge functions |
| `src/updater/gui/frontend/src/App.vue` | Root component (side panel layout) |
| `src/updater/gui/frontend/src/components/PackageTable.vue` | Package list table |
| `src/updater/gui/frontend/src/components/ActionPanel.vue` | Update/Launch buttons |
| `src/updater/gui/frontend/src/components/LogConsole.vue` | Real-time log display |
| `src/updater/gui/frontend/src/themes/blueprint.css` | Light Industrial / Blueprint theme |
| `scripts/build_gui.bat` | Nuitka build script for GUI exe |
| `tests/mock_app.py` | Test startup file for launcher validation |
| `tests/test_config.py` | Config module unit tests |
| `tests/test_core.py` | Core module unit tests |
| `tests/test_launcher.py` | Launcher module unit tests |

### Modified files

| File | Changes |
|------|---------|
| `src/updater/main.py` | Slim down to thin CLI wrapper calling `core` + `config` + `launcher` |
| `src/updater/__init__.py` | No change (keeps `__version__`) |
| `pyproject.toml` | Add `gui` optional dep, add `updater-gui` entry point |
| `updater.toml` | Add `[launcher]` and `[gui]` sections |
| `.gitignore` | Add `node_modules/`, `src/updater/gui/frontend/dist/` |

---

## Chunk 1: Config Module

### Task 1: Create config dataclasses and toml loader

**Files:**
- Create: `src/updater/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for config loading**

Create `tests/test_config.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'updater.config'`

- [ ] **Step 3: Implement config.py**

Create `src/updater/config.py`:

```python
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
    enabled: bool = False
    executable: str = ""
    args: list[str] = field(default_factory=list)
    mode: str = "on_success"
    auto_launch: bool = False
    auto_update: bool = False


@dataclass
class GuiConfig:
    theme: str = "blueprint"


@dataclass
class UpdaterConfig:
    source: str = _BUILTIN_SOURCE
    packages: list[str] = field(default_factory=lambda: list(_BUILTIN_PACKAGES))
    launcher: LauncherConfig = field(default_factory=LauncherConfig)
    gui: GuiConfig = field(default_factory=GuiConfig)
    config_dir: Path = field(default_factory=lambda: Path("."))


def load_config(toml_path: Path) -> UpdaterConfig:
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
    return Path(sys.argv[0]).resolve().parent / CONFIG_FILENAME
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_config.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/updater/config.py tests/test_config.py
git commit -m "feat(config): add typed config dataclasses and toml loader"
```

---

## Chunk 2: Core Extraction

### Task 2: Extract core logic from main.py into core.py

**Files:**
- Create: `src/updater/core.py`
- Test: `tests/test_core.py`

- [ ] **Step 1: Write failing tests for core functions**

Create `tests/test_core.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from updater.core import (
    PackageStatus,
    UpdateResult,
    normalize_name,
    scan_packages,
    check_updates,
)


class TestNormalizeName:
    def test_hyphen(self) -> None:
        assert normalize_name("my-package") == "my-package"

    def test_underscore(self) -> None:
        assert normalize_name("my_package") == "my-package"

    def test_dot(self) -> None:
        assert normalize_name("my.package") == "my-package"

    def test_mixed(self) -> None:
        assert normalize_name("My_Package.Name") == "my-package-name"

    def test_uppercase(self) -> None:
        assert normalize_name("MyPackage") == "mypackage"


class TestPackageStatus:
    def test_up_to_date(self) -> None:
        ps = PackageStatus(
            name="pkg", installed="1.0.0", available="1.0.0", status="up_to_date"
        )
        assert ps.status == "up_to_date"

    def test_update_available(self) -> None:
        ps = PackageStatus(
            name="pkg", installed="1.0.0", available="2.0.0", status="update_available"
        )
        assert ps.status == "update_available"

    def test_not_installed(self) -> None:
        ps = PackageStatus(
            name="pkg", installed=None, available="1.0.0", status="not_installed"
        )
        assert ps.installed is None


class TestScanPackages:
    def test_scan_empty_dir(self, tmp_path: Path) -> None:
        result = scan_packages(tmp_path)
        assert result == {}

    def test_scan_nonexistent_dir(self) -> None:
        result = scan_packages(Path("/nonexistent"))
        assert result == {}

    def test_scan_finds_whl(self, tmp_path: Path) -> None:
        whl = tmp_path / "my_package-1.2.3-py3-none-any.whl"
        whl.write_bytes(b"fake")
        result = scan_packages(tmp_path)
        assert "my-package" in result
        assert result["my-package"][0] == "1.2.3"

    def test_scan_keeps_latest_version(self, tmp_path: Path) -> None:
        (tmp_path / "pkg-1.0.0-py3-none-any.whl").write_bytes(b"old")
        (tmp_path / "pkg-2.0.0-py3-none-any.whl").write_bytes(b"new")
        result = scan_packages(tmp_path)
        assert result["pkg"][0] == "2.0.0"


class TestCheckUpdates:
    def test_up_to_date(self) -> None:
        available = {"pkg-a": ("1.0.0", Path("pkg_a-1.0.0.whl"))}
        installed = {"pkg-a": "1.0.0"}
        statuses = check_updates(["pkg-a"], installed, available)
        assert statuses[0].status == "up_to_date"

    def test_update_available(self) -> None:
        available = {"pkg-a": ("2.0.0", Path("pkg_a-2.0.0.whl"))}
        installed = {"pkg-a": "1.0.0"}
        statuses = check_updates(["pkg-a"], installed, available)
        assert statuses[0].status == "update_available"

    def test_not_in_source(self) -> None:
        available: dict[str, tuple[str, Path]] = {}
        installed = {"pkg-a": "1.0.0"}
        statuses = check_updates(["pkg-a"], installed, available)
        assert statuses[0].status == "not_in_source"

    def test_not_installed(self) -> None:
        available = {"pkg-a": ("1.0.0", Path("pkg_a-1.0.0.whl"))}
        installed: dict[str, str | None] = {"pkg-a": None}
        statuses = check_updates(["pkg-a"], installed, available)
        assert statuses[0].status == "not_installed"


class TestUpdateResult:
    def test_all_success(self) -> None:
        r = UpdateResult(total=3, updated=3, failed=0, failures=[])
        assert r.all_success is True

    def test_has_failures(self) -> None:
        r = UpdateResult(total=3, updated=2, failed=1, failures=["pkg-x"])
        assert r.all_success is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_core.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'updater.core'`

- [ ] **Step 3: Implement core.py**

Create `src/updater/core.py`. Extract and refactor from `main.py`:

```python
from __future__ import annotations

import importlib.metadata
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from packaging.version import InvalidVersion, Version


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


@dataclass
class PackageStatus:
    name: str
    installed: str | None
    available: str | None
    status: str  # "up_to_date" | "update_available" | "not_in_source" | "not_installed"
    whl_path: Path | None = None


@dataclass
class UpdateResult:
    total: int
    updated: int
    failed: int
    failures: list[str] = field(default_factory=list)

    @property
    def all_success(self) -> bool:
        return self.failed == 0


ProgressCallback = Callable[[str, str], None]  # (level, message)


_pip_cache: dict[str, dict[str, str]] = {}


def get_installed_versions_batch(
    python_exe: Path, package_names: list[str]
) -> dict[str, str | None]:
    exe_key = str(python_exe)
    if exe_key not in _pip_cache:
        try:
            result = subprocess.run(
                [str(python_exe), "-m", "pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                packages = json.loads(result.stdout)
                _pip_cache[exe_key] = {
                    normalize_name(p["name"]): p["version"] for p in packages
                }
            else:
                _pip_cache[exe_key] = {}
        except (subprocess.TimeoutExpired, Exception):
            _pip_cache[exe_key] = {}

    cached = _pip_cache[exe_key]
    return {pkg: cached.get(normalize_name(pkg)) for pkg in package_names}


def clear_pip_cache() -> None:
    _pip_cache.clear()


def _parse_whl_file(whl: Path) -> tuple[str, str, Path] | None:
    parts = whl.stem.split("-")
    if len(parts) < 2:
        return None
    dist_name = normalize_name(parts[0])
    ver_str = parts[1]
    try:
        Version(ver_str)
        return (dist_name, ver_str, whl)
    except InvalidVersion:
        return None


def scan_packages(source_path: Path) -> dict[str, tuple[str, Path]]:
    available: dict[str, tuple[str, Path]] = {}
    if not source_path.exists():
        return available

    whl_files = list(source_path.glob("*.whl"))
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = executor.map(_parse_whl_file, whl_files)

    for result in results:
        if result is None:
            continue
        dist_name, ver_str, whl = result
        if dist_name not in available or Version(ver_str) > Version(
            available[dist_name][0]
        ):
            available[dist_name] = (ver_str, whl)

    return available


def check_updates(
    target_packages: list[str],
    installed_versions: dict[str, str | None],
    available: dict[str, tuple[str, Path]],
) -> list[PackageStatus]:
    statuses: list[PackageStatus] = []
    for pkg in target_packages:
        norm = normalize_name(pkg)
        installed = installed_versions.get(pkg)

        if norm not in available:
            statuses.append(
                PackageStatus(
                    name=pkg,
                    installed=installed,
                    available=None,
                    status="not_in_source",
                )
            )
            continue

        avail_ver, whl_path = available[norm]

        if installed is None:
            statuses.append(
                PackageStatus(
                    name=pkg,
                    installed=None,
                    available=avail_ver,
                    status="not_installed",
                    whl_path=whl_path,
                )
            )
            continue

        try:
            if Version(installed) >= Version(avail_ver):
                statuses.append(
                    PackageStatus(
                        name=pkg,
                        installed=installed,
                        available=avail_ver,
                        status="up_to_date",
                    )
                )
                continue
        except InvalidVersion:
            pass

        statuses.append(
            PackageStatus(
                name=pkg,
                installed=installed,
                available=avail_ver,
                status="update_available",
                whl_path=whl_path,
            )
        )

    return statuses


def install_whl(whl_path: Path, python_exe: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [
                str(python_exe),
                "-m",
                "pip",
                "install",
                str(whl_path),
                "--no-deps",
                "--no-input",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return True, ""
        return False, (result.stderr or result.stdout).strip()
    except subprocess.TimeoutExpired:
        return False, "Timed out after 120s"
    except Exception as exc:
        return False, str(exc)


def install_updates(
    statuses: list[PackageStatus],
    python_exe: Path,
    on_progress: ProgressCallback | None = None,
) -> UpdateResult:
    to_update = [s for s in statuses if s.status in ("update_available", "not_installed")]
    updated = 0
    failed = 0
    failures: list[str] = []

    for ps in to_update:
        assert ps.whl_path is not None
        if on_progress:
            arrow = f"{ps.installed or 'not installed'} -> {ps.available}"
            on_progress("info", f"{ps.name}: {arrow} installing...")

        ok, err = install_whl(ps.whl_path, python_exe)
        if ok:
            updated += 1
            if on_progress:
                on_progress("success", f"{ps.name}: updated to {ps.available}")
        else:
            failed += 1
            failures.append(ps.name)
            if on_progress:
                on_progress("error", f"{ps.name}: FAILED - {err}")

    return UpdateResult(total=len(to_update), updated=updated, failed=failed, failures=failures)


def find_venv_python(venv_arg: str | None, exe_dir: Path) -> Path | None:
    candidates: list[Path] = []
    if venv_arg:
        candidates.append(Path(venv_arg) / "Scripts" / "python.exe")

    cwd = Path.cwd()
    candidates += [
        exe_dir / "venv" / "Scripts" / "python.exe",
        exe_dir / ".venv" / "Scripts" / "python.exe",
        exe_dir.parent / "venv" / "Scripts" / "python.exe",
        exe_dir.parent / ".venv" / "Scripts" / "python.exe",
        cwd / "venv" / "Scripts" / "python.exe",
        cwd / ".venv" / "Scripts" / "python.exe",
        cwd.parent / "venv" / "Scripts" / "python.exe",
        cwd.parent / ".venv" / "Scripts" / "python.exe",
    ]

    for p in candidates:
        if p.exists():
            return p
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_core.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/updater/core.py tests/test_core.py
git commit -m "feat(core): extract scan, compare, install logic from main.py"
```

---

### Task 3: Refactor main.py to use core + config

**Files:**
- Modify: `src/updater/main.py`

- [ ] **Step 1: Rewrite main.py as thin CLI wrapper**

Replace `src/updater/main.py` with:

```python
"""
Test Matrix Package Updater

Standalone updater compiled with Nuitka to updater.exe.
Scans a whl source directory (default: PNT52 network share),
compares against installed versions, and installs newer packages
into the local venv.

Usage:
  updater.exe [--source <path>] [--venv <path>] [--packages pkg1 pkg2 ...]
              [--dry-run]
"""

import argparse
import sys
from pathlib import Path

from updater.config import find_config, load_config
from updater.core import (
    check_updates,
    find_venv_python,
    get_installed_versions_batch,
    install_updates,
    scan_packages,
)
from updater.launcher import launch_executable, should_launch, LauncherError


def _cli_progress(level: str, message: str) -> None:
    prefix = {"info": "  ", "success": "  ", "error": "  [ERROR] "}
    print(f"{prefix.get(level, '  ')}{message}")


def main() -> None:
    config = load_config(find_config())

    parser = argparse.ArgumentParser(
        description="Test Matrix Package Updater - installs .whl packages from a network share"
    )
    parser.add_argument(
        "--source", default=config.source, help="Path to whl source directory"
    )
    parser.add_argument("--venv", default=None, help="Path to Python venv directory")
    parser.add_argument(
        "--packages",
        nargs="*",
        help="Packages to update (default: all managed packages)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check for updates without installing",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug output"
    )
    args = parser.parse_args()

    source_path = Path(args.source)
    exe_dir = Path(__file__).parent

    print("Test Matrix Updater")
    print(f"Source : {source_path}")
    if args.dry_run:
        print("Mode   : dry-run (no changes will be made)")
    print("-" * 55)

    python_exe = find_venv_python(args.venv, exe_dir)
    if python_exe is None:
        print(
            "[ERROR] Cannot find venv Python. Use --venv <path> to specify the venv directory."
        )
        sys.exit(1)
    print(f"Venv   : {python_exe.parent.parent}")
    print("-" * 55)

    print("Scanning source for available packages...")
    available = scan_packages(source_path)

    if not available:
        print("[WARNING] No .whl files found in source path. Nothing to do.")
        sys.exit(0)

    print(f"Found {len(available)} package(s) in source.\n")

    target_packages: list[str] = args.packages if args.packages else config.packages
    installed_versions = get_installed_versions_batch(python_exe, target_packages)
    statuses = check_updates(target_packages, installed_versions, available)

    if args.dry_run:
        for ps in statuses:
            installed_str = ps.installed or "not installed"
            if ps.status == "update_available":
                print(
                    f"  {ps.name:<35} {installed_str} -> {ps.available}  [update available]"
                )
            elif ps.status == "not_installed":
                print(
                    f"  {ps.name:<35} {installed_str} -> {ps.available}  [new install]"
                )
            elif ps.status == "up_to_date":
                print(f"  {ps.name:<35} {installed_str:<15}  up to date")
            else:
                print(
                    f"  {ps.name:<35} {installed_str:<15}  (not in source, skipped)"
                )
        updates = [s for s in statuses if s.status in ("update_available", "not_installed")]
        print("-" * 55)
        print(f"Updates available: {len(updates)}")
        return

    result = install_updates(statuses, python_exe, on_progress=_cli_progress)

    print("-" * 55)
    print(f"Updated : {result.updated}/{result.total}")
    if result.failed:
        print(f"Failures: {result.failed}")

    # Launcher
    if config.launcher.enabled and config.launcher.executable:
        if should_launch(config.launcher.mode, result):
            print(f"\nLaunching: {config.launcher.executable}")
            try:
                proc = launch_executable(config, python_exe)
                print(f"Launched (PID: {proc.pid})")
            except LauncherError as exc:
                print(f"[ERROR] Launch failed: {exc}", file=sys.stderr)
                sys.exit(2)
        else:
            print("\nLaunch skipped (conditions not met).")

    if result.failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run existing tests (if any) plus quick manual check**

Run: `.venv/Scripts/python.exe -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add src/updater/main.py
git commit -m "refactor(main): rewrite as thin CLI wrapper using core + config"
```

---

## Chunk 3: Launcher Module

### Task 4: Create launcher module with tests

**Files:**
- Create: `src/updater/launcher.py`
- Create: `tests/mock_app.py`
- Test: `tests/test_launcher.py`

- [ ] **Step 1: Create mock startup file for testing**

Create `tests/mock_app.py`:

```python
"""Mock application for testing the launcher module."""
import sys
import time


def main() -> None:
    print(f"App launched with args: {sys.argv[1:]}")
    time.sleep(3)
    print("App exiting.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write failing tests for launcher**

Create `tests/test_launcher.py`:

```python
import sys
from pathlib import Path
from unittest.mock import MagicMock

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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_launcher.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'updater.launcher'`

- [ ] **Step 4: Implement launcher.py**

Create `src/updater/launcher.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path

from updater.config import UpdaterConfig
from updater.core import UpdateResult


class LauncherError(Exception):
    pass


def should_launch(mode: str, result: UpdateResult) -> bool:
    if mode == "on_complete":
        return True
    # on_success: zero failures
    return result.all_success


def resolve_executable_path(executable: str, config_dir: Path) -> Path:
    path = Path(executable)
    if not path.is_absolute():
        path = config_dir / path
    path = path.resolve()
    if not path.exists():
        raise LauncherError(f"Executable not found: {path}")
    return path


def launch_executable(
    config: UpdaterConfig, python_exe: Path
) -> subprocess.Popen[str]:
    exe_path = resolve_executable_path(
        config.launcher.executable, config.config_dir
    )
    suffix = exe_path.suffix.lower()

    if suffix == ".py":
        cmd = [str(python_exe), str(exe_path)] + config.launcher.args
    elif suffix == ".exe":
        cmd = [str(exe_path)] + config.launcher.args
    else:
        raise LauncherError(f"Unsupported executable type: {suffix}")

    try:
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except PermissionError as exc:
        raise LauncherError(f"Permission denied: {exe_path} - {exc}") from exc
    except FileNotFoundError as exc:
        raise LauncherError(f"File not found: {exe_path} - {exc}") from exc
    except OSError as exc:
        raise LauncherError(f"OS error launching {exe_path}: {exc}") from exc
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_launcher.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/updater/launcher.py tests/test_launcher.py tests/mock_app.py
git commit -m "feat(launcher): add post-update executable launcher with mode evaluation"
```

---

## Chunk 4: Project Config Updates & CLI Integration

### Task 5: Update pyproject.toml and updater.toml

**Files:**
- Modify: `pyproject.toml`
- Modify: `updater.toml`
- Modify: `.gitignore`

- [ ] **Step 1: Update pyproject.toml**

Add GUI optional dependency and entry point:

In `pyproject.toml`, replace the existing `[project.optional-dependencies]` section with:
```toml
[project.optional-dependencies]
gui = [
    "pywebview>=5.0",
]
dev = [
    "nuitka>=1.0.0",
    "pywebview>=5.0",
    "pytest>=7.0.0",
    "black>=22.0.0",
    "isort>=5.10.0",
    "flake8>=5.0.0",
    "mypy>=1.0.0",
]
```

In `[project.scripts]`, add:
```toml
[project.scripts]
updater = "updater.main:main"
updater-gui = "updater.gui.app:main"
```

- [ ] **Step 2: Update updater.toml with new sections**

Append to `updater.toml`:
```toml

[launcher]
enabled = false
executable = ""
args = []
mode = "on_success"
auto_launch = false
auto_update = false

[gui]
theme = "blueprint"
```

- [ ] **Step 3: Update .gitignore**

Append to `.gitignore`:
```
node_modules/
src/updater/gui/frontend/dist/
```

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml updater.toml .gitignore
git commit -m "chore: update project config with launcher, gui sections, and new deps"
```

---

## Chunk 5: Vue Frontend

### Task 6: Scaffold Vite + Vue project

**Files:**
- Create: `src/updater/gui/__init__.py`
- Create: `src/updater/gui/frontend/package.json`
- Create: `src/updater/gui/frontend/vite.config.js`
- Create: `src/updater/gui/frontend/index.html`
- Create: `src/updater/gui/frontend/src/main.js`

- [ ] **Step 1: Create GUI package init**

Create `src/updater/gui/__init__.py`:

```python
"""Updater GUI - PyWebView + Vue frontend."""
```

- [ ] **Step 2: Create package.json**

Create `src/updater/gui/frontend/package.json`:

```json
{
  "name": "updater-gui",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.5.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^6.0.0"
  }
}
```

- [ ] **Step 3: Create vite.config.js**

Create `src/updater/gui/frontend/vite.config.js`:

```js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 15173,
    strictPort: true,
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
```

- [ ] **Step 4: Create index.html**

Create `src/updater/gui/frontend/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Test Matrix Updater</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 5: Create main.js with bridge globals**

Create `src/updater/gui/frontend/src/main.js`:

```js
import { createApp, reactive } from 'vue'
import App from './App.vue'

const store = reactive({
  packages: [],
  logs: [],
  config: {},
  updateComplete: false,
  updateResult: null,
  isUpdating: false,
  isLaunching: false,
})

window.addLogLine = (entry) => {
  store.logs.push(entry)
}

window.onUpdateComplete = (result) => {
  store.updateComplete = true
  store.updateResult = result
  store.isUpdating = false
}

window.updatePackages = (packages) => {
  store.packages = packages
}

window.addEventListener('pywebviewready', async () => {
  store.config = await window.pywebview.api.get_config()
  const packages = await window.pywebview.api.get_packages()
  if (packages && packages.length) {
    store.packages = packages
  }
})

const app = createApp(App)
app.provide('store', store)
app.mount('#app')
```

- [ ] **Step 6: Install npm dependencies**

Run: `cd src/updater/gui/frontend && npm install`

- [ ] **Step 7: Commit**

```bash
git add src/updater/gui/__init__.py src/updater/gui/frontend/package.json src/updater/gui/frontend/vite.config.js src/updater/gui/frontend/index.html src/updater/gui/frontend/src/main.js src/updater/gui/frontend/package-lock.json
git commit -m "feat(gui): scaffold Vite + Vue project with PyWebView bridge globals"
```

---

### Task 7: Build Vue components and theme

**Files:**
- Create: `src/updater/gui/frontend/src/App.vue`
- Create: `src/updater/gui/frontend/src/components/PackageTable.vue`
- Create: `src/updater/gui/frontend/src/components/ActionPanel.vue`
- Create: `src/updater/gui/frontend/src/components/LogConsole.vue`
- Create: `src/updater/gui/frontend/src/themes/blueprint.css`

- [ ] **Step 1: Create blueprint.css theme**

Create `src/updater/gui/frontend/src/themes/blueprint.css`:

```css
:root {
  --bg-primary: #f5f5f5;
  --bg-card: #ffffff;
  --bg-header: #1565c0;
  --bg-log: #263238;
  --text-primary: #212121;
  --text-secondary: #757575;
  --text-header: #ffffff;
  --text-log: #b0bec5;
  --accent-blue: #1565c0;
  --accent-green: #66bb6a;
  --accent-orange: #ff9800;
  --accent-red: #e53935;
  --border-color: #e0e0e0;
  --row-highlight: #fff8e1;
  --shadow-card: 0 1px 3px rgba(0, 0, 0, 0.12);
  --font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  --font-mono: 'Cascadia Code', 'Consolas', monospace;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: var(--font-family);
  background: var(--bg-primary);
  color: var(--text-primary);
  font-size: 13px;
  overflow: hidden;
  height: 100vh;
}

#app {
  height: 100vh;
  display: flex;
  flex-direction: column;
}
```

- [ ] **Step 2: Create PackageTable.vue**

Create `src/updater/gui/frontend/src/components/PackageTable.vue`:

```vue
<template>
  <div class="package-table">
    <div class="table-header">
      <span class="col-name">Package</span>
      <span class="col-installed">Installed</span>
      <span class="col-available">Available</span>
      <span class="col-status">Status</span>
    </div>
    <div class="table-body">
      <div
        v-for="pkg in packages"
        :key="pkg.name"
        class="table-row"
        :class="rowClass(pkg)"
      >
        <span class="col-name">{{ pkg.name }}</span>
        <span class="col-installed">{{ pkg.installed || '-' }}</span>
        <span class="col-available">{{ pkg.available || '-' }}</span>
        <span class="col-status" :class="statusClass(pkg)">
          {{ statusText(pkg) }}
        </span>
      </div>
      <div v-if="packages.length === 0" class="table-empty">
        No packages loaded
      </div>
    </div>
  </div>
</template>

<script setup>
import { inject, computed } from 'vue'

const store = inject('store')
const packages = computed(() => store.packages)

function rowClass(pkg) {
  return {
    'row-update': pkg.status === 'update_available',
    'row-missing': pkg.status === 'not_installed',
  }
}

function statusClass(pkg) {
  return {
    'status-ok': pkg.status === 'up_to_date',
    'status-update': pkg.status === 'update_available',
    'status-missing': pkg.status === 'not_installed' || pkg.status === 'not_in_source',
  }
}

function statusText(pkg) {
  const map = {
    up_to_date: 'Up to date',
    update_available: '▲ Update',
    not_in_source: 'Not in source',
    not_installed: 'Not installed',
  }
  return map[pkg.status] || pkg.status
}
</script>

<style scoped>
.package-table {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.table-header {
  display: flex;
  background: #e3f2fd;
  padding: 8px 12px;
  font-weight: 600;
  color: var(--accent-blue);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 2px solid var(--accent-blue);
}

.table-body {
  flex: 1;
  overflow-y: auto;
}

.table-row {
  display: flex;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-color);
  transition: background 0.15s;
}

.table-row:hover {
  background: #f0f4f8;
}

.row-update {
  background: var(--row-highlight);
}

.row-missing {
  background: #fff3e0;
}

.col-name { flex: 2; font-weight: 500; }
.col-installed { flex: 1; }
.col-available { flex: 1; }
.col-status { flex: 1; text-align: right; font-weight: 500; }

.status-ok { color: var(--accent-green); }
.status-update { color: #e65100; }
.status-missing { color: var(--text-secondary); }

.table-empty {
  padding: 40px;
  text-align: center;
  color: var(--text-secondary);
}
</style>
```

- [ ] **Step 3: Create ActionPanel.vue**

Create `src/updater/gui/frontend/src/components/ActionPanel.vue`:

```vue
<template>
  <div class="action-panel">
    <div class="actions">
      <button
        class="btn btn-primary"
        :disabled="store.isUpdating"
        @click="runUpdate"
      >
        <span v-if="store.isUpdating" class="spinner"></span>
        {{ store.isUpdating ? 'Updating...' : '↻ Update All' }}
      </button>
      <button
        class="btn btn-success"
        :disabled="!canLaunch"
        @click="launchApp"
      >
        {{ store.isLaunching ? 'Running...' : '▶ Launch' }}
      </button>
    </div>
    <div class="status-bar" v-if="store.updateResult">
      <div class="status-item">
        <span class="status-label">Updated</span>
        <span class="status-value ok">{{ store.updateResult.updated }}</span>
      </div>
      <div class="status-item">
        <span class="status-label">Failed</span>
        <span class="status-value" :class="store.updateResult.failed > 0 ? 'fail' : 'ok'">
          {{ store.updateResult.failed }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { inject, computed } from 'vue'

const store = inject('store')

const canLaunch = computed(() => {
  return store.updateComplete
    && !store.isLaunching
    && store.config.launcher_enabled
    && store.config.launcher_executable
})

async function runUpdate() {
  store.isUpdating = true
  store.updateComplete = false
  store.updateResult = null
  store.logs = []
  if (window.pywebview) {
    await window.pywebview.api.run_update()
  }
}

async function launchApp() {
  store.isLaunching = true
  if (window.pywebview) {
    const result = await window.pywebview.api.launch_app()
    if (!result.success) {
      store.isLaunching = false
    }
  }
}
</script>

<style scoped>
.action-panel {
  padding: 12px;
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.btn {
  padding: 10px 16px;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s, opacity 0.2s;
  font-family: var(--font-family);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--accent-blue);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #0d47a1;
}

.btn-success {
  background: #2e7d32;
  color: white;
}

.btn-success:hover:not(:disabled) {
  background: #1b5e20;
}

.spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-right: 6px;
  vertical-align: middle;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.status-bar {
  display: flex;
  gap: 12px;
  margin-top: 12px;
  padding: 8px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 4px;
}

.status-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
}

.status-label {
  font-size: 10px;
  text-transform: uppercase;
  color: var(--text-secondary);
  letter-spacing: 0.5px;
}

.status-value {
  font-size: 18px;
  font-weight: 700;
}

.status-value.ok { color: var(--accent-green); }
.status-value.fail { color: var(--accent-red); }
</style>
```

- [ ] **Step 4: Create LogConsole.vue**

Create `src/updater/gui/frontend/src/components/LogConsole.vue`:

```vue
<template>
  <div class="log-console">
    <div class="log-header">Console</div>
    <div class="log-body" ref="logBody">
      <div
        v-for="(entry, i) in logs"
        :key="i"
        class="log-line"
        :class="'log-' + entry.level"
      >
        <span class="log-time">{{ entry.timestamp }}</span>
        <span class="log-msg">{{ entry.message }}</span>
      </div>
      <div v-if="logs.length === 0" class="log-empty">
        Waiting for activity...
      </div>
    </div>
  </div>
</template>

<script setup>
import { inject, computed, ref, watch, nextTick } from 'vue'

const store = inject('store')
const logs = computed(() => store.logs)
const logBody = ref(null)

watch(logs, async () => {
  await nextTick()
  if (logBody.value) {
    logBody.value.scrollTop = logBody.value.scrollHeight
  }
}, { deep: true })
</script>

<style scoped>
.log-console {
  flex: 1;
  display: flex;
  flex-direction: column;
  border-top: 2px solid var(--accent-blue);
  margin-top: 12px;
  min-height: 0;
}

.log-header {
  padding: 6px 12px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-secondary);
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
}

.log-body {
  flex: 1;
  overflow-y: auto;
  background: var(--bg-log);
  padding: 8px 12px;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.6;
}

.log-line {
  display: flex;
  gap: 8px;
}

.log-time {
  color: #546e7a;
  flex-shrink: 0;
}

.log-msg {
  color: var(--text-log);
}

.log-info .log-msg { color: #4fc3f7; }
.log-success .log-msg { color: var(--accent-green); }
.log-error .log-msg { color: var(--accent-red); }

.log-empty {
  color: #546e7a;
  font-style: italic;
  padding: 20px 0;
}
</style>
```

- [ ] **Step 5: Create App.vue (root layout)**

Create `src/updater/gui/frontend/src/App.vue`:

```vue
<template>
  <div class="app">
    <header class="app-header">
      <h1>Test Matrix Updater</h1>
      <div class="header-status">
        <span v-if="updateCount > 0" class="badge badge-update">
          {{ updateCount }} update{{ updateCount > 1 ? 's' : '' }}
        </span>
        <span v-else-if="store.packages.length > 0" class="badge badge-ok">
          All up to date
        </span>
      </div>
    </header>
    <div class="app-body">
      <div class="panel-left">
        <PackageTable />
      </div>
      <div class="panel-right">
        <ActionPanel />
        <LogConsole />
      </div>
    </div>
  </div>
</template>

<script setup>
import { inject, computed } from 'vue'
import PackageTable from './components/PackageTable.vue'
import ActionPanel from './components/ActionPanel.vue'
import LogConsole from './components/LogConsole.vue'

const store = inject('store')

const updateCount = computed(() =>
  store.packages.filter(p =>
    p.status === 'update_available' || p.status === 'not_installed'
  ).length
)
</script>

<style>
@import './themes/blueprint.css';

.app {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  background: var(--bg-header);
  color: var(--text-header);
  padding: 12px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
  z-index: 10;
}

.app-header h1 {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.badge {
  padding: 3px 10px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
}

.badge-update {
  background: var(--accent-orange);
  color: white;
}

.badge-ok {
  background: rgba(255, 255, 255, 0.2);
  color: white;
}

.app-body {
  flex: 1;
  display: flex;
  min-height: 0;
}

.panel-left {
  flex: 65;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-color);
  background: var(--bg-card);
}

.panel-right {
  flex: 35;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
}
</style>
```

- [ ] **Step 6: Verify frontend builds**

Run:
```bash
cd src/updater/gui/frontend && npm run build
```
Expected: Build succeeds, `dist/` directory created with `index.html` + assets

- [ ] **Step 7: Commit**

```bash
git add src/updater/gui/frontend/src/
git commit -m "feat(gui): build Vue components - PackageTable, ActionPanel, LogConsole with Blueprint theme"
```

---

## Chunk 6: PyWebView GUI Application

### Task 8: Create PyWebView bridge application

**Files:**
- Create: `src/updater/gui/app.py`

- [ ] **Step 1: Implement gui/app.py**

Create `src/updater/gui/app.py`:

```python
from __future__ import annotations

import argparse
import json
import sys
import threading
from datetime import datetime
from pathlib import Path

import webview

from updater.config import UpdaterConfig, find_config, load_config
from updater.core import (
    check_updates,
    find_venv_python,
    get_installed_versions_batch,
    install_updates,
    scan_packages,
)
from updater.launcher import LauncherError, launch_executable, should_launch


class Api:
    def __init__(self, config: UpdaterConfig, python_exe: Path | None) -> None:
        self._config = config
        self._python_exe = python_exe
        self._window: webview.Window | None = None

    def _set_window(self, window: webview.Window) -> None:
        self._window = window

    def _push_log(self, level: str, message: str) -> None:
        if self._window is None:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        payload = json.dumps({"level": level, "message": message, "timestamp": ts})
        self._window.evaluate_js(f"window.addLogLine({payload})")

    def _push_packages(self, packages: list[dict[str, str | None]]) -> None:
        if self._window is None:
            return
        payload = json.dumps(packages)
        self._window.evaluate_js(f"window.updatePackages({payload})")

    def get_config(self) -> dict[str, object]:
        return {
            "launcher_enabled": self._config.launcher.enabled,
            "launcher_executable": self._config.launcher.executable,
            "auto_launch": self._config.launcher.auto_launch,
            "auto_update": self._config.launcher.auto_update,
            "theme": self._config.gui.theme,
        }

    def get_packages(self) -> list[dict[str, str | None]]:
        if self._python_exe is None:
            return []
        installed = get_installed_versions_batch(
            self._python_exe, self._config.packages
        )
        return [
            {
                "name": pkg,
                "installed": ver,
                "available": None,
                "status": "up_to_date" if ver else "not_installed",
            }
            for pkg, ver in installed.items()
        ]

    def run_update(self) -> None:
        thread = threading.Thread(target=self._do_update, daemon=True)
        thread.start()

    def _do_update(self) -> None:
        if self._python_exe is None:
            self._push_log("error", "No venv Python found")
            return

        self._push_log("info", f"Scanning source: {self._config.source}")
        available = scan_packages(Path(self._config.source))

        if not available:
            self._push_log("error", "No .whl files found in source path")
            if self._window:
                summary = json.dumps(
                    {"total": 0, "updated": 0, "failed": 0, "should_launch": False}
                )
                self._window.evaluate_js(f"window.onUpdateComplete({summary})")
            return

        self._push_log("info", f"Found {len(available)} package(s) in source")

        installed_versions = get_installed_versions_batch(
            self._python_exe, self._config.packages
        )
        statuses = check_updates(
            self._config.packages, installed_versions, available
        )

        pkg_data = [
            {
                "name": s.name,
                "installed": s.installed,
                "available": s.available,
                "status": s.status,
            }
            for s in statuses
        ]
        self._push_packages(pkg_data)

        to_update = [
            s for s in statuses if s.status in ("update_available", "not_installed")
        ]
        self._push_log(
            "info", f"{len(to_update)} package(s) to update"
        )

        result = install_updates(statuses, self._python_exe, on_progress=self._push_log)

        do_launch = should_launch(self._config.launcher.mode, result)
        summary = json.dumps(
            {
                "total": result.total,
                "updated": result.updated,
                "failed": result.failed,
                "should_launch": do_launch
                and self._config.launcher.enabled
                and bool(self._config.launcher.executable),
            }
        )
        if self._window:
            self._window.evaluate_js(f"window.onUpdateComplete({summary})")

        if (
            self._config.launcher.auto_launch
            and self._config.launcher.enabled
            and self._config.launcher.executable
            and do_launch
        ):
            self._push_log("info", "Auto-launching application...")
            self._do_launch()

    def launch_app(self) -> dict[str, object]:
        return self._do_launch()

    def _do_launch(self) -> dict[str, object]:
        if not self._python_exe:
            return {"success": False, "error": "No venv Python found", "pid": None}
        try:
            proc = launch_executable(self._config, self._python_exe)
            self._push_log("success", f"Launched (PID: {proc.pid})")
            return {"success": True, "error": None, "pid": proc.pid}
        except LauncherError as exc:
            self._push_log("error", f"Launch failed: {exc}")
            return {"success": False, "error": str(exc), "pid": None}


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Matrix Updater GUI")
    parser.add_argument(
        "--dev", action="store_true", help="Load from Vite dev server"
    )
    args = parser.parse_args()

    config = load_config(find_config())
    exe_dir = Path(__file__).parent
    python_exe = find_venv_python(None, exe_dir)

    api = Api(config, python_exe)

    if args.dev:
        url = "http://localhost:15173"
    else:
        frontend_dist = Path(__file__).parent / "frontend" / "dist" / "index.html"
        if not frontend_dist.exists():
            print(
                f"[ERROR] Frontend not built. Run: cd {frontend_dist.parent.parent} && npm run build"
            )
            sys.exit(1)
        url = str(frontend_dist)

    window = webview.create_window(
        "Test Matrix Updater",
        url=url,
        js_api=api,
        width=900,
        height=550,
        min_size=(700, 400),
    )
    api._set_window(window)

    def on_loaded() -> None:
        cfg = api.get_config()
        if cfg.get("auto_update"):
            window.evaluate_js("window.pywebview.api.run_update()")

    window.events.loaded += on_loaded

    webview.start()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify dev mode works**

Run in two terminals:
```bash
# Terminal 1
cd src/updater/gui/frontend && npm run dev

# Terminal 2
.venv/Scripts/python.exe -m updater.gui.app --dev
```
Expected: PyWebView window opens showing the Vue app at localhost:15173

- [ ] **Step 3: Commit**

```bash
git add src/updater/gui/app.py
git commit -m "feat(gui): add PyWebView bridge with update, launch, and log streaming"
```

---

### Task 9: Create GUI build script

**Files:**
- Create: `scripts/build_gui.bat`

- [ ] **Step 1: Create build_gui.bat**

Create `scripts/build_gui.bat`:

```batch
@echo off
setlocal

set SCRIPT_DIR=%~dp0
set ROOT_DIR=%SCRIPT_DIR%..
set VENV_PYTHON=%ROOT_DIR%\.venv\Scripts\python.exe
set SOURCE_FILE=%ROOT_DIR%\src\updater\gui\app.py
set FRONTEND_DIR=%ROOT_DIR%\src\updater\gui\frontend
set OUTPUT_DIR=%ROOT_DIR%\dist

if not exist "%VENV_PYTHON%" (
    echo [ERROR] venv not found at %VENV_PYTHON%
    echo Please create the venv first: python -m venv .venv
    pause
    exit /b 1
)

echo Checking Nuitka installation...
"%VENV_PYTHON%" -m nuitka --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Nuitka not installed. Run: pip install nuitka
    pause
    exit /b 1
)

echo.
echo Building frontend...
cd "%FRONTEND_DIR%"
call npm run build
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Frontend build failed.
    pause
    exit /b 1
)
cd "%ROOT_DIR%"

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo.
echo Building updater_gui.exe with Nuitka...
echo Source : %SOURCE_FILE%
echo Output : %OUTPUT_DIR%\updater_gui.exe
echo.

"%VENV_PYTHON%" -m nuitka ^
    --onefile ^
    --mingw64 ^
    --output-filename=updater_gui.exe ^
    --output-dir="%OUTPUT_DIR%" ^
    --include-data-dir="%FRONTEND_DIR%\dist"=updater/gui/frontend/dist ^
    --include-package=webview ^
    --include-package=packaging ^
    --windows-console-mode=disable ^
    --assume-yes-for-downloads ^
    "%SOURCE_FILE%"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo Build successful: %OUTPUT_DIR%\updater_gui.exe
pause
```

- [ ] **Step 2: Commit**

```bash
git add scripts/build_gui.bat
git commit -m "feat(build): add Nuitka build script for GUI executable"
```

---

## Chunk 7: Integration & Final Polish

### Task 10: Run all tests and verify integration

**Files:**
- All test files

- [ ] **Step 1: Run full test suite**

Run: `.venv/Scripts/python.exe -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Verify frontend build**

Run: `cd src/updater/gui/frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Manual integration test - dev mode**

Run in two terminals:
```bash
# Terminal 1
cd src/updater/gui/frontend && npm run dev

# Terminal 2
.venv/Scripts/python.exe -m updater.gui.app --dev
```
Expected:
- Window opens with "Test Matrix Updater" header
- Package table shows (may be empty if no venv detected)
- Update All and Launch buttons visible
- Log console area visible
- Blueprint theme applied (light grey bg, blue header)
- Open browser DevTools (F12): verify `pywebviewready` fired and `store.config` was populated
- Click "Update All": verify log lines stream into the console
- After update completes: verify Launch button enables (if launcher configured)

- [ ] **Step 4: Test auto_update flow**

Create a temporary `updater.toml` with `auto_update = true` under `[launcher]`. Launch the GUI.
Expected: Update process starts automatically without clicking "Update All".

- [ ] **Step 5: Verify CLI still works**

Run: `.venv/Scripts/python.exe -m updater.main --dry-run --source .`
Expected: CLI runs, shows package scan results (or "no .whl files" if no source)

- [ ] **Step 6: Final commit with all remaining files**

```bash
git add -A
git status
git commit -m "feat: complete Updater GUI & Launcher integration"
```
