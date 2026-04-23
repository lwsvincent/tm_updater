from __future__ import annotations

import argparse
import json
import sys
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import webview

from updater.config import UpdaterConfig, find_config, load_config
from updater.core import (
    STATUS_NOT_INSTALLED,
    STATUS_UP_TO_DATE,
    STATUS_UPDATE_AVAILABLE,
    UPDATABLE_STATUSES,
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
        self._update_lock = threading.Lock()

    def _set_window(self, window: webview.Window) -> None:
        self._window = window

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
            self._config.launcher.enabled
            or self._config.launcher.auto_launch_enable
        )
        has_executable = bool(self._config.launcher.executable)
        return has_auto_launch and is_enabled and has_executable and do_launch

    def _serialize_packages(self, statuses: list) -> None:
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

    def check_for_updates(self) -> None:
        self._run_with_lock(self._do_scan)

    def _do_scan(self) -> None:
        if self._python_exe is None:
            self._push_log("error", "No venv Python found")
            return

        print(f"[DEBUG] Starting scan. Source: {self._config.source}")
        available = scan_packages(Path(self._config.source))
        print(f"[DEBUG] Available packages in source: {list(available.keys())}")
        
        installed_versions = get_installed_versions_batch(
            self._python_exe, self._config.packages
        )
        statuses = check_updates(
            self._config.packages, installed_versions, available
        )

        self._serialize_packages(statuses)

        updatable = [s.name for s in statuses if s.status in UPDATABLE_STATUSES]
        print(f"[DEBUG] Updatable packages found: {updatable}")
        
        has_updates = len(updatable) > 0
        if self._window:
            print(f"[DEBUG] Calling window.onScanComplete({has_updates})")
            self._window.evaluate_js(f"window.onScanComplete({json.dumps(has_updates)})")

    def run_update(self) -> None:
        self._run_with_lock(self._do_update)

    def _do_update(self) -> None:
        if self._python_exe is None:
            self._push_log("error", "No venv Python found")
            return

        print(f"[DEBUG] Starting update process (_do_update)...")
        self._push_log("info", f"Scanning source: {self._config.source}")
        available = scan_packages(Path(self._config.source))

        if not available:
            print(f"[DEBUG] Update failed: No whl files found")
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

        self._serialize_packages(statuses)

        to_update = [
            s for s in statuses if s.status in UPDATABLE_STATUSES
        ]
        self._push_log("info", f"{len(to_update)} package(s) to update")

        result = install_updates(statuses, self._python_exe, on_progress=self._push_log)

        # Refresh package statuses to reflect updates in GUI
        available_now = scan_packages(Path(self._config.source))
        installed_now = get_installed_versions_batch(
            self._python_exe, self._config.packages
        )
        statuses_now = check_updates(
            self._config.packages, installed_now, available_now
        )
        self._serialize_packages(statuses_now)

        do_launch = should_launch(self._config.launcher.mode, result)
        should_launch_final = (
            do_launch
            and (self._config.launcher.enabled or self._config.launcher.auto_launch_enable)
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

    webview.start()


if __name__ == "__main__":
    main()
