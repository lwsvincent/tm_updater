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
