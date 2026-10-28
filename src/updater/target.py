"""
Target resolution: decide which project folder an updater run operates on.

Spec: docs/specs/target_resolution_spec.md

Pure functions - no global state, no side effects other than reading the
filesystem.  `exe_dir` and `cwd` are injected by the callers (CLI / GUI) so
the resolution order can be unit-tested without touching the real machine.
"""

from __future__ import annotations

import ntpath
from dataclasses import dataclass
from pathlib import Path

from updater.config import CONFIG_FILENAME, UpdaterConfig, load_config

# How many ancestor levels to walk when inferring the project from the cwd.
MAX_ANCESTOR_LOOKUP = 4

# config_origin values (reported to the GUI / --debug output)
ORIGIN_PROJECT = "project"
ORIGIN_EXE = "exe"
ORIGIN_BUILTIN = "builtin"

_VENV_SCRIPTS = ("Scripts", "python.exe")


class TargetError(Exception):
    """Raised when an explicitly given target is unusable."""


@dataclass(frozen=True)
class UpdateTarget:
    """Everything the updater needs to know about the folder it operates on."""

    project_root: Path
    config: UpdaterConfig
    python_exe: Path | None
    config_origin: str

    def describe(self) -> str:
        """Human readable summary for CLI / GUI log lines."""
        venv = self.python_exe.parent.parent if self.python_exe else "not found"
        return (
            f"Project: {self.project_root} | "
            f"Venv: {venv} | "
            f"Config: {self.config.config_dir} ({self.config_origin}) | "
            f"Source: {self.config.source}"
        )


def _is_project_marker(path: Path, venv_names: list[str]) -> bool:
    if (path / CONFIG_FILENAME).exists():
        return True
    return any((path / name / "Scripts" / "python.exe").exists() for name in venv_names)


def find_project_root(
    start: Path, venv_names: list[str], max_up: int = MAX_ANCESTOR_LOOKUP
) -> Path | None:
    """
    Walk up from `start` and return the nearest ancestor that looks like an
    updater target (has updater.toml or <venv_name>/Scripts/python.exe).
    """
    current = start.resolve()
    for _ in range(max_up + 1):
        if _is_project_marker(current, venv_names):
            return current
        if current.parent == current:
            break
        current = current.parent
    return None


def _venv_candidates(root: Path, venv_names: list[str]) -> list[Path]:
    scripts = Path(*_VENV_SCRIPTS)
    return [
        root / name / scripts for name in venv_names
    ] + [root.parent / name / scripts for name in venv_names]


def find_target_python(project_root: Path, venv_names: list[str]) -> Path | None:
    for candidate in _venv_candidates(project_root, venv_names):
        if candidate.exists():
            return candidate
    return None


def resolve_venv_arg(venv_arg: str, venv_names: list[str]) -> Path:
    """
    Resolve an explicit --venv directory.  Unlike the legacy candidate search
    this fails loudly, because a typo would otherwise silently update the
    wrong environment.
    """
    venv_dir = Path(venv_arg)
    if not venv_dir.is_dir():
        raise TargetError(f"venv directory not found: {venv_dir}")
    scripts = Path(*_VENV_SCRIPTS)
    python_exe = venv_dir / scripts
    if not python_exe.exists():
        # A bare venv root may also be given as the Scripts dir itself.
        alt = venv_dir / "python.exe"
        if alt.exists():
            return alt.parent.parent
        raise TargetError(
            f"no Scripts/python.exe under the given venv: {venv_dir} "
            f"(expected {venv_dir / scripts})"
        )
    return python_exe


def _is_anchored(raw: str) -> bool:
    """
    True when the configured source already points at a fixed location.

    Path.is_absolute() is not enough: on Python 3.11 a UNC path such as
    ``\\\\pnt52\\packages`` reports is_absolute() == False and an empty .drive,
    so it would wrongly be treated as relative.  Windows-only project, so
    ntpath is the right flavour.
    """
    if raw.startswith("\\\\"):
        return True
    if ntpath.splitdrive(raw)[0]:
        return True
    return Path(raw).is_absolute()


def resolve_source(config: UpdaterConfig) -> Path:
    """
    Resolve config.source to an absolute path.  A relative source is anchored
    at config_dir so a per-project updater.toml can ship a local packages/
    folder.  Anchored paths (UNC / drive-anchored) are returned untouched -
    Path.resolve() would rewrite them (e.g. append a trailing backslash).
    """
    raw = config.source
    if _is_anchored(raw):
        return Path(raw)
    return (config.config_dir / raw).resolve()


def find_exe_config(exe_dir: Path) -> Path:
    """
    Locate updater.toml beside the exe or up to two levels above it.

    Mirrors config.find_config(), but takes exe_dir as input instead of
    reading sys.argv[0], so the resolution order is testable.
    """
    for dir_path in (exe_dir, exe_dir.parent, exe_dir.parent.parent):
        candidate = dir_path / CONFIG_FILENAME
        if candidate.exists():
            return candidate
    return exe_dir / CONFIG_FILENAME


def _load_project_config(project_root: Path) -> UpdaterConfig | None:
    toml_path = project_root / CONFIG_FILENAME
    if not toml_path.exists():
        return None
    return load_config(toml_path)


def resolve_target(
    project_arg: str | None,
    exe_dir: Path,
    cwd: Path,
    *,
    default_venv_names: list[str] | None = None,
) -> UpdateTarget:
    """
    Apply the spec's resolution order and return the UpdateTarget.

    Args:
        project_arg: value of --project (None when not given).
        exe_dir: directory of the running executable / entry script.
        cwd: current working directory.
        default_venv_names: venv folder names to look for before any config
            has been loaded (defaults to ["venv", ".venv"]).
    """
    venv_names = default_venv_names or ["venv", ".venv"]

    if project_arg:
        project_root = Path(project_arg)
        if not project_root.exists():
            raise TargetError(f"--project path not found: {project_root}")
        if not project_root.is_dir():
            raise TargetError(f"--project is not a directory: {project_root}")
        project_root = project_root.resolve()
    else:
        project_root = (
            find_project_root(cwd, venv_names)
            or find_project_root(exe_dir, venv_names)
            or exe_dir
        )

    # The "exe level" toml is the shared default; a toml anywhere else belongs
    # to the project being updated and takes precedence (spec section 4).
    exe_config_path = find_exe_config(exe_dir)
    config = _load_project_config(project_root)
    if config is None:
        if exe_config_path.exists():
            config = load_config(exe_config_path)
            config_origin = ORIGIN_EXE
        else:
            config = load_config(exe_config_path)  # prints DEBUG, returns defaults
            config_origin = ORIGIN_BUILTIN
    elif (project_root / CONFIG_FILENAME) == exe_config_path:
        config_origin = ORIGIN_EXE
    else:
        config_origin = ORIGIN_PROJECT

    python_exe = find_target_python(project_root, config.venv_names)
    if python_exe is None and project_root != exe_dir:
        python_exe = find_target_python(exe_dir, config.venv_names)
    if python_exe is not None and not project_arg:
        # Legacy layout: the updater (and its toml) sits *inside* the project,
        # so the folder that owns the venv is the real project root.
        # python_exe = <root>/<venv_name>/Scripts/python.exe
        project_root = python_exe.parents[2]

    return UpdateTarget(
        project_root=project_root,
        config=config,
        python_exe=python_exe,
        config_origin=config_origin,
    )
