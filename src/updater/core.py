from __future__ import annotations

import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
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

# Package status constants
STATUS_UP_TO_DATE = "up_to_date"
STATUS_UPDATE_AVAILABLE = "update_available"
STATUS_NOT_IN_SOURCE = "not_in_source"
STATUS_NOT_INSTALLED = "not_installed"
STATUS_VERSION_SPECIFIED = "version_specified"
UPDATABLE_STATUSES = (STATUS_UPDATE_AVAILABLE, STATUS_NOT_INSTALLED, STATUS_VERSION_SPECIFIED)

_pip_cache: dict[str, dict[str, str]] = {}


def _get_subprocess_kwargs() -> dict:
    """Return subprocess kwargs for Windows no-window behavior."""
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


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
                encoding="utf-8",
                timeout=30,
                **_get_subprocess_kwargs(),
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
                    status=STATUS_NOT_IN_SOURCE,
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
                    status=STATUS_NOT_INSTALLED,
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
                        status=STATUS_UP_TO_DATE,
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
                status=STATUS_UPDATE_AVAILABLE,
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
            encoding="utf-8",
            timeout=120,
            **_get_subprocess_kwargs(),
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
    target_version: str | None = None,
    source_path: Path | None = None,
) -> UpdateResult:
    if target_version:
        updated_statuses = []
        for s in statuses:
            if s.status == STATUS_UP_TO_DATE and s.installed != target_version:
                if on_progress:
                    on_progress(
                        "debug",
                        f"{s.name}: overriding status to version_specified "
                        f"(installed={s.installed}, target={target_version})",
                    )
                updated_statuses.append(replace(s, status=STATUS_VERSION_SPECIFIED))
            else:
                updated_statuses.append(s)
        statuses = updated_statuses

    to_update = [s for s in statuses if s.status in UPDATABLE_STATUSES]
    updated = 0
    failed = 0
    failures: list[str] = []

    for ps in to_update:
        if on_progress:
            arrow = f"{ps.installed or 'not installed'} -> {target_version or ps.available}"
            on_progress("info", f"{ps.name}: {arrow} installing...")

        if target_version:
            try:
                # Uninstall existing version first
                uninstall_cmd = [
                    str(python_exe),
                    "-m",
                    "pip",
                    "uninstall",
                    "-y",
                    ps.name,
                ]
                if on_progress:
                    on_progress(
                        "debug",
                        f"{ps.name}: [DEBUG] Uninstalling current version - cmd: {' '.join(uninstall_cmd)}",
                    )
                uninstall_result = subprocess.run(
                    uninstall_cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=120,
                    **_get_subprocess_kwargs(),
                )
                if on_progress:
                    on_progress(
                        "debug",
                        f"{ps.name}: [DEBUG] Uninstall returncode: {uninstall_result.returncode}",
                    )
                if uninstall_result.returncode != 0:
                    if on_progress:
                        on_progress(
                            "error",
                            f"{ps.name}: uninstall failed - {uninstall_result.stderr}",
                        )
                    failed += 1
                    failures.append(f"{ps.name}: uninstall failed")
                    continue

                # Install the specific target version
                # Use --find-links to install from local source directory
                if source_path:
                    install_cmd = [
                        str(python_exe),
                        "-m",
                        "pip",
                        "install",
                        f"--find-links={source_path}",
                        f"{ps.name}=={target_version}",
                    ]
                    if on_progress:
                        on_progress(
                            "debug",
                            f"{ps.name}: [DEBUG] Installing from local source - cmd: {' '.join(install_cmd)}",
                        )
                    install_result = subprocess.run(
                        install_cmd,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        timeout=120,
                        **_get_subprocess_kwargs(),
                    )
                    if on_progress:
                        on_progress(
                            "debug",
                            f"{ps.name}: [DEBUG] pip install returncode: {install_result.returncode}",
                        )
                        if install_result.stdout:
                            on_progress(
                                "debug",
                                f"{ps.name}: [DEBUG] pip stdout: {install_result.stdout[:500]}",
                            )
                        if install_result.stderr:
                            on_progress(
                                "debug",
                                f"{ps.name}: [DEBUG] pip stderr: {install_result.stderr[:500]}",
                            )
                    ok = install_result.returncode == 0
                    err = install_result.stderr if not ok else ""
                else:
                    # Fallback to direct wheel installation if source_path not provided
                    if ps.whl_path:
                        if on_progress:
                            on_progress(
                                "debug",
                                f"{ps.name}: [DEBUG] Using local wheel file: {ps.whl_path}",
                            )
                        ok, err = install_whl(ps.whl_path, python_exe)
                    else:
                        # Last resort: try PyPI
                        install_cmd = [
                            str(python_exe),
                            "-m",
                            "pip",
                            "install",
                            f"{ps.name}=={target_version}",
                        ]
                        if on_progress:
                            on_progress(
                                "debug",
                                f"{ps.name}: [DEBUG] Installing from PyPI - cmd: {' '.join(install_cmd)}",
                            )
                        install_result = subprocess.run(
                            install_cmd,
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            timeout=120,
                            **_get_subprocess_kwargs(),
                        )
                        if on_progress:
                            on_progress(
                                "debug",
                                f"{ps.name}: [DEBUG] pip install returncode: {install_result.returncode}",
                            )
                        ok = install_result.returncode == 0
                        err = install_result.stderr if not ok else ""
            except subprocess.TimeoutExpired:
                if on_progress:
                    on_progress("error", f"{ps.name}: timed out after 120s")
                failed += 1
                failures.append(f"{ps.name}: timeout")
                continue
        else:
            assert ps.whl_path is not None
            ok, err = install_whl(ps.whl_path, python_exe)

        if ok:
            updated += 1
            if on_progress:
                on_progress(
                    "success", f"{ps.name}: updated to {target_version or ps.available}"
                )
        else:
            failed += 1
            failures.append(ps.name)
            if on_progress:
                on_progress("error", f"{ps.name}: FAILED - {err}")

    clear_pip_cache()
    return UpdateResult(
        total=len(to_update), updated=updated, failed=failed, failures=failures
    )


def get_all_versions(package_name: str, source_path: Path) -> list[str]:
    """
    Scan source directory for all available versions of a package.
    Returns versions sorted newest-first.

    Args:
        package_name: Normalized package name (e.g., "test-matrix")
        source_path: Path to wheel file source directory

    Returns:
        List of version strings sorted newest-first, e.g., ["1.5.0", "1.4.2", "1.0.0"]
    """
    versions: dict[str, Path] = {}
    normalized_name = normalize_name(package_name)

    # Scan source directory for matching wheel files
    if not source_path.exists():
        return []

    for whl_file in source_path.glob("*.whl"):
        # Parse wheel filename: {distribution}-{version}(-{build tag})?-{python tag}-{abi tag}-{platform tag}.whl
        parts = whl_file.stem.split("-")
        if len(parts) >= 2 and normalize_name(parts[0]) == normalized_name:
            version_str = parts[1]
            try:
                Version(version_str)  # Validate version format
                versions[version_str] = whl_file
            except InvalidVersion:
                continue

    # Sort by Version object (newest first)
    sorted_versions = sorted(versions.keys(), key=Version, reverse=True)
    return sorted_versions


def find_venv_python(
    venv_arg: str | None, exe_dir: Path, venv_names: list[str] | None = None
) -> Path | None:
    if venv_names is None:
        venv_names = ["venv", ".venv"]

    candidates: list[Path] = []
    if venv_arg:
        candidates.append(Path(venv_arg) / "Scripts" / "python.exe")

    cwd = Path.cwd()
    for name in venv_names:
        candidates += [
            exe_dir / name / "Scripts" / "python.exe",
            exe_dir.parent / name / "Scripts" / "python.exe",
            cwd / name / "Scripts" / "python.exe",
            cwd.parent / name / "Scripts" / "python.exe",
        ]

    for p in candidates:
        if p.exists():
            return p
    return None
