---
title: Version Selection Feature Design
date: 2026-04-23
status: approved
---

# Version Selection Feature Design

## Overview

Add version downgrade capability to the Updater GUI, allowing users to select and install older versions of managed packages. When an older version is selected, auto-update is disabled for the current session to prevent overwrites.

## Problem Statement

Currently, the Updater only supports installing the latest available version of packages. Users cannot downgrade to older versions if needed for compatibility or testing purposes. This feature adds that capability with proper safeguards.

## Requirements

### Functional Requirements

1. **Version Dropdown**
   - Replace static "Available: X.Y.Z" text with a dropdown selector
   - Populate with all available versions from the source (PNT52)
   - Sort versions newest-first
   - Default to latest version

2. **Version Selection & Installation**
   - User selects older version → Modal confirmation dialog appears
   - Confirmation dialog: "Install version X.Y.Z? This will uninstall the current version first."
   - On confirmation: Execute `pip uninstall <package_name>` → `pip install <package_name>==X.Y.Z`

3. **Session-Level Auto-Update Disabling**
   - When older version is installed, set session flag `_auto_update_disabled = True`
   - Subsequent package scans do NOT trigger automatic installation
   - Flag applies only to current session; resets on app restart

4. **UI State Management During Installation**
   - Lock dropdown while installation runs
   - Lock install button while installation runs
   - Show installation progress in existing log panel
   - Auto-refresh installed version display after completion

### Non-Functional Requirements

- No breaking changes to existing CLI or API contracts
- Maintain current performance (parallel scanning, batch pip queries)
- All changes backward-compatible with existing config (`updater.toml`)

## Design

### Frontend Architecture

**Component Changes:**
- Package row: Replace static version display with dropdown selector
  - Old: `<div>Available: X.Y.Z</div>`
  - New: `<select id="version-${pkg.name}"><option value="X.Y.Z">X.Y.Z</option>...</select>`
  - Disabled attribute set to `true` while installation is running

**Events:**
- On dropdown change: Update internal state, no API call yet
- On "Install" button click: 
  - Show modal confirmation with selected version
  - On modal "Confirm": Call new `install_versioned_package()` API endpoint
  - On modal "Cancel": Do nothing, dropdown remains at selection

**State Management:**
- Add `versionsMap` state: Maps package name to list of available versions
- Add `selectedVersions` state: Maps package name to currently selected version
- Add `installationInProgress` state: Boolean flag to lock UI during install

### Backend Architecture

**API Endpoints:**

1. **GET `/api/versions/<package_name>`** (New)
   - Returns: `{"versions": ["X.Y.Z", "A.B.C", ...]}` sorted newest-first
   - Called once on app load or scan refresh to populate dropdowns
   - Uses existing wheel file scanning logic

2. **POST `/api/install`** (Modified)
   - Current signature: Accepts list of packages to install
   - New signature: Accepts list of `{name, version}` objects
   - Example: `{"packages": [{"name": "scope_driver", "version": "1.5.0"}]}`
   - Backward compatible: If `version` not provided, defaults to latest

**Core Module Changes (`core.py`):**
- Add parameter `target_version: str | None = None` to `install_updates()` function
- If `target_version` provided:
  - Execute: `pip uninstall <package_name> -y` (auto-confirm)
  - Then: `pip install <package_name>==<target_version>`
- If install fails at any step: Log error, return failure reason

**API Class Changes (`gui/app.py`):**
- Add session flag: `self._auto_update_disabled = False`
- New method: `install_versioned_package(package_name: str, version: str) -> dict`
  - Sets `self._auto_update_disabled = True`
  - Calls `install_updates([PackageStatus(name=package_name, ...)])` with target_version
  - Returns installation result (success/failure)
- Modify `check_updates()` method:
  - Early exit if `self._auto_update_disabled is True`
  - Log: "Auto-update disabled for this session (older version installed)"

### Data Flow

```
User selects older version in dropdown
  ↓
Click "Install" button
  ↓
Modal confirmation: "Install version X.Y.Z?"
  ↓
User clicks "Confirm"
  ↓
Frontend locks dropdown + button
  ↓
POST /api/install_versioned_package {name: "pkg", version: "X.Y.Z"}
  ↓
Backend:
  - Set session flag: _auto_update_disabled = True
  - Call pip uninstall → pip install
  - Return result (success/failure + message)
  ↓
Frontend:
  - Show result in log panel
  - Auto-refresh package status
  - Unlock dropdown + button
```

## Implementation Phases

### Phase 1: Backend Version Retrieval
- Implement `GET /api/versions/<package_name>` endpoint
- Returns all available versions for a package

### Phase 2: Backend Installation Logic
- Modify `install_updates()` to support target version parameter
- Implement `install_versioned_package()` in Api class
- Add session flag logic to disable auto-update

### Phase 3: Frontend UI
- Add dropdown selector to package rows
- Populate with versions from Phase 1
- Implement selection state management

### Phase 4: Frontend Installation Flow
- Add confirmation modal
- Connect modal to backend endpoint
- Lock/unlock UI during installation
- Auto-refresh status after completion

## Error Handling

| Error Scenario | Behavior |
|---|---|
| pip uninstall fails | Log error, don't attempt install, unlock UI |
| pip install fails | Log error with package version, unlock UI |
| Invalid version selected | Validate before submission, show error |
| Network timeout during install | Show timeout error, unlock UI |

## Testing Strategy

### Unit Tests
- Test version sorting (newest-first)
- Test pip command construction with version parameter
- Test session flag state persistence within session

### Integration Tests
- Test complete flow: select version → confirm → install → auto-refresh
- Test auto-update skips when session flag is set
- Test error cases (bad version, pip failures)

### Manual Testing
- Verify dropdown shows all versions correctly
- Verify modal confirmation works
- Verify installation completes successfully
- Verify auto-update disabled for session
- Verify UI locks/unlocks during installation

## Rollout Plan

1. Create new branch from main
2. Implement in phases (1 → 2 → 3 → 4)
3. All tests pass locally
4. Create PR with design document
5. Merge to main after review
6. Build new executable version
7. Deploy to PNT52

## Open Questions

None — design is finalized per user approval.

## Success Criteria

- ✓ Dropdown shows all available versions sorted newest-first
- ✓ Users can select and install older versions
- ✓ Confirmation modal prevents accidental downgrades
- ✓ Auto-update disabled for session after downgrade
- ✓ No breaking changes to existing APIs or CLI
- ✓ All tests pass with >5% coverage threshold
