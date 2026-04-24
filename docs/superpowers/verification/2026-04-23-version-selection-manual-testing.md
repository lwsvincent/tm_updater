# Manual Testing Checklist: Version Selection Feature

**Date:** 2026-04-23
**Feature:** Version Selection and Downgrade via GUI Dropdown
**Estimated Time:** 30-45 minutes for a complete run

---

## Overview

This checklist verifies the version selection feature end-to-end from the GUI.
The feature allows users to select any available version of a managed package
from a dropdown and install it, with automatic session-level protection against
auto-update overwriting the pinned version.

A tester unfamiliar with the code can use this document alone to verify all
behaviors. Each section includes expected outcomes and troubleshooting notes.

---

## 1. Test Environment Setup

### 1.1 Prerequisites

- [ ] Python is installed and accessible (`python --version` responds)
- [ ] The Updater virtual environment is set up at `<repo>\.venv\` or `<repo>\venv\`
- [ ] The frontend has been built: `<repo>\src\updater\gui\frontend\dist\index.html` exists

  If the frontend is not built, run from the frontend directory:

  ```
  cd src\updater\gui\frontend
  npm run build
  ```

- [ ] Git working tree is clean (no unrelated changes that could interfere)

### 1.2 Create the Test Source Directory

Create a local directory to act as the wheel source. This replaces the default
PNT52 network share for testing purposes.

```
mkdir C:\tmp\updater_test_source
```

Copy (or create empty placeholder) wheel files into that directory with these
exact names:

```
C:\tmp\updater_test_source\test-matrix-1.5.0-py3-none-any.whl   <-- latest
C:\tmp\updater_test_source\test-matrix-1.4.0-py3-none-any.whl
C:\tmp\updater_test_source\test-matrix-1.3.0-py3-none-any.whl
C:\tmp\updater_test_source\test-matrix-1.0.0-py3-none-any.whl
```

Note on wheel file names: The format is `{distribution}-{version}-{python tag}-{abi tag}-{platform tag}.whl`.
A file named `test-matrix-1.4.0-py3-none-any.whl` is a valid name for any
Python 3, pure-Python, any-platform wheel for the `test-matrix` package at
version 1.4.0.

If you want to test with real packages, copy actual `.whl` files from the
PNT52 source directory. Multiple versions of the same package can coexist in
the source directory; the updater reads all of them.

### 1.3 Create a Local updater.toml

Create `<repo>\updater.toml` with the following content, pointing the source
to the directory created above:

```toml
[updater]
source = "C:\\tmp\\updater_test_source"
packages = ["test-matrix"]

[launcher]
enabled = false

[gui]
theme = "blueprint"
```

This overrides the default PNT52 path and limits the package list to one
package so the test is focused.

### 1.4 Verify Initial Installed Version

Check what version of test-matrix is currently installed in the venv:

```
.venv\Scripts\python.exe -m pip show test-matrix
```

Record the output. If test-matrix is not installed, that is also acceptable
(the GUI will show "Not installed" status).

For the most instructive test, install version 1.3.0 first so there is a
visible "available" update and also an older version to downgrade to:

```
.venv\Scripts\python.exe -m pip install C:\tmp\updater_test_source\test-matrix-1.3.0-py3-none-any.whl --no-deps
```

Expected: test-matrix 1.3.0 is now installed.

### 1.5 Start the GUI

From the repository root:

```
.venv\Scripts\python.exe -m updater.gui.app
```

Or use the provided launcher script:

```
start_gui.bat
```

Expected: A window titled "Test Matrix Updater" appears with a two-panel layout.
The left panel shows a package table. The right panel shows action buttons above
a Console log area.

### 1.6 Verify the GUI Is Ready

- [ ] The window opens without any error dialog
- [ ] The Console log shows at least one entry (the scan starts automatically on load)
- [ ] The package table shows at least "test-matrix" in the Package column
- [ ] The log does NOT show a red "No venv Python found" error

**Troubleshooting:**

- If "No venv Python found" appears in the log: The `.venv` or `venv` directory
  is missing from the repo root or the parent directory. Re-run the venv creation
  script.
- If the window is blank/white: The frontend build is missing. Run `npm run build`
  inside `src\updater\gui\frontend\`.
- If "No .whl files found in source path" appears: The `updater.toml` source path
  is wrong or the directory is empty. Verify `C:\tmp\updater_test_source` contains
  `.whl` files.

---

## 2. Golden Path Testing

These steps verify normal successful operation.

### 2.1 Dropdown Is Populated with All Available Versions

- [ ] In the package table, locate the "Available" column for test-matrix
- [ ] Click the dropdown in that column
- [ ] Verify 4 options are shown: 1.5.0, 1.4.0, 1.3.0, 1.0.0
- [ ] Verify the options are sorted newest-first (1.5.0 at top, 1.0.0 at bottom)

Expected outcome: All four wheel files in the source directory are reflected as
dropdown options.

**Troubleshooting:**

- If the dropdown shows only one option or "-": The GUI could not find versions.
  Check the Console log for errors related to `get_versions`. Verify wheel file
  names follow the format `{package}-{version}-py3-none-any.whl` and that the
  package name in the filename matches the `packages` list in `updater.toml`
  (normalized: `test-matrix`).

### 2.2 Default Selection Is the Latest Version

- [ ] Before clicking the dropdown, observe the value displayed in the dropdown
- [ ] Verify it shows "1.5.0" (the latest version) as the default

Expected outcome: The newest available version is pre-selected on load.

### 2.3 Selecting a Different Version Updates Dropdown State

- [ ] Click the dropdown and select "1.4.0"
- [ ] Verify the dropdown now shows "1.4.0"
- [ ] Open the browser console (not applicable in production GUI; use Console log panel)
  The Console panel is not the browser DevTools -- it is the log panel in the GUI's
  right side. No browser console is available in production. Skip DevTools steps.

Expected outcome: Selecting a version changes the displayed value. No network
request or installation occurs at this point.

### 2.4 "Install Selected Version" Button Enables Correctly

- [ ] With "1.4.0" selected in the dropdown (different from the installed 1.3.0),
  verify the "Install Selected Version" button in the right panel is enabled
  (not greyed out)
- [ ] Now select "1.3.0" in the dropdown (same as installed version)
- [ ] Verify the "Install Selected Version" button becomes disabled/greyed out

Expected outcome: The button is only enabled when the selected version differs
from the currently installed version.

Note: The button checks whether ANY package's selected version differs from its
installed version. If multiple packages are shown, the button may remain enabled
if another package also has a version mismatch.

### 2.5 Modal Appears with Correct Version on Button Click

- [ ] Select "1.4.0" in the dropdown (different from installed 1.3.0)
- [ ] Click the "Install Selected Version" button
- [ ] Verify a modal dialog appears on screen

Expected outcome: A confirmation modal appears centered on the window.

### 2.6 Modal Shows Correct Package and Version

- [ ] Read the text in the modal dialog
- [ ] Verify it says something like: "Install version 1.4.0? This will uninstall the
  current version first."
- [ ] Verify both the version number (1.4.0) and the warning about uninstalling are
  visible

Expected outcome: The modal clearly states what version will be installed and
warns that the current version will be removed first.

### 2.7 Cancel Button Closes Modal Without Installing

- [ ] With the modal open, click the "Cancel" button
- [ ] Verify the modal disappears
- [ ] Verify no new log entries appear in the Console (no installation attempt)
- [ ] Verify the installed version of test-matrix has not changed

  Check via: `.venv\Scripts\python.exe -m pip show test-matrix` -- should still
  show 1.3.0.

Expected outcome: Cancel is a no-op. State is unchanged.

### 2.8 Confirm Button Triggers Installation

- [ ] Select "1.4.0" in the dropdown
- [ ] Click "Install Selected Version"
- [ ] In the modal, click "Install"
- [ ] Verify the modal does NOT close immediately (it stays open while installing)
- [ ] Verify new log entries appear in the Console panel immediately after clicking

Expected outcome: Installation begins. The modal stays visible with the "Install"
button showing "Installing..." to communicate that work is in progress.

### 2.9 Installation Progress Is Logged

While the installation from 2.8 is in progress:

- [ ] Watch the Console log panel on the right side
- [ ] Verify a log entry appears: "Auto-update disabled for this session (older version installed)"
- [ ] Verify a log entry appears: "Installing test-matrix==1.4.0..."
- [ ] Verify a log entry appears: "test-matrix: 1.3.0 -> 1.4.0 installing..."

Expected outcome: Installation activity is visible in the Console in real time.
All messages should appear within a few seconds.

### 2.10 Installation Completes Within Expected Time

- [ ] Time the installation from clicking "Install" to seeing a success or error message
- [ ] Verify installation completes within 30 seconds for a local wheel file

Expected timing: A local `.whl` install (no network) typically takes 2-10 seconds.
If it exceeds 30 seconds, something is wrong.

**Troubleshooting:**

- If the modal stays on "Installing..." indefinitely: A background thread may be
  blocked. Check if another operation holds the lock (e.g., a scan started
  simultaneously). Restart the app and try again.

### 2.11 Success Message in Log

After installation completes:

- [ ] Verify a success log entry appears in green: "test-matrix: updated to 1.4.0"
- [ ] Verify no red error entries appeared

Expected outcome: Green "updated to 1.4.0" confirms the installation succeeded.

### 2.12 Package List Refreshes Automatically

After the success message:

- [ ] Verify the modal closes automatically (without user action)
- [ ] Verify the "Installed" column for test-matrix now shows "1.4.0"
- [ ] Verify the "Status" column reflects the correct state:
  - If 1.5.0 is available and 1.4.0 is installed: status should show "Update" (update available)
  - If only 1.4.0 is available: status should show "Up to date"

Expected outcome: The package table updates without requiring a manual scan.

### 2.13 "Install Selected Version" Button Re-Enables After Install Completes

After the modal closes:

- [ ] Verify the "Install Selected Version" button is enabled (not greyed out)
  assuming a different version is selected in the dropdown

Expected outcome: The UI is unlocked. Buttons are interactive again.

### 2.14 Dropdown Auto-Selects the Newly Installed Version

After install completes:

- [ ] Observe the dropdown value for test-matrix
- [ ] Verify it now shows "1.4.0" (the just-installed version)

Expected outcome: The dropdown defaults to the version that was just installed,
reflecting the current state of the environment.

---

## 3. Auto-Update Disable Testing

This section verifies that installing an older version prevents auto-update from
overwriting it during the same session.

### 3.1 Downgrade to Older Version

If test-matrix 1.4.0 is currently installed (from Section 2), downgrade further:

- [ ] Select "1.3.0" in the dropdown
- [ ] Click "Install Selected Version", then confirm
- [ ] Wait for completion (success message in log)
- [ ] Verify test-matrix 1.3.0 is now installed (check "Installed" column)

### 3.2 Trigger a Manual Scan

- [ ] Click the "Update All" button (or look for a "Check for Updates" / "Scan" button)
  Note: In the current GUI, there is no standalone "Scan" button. The scan runs
  automatically on startup. To re-trigger it, use the "Update All" button which
  first scans before installing.

  Alternatively, trigger a second check by restarting the app with the same config.

  If triggering via the "Update All" button:
  - [ ] The button should be enabled (test-matrix 1.3.0 is installed, 1.5.0 is available)
  - [ ] Click "Update All"

### 3.3 Verify Auto-Update Disabled Log Message

After triggering the scan/update:

- [ ] Look at the Console log
- [ ] Verify this message appears: "Auto-update disabled for this session (older version installed)"
- [ ] Verify test-matrix was NOT upgraded to 1.5.0 (no "updated to 1.5.0" log entry)

Expected outcome: The session flag prevents auto-update from overwriting the
manually selected version.

### 3.4 Trigger Another Scan and Verify Protection Persists

- [ ] Without restarting the app, trigger the scan again (same method as 3.2)
- [ ] Verify the same "Auto-update disabled" message appears again
- [ ] Verify no installation occurs

Expected outcome: The session flag persists throughout the current app session.
Every scan attempt is blocked by the flag until the app is restarted.

### 3.5 Restart App and Verify Auto-Update Re-Enables

- [ ] Close the GUI window
- [ ] Start the GUI again with the same command
- [ ] Wait for the automatic startup scan to complete
- [ ] Look at the Console log

Expected outcome: The "Auto-update disabled" message does NOT appear this time.
The scan runs normally. If test-matrix 1.3.0 is installed and 1.5.0 is available,
the log should show "update_available" status and (if auto_update is enabled in
config) may attempt to install 1.5.0.

Note: The session flag `_auto_update_disabled` is an in-memory flag on the `Api`
class instance. It is never persisted to disk. Restarting the app creates a new
instance with the flag set to `False`.

---

## 4. Edge Case Testing

### 4.1 Install When Already on That Version (Button Should Be Disabled)

- [ ] Verify test-matrix is installed at some version (e.g., 1.4.0)
- [ ] In the dropdown, select the same version that is currently installed (1.4.0)
- [ ] Observe the "Install Selected Version" button
- [ ] Verify the button is disabled (greyed out)
- [ ] Verify clicking the greyed-out button does nothing

Expected outcome: The button is non-interactive when the selected version matches
the installed version. This prevents a no-op reinstall.

Technical note: The button's disabled condition is derived from the `targetPackage`
computed property in `ActionPanel.vue`, which returns null when no package has a
selected version that differs from its installed version.

### 4.2 Select Version That Fails to Install (Verify Error Message)

To test failure handling, temporarily rename a wheel file to break its contents,
or use a version string that does not exist:

Method A -- Use a non-existent version:
- [ ] Manually edit `updater.toml` to add a bogus wheel name, OR
- [ ] This scenario is difficult to trigger via the normal dropdown because the
  dropdown only shows versions of files that actually exist in the source.

Method B -- Use a real package that is not in the local venv environment and
verify the error path:
- [ ] Trigger installation of a version from the dropdown
- [ ] While installation is running, check if the Console shows any red error entries
  if the pip subprocess encounters an error

Expected outcome on any failure: A red error entry appears in the Console log
showing: "test-matrix: FAILED - <error details>". The modal closes and the UI
unlocks (buttons become interactive again).

**Verification:** After a failed install, check that `store.isUpdating` is false
by verifying the buttons are clickable. If buttons remain greyed out after a
failure, that is a bug.

### 4.3 Rapid Version Selection (Clicking Dropdown Multiple Times)

- [ ] Click the dropdown and change the selection rapidly several times
- [ ] Do not click "Install Selected Version" during rapid selection
- [ ] After settling on a final version, observe the dropdown shows that final selection

Expected outcome: Rapid dropdown changes do not cause any errors or unexpected
API calls. Version selection is client-side state only until the install button
is clicked.

### 4.4 Clicking Install Button While Installation Is in Progress (Should Be Disabled)

- [ ] Start an installation (click "Install Selected Version" and confirm)
- [ ] While the "Installing..." state is visible, look at the "Install Selected Version"
  button and the "Update All" button
- [ ] Verify both buttons are disabled (greyed out) during installation
- [ ] Verify the dropdown is also disabled (cannot change selection)

Expected outcome: All action controls are locked during an active installation.
The `store.isUpdating` flag set to `true` disables the dropdown (`store.isUpdating`
is bound to `:disabled` on the select element) and buttons throughout the app.

### 4.5 Close Modal During Installation (Modal Should Remain Locked)

- [ ] Start an installation (click "Install Selected Version" and confirm)
- [ ] While the modal shows "Installing...", attempt to click "Cancel"
- [ ] Verify the "Cancel" button is disabled during installation

Expected outcome: The modal's Cancel button is disabled while `store.isUpdating`
is true. The user cannot dismiss the modal mid-install. This is by design to
prevent partial installation states.

Technical note: In `VersionConfirmModal.vue`, both buttons have
`:disabled="store.isUpdating"`, so the modal effectively locks until the backend
calls `window.onVersionedInstallComplete`.

---

## 5. UI Behavior Testing

### 5.1 Version Dropdown Is Disabled While Installation Is in Progress

- [ ] Start an installation
- [ ] While "Installing..." is shown, attempt to open the dropdown in the package table
- [ ] Verify the dropdown is non-interactive (the click does nothing)

Expected outcome: The dropdown has `opacity: 0.5; cursor: not-allowed;` styling
when disabled. Clicking it does not open the options list.

### 5.2 Action Buttons Are Disabled During Installation

- [ ] Start an installation
- [ ] Verify all three buttons in the right panel are greyed out:
  - "Update All" (spinning icon if it was the trigger)
  - "Install Selected Version"
  - "Launch" (if enabled)

Expected outcome: All buttons become non-interactive while `store.isUpdating` is
true.

### 5.3 Install Button Text/State Changes During Installation

- [ ] Open the confirmation modal
- [ ] Click "Install" to begin installation
- [ ] Immediately observe the button text in the modal

Expected outcome: The "Install" button text changes to "Installing..." while the
operation is in progress. This provides feedback that the click was registered
and work is happening.

### 5.4 Package Table Rows Highlight During Refresh

- [ ] After an installation completes, watch the package table rows briefly

Expected outcome: Rows briefly show a green highlight animation (`row-refreshing`
class with `refresh-pulse` keyframe animation) when `store.isUpdating` is true.
The highlight fades after about 0.8 seconds.

Note: This highlight applies to ALL rows because `isUpdating` is a global flag,
not per-package. This is expected behavior.

### 5.5 Log Panel Scrolls to Show Latest Messages

- [ ] Trigger an installation that produces several log lines
- [ ] Observe the Console log panel behavior as messages arrive

Expected outcome: The log panel automatically scrolls down to show the newest
message. The user does not need to manually scroll. This is implemented via a
Vue `watch` on `store.logs` that sets `scrollTop = scrollHeight` after each
update.

### 5.6 Error Messages Clearly Indicate Which Package Failed

- [ ] If an installation failure occurs (see Section 4.2 for setup), read the error
  message in the Console log
- [ ] Verify the error message includes the package name

Expected outcome: Error messages follow the format:
`"<package-name>: FAILED - <pip error output>"`

For example: `"test-matrix: FAILED - ERROR: No matching distribution found for test-matrix==9.9.9"`

---

## 6. Log Message Reference

These are the expected log messages for each operation. Use these to verify
correct behavior in the Console panel.

| Operation | Log Level | Expected Message Pattern |
|---|---|---|
| App startup scan | info | "Test Matrix Updater GUI (vX.Y.Z)" |
| Versioned install triggered | info | "Auto-update disabled for this session (older version installed)" |
| Install begins | info | "Installing test-matrix==X.Y.Z..." |
| Pip uninstall/install step | info | "test-matrix: 1.3.0 -> 1.4.0 installing..." |
| Install success | success | "test-matrix: updated to 1.4.0" |
| Install failure | error | "test-matrix: FAILED - <reason>" |
| Subsequent scan with flag | info | "Auto-update disabled for this session (older version installed)" |
| No venv found | error | "No venv Python found" |

Log levels map to colors in the Console panel:
- `info` messages appear in light blue
- `success` messages appear in green
- `error` messages appear in red

---

## 7. Resetting App State

If testing gets stuck (installation hangs, UI is locked, etc.), follow these steps:

### 7.1 Force Close the GUI

Close the window by clicking the X button or using Task Manager to end the
`python.exe` or `updater_gui.exe` process.

### 7.2 Verify Venv State

After force-close, check whether pip left packages in a partial state:

```
.venv\Scripts\python.exe -m pip check
```

If packages are broken, reinstall from a known-good wheel:

```
.venv\Scripts\python.exe -m pip install C:\tmp\updater_test_source\test-matrix-1.3.0-py3-none-any.whl --no-deps --force-reinstall
```

### 7.3 Restart the GUI

The session-level auto-update disable flag resets on restart. Simply start the
GUI again:

```
.venv\Scripts\python.exe -m updater.gui.app
```

### 7.4 If the Frontend Shows a Blank Screen

The frontend dist may be out of date. Rebuild:

```
cd src\updater\gui\frontend
npm run build
```

Then restart the GUI.

---

## 8. Test Data Summary

Files required in the test source directory:

```
C:\tmp\updater_test_source\
  test-matrix-1.5.0-py3-none-any.whl   (latest)
  test-matrix-1.4.0-py3-none-any.whl
  test-matrix-1.3.0-py3-none-any.whl
  test-matrix-1.0.0-py3-none-any.whl
```

For testing other packages (e.g., scope_driver), add additional wheel files:

```
C:\tmp\updater_test_source\
  scope_driver-2.1.0-py3-none-any.whl
  scope_driver-2.0.0-py3-none-any.whl
```

And add `"scope_driver"` to the `packages` list in `updater.toml`.

Wheel files can be zero-byte placeholders for testing version discovery and
dropdown population. However, actual installation will fail on zero-byte files
(pip will report an error). For install testing, use real wheel files from the
PNT52 source directory.

---

## 9. Success Criteria Summary

All items in this checklist should pass for the version selection feature to be
considered complete and working:

- [ ] Dropdown is populated with all available versions, sorted newest-first
- [ ] Default selection is the latest version on app load
- [ ] Dropdown selection is client-side state only (no API call on change)
- [ ] "Install Selected Version" button enables only when selected != installed
- [ ] Confirmation modal appears with correct version and package name
- [ ] Cancel closes modal without any side effects
- [ ] Confirm triggers installation on background thread
- [ ] UI is fully locked during installation (dropdown + buttons disabled)
- [ ] Modal shows "Installing..." while in progress
- [ ] Modal cannot be dismissed during installation
- [ ] Installation completes within 30 seconds for local wheel files
- [ ] Success log entry appears in green
- [ ] Package table refreshes automatically after install
- [ ] Installed version column shows the newly installed version
- [ ] Dropdown auto-selects the newly installed version
- [ ] Subsequent scans do not trigger auto-update after a versioned install
- [ ] "Auto-update disabled" message appears in log on each blocked scan
- [ ] Restarting the app resets the auto-update disable flag
- [ ] Error messages name the failing package and include pip's error output
- [ ] UI unlocks correctly after both success and failure
