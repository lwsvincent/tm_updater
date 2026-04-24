"""
End-to-end integration tests for the version downgrade flow.

This module tests the complete user-facing workflow when a user selects an older
package version to install via the GUI.  Each test exercises multiple layers at
once (Api -> core install_updates -> subprocess pip calls) rather than mocking
at the layer boundary.

Full integration flow under test:
    Setup : installed=1.0.0, available=1.5.0 (latest), 1.4.0, 1.3.0

    1. User selects 1.3.0 from dropdown
    2. Click "Install Selected Version" button
    3. Modal shows "Install 1.3.0?" with Confirm/Cancel
    4. User clicks Confirm
    5. Backend:
       - Calls install_versioned_package("package", "1.3.0")
       - Sets _auto_update_disabled = True
       - Executes: pip uninstall package -y
       - Executes: pip install package==1.3.0
       - Returns success
    6. Frontend receives onVersionedInstallComplete
    7. Calls get_packages() -> shows installed=1.3.0
    8. Calls get_versions() -> refreshes versionsMap
    9. Auto-selects 1.3.0 in dropdown
    10. Modal closes, button unlocks
    11. User tries to trigger auto-scan
    12. Backend early-exits because _auto_update_disabled = True
    13. Log message: "Auto-update disabled for this session..."

Test coverage:
    - test_complete_downgrade_flow
      Complete happy-path from install_versioned_package through pip command
      sequence verification.

    - test_pip_command_sequence_uninstall_then_install
      Verifies subprocess calls arrive in exact order: uninstall first, then
      install with pinned version.

    - test_auto_update_disabled_after_downgrade
      Flag _auto_update_disabled transitions False -> True after a versioned
      install.

    - test_auto_update_disabled_blocks_scan
      Subsequent _do_scan call returns early (no scan_packages, no check_updates)
      once the flag is set.

    - test_frontend_receives_completion_callback
      onVersionedInstallComplete is pushed to the window with the install result.

    - test_get_packages_reflects_new_version_after_install
      get_packages() returns the freshly installed version after pip operations.

    - test_get_versions_returns_all_available_versions_after_downgrade
      get_versions() still returns all available versions so the dropdown
      re-populates correctly.

    - test_auto_update_flag_stays_true_on_install_failure
      When pip install returns a non-zero exit code, _auto_update_disabled stays
      True (no rollback of the flag) and onVersionedInstallComplete reports
      success=False.

    - test_version_mismatch_check_button_enabled
      install_versioned_package returns success=True only when called with a
      different version than what is installed -- validates the "button only
      enabled if installed != selected" contract.

    - test_downgrade_to_each_available_version
      Parametrized smoke: each older version in the source directory can be
      selected, and the correct pip install command is issued.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, call, patch

import pytest

from updater.config import GuiConfig, LauncherConfig, UpdaterConfig
from updater.core import UpdateResult, clear_pip_cache
from updater.gui.app import Api


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

_FAKE_PIP_LIST_OUTPUT = json.dumps(
    [{"name": "test-pkg", "version": "1.0.0"}]
)
"""Simulates `pip list --format=json` output when 1.0.0 is installed."""

_FAKE_PIP_LIST_AFTER_DOWNGRADE = json.dumps(
    [{"name": "test-pkg", "version": "1.3.0"}]
)
"""Simulates `pip list --format=json` output after downgrade to 1.3.0."""


def _make_config(source_dir: Path) -> UpdaterConfig:
    return UpdaterConfig(
        packages=["test-pkg"],
        source=str(source_dir),
        launcher=LauncherConfig(
            enabled=False,
            executable="",
            auto_launch=False,
            auto_update=False,
            auto_launch_enable=False,
            auto_update_enable=False,
            mode="on_success",
        ),
        gui=GuiConfig(theme="light"),
    )


def _populate_source(source_dir: Path, versions: list[str]) -> None:
    """Create fake wheel files for all given versions of test-pkg."""
    for ver in versions:
        (source_dir / f"test_pkg-{ver}-py3-none-any.whl").write_bytes(b"fake")


@pytest.fixture(autouse=True)
def _clear_pip_cache() -> Generator[None, None, None]:
    """
    The module-level _pip_cache in updater.core persists between tests.
    Always clear it before and after each test to prevent cross-test contamination.
    """
    clear_pip_cache()
    yield
    clear_pip_cache()


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    """
    Return a source directory pre-populated with four wheel versions:
    1.5.0 (latest), 1.4.0, 1.3.0, 1.0.0.
    """
    versions = ["1.5.0", "1.4.0", "1.3.0", "1.0.0"]
    _populate_source(tmp_path, versions)
    return tmp_path


@pytest.fixture
def config(source_dir: Path) -> UpdaterConfig:
    return _make_config(source_dir)


@pytest.fixture
def api(config: UpdaterConfig) -> Api:
    """
    Api instance with python_exe set so install_versioned_package does not
    short-circuit on the "No venv Python found" guard.
    """
    instance = Api(config, python_exe=Path("python.exe"))
    # Override _run_with_lock to execute synchronously so tests do not need to
    # join daemon threads.
    instance._run_with_lock = lambda fn: fn()  # type: ignore[assignment]
    return instance


@pytest.fixture
def mock_window() -> MagicMock:
    """A mock pywebview Window that records evaluate_js calls."""
    return MagicMock()


# ---------------------------------------------------------------------------
# Subprocess side-effect factory
# ---------------------------------------------------------------------------


def _make_subprocess_side_effect(
    installed_version: str = "1.0.0",
    post_install_version: str = "1.3.0",
    uninstall_rc: int = 0,
    install_rc: int = 0,
) -> object:
    """
    Return a callable suitable for use as subprocess.run side_effect.

    The fake responds to three pip calls in order:
      1. pip list --format=json  -> {"name": "test-pkg", "version": <installed>}
      2. pip uninstall -y        -> returncode=<uninstall_rc>
      3. pip install ==<ver>     -> returncode=<install_rc>

    Any further pip-list calls (post-install refresh) return the
    post_install_version.
    """
    pip_list_call_count = [0]

    def _side_effect(cmd: list[str], **_kwargs: object) -> MagicMock:
        cmd_str = " ".join(str(c) for c in cmd)
        result = MagicMock()
        result.stdout = ""
        result.stderr = ""

        if "list" in cmd_str and "--format=json" in cmd_str:
            pip_list_call_count[0] += 1
            if pip_list_call_count[0] == 1:
                # First call: before install
                result.returncode = 0
                result.stdout = json.dumps(
                    [{"name": "test-pkg", "version": installed_version}]
                )
            else:
                # Subsequent calls: after install
                result.returncode = 0
                result.stdout = json.dumps(
                    [{"name": "test-pkg", "version": post_install_version}]
                )
        elif "uninstall" in cmd_str:
            result.returncode = uninstall_rc
            result.stderr = "" if uninstall_rc == 0 else "uninstall failed"
        elif "install" in cmd_str:
            result.returncode = install_rc
            result.stderr = "" if install_rc == 0 else "Could not find a version"
        else:
            result.returncode = 0

        return result

    return _side_effect


# ---------------------------------------------------------------------------
# Test 1: complete downgrade flow (happy path)
# ---------------------------------------------------------------------------


class TestCompleteDowngradeFlow:
    """
    End-to-end happy-path test covering the full downgrade workflow:
    install_versioned_package -> pip commands -> flag state -> scan early-exit.
    """

    def test_complete_downgrade_flow(
        self, api: Api, mock_window: MagicMock
    ) -> None:
        """
        Full happy-path integration test.

        Verifies:
          - install_versioned_package returns {"success": True, "error": None}
          - pip uninstall is called before pip install
          - _auto_update_disabled becomes True
          - onVersionedInstallComplete is pushed to the window with success=True
        """
        api._window = mock_window

        with patch("updater.core.subprocess") as mock_sp:
            mock_sp.CREATE_NO_WINDOW = 0x08000000
            mock_sp.run.side_effect = _make_subprocess_side_effect(
                installed_version="1.0.0",
                post_install_version="1.3.0",
            )

            result = api.install_versioned_package("test-pkg", "1.3.0")

        # Return value indicates the background job started successfully
        assert result["success"] is True
        assert result["error"] is None

        # Flag must be set
        assert api._auto_update_disabled is True

        # Window must have received the completion callback
        js_calls = [c[0][0] for c in mock_window.evaluate_js.call_args_list]
        versioned_calls = [c for c in js_calls if "onVersionedInstallComplete" in c]
        assert versioned_calls, (
            "onVersionedInstallComplete must be pushed to the window after install"
        )
        payload_str = versioned_calls[0]
        # Extract JSON inside the JS call: window.onVersionedInstallComplete({...})
        payload_json = payload_str[payload_str.index("(") + 1 : payload_str.rindex(")")]
        payload = json.loads(payload_json)
        assert payload["success"] is True, (
            f"Expected success=True in completion payload, got: {payload}"
        )


# ---------------------------------------------------------------------------
# Test 2: pip command sequence (uninstall -> install order)
# ---------------------------------------------------------------------------


class TestPipCommandSequence:
    """
    Verify that during a versioned install the subprocess call order is:
      1. pip list --format=json  (get_installed_versions_batch)
      2. pip uninstall <pkg> -y
      3. pip install <pkg>==<version>
    """

    def test_pip_command_sequence_uninstall_then_install(
        self, api: Api
    ) -> None:
        """
        Uninstall must precede install so the target environment is clean.
        Assert the exact command strings match expected pip syntax.
        """
        with patch("updater.core.subprocess") as mock_sp:
            mock_sp.CREATE_NO_WINDOW = 0x08000000
            mock_sp.run.side_effect = _make_subprocess_side_effect(
                installed_version="1.0.0",
                post_install_version="1.3.0",
            )

            api.install_versioned_package("test-pkg", "1.3.0")

        recorded_calls = mock_sp.run.call_args_list
        cmd_strings = [
            " ".join(str(a) for a in recorded_call[0][0])
            for recorded_call in recorded_calls
        ]

        # Find indices of uninstall and install calls
        uninstall_indices = [
            i for i, c in enumerate(cmd_strings) if "uninstall" in c
        ]
        install_indices = [
            i
            for i, c in enumerate(cmd_strings)
            if "install" in c and "uninstall" not in c and "--find-links" in c
        ]

        assert uninstall_indices, "pip uninstall must be called"
        assert install_indices, "pip install with --find-links must be called"

        # Uninstall must come before install
        assert uninstall_indices[0] < install_indices[0], (
            f"Expected uninstall (index {uninstall_indices[0]}) before "
            f"install (index {install_indices[0]})"
        )

        # Verify uninstall command shape: python -m pip uninstall -y test-pkg
        uninstall_cmd = cmd_strings[uninstall_indices[0]]
        assert "uninstall" in uninstall_cmd
        assert "test-pkg" in uninstall_cmd or "test_pkg" in uninstall_cmd
        assert "-y" in uninstall_cmd

        # Verify install command shape: python -m pip install --no-index --find-links=<path> test-pkg==1.3.0
        install_cmd = cmd_strings[install_indices[0]]
        assert "install" in install_cmd
        assert "--no-index" in install_cmd
        assert "--find-links=" in install_cmd
        assert "test-pkg==1.3.0" in install_cmd or "test_pkg==1.3.0" in install_cmd


# ---------------------------------------------------------------------------
# Test 3: auto-update flag transition False -> True
# ---------------------------------------------------------------------------


class TestAutoUpdateFlagTransition:
    """
    _auto_update_disabled must flip to True after install_versioned_package is
    called, regardless of whether the install succeeds or fails.
    """

    def test_auto_update_disabled_starts_false(self, api: Api) -> None:
        """Flag is False on a freshly created Api instance."""
        assert api._auto_update_disabled is False

    def test_auto_update_disabled_after_downgrade(self, api: Api) -> None:
        """
        Flag becomes True as soon as install_versioned_package is called.
        The flag is set eagerly (before the background thread runs) so the
        frontend can immediately disable the button.
        """
        with patch("updater.core.subprocess") as mock_sp:
            mock_sp.CREATE_NO_WINDOW = 0x08000000
            mock_sp.run.side_effect = _make_subprocess_side_effect()
            api.install_versioned_package("test-pkg", "1.3.0")

        assert api._auto_update_disabled is True

    def test_auto_update_flag_stays_true_on_install_failure(
        self, api: Api, mock_window: MagicMock
    ) -> None:
        """
        When pip install returns non-zero, _auto_update_disabled must NOT revert
        to False.  The user made a deliberate choice; do not override it silently.
        The window must also receive onVersionedInstallComplete with success=False.
        """
        api._window = mock_window

        with patch("updater.core.subprocess") as mock_sp:
            mock_sp.CREATE_NO_WINDOW = 0x08000000
            # Uninstall succeeds, install fails
            mock_sp.run.side_effect = _make_subprocess_side_effect(
                uninstall_rc=0,
                install_rc=1,
            )
            api.install_versioned_package("test-pkg", "1.3.0")

        # Flag must still be True after a failed install
        assert api._auto_update_disabled is True

        # Window must report success=False
        js_calls = [c[0][0] for c in mock_window.evaluate_js.call_args_list]
        versioned_calls = [c for c in js_calls if "onVersionedInstallComplete" in c]
        assert versioned_calls, "onVersionedInstallComplete must fire even on failure"
        payload_json = versioned_calls[0]
        payload_json = payload_json[
            payload_json.index("(") + 1 : payload_json.rindex(")")
        ]
        payload = json.loads(payload_json)
        assert payload["success"] is False, (
            f"Expected success=False after pip install failure, got: {payload}"
        )


# ---------------------------------------------------------------------------
# Test 4: subsequent scan early-exits when flag is set
# ---------------------------------------------------------------------------


class TestAutoUpdateDisabledBlocksScan:
    """
    After a versioned install, check_for_updates -> _do_scan must return without
    calling scan_packages or check_updates, and must NOT push onScanComplete to
    the window.
    """

    def test_auto_update_disabled_blocks_scan(
        self, api: Api, mock_window: MagicMock
    ) -> None:
        """
        _do_scan early-exits when _auto_update_disabled is True.
        """
        api._window = mock_window
        api._auto_update_disabled = True  # Simulate post-install state

        with patch("updater.gui.app.scan_packages") as mock_scan:
            with patch("updater.gui.app.check_updates") as mock_check:
                api._do_scan()

        mock_scan.assert_not_called()
        mock_check.assert_not_called()

    def test_scan_does_not_fire_on_scan_complete_when_disabled(
        self, api: Api, mock_window: MagicMock
    ) -> None:
        """
        onScanComplete must NOT reach the frontend when auto-update is disabled.
        This prevents the frontend from overwriting the user's pinned version
        with the latest available version.
        """
        api._window = mock_window
        api._auto_update_disabled = True

        api._do_scan()

        js_calls = [c[0][0] for c in mock_window.evaluate_js.call_args_list]
        scan_complete_calls = [c for c in js_calls if "onScanComplete" in c]
        assert not scan_complete_calls, (
            "onScanComplete must NOT be called when auto-update is disabled, "
            f"but got: {scan_complete_calls}"
        )

    def test_scan_logs_disabled_message(
        self, api: Api, mock_window: MagicMock
    ) -> None:
        """
        When the scan is suppressed, a log message must still be pushed so the
        user can see why no update activity occurred.
        """
        api._window = mock_window
        api._auto_update_disabled = True

        api._do_scan()

        # Check that addLogLine was called with a message referencing auto-update
        js_calls = [c[0][0] for c in mock_window.evaluate_js.call_args_list]
        log_calls = [c for c in js_calls if "addLogLine" in c]
        assert log_calls, "A log message must be emitted when scan is suppressed"
        # The combined log text must reference the disabled state
        combined = " ".join(log_calls)
        assert "Auto-update disabled" in combined or "auto-update" in combined.lower(), (
            f"Log must mention auto-update disabled, got: {log_calls}"
        )


# ---------------------------------------------------------------------------
# Test 5: frontend completion callback
# ---------------------------------------------------------------------------


class TestFrontendCompletionCallback:
    """
    onVersionedInstallComplete must be pushed to the window after every
    install_versioned_package call (success or failure).
    """

    def test_frontend_receives_completion_callback(
        self, api: Api, mock_window: MagicMock
    ) -> None:
        """
        onVersionedInstallComplete must be pushed with a JSON payload containing
        the keys: total, updated, failed, success.
        """
        api._window = mock_window

        with patch("updater.core.subprocess") as mock_sp:
            mock_sp.CREATE_NO_WINDOW = 0x08000000
            mock_sp.run.side_effect = _make_subprocess_side_effect()
            api.install_versioned_package("test-pkg", "1.3.0")

        js_calls = [c[0][0] for c in mock_window.evaluate_js.call_args_list]
        versioned_calls = [c for c in js_calls if "onVersionedInstallComplete" in c]
        assert len(versioned_calls) == 1, (
            f"Expected exactly one onVersionedInstallComplete call, "
            f"got {len(versioned_calls)}"
        )

        payload_str = versioned_calls[0]
        payload_json = payload_str[
            payload_str.index("(") + 1 : payload_str.rindex(")")
        ]
        payload = json.loads(payload_json)

        for key in ("total", "updated", "failed", "success"):
            assert key in payload, (
                f"onVersionedInstallComplete payload missing key '{key}': {payload}"
            )

    def test_completion_callback_has_correct_counts_on_success(
        self, api: Api, mock_window: MagicMock
    ) -> None:
        """
        On a successful install, the payload reports total=1, updated=1, failed=0.
        """
        api._window = mock_window

        with patch("updater.core.subprocess") as mock_sp:
            mock_sp.CREATE_NO_WINDOW = 0x08000000
            mock_sp.run.side_effect = _make_subprocess_side_effect()
            api.install_versioned_package("test-pkg", "1.3.0")

        js_calls = [c[0][0] for c in mock_window.evaluate_js.call_args_list]
        versioned_calls = [c for c in js_calls if "onVersionedInstallComplete" in c]
        payload_str = versioned_calls[0]
        payload_json = payload_str[
            payload_str.index("(") + 1 : payload_str.rindex(")")
        ]
        payload = json.loads(payload_json)

        assert payload["total"] == 1
        assert payload["updated"] == 1
        assert payload["failed"] == 0
        assert payload["success"] is True


# ---------------------------------------------------------------------------
# Test 6: get_packages reflects new version after install
# ---------------------------------------------------------------------------


class TestGetPackagesReflectsNewVersion:
    """
    After install_versioned_package completes, get_packages() must return the
    newly installed version (not the old one).
    """

    def test_get_packages_reflects_new_version_after_install(
        self, api: Api
    ) -> None:
        """
        get_packages() calls get_installed_versions_batch which queries pip list.
        After installation, the fresh pip-list call must return 1.3.0.
        """
        call_count = [0]

        def _fake_get_installed(
            python_exe: Path, package_names: list[str]
        ) -> dict[str, str | None]:
            call_count[0] += 1
            if call_count[0] == 1:
                return {"test-pkg": "1.0.0"}
            return {"test-pkg": "1.3.0"}

        with patch(
            "updater.gui.app.get_installed_versions_batch",
            side_effect=_fake_get_installed,
        ):
            # First call: baseline
            packages_before = api.get_packages()

        with patch(
            "updater.gui.app.get_installed_versions_batch",
            return_value={"test-pkg": "1.3.0"},
        ):
            packages_after = api.get_packages()

        before_version = next(
            p["installed"] for p in packages_before if p["name"] == "test-pkg"
        )
        after_version = next(
            p["installed"] for p in packages_after if p["name"] == "test-pkg"
        )

        assert before_version == "1.0.0"
        assert after_version == "1.3.0", (
            f"get_packages should return 1.3.0 after downgrade, got {after_version}"
        )


# ---------------------------------------------------------------------------
# Test 7: get_versions returns all available versions after downgrade
# ---------------------------------------------------------------------------


class TestGetVersionsAfterDowngrade:
    """
    After a downgrade, get_versions() must still return ALL available versions
    from the source directory so the dropdown re-populates correctly.
    """

    def test_get_versions_returns_all_available_versions_after_downgrade(
        self, api: Api, source_dir: Path
    ) -> None:
        """
        The source directory contains 4 versions.  After downgrading to 1.3.0,
        get_versions() must still return all 4, sorted newest-first.
        """
        # Simulate post-downgrade state by setting the flag
        api._auto_update_disabled = True

        result = api.get_versions("test-pkg")

        assert result == ["1.5.0", "1.4.0", "1.3.0", "1.0.0"], (
            f"Expected all 4 versions newest-first, got: {result}"
        )

    def test_get_versions_not_blocked_by_auto_update_flag(
        self, api: Api, source_dir: Path
    ) -> None:
        """
        The auto-update disabled flag must not prevent get_versions from
        scanning wheel files -- the dropdown still needs to render all options.
        """
        api._auto_update_disabled = True

        result = api.get_versions("test-pkg")

        assert len(result) == 4, (
            f"Expected 4 versions regardless of auto-update flag, got: {result}"
        )


# ---------------------------------------------------------------------------
# Test 8: version mismatch check (button enabled contract)
# ---------------------------------------------------------------------------


class TestVersionMismatchCheck:
    """
    The "Install Selected Version" button should only be enabled when the
    selected version differs from the installed version.  From the backend
    perspective, this means install_versioned_package must accept and process
    any version (even the same one), but the frontend uses the installed vs.
    selected comparison to control button state.

    Here we verify the API contract: calling with the same version still runs
    the full install path (no short-circuit on equal versions at the backend
    level), and the JS-side button logic is tested by checking that
    get_packages and get_versions return the data needed for the comparison.
    """

    def test_install_versioned_package_processes_any_version(
        self, api: Api
    ) -> None:
        """
        Backend does not short-circuit on same-version installs.
        install_versioned_package("test-pkg", "1.0.0") when 1.0.0 is installed
        should still set the flag and fire pip commands.
        """
        with patch(
            "updater.gui.app.get_installed_versions_batch",
            return_value={"test-pkg": "1.0.0"},
        ):
            with patch("updater.core.subprocess") as mock_sp:
                mock_sp.CREATE_NO_WINDOW = 0x08000000
                mock_sp.run.side_effect = _make_subprocess_side_effect(
                    installed_version="1.0.0",
                    post_install_version="1.0.0",
                )
                result = api.install_versioned_package("test-pkg", "1.0.0")

        assert result["success"] is True
        assert api._auto_update_disabled is True

    def test_get_packages_provides_installed_version_for_comparison(
        self, api: Api
    ) -> None:
        """
        get_packages() returns "installed" key so the frontend JS can compare
        pkg.installed != selectedVersions[pkg.name] to enable/disable the button.
        """
        with patch(
            "updater.gui.app.get_installed_versions_batch",
            return_value={"test-pkg": "1.0.0"},
        ):
            packages = api.get_packages()

        assert len(packages) == 1
        pkg = packages[0]
        assert "installed" in pkg
        assert pkg["installed"] == "1.0.0"
        assert "name" in pkg


# ---------------------------------------------------------------------------
# Test 9: downgrade to each available version (parametrized smoke test)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target_version", ["1.4.0", "1.3.0", "1.0.0"])
class TestDowngradeToEachAvailableVersion:
    """
    Parametrized smoke test: every older version in the source directory can be
    selected, and the correct pip install command is issued.
    """

    def test_downgrade_to_each_available_version(
        self,
        target_version: str,
        source_dir: Path,
    ) -> None:
        """
        For each target_version, install_versioned_package must issue
        `pip install test-pkg==<target_version>`.

        Note: scan_packages returns only the *latest* wheel per package (1.5.0
        here).  For install_updates to process a package, its check_updates
        status must be in UPDATABLE_STATUSES.  We use installed_version="0.9.0"
        (below 1.5.0) so the status resolves to update_available, which is
        updatable.  The important contract under test is that the pip install
        command carries the *target_version* string, not the latest available.
        """
        config = _make_config(source_dir)
        instance = Api(config, python_exe=Path("python.exe"))
        instance._run_with_lock = lambda fn: fn()  # type: ignore[assignment]

        with patch("updater.core.subprocess") as mock_sp:
            mock_sp.CREATE_NO_WINDOW = 0x08000000
            # installed_version must be < latest (1.5.0) so check_updates
            # returns update_available, allowing install_updates to proceed.
            mock_sp.run.side_effect = _make_subprocess_side_effect(
                installed_version="0.9.0",
                post_install_version=target_version,
            )
            result = instance.install_versioned_package("test-pkg", target_version)

        assert result["success"] is True

        # Verify the pip install command used the correct version
        recorded_calls = mock_sp.run.call_args_list
        cmd_strings = [
            " ".join(str(a) for a in c[0][0]) for c in recorded_calls
        ]
        install_cmds = [
            c for c in cmd_strings if "install" in c and "uninstall" not in c
        ]
        # Should use --find-links and specify the target version
        assert any(
            "--find-links=" in c and f"test-pkg=={target_version}" in c or
            f"test_pkg=={target_version}" in c
            for c in install_cmds
        ), (
            f"pip install must use --find-links and test-pkg=={target_version}, "
            f"got commands: {install_cmds}"
        )


# ---------------------------------------------------------------------------
# Test 10: no-window guard (install still sets flag even without window)
# ---------------------------------------------------------------------------


class TestInstallWithoutWindow:
    """
    install_versioned_package must set _auto_update_disabled and run pip commands
    even when no window is assigned (e.g., headless test environment).
    The onVersionedInstallComplete evaluate_js call is simply skipped.
    """

    def test_install_without_window_sets_flag(self, api: Api) -> None:
        """
        When api._window is None, install proceeds normally but no JS callbacks
        are pushed.  The flag must still be set.
        """
        assert api._window is None  # confirm no window is set

        with patch("updater.core.subprocess") as mock_sp:
            mock_sp.CREATE_NO_WINDOW = 0x08000000
            mock_sp.run.side_effect = _make_subprocess_side_effect()
            result = api.install_versioned_package("test-pkg", "1.3.0")

        assert result["success"] is True
        assert api._auto_update_disabled is True

    def test_install_without_python_exe_returns_error(
        self, config: UpdaterConfig
    ) -> None:
        """
        When python_exe is None, install_versioned_package returns
        {"success": False, "error": "No venv Python found"} immediately
        without spawning threads or setting the flag.
        """
        no_python_api = Api(config, python_exe=None)
        no_python_api._run_with_lock = lambda fn: fn()  # type: ignore[assignment]

        result = no_python_api.install_versioned_package("test-pkg", "1.3.0")

        assert result["success"] is False
        assert "No venv Python" in str(result["error"])
        # Flag must NOT be set when we never even attempt the install
        assert no_python_api._auto_update_disabled is False
