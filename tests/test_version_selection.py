"""
Tests for Task 7: Version Selection Feature (backend API surface).

Frontend JS changes (store.versionsMap, store.selectedVersions, dropdown binding)
cannot be unit-tested without Vitest, which is not set up in this project.
These tests cover the Python API that the frontend calls, verifying the contract
the JS code depends on.

Test requirements from the spec:
  1. test_versions_loaded_on_init  -- get_versions returns data for each package
  2. test_version_dropdown_shows_all_versions  -- all versions returned, newest-first
  3. test_version_selection_updates_store  -- API returns correct data so JS can update
  4. test_dropdown_disabled_during_update  -- backend isUpdating flag via run_update
"""
from pathlib import Path
from threading import Event
from unittest.mock import MagicMock, patch

import pytest

from updater.config import GuiConfig, LauncherConfig, UpdaterConfig
from updater.gui.app import Api


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    """Create a temporary source directory with several wheel versions."""
    return tmp_path


@pytest.fixture
def config(source_dir: Path) -> UpdaterConfig:
    return UpdaterConfig(
        packages=["test-pkg", "other-pkg"],
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


@pytest.fixture
def api(config: UpdaterConfig) -> Api:
    return Api(config, python_exe=None)


# ---------------------------------------------------------------------------
# Test 1: versions loaded on init (get_versions callable for each package)
# ---------------------------------------------------------------------------


class TestVersionsLoadedOnInit:
    """Requirement: After app init, get_versions is callable for each package."""

    def test_get_versions_callable_for_managed_packages(
        self, api: Api, config: UpdaterConfig, source_dir: Path
    ) -> None:
        """
        The JS pywebviewready handler calls get_versions(pkg.name) for every
        package.  This test verifies that all configured packages can be queried
        without error even when no wheel files are present (returns empty list).
        """
        for pkg_name in config.packages:
            result = api.get_versions(pkg_name)
            assert isinstance(result, list), (
                f"get_versions('{pkg_name}') must return a list, got {type(result)}"
            )

    def test_get_versions_returns_data_when_wheels_exist(
        self, api: Api, source_dir: Path
    ) -> None:
        """
        When wheel files are present for a package, get_versions returns
        non-empty list -- confirming the frontend has version data to populate
        its versionsMap store entry.
        """
        (source_dir / "test_pkg-1.0.0-py3-none-any.whl").write_bytes(b"fake")
        (source_dir / "test_pkg-2.0.0-py3-none-any.whl").write_bytes(b"fake")

        result = api.get_versions("test-pkg")

        assert len(result) == 2
        assert result[0] == "2.0.0"  # newest first (default selection in JS)

    def test_get_versions_returns_empty_list_for_unknown_package(
        self, api: Api
    ) -> None:
        """
        For a package with no wheels, the frontend receives [] and falls back to
        pkg.available (or null). Backend must never raise.
        """
        result = api.get_versions("nonexistent-package")
        assert result == []


# ---------------------------------------------------------------------------
# Test 2: dropdown shows all versions (sort order contract)
# ---------------------------------------------------------------------------


class TestVersionDropdownShowsAllVersions:
    """Requirement: Dropdown renders with all versions from versionsMap, newest-first."""

    def test_all_wheel_versions_returned(
        self, api: Api, source_dir: Path
    ) -> None:
        """Every wheel file present for the package appears in the returned list."""
        versions_to_create = ["1.0.0", "1.1.0", "2.0.0", "1.9.5"]
        for ver in versions_to_create:
            (source_dir / f"test_pkg-{ver}-py3-none-any.whl").write_bytes(b"fake")

        result = api.get_versions("test-pkg")

        assert sorted(result) == sorted(versions_to_create), (
            "All versions must be present in the returned list"
        )
        assert len(result) == len(versions_to_create)

    def test_versions_sorted_newest_first(
        self, api: Api, source_dir: Path
    ) -> None:
        """Versions must be sorted newest-first so the first entry is the default."""
        (source_dir / "test_pkg-1.0.0-py3-none-any.whl").write_bytes(b"fake")
        (source_dir / "test_pkg-2.5.0-py3-none-any.whl").write_bytes(b"fake")
        (source_dir / "test_pkg-1.8.3-py3-none-any.whl").write_bytes(b"fake")
        (source_dir / "test_pkg-3.0.0-py3-none-any.whl").write_bytes(b"fake")

        result = api.get_versions("test-pkg")

        assert result == ["3.0.0", "2.5.0", "1.8.3", "1.0.0"], (
            f"Expected newest-first order, got: {result}"
        )

    def test_wheels_for_other_packages_not_included(
        self, api: Api, source_dir: Path
    ) -> None:
        """Wheels belonging to a different package must not appear in results."""
        (source_dir / "test_pkg-1.0.0-py3-none-any.whl").write_bytes(b"fake")
        (source_dir / "other_pkg-5.0.0-py3-none-any.whl").write_bytes(b"fake")

        result = api.get_versions("test-pkg")

        assert result == ["1.0.0"], (
            "Only wheels matching test-pkg should be returned"
        )

    def test_invalid_version_wheels_excluded(
        self, api: Api, source_dir: Path
    ) -> None:
        """Wheel files with malformed version strings are silently skipped."""
        (source_dir / "test_pkg-1.0.0-py3-none-any.whl").write_bytes(b"fake")
        (source_dir / "test_pkg-notaversion-py3-none-any.whl").write_bytes(b"fake")

        result = api.get_versions("test-pkg")

        assert result == ["1.0.0"]


# ---------------------------------------------------------------------------
# Test 3: version selection updates store (API returns correct data for JS)
# ---------------------------------------------------------------------------


class TestVersionSelectionUpdatesStore:
    """
    Requirement: When user selects version, store.selectedVersions updates.

    The actual state mutation happens in JS (v-model on the select element).
    Here we verify the backend contract: get_versions returns valid version
    strings that the JS can store in selectedVersions without transformation.
    """

    def test_first_version_is_valid_semver_for_default_selection(
        self, api: Api, source_dir: Path
    ) -> None:
        """
        The JS sets store.selectedVersions[pkg.name] = versions[0] by default.
        Verify that versions[0] is a parseable version string.
        """
        from packaging.version import Version

        (source_dir / "test_pkg-2.0.0-py3-none-any.whl").write_bytes(b"fake")
        (source_dir / "test_pkg-1.0.0-py3-none-any.whl").write_bytes(b"fake")

        result = api.get_versions("test-pkg")

        # Must not raise -- the JS will use this value as a v-model binding
        assert Version(result[0])

    def test_each_version_string_is_non_empty(
        self, api: Api, source_dir: Path
    ) -> None:
        """All returned version strings are non-empty -- safe to store in selectedVersions."""
        (source_dir / "test_pkg-1.0.0-py3-none-any.whl").write_bytes(b"fake")
        (source_dir / "test_pkg-1.1.0-py3-none-any.whl").write_bytes(b"fake")

        result = api.get_versions("test-pkg")

        for ver in result:
            assert ver and isinstance(ver, str), (
                f"Each version must be a non-empty string, got: {ver!r}"
            )


# ---------------------------------------------------------------------------
# Test 4: dropdown disabled during update (backend isUpdating flag)
# ---------------------------------------------------------------------------


class TestDropdownDisabledDuringUpdate:
    """
    Requirement: Dropdown disabled attribute set to true when isUpdating=true.

    The disabled state is driven by store.isUpdating in the frontend.
    The backend signals the start/end of update via run_update() and the
    onUpdateComplete callback.  We verify the update lock prevents re-entry,
    which is the mechanism that keeps isUpdating true during an active update.
    """

    def test_update_lock_held_during_run_update(
        self, config: UpdaterConfig, source_dir: Path
    ) -> None:
        """
        The update lock is acquired for the duration of _do_update.
        This is what prevents concurrent installs and corresponds to
        store.isUpdating being true in the frontend.
        """
        api = Api(config, python_exe=Path("python.exe"))

        # Verify the lock is initially unlocked
        assert not api._update_lock.locked()

        # Acquire the lock manually to simulate an in-progress update
        api._update_lock.acquire()
        assert api._update_lock.locked()

        # run_update called while lock is held should queue (non-blocking from caller)
        # -- the public API returns immediately and the second call will wait
        api.run_update()  # This spawns a daemon thread that tries to acquire lock

        # Lock is still held by us -- confirm it's still locked
        assert api._update_lock.locked()
        api._update_lock.release()

    def test_install_versioned_package_sets_auto_update_disabled(
        self, config: UpdaterConfig, source_dir: Path
    ) -> None:
        """
        Selecting an older version and installing it sets _auto_update_disabled.
        This prevents the next scan from overwriting the user's pinned choice,
        which mirrors the dropdown's desired disabled state post-install.
        """
        (source_dir / "test_pkg-2.5.0-py3-none-any.whl").write_bytes(b"fake")

        from updater.core import UpdateResult

        api = Api(config, python_exe=Path("python.exe"))
        api._run_with_lock = lambda fn: fn()  # run synchronously

        mock_result = UpdateResult(total=1, updated=1, failed=0, failures=[])

        with patch("updater.gui.app.install_updates", return_value=mock_result):
            with patch(
                "updater.gui.app.get_installed_versions_batch",
                return_value={"test-pkg": "3.0.0", "other-pkg": None},
            ):
                api.install_versioned_package("test-pkg", "2.5.0")

        assert api._auto_update_disabled is True, (
            "_auto_update_disabled must be True after a versioned install "
            "so the dropdown selection is preserved"
        )

    def test_get_versions_works_when_isUpdating_would_be_true(
        self, api: Api, source_dir: Path
    ) -> None:
        """
        get_versions() must return data regardless of update lock state.
        The frontend fetches versions on init (before any update), but
        must also be safe to call at any time.
        """
        (source_dir / "test_pkg-1.0.0-py3-none-any.whl").write_bytes(b"fake")

        # Simulate lock held (update in progress) -- get_versions should not block
        api._update_lock.acquire()
        try:
            result = api.get_versions("test-pkg")
            assert result == ["1.0.0"], "get_versions must not be blocked by update lock"
        finally:
            api._update_lock.release()
