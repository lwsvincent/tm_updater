"""
Test Matrix Package Updater

Standalone updater compiled with Nuitka to updater.exe.
Scans a whl source directory (default: PNT52 network share),
compares against installed versions, and installs newer packages
into the local venv.

Usage:
  updater.exe [--project <path>] [--source <path>] [--venv <path>]
              [--packages pkg1 pkg2 ...] [--dry-run]

  --project selects the folder to update (its venv and updater.toml).  The
  executable itself may live anywhere; see docs/specs/target_resolution_spec.md
"""

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from updater import get_version
from updater.core import (
    check_updates,
    find_venv_python,
    get_installed_versions_batch,
    install_updates,
    scan_packages,
)
from updater.launcher import LauncherError, launch_executable, should_launch
from updater.target import (
    UpdateTarget,
    TargetError,
    resolve_source,
    resolve_target,
    resolve_venv_arg,
)


def _cli_progress(level: str, message: str) -> None:
    prefix = {"info": "  ", "success": "  ", "error": "  [ERROR] "}
    print(f"{prefix.get(level, '  ')}{message}")


def _resolve_cli_target(args: argparse.Namespace, exe_dir: Path) -> UpdateTarget:
    """Resolve the target folder per target_resolution_spec (fails loudly)."""
    try:
        target = resolve_target(args.project, exe_dir, Path.cwd())
        if args.venv:
            python_exe = resolve_venv_arg(args.venv, target.config.venv_names)
            target = replace(target, python_exe=python_exe)
        elif target.python_exe is None:
            # Legacy candidate chain, kept for installations that predate --project.
            target = replace(
                target,
                python_exe=find_venv_python(None, exe_dir, target.config.venv_names),
            )
        return target
    except TargetError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)


def main() -> None:
    print(f"Test Matrix Updater (v{get_version()})")

    parser = argparse.ArgumentParser(
        description="Test Matrix Package Updater - installs .whl packages from a network share"
    )
    parser.add_argument(
        "--project",
        default=None,
        help="Folder to update (its venv and updater.toml). Defaults to the "
        "nearest project marker from the current directory.",
    )
    parser.add_argument(
        "--source", default=None, help="Path to whl source directory"
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

    exe_dir = Path(__file__).parent
    target = _resolve_cli_target(args, exe_dir)
    config = target.config
    python_exe = target.python_exe
    source_path = Path(args.source) if args.source else resolve_source(config)
    if config.parse_error:
        print(f"[WARNING] {config.parse_error}")

    print(f"Source : {source_path}")
    if args.dry_run:
        print("Mode   : dry-run (no changes will be made)")
    print("-" * 55)

    if python_exe is None:
        print(
            "[ERROR] Cannot find venv Python. Use --project <folder> or "
            "--venv <path> to specify the folder to update."
        )
        sys.exit(1)
    print(f"Venv   : {python_exe.parent.parent}")
    if args.debug:
        print(f"Target : {target.describe()}")
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
