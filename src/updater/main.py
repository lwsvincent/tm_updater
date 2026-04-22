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
import importlib.metadata
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from packaging.version import Version, InvalidVersion

DEFAULT_SOURCE = r"\\pnt52\研發本部_技術服務處\技術服務處\DS-TA\Test_Matrix\packages"

MANAGED_PACKAGES = [
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


def normalize_name(name: str) -> str:
    """Normalize package name per PEP 503 (hyphens/underscores/dots -> hyphen, lowercase)."""
    return re.sub(r"[-_.]+", "-", name).lower()


# Cache for pip list results (per venv)
_pip_cache: dict[str, dict[str, str]] = {}


def get_installed_versions_batch(python_exe: Path, package_names: list[str]) -> dict[str, str | None]:
    """
    Get versions for multiple packages at once using 'pip list --format=json'.
    Much faster than individual 'pip show' calls.
    Returns {package_name: version_str or None}.
    """
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
                import json
                packages = json.loads(result.stdout)
                # Build dict: {name_normalized: version}
                _pip_cache[exe_key] = {normalize_name(p["name"]): p["version"] for p in packages}
            else:
                _pip_cache[exe_key] = {}
        except (subprocess.TimeoutExpired, Exception):
            _pip_cache[exe_key] = {}

    cached = _pip_cache[exe_key]
    return {pkg: cached.get(normalize_name(pkg)) for pkg in package_names}


def get_installed_version(package_name: str, python_exe: Path | None = None) -> str | None:
    """Get installed version. If python_exe provided, query that venv; otherwise use current Python."""
    try:
        if python_exe:
            # Use batch query (faster than individual pip show calls)
            versions = get_installed_versions_batch(python_exe, [package_name])
            return versions[package_name]
        else:
            return importlib.metadata.version(package_name)
    except (importlib.metadata.PackageNotFoundError, subprocess.TimeoutExpired):
        return None


def _parse_whl_file(whl: Path) -> tuple[str, str, Path] | None:
    """Parse single .whl file. Returns (normalized_name, version_str, path) or None."""
    parts = whl.stem.split("-")
    if len(parts) < 2:
        return None
    dist_name = normalize_name(parts[0])
    ver_str = parts[1]
    try:
        Version(ver_str)  # Validate version
        return (dist_name, ver_str, whl)
    except InvalidVersion:
        return None


def scan_whl_source(source_path: Path) -> dict[str, tuple[str, Path]]:
    """
    Scan source directory for .whl files (parallel).
    Returns {normalized_name: (latest_version_str, whl_path)}.
    Only keeps the latest version per package.
    """
    available: dict[str, tuple[str, Path]] = {}

    if not source_path.exists():
        print(f"[ERROR] Source path not accessible: {source_path}")
        return available

    whl_files = list(source_path.glob("*.whl"))

    # Parse wheel files in parallel
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = executor.map(_parse_whl_file, whl_files)

    for result in results:
        if result is None:
            continue
        dist_name, ver_str, whl = result
        if dist_name not in available or Version(ver_str) > Version(available[dist_name][0]):
            available[dist_name] = (ver_str, whl)

    return available


def find_venv_python(venv_arg: str | None, exe_dir: Path) -> Path | None:
    """Locate venv python.exe. Checks --venv arg first, then common relative locations."""
    candidates: list[Path] = []

    if venv_arg:
        candidates.append(Path(venv_arg) / "Scripts" / "python.exe")

    # Also check from current working directory (where exe is typically run)
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


def install_whl(whl_path: Path, python_exe: Path) -> tuple[bool, str]:
    """Install a single .whl file via the venv pip. Returns (success, error_msg)."""
    try:
        result = subprocess.run(
            [str(python_exe), "-m", "pip", "install", str(whl_path), "--no-deps", "--no-input"],
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test Matrix Package Updater - installs .whl packages from a network share"
    )
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="Path to whl source directory")
    parser.add_argument("--venv", default=None, help="Path to Python venv directory")
    parser.add_argument("--packages", nargs="*", help="Packages to update (default: all managed packages)")
    parser.add_argument("--dry-run", action="store_true", help="Check for updates without installing")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()

    source_path = Path(args.source)
    # Nuitka exe extracts to temp dir, so use script directory as fallback
    exe_dir = Path(__file__).parent

    print("Test Matrix Updater")
    print(f"Source : {source_path}")
    if args.dry_run:
        print("Mode   : dry-run (no changes will be made)")
    print("-" * 55)

    # Locate venv Python (needed for version checking and installation)
    python_exe = find_venv_python(args.venv, exe_dir)
    if python_exe is None:
        print("[ERROR] Cannot find venv Python. Use --venv <path> to specify the venv directory.")
        sys.exit(1)
    print(f"Venv   : {python_exe.parent.parent}")
    print("-" * 55)

    # Scan source directory
    print("Scanning source for available packages...")
    available = scan_whl_source(source_path)

    if not available:
        print("[WARNING] No .whl files found in source path. Nothing to do.")
        sys.exit(0)

    print(f"Found {len(available)} package(s) in source.\n")

    # Determine which packages to process
    target_packages: list[str] = args.packages if args.packages else MANAGED_PACKAGES

    # Get all installed versions at once (single pip list call)
    installed_versions = get_installed_versions_batch(python_exe, target_packages) if python_exe else {}

    updates_found = 0
    updates_done = 0
    failures = 0

    for pkg in target_packages:
        norm = normalize_name(pkg)
        installed = installed_versions[pkg]
        installed_str = installed or "not installed"

        if norm not in available:
            print(f"  {pkg:<35} {installed_str:<15}  (not in source, skipped)")
            continue

        avail_ver, whl_path = available[norm]

        # Already up to date?
        if installed:
            try:
                if Version(installed) >= Version(avail_ver):
                    print(f"  {pkg:<35} {installed_str:<15}  up to date")
                    continue
            except InvalidVersion:
                pass  # treat as needs update

        updates_found += 1
        arrow = f"{installed_str} -> {avail_ver}"

        if args.dry_run:
            print(f"  {pkg:<35} {arrow}  [update available]")
            continue

        print(f"  {pkg:<35} {arrow}  installing...", end="", flush=True)
        ok, err = install_whl(whl_path, python_exe)
        if ok:
            updates_done += 1
            print(" OK")
        else:
            failures += 1
            print(f" FAILED\n    {err}")

    print("-" * 55)

    if args.dry_run:
        print(f"Updates available: {updates_found}")
    else:
        print(f"Updated : {updates_done}/{updates_found}")
        if failures:
            print(f"Failures: {failures}")
        if updates_done > 0:
            print("\nRestart the Test Matrix service to apply changes.")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
