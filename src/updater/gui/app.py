from __future__ import annotations

import argparse
import json
import sys
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import webview

from updater import get_version
from updater.config import UpdaterConfig
from packaging.version import Version

from updater.core import (
    STATUS_NOT_INSTALLED,
    STATUS_UP_TO_DATE,
    STATUS_UPDATE_AVAILABLE,
    UPDATABLE_STATUSES,
    PackageStatus,
    check_updates,
    clear_pip_cache,
    get_all_versions,
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
)


class Api:
    def __init__(
        self,
        config: UpdaterConfig,
        python_exe: Path | None,
        target: UpdateTarget | None = None,
    ) -> None:
        self._config = config
        self._python_exe = python_exe
        self._target = target
        self._window: webview.Window | None = None
        self._update_lock = threading.Lock()
        self._auto_update_disabled = False
        self._config_error_logged = False

    def _set_window(self, window: webview.Window) -> None:
        self._window = window

    # --- target (folder to update) -------------------------------------

    def _source_path(self) -> Path:
        """whl source directory, resolved per target_resolution_spec section 6."""
        return resolve_source(self._config)

    def _apply_target(self, target: UpdateTarget) -> None:
        """Hot-swap the folder being updated and drop stale pip data."""
        self._target = target
        self._config = target.config
        self._python_exe = target.python_exe
        clear_pip_cache()
        self._auto_update_disabled = False
        self._config_error_logged = False

    def get_target(self) -> dict[str, object]:
        """Current update target, for the GUI header."""
        base = {
            "project": "",
            "venv": "",
            "source": str(self._source_path()),
            "config": str(self._config.config_dir),
            "config_origin": "",
            "config_error": self._config.parse_error,
            "encoding": self._config.encoding,
        }
        if self._target is None:
            base["error"] = "未解析到目標資料夾"
            return base
        venv = self._target.python_exe
        base.update(
            {
                "project": str(self._target.project_root),
                "venv": str(venv.parent.parent) if venv else "",
                "config_origin": self._target.config_origin,
                "error": "" if venv else "找不到 venv，請指定正確的專案資料夾",
            }
        )
        return base

    def set_target(self, project_path: str) -> dict[str, object]:
        """
        Point the updater at another project folder (typed in the GUI).

        Returns the new target payload, or {"error": "..."} when the path is
        unusable - the previous target stays active in that case.
        """
        exe_dir = Path(sys.argv[0]).resolve().parent
        try:
            target = resolve_target(project_path, exe_dir, Path.cwd())
        except TargetError as exc:
            self._push_log("error", f"目標設定失敗: {exc}")
            return {"error": str(exc), "target": self.get_target()}

        self._apply_target(target)
        self._push_log("success", f"目標資料夾: {target.describe()}")
        return {"error": None, "target": self.get_target()}

    def choose_target_folder(self) -> dict[str, object]:
        """
        Open a native folder dialog and switch the target to the choice.

        Returns {"cancelled": True} when the dialog is dismissed or the backend
        has no folder dialog support; the caller then falls back to typing a path.
        """
        start_dir = ""
        if self._target is not None:
            start_dir = str(self._target.project_root)
        try:
            result = webview.create_file_dialog(
                webview.FOLDER_DIALOG, directory=start_dir
            )
        except Exception as exc:
            self._push_log("debug", f"Folder dialog unavailable: {exc}")
            return {"cancelled": True, "reason": str(exc), "target": self.get_target()}

        if not result:
            return {"cancelled": True, "target": self.get_target()}
        chosen = result[0] if isinstance(result, (list, tuple)) else result
        return self.set_target(str(chosen))

    def _run_with_lock(self, target_func: Callable[[], None]) -> None:
        """Spawn a daemon thread that runs target_func with lock management."""

        def safe_wrapper() -> None:
            # Wait for previous operations (like scanning) to release the lock
            self._update_lock.acquire(blocking=True)
            try:
                target_func()
            finally:
                self._update_lock.release()

        threading.Thread(target=safe_wrapper, daemon=True).start()

    def _should_auto_launch(self, do_launch: bool) -> bool:
        """Check if automatic launch should occur after update."""
        has_auto_launch = (
            self._config.launcher.auto_launch
            or self._config.launcher.auto_launch_enable
        )
        is_enabled = (
            self._config.launcher.enabled or self._config.launcher.auto_launch_enable
        )
        has_executable = bool(self._config.launcher.executable)
        return has_auto_launch and is_enabled and has_executable and do_launch


    def _serialize_packages(self, statuses: list[PackageStatus]) -> None:
        """Convert package statuses to JSON-friendly format and push to frontend."""
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
            "auto_launch_enable": self._config.launcher.auto_launch_enable,
            "auto_update_enable": self._config.launcher.auto_update_enable,
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
                "status": STATUS_UP_TO_DATE if ver else STATUS_NOT_INSTALLED,
            }
            for pkg, ver in installed.items()
        ]

    def get_versions(self, package_name: str) -> list[str]:
        """
        Get all available versions for a package from the source directory.

        Args:
            package_name: Package name (e.g., "test-matrix")

        Returns:
            List of version strings sorted newest-first
        """
        versions = get_all_versions(package_name, self._source_path())
        return versions

    def check_for_updates(self) -> None:
        self._run_with_lock(self._do_scan)

    def _do_scan(self) -> None:
        if self._config.parse_error and not self._config_error_logged:
            self._config_error_logged = True
            self._push_log("error", self._config.parse_error)
        if self._python_exe is None:
            self._push_log(
                "error",
                "找不到 venv：請在上方「目標資料夾」指定專案，或用 "
                "updater_gui.exe --project <專案資料夾> 啟動",
            )
            return

        if self._auto_update_disabled:
            self._push_log(
                "info",
                "Auto-update disabled for this session (older version installed) — scan continues",
            )

        self._push_log("info", f"Test Matrix Updater GUI (v{get_version()})")
        print(f"[DEBUG] Starting scan. Source: {self._config.source}")
        available = scan_packages(self._source_path())
        print(f"[DEBUG] Available packages in source: {list(available.keys())}")

        installed_versions = get_installed_versions_batch(
            self._python_exe, self._config.packages
        )
        statuses = check_updates(self._config.packages, installed_versions, available)

        self._serialize_packages(statuses)

        updatable = [s.name for s in statuses if s.status in UPDATABLE_STATUSES]
        print(f"[DEBUG] Updatable packages found: {updatable}")

        has_updates = len(updatable) > 0
        if self._window:
            print(
                f"[DEBUG] Calling window.onScanComplete({has_updates}, "
                f"autoUpdateDisabled={self._auto_update_disabled})"
            )
            self._window.evaluate_js(
                f"window.onScanComplete("
                f"{json.dumps(has_updates)}, "
                f"{json.dumps(self._auto_update_disabled)})"
            )

    def run_update(self) -> None:
        self._run_with_lock(self._do_update)

    def _do_update(self) -> None:
        if self._python_exe is None:
            self._push_log("error", "No venv Python found")
            return

        print("[DEBUG] Starting update process (_do_update)...")
        self._push_log("info", f"Scanning source: {self._config.source}")
        available = scan_packages(self._source_path())

        if not available:
            print("[DEBUG] Update failed: No whl files found")
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
        statuses = check_updates(self._config.packages, installed_versions, available)

        self._serialize_packages(statuses)

        to_update = [s for s in statuses if s.status in UPDATABLE_STATUSES]
        self._push_log("info", f"{len(to_update)} package(s) to update")

        result = install_updates(statuses, self._python_exe, on_progress=self._push_log)

        # Refresh package statuses to reflect updates in GUI
        available_now = scan_packages(self._source_path())
        installed_now = get_installed_versions_batch(
            self._python_exe, self._config.packages
        )
        statuses_now = check_updates(
            self._config.packages, installed_now, available_now
        )
        self._serialize_packages(statuses_now)

        # Regular update always installs the latest — re-enable auto-update.
        self._auto_update_disabled = False
        print("[DEBUG] _do_update complete — auto_update_disabled reset to False")

        do_launch = should_launch(self._config.launcher.mode, result)
        should_launch_final = (
            do_launch
            and (
                self._config.launcher.enabled
                or self._config.launcher.auto_launch_enable
            )
            and bool(self._config.launcher.executable)
        )
        summary = json.dumps(
            {
                "total": result.total,
                "updated": result.updated,
                "failed": result.failed,
                "should_launch": should_launch_final,
            }
        )
        if self._window:
            self._window.evaluate_js(f"window.onUpdateComplete({summary})")

        if self._should_auto_launch(do_launch):
            self._push_log("info", "Auto-launching application...")
            self._do_launch()

    def install_versioned_package(
        self, package_name: str, version: str
    ) -> dict[str, object]:
        """
        Install a specific version of a package, disabling auto-update for the session.

        Sets _auto_update_disabled to True so subsequent scan cycles do not overwrite
        the pinned version.  The actual installation runs on a background thread via
        _run_with_lock (mirrors the run_update pattern).

        Args:
            package_name: The package to install (e.g., "test-matrix").
            version: The exact version string to install (e.g., "1.4.2").

        Returns:
            {"success": True, "error": None} when the background job starts, or
            {"success": False, "error": "<reason>"} for immediate validation failures.
        """
        if self._python_exe is None:
            return {"success": False, "error": "No venv Python found"}

        # Only suppress auto-update when installing an older (non-latest) version.
        all_versions = get_all_versions(package_name, self._source_path())
        is_downgrade = bool(all_versions) and Version(version) < Version(all_versions[0])
        print(
            f"[DEBUG] install_versioned_package: version={version}, "
            f"latest={all_versions[0] if all_versions else 'n/a'}, "
            f"is_downgrade={is_downgrade}"
        )
        if is_downgrade:
            self._auto_update_disabled = True
            self._push_log(
                "info",
                f"Auto-update disabled for this session (downgrade to {version})",
            )
        else:
            self._auto_update_disabled = False
            self._push_log("info", f"Installing {package_name}=={version} (latest)")

        def _do_install() -> None:
            if self._python_exe is None:
                self._push_log("error", "No venv Python found")
                return

            self._push_log("info", f"Installing {package_name}=={version}...")

            # Build a PackageStatus for the target package so install_updates
            # knows what to operate on.  We scan for the current installed version
            # to populate the status faithfully.
            available = scan_packages(self._source_path())
            installed_versions = get_installed_versions_batch(
                self._python_exe, self._config.packages
            )
            statuses = check_updates(
                self._config.packages, installed_versions, available
            )

            # Find the matching status; fall back to a synthetic entry if the
            # package is somehow not listed in config packages.
            target_statuses = [s for s in statuses if s.name == package_name]
            if not target_statuses:
                self._push_log(
                    "debug",
                    f"{package_name}: not found in config packages, using synthetic status",
                )
                target_statuses = [
                    PackageStatus(
                        name=package_name,
                        installed=installed_versions.get(package_name),
                        available=version,
                        status=STATUS_UPDATE_AVAILABLE,
                    )
                ]

            for s in target_statuses:
                self._push_log(
                    "debug",
                    f"{s.name}: current status={s.status}, installed={s.installed}, target={version}",
                )

            result = install_updates(
                target_statuses,
                self._python_exe,
                on_progress=self._push_log,
                target_version=version,
                source_path=self._source_path(),
            )

            # Refresh package status in the GUI after installation
            available_now = scan_packages(self._source_path())
            installed_now = get_installed_versions_batch(
                self._python_exe, self._config.packages
            )
            statuses_now = check_updates(
                self._config.packages, installed_now, available_now
            )
            self._serialize_packages(statuses_now)

            summary = {
                "total": result.total,
                "updated": result.updated,
                "failed": result.failed,
                "success": result.all_success,
            }
            if self._window:
                self._window.evaluate_js(
                    f"window.onVersionedInstallComplete({json.dumps(summary)})"
                )

        self._run_with_lock(_do_install)
        return {"success": True, "error": None}

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
    # Enable DPI awareness (Level 2: Per Monitor DPI Aware)
    if sys.platform == "win32":
        import ctypes

        try:
            # Try SetProcessDpiAwareness (Level 2)
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    parser = argparse.ArgumentParser(description="Test Matrix Updater GUI")
    parser.add_argument("--dev", action="store_true", help="Load from Vite dev server")
    parser.add_argument(
        "--project",
        default=None,
        help="Folder to update (its venv and updater.toml).  The exe itself "
        "may live anywhere; the GUI can also switch folders at runtime.",
    )
    args = parser.parse_args()

    # sys.argv[0] is the exe (frozen) or this script (dev); its parent is the
    # directory the legacy find_config()/find_venv_python() anchored on.
    exe_dir = Path(sys.argv[0]).resolve().parent
    try:
        target = resolve_target(args.project, exe_dir, Path.cwd())
    except TargetError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)

    print(f"[DEBUG] {target.describe()}")
    api = Api(target.config, target.python_exe, target)

    if args.dev:
        url = "http://localhost:15173"
    else:
        frontend_dist = Path(__file__).parent / "frontend" / "dist" / "index.html"
        if not frontend_dist.exists():
            print(
                "[ERROR] Frontend not built. Run: "
                f"cd {frontend_dist.parent.parent} && npm run build"
            )
            sys.exit(1)
        url = str(frontend_dist)

    # Determine window height and position based on screen resolution
    # (70% of screen height)
    try:
        screens = webview.screens
        if screens:
            screen = screens[0]
            # Use 70% of screen height, but keep it within reasonable bounds
            calculated_height = int(screen.height * 0.7)
            target_height = max(500, min(1000, calculated_height))

            # Position: Top = 3% of screen height, Horizontal = Center
            window_width = 900
            start_x = max(0, int((screen.width - window_width) / 2))
            start_y = int(screen.height * 0.03)
        else:
            screen = None
            target_height = 700
            start_x = None
            start_y = None
    except Exception:
        screen = None
        target_height = 700
        start_x = None
        start_y = None

    if screen:
        print(
            f"[DEBUG] Screen: {screen.width}x{screen.height}, "
            f"Target Height: {target_height}, Position: ({start_x}, {start_y})"
        )
    else:
        print(f"[DEBUG] Calculated window height: {target_height}")

    window = webview.create_window(
        "Test Matrix Updater",
        url=url,
        js_api=api,
        width=900,
        height=target_height,
        x=start_x,
        y=start_y,
        min_size=(700, 400),
    )
    assert window is not None, "webview.create_window returned None"
    api._set_window(window)

    webview.start()


if __name__ == "__main__":
    main()
