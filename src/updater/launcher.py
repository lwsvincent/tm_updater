from __future__ import annotations

import subprocess
import sys
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
) -> subprocess.Popen[bytes]:
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

    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    try:
        return subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
    except PermissionError as exc:
        raise LauncherError(f"Permission denied: {exe_path} - {exc}") from exc
    except FileNotFoundError as exc:
        raise LauncherError(f"File not found: {exe_path} - {exc}") from exc
    except OSError as exc:
        raise LauncherError(f"OS error launching {exe_path}: {exc}") from exc
