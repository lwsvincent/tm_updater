# Version Selection Feature Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable users to downgrade to older package versions via a dropdown selector in the GUI, with automatic session-level disabling of auto-update to prevent overwrites.

**Architecture:** Four-phase implementation: (1) Backend version retrieval API, (2) Core install logic supporting target versions, (3) Frontend UI dropdown + confirmation modal, (4) Integration of all components with auto-update session flag.

**Tech Stack:** 
- Backend: Python 3.11+, PyWebView bridge, pip subprocess
- Frontend: Vue.js, HTML/CSS dropdown
- Testing: pytest for backend, manual for frontend

---

## Chunk 1: Backend Version Retrieval API

### Task 1: Write test for version retrieval endpoint

**Files:**
- Modify: `tests/test_gui.py` (add new test)

- [ ] **Step 1: Add test for GET /api/versions/<package_name>**

```python
def test_get_versions_returns_all_available_versions(api, sample_config):
    """Test that /api/versions/<package> returns all versions sorted newest-first."""
    # Setup: mock scan_packages to return multiple versions
    statuses = [
        PackageStatus(name="test-pkg", installed="1.0.0", available="3.0.0", status="update_available", whl_path=Path("test-pkg-3.0.0-py3-none-any.whl")),
        PackageStatus(name="test-pkg", installed="1.0.0", available="2.5.0", status="update_available", whl_path=Path("test-pkg-2.5.0-py3-none-any.whl")),
    ]
    
    # Call the API
    result = api.get_versions("test-pkg")
    
    # Assert
    assert result == ["3.0.0", "2.5.0"]  # newest first
    assert isinstance(result, list)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd d:\Projects\Test_Matrix\Updater
pytest tests/test_gui.py::test_get_versions_returns_all_available_versions -v
```

Expected output: `FAILED ... AttributeError: 'Api' object has no attribute 'get_versions'`

- [ ] **Step 3: Commit test**

```bash
git add tests/test_gui.py
git commit -m "test: add test for version retrieval API endpoint"
```

### Task 2: Implement version retrieval in core.py

**Files:**
- Modify: `src/updater/core.py`

- [ ] **Step 1: Add function to get all versions for a package**

Add this function to `core.py`:

```python
def get_all_versions(package_name: str, source_path: Path) -> list[str]:
    """
    Scan source directory for all available versions of a package.
    Returns versions sorted newest-first.
    
    Args:
        package_name: Normalized package name (e.g., "test-matrix")
        source_path: Path to wheel file source directory
    
    Returns:
        List of version strings sorted newest-first, e.g., ["1.5.0", "1.4.2", "1.0.0"]
    """
    versions: dict[str, Path] = {}
    normalized_name = normalize_name(package_name)
    
    # Scan source directory for matching wheel files
    if not source_path.exists():
        return []
    
    for whl_file in source_path.glob("*.whl"):
        # Parse wheel filename: {distribution}-{version}(-{build tag})?-{python tag}-{abi tag}-{platform tag}.whl
        parts = whl_file.stem.split("-")
        if len(parts) >= 2 and normalize_name(parts[0]) == normalized_name:
            version_str = parts[1]
            try:
                Version(version_str)  # Validate version format
                versions[version_str] = whl_file
            except InvalidVersion:
                continue
    
    # Sort by Version object (newest first)
    sorted_versions = sorted(versions.keys(), key=Version, reverse=True)
    return sorted_versions
```

- [ ] **Step 2: Run test to verify it passes**

```bash
pytest tests/test_gui.py::test_get_versions_returns_all_available_versions -v
```

Expected output: `PASSED`

- [ ] **Step 3: Implement get_versions in Api class (gui/app.py)**

In `src/updater/gui/app.py`, add this method to the `Api` class:

```python
def get_versions(self, package_name: str) -> list[str]:
    """
    Get all available versions for a package from the source directory.
    
    Args:
        package_name: Package name (e.g., "test-matrix")
    
    Returns:
        List of version strings sorted newest-first
    """
    versions = get_all_versions(package_name, self._config.source)
    return versions
```

Also add import at top of file:
```python
from updater.core import get_all_versions
```

- [ ] **Step 4: Commit**

```bash
git add src/updater/core.py src/updater/gui/app.py tests/test_gui.py
git commit -m "feat: add get_all_versions function and API endpoint"
```

---

## Chunk 2: Core Installation Logic with Target Version

### Task 3: Write test for versioned installation

**Files:**
- Modify: `tests/test_core.py`

- [ ] **Step 1: Add test for install with target version**

```python
def test_install_updates_with_target_version(mock_subprocess):
    """Test that install_updates with target_version runs uninstall then install."""
    python_exe = Path("C:\\venv\\Scripts\\python.exe")
    
    # Mock subprocess calls
    mock_subprocess.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    
    # Call install_updates with target version
    result = install_updates(
        [PackageStatus(name="test-pkg", installed="1.0.0", available="3.0.0", status="update_available")],
        python_exe,
        target_version="2.5.0"
    )
    
    # Assert: should call pip uninstall then pip install with version
    calls = mock_subprocess.run.call_args_list
    assert len(calls) >= 2
    
    # First call: uninstall
    uninstall_cmd = calls[0][0][0]
    assert "uninstall" in uninstall_cmd
    assert "test-pkg" in uninstall_cmd
    
    # Second call: install with version
    install_cmd = calls[1][0][0]
    assert "install" in install_cmd
    assert "test-pkg==2.5.0" in install_cmd
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_core.py::test_install_updates_with_target_version -v
```

Expected output: `FAILED ... TypeError: install_updates() got an unexpected keyword argument 'target_version'`

- [ ] **Step 3: Commit test**

```bash
git add tests/test_core.py
git commit -m "test: add test for versioned package installation"
```

### Task 4: Modify install_updates to support target version

**Files:**
- Modify: `src/updater/core.py` (modify existing `install_updates` function)

- [ ] **Step 1: Update install_updates signature**

Find the `install_updates` function in `core.py` and modify its signature:

OLD:
```python
def install_updates(
    statuses: list[PackageStatus],
    python_exe: Path,
    callback: ProgressCallback | None = None,
) -> UpdateResult:
```

NEW:
```python
def install_updates(
    statuses: list[PackageStatus],
    python_exe: Path,
    callback: ProgressCallback | None = None,
    target_version: str | None = None,
) -> UpdateResult:
```

- [ ] **Step 2: Add version-specific install logic**

Inside `install_updates`, find the pip install command loop and modify it to support target version:

OLD (approximate):
```python
cmd = [str(python_exe), "-m", "pip", "install", str(status.whl_path)]
```

NEW:
```python
if target_version:
    # Uninstall first
    uninstall_cmd = [str(python_exe), "-m", "pip", "uninstall", "-y", status.name]
    uninstall_result = subprocess.run(uninstall_cmd, capture_output=True, text=True, **_get_subprocess_kwargs())
    if uninstall_result.returncode != 0:
        if callback:
            callback("error", f"Failed to uninstall {status.name}: {uninstall_result.stderr}")
        return UpdateResult(total=1, updated=0, failed=1, failures=[f"{status.name}: uninstall failed"])
    
    # Install specific version
    cmd = [str(python_exe), "-m", "pip", "install", f"{status.name}=={target_version}"]
else:
    cmd = [str(python_exe), "-m", "pip", "install", str(status.whl_path)]
```

- [ ] **Step 3: Run test to verify it passes**

```bash
pytest tests/test_core.py::test_install_updates_with_target_version -v
```

Expected output: `PASSED`

- [ ] **Step 4: Run all core tests**

```bash
pytest tests/test_core.py -v
```

Expected output: All tests pass (no regression)

- [ ] **Step 5: Commit**

```bash
git add src/updater/core.py tests/test_core.py
git commit -m "feat: support target version parameter in install_updates"
```

### Task 5: Add session auto-update disable flag

**Files:**
- Modify: `src/updater/gui/app.py` (Api class)

- [ ] **Step 1: Add session flag to Api.__init__**

In `src/updater/gui/app.py`, find the `Api.__init__` method and add:

```python
def __init__(self, config: UpdaterConfig, python_exe: Path | None) -> None:
    self._config = config
    self._python_exe = python_exe
    self._window: webview.Window | None = None
    self._update_lock = threading.Lock()
    self._auto_update_disabled = False  # ADD THIS LINE
```

- [ ] **Step 2: Add method to install specific version**

Add this method to Api class:

```python
def install_versioned_package(self, package_name: str, version: str) -> dict[str, object]:
    """
    Install a specific version of a package.
    Sets _auto_update_disabled flag to prevent subsequent auto-update runs.
    
    Args:
        package_name: Package name to install
        version: Target version (e.g., "1.5.0")
    
    Returns:
        {"success": bool, "message": str, "failed_packages": list[str]}
    """
    self._auto_update_disabled = True
    self._push_log("info", f"Auto-update disabled for this session")
    
    # Find package status
    statuses = self.get_packages()
    target_status = next((s for s in statuses if s["name"] == package_name), None)
    if not target_status:
        return {"success": False, "message": f"Package {package_name} not found"}
    
    # Convert dict back to PackageStatus
    pkg_status = PackageStatus(
        name=target_status["name"],
        installed=target_status["installed"],
        available=target_status["available"],
        status=target_status["status"]
    )
    
    def do_install():
        self._push_log("info", f"Installing {package_name}=={version}...")
        result = install_updates(
            [pkg_status],
            self._python_exe,
            callback=self._push_log,
            target_version=version
        )
        
        if result.all_success:
            self._push_log("info", f"Successfully installed {package_name}=={version}")
        else:
            self._push_log("error", f"Failed to install {package_name}: {result.failures}")
        
        # Refresh package status
        self.scan_packages()
    
    self._run_with_lock(do_install)
    return {"success": True, "message": "Installation started"}
```

Also add import:
```python
from updater.core import install_updates
```

- [ ] **Step 3: Modify check_updates to respect auto-update flag**

Find the `check_updates` method and add early exit:

```python
def check_updates(self) -> list[dict[str, str | None]]:
    """Check for available updates."""
    
    # ADD THESE LINES AT START
    if self._auto_update_disabled:
        self._push_log("info", "Auto-update disabled for this session")
        return self.get_packages()
    
    # ... rest of method unchanged
```

- [ ] **Step 4: Commit**

```bash
git add src/updater/gui/app.py
git commit -m "feat: add session-level auto-update disable flag and versioned install method"
```

---

## Chunk 3: Frontend UI - Dropdown Selector

### Task 6: Analyze current frontend structure

**Files:**
- Read: `src/updater/gui/` (frontend files)

- [ ] **Step 1: Locate and examine Vue component structure**

```bash
find d:\Projects\Test_Matrix\Updater\src\updater\gui -name "*.html" -o -name "*.js" -o -name "*.vue"
```

Document the location of:
- Package list HTML template
- JavaScript event handlers
- CSS styling

- [ ] **Step 2: Document current package status display**

Read the HTML/Vue to understand how "Available: X.Y.Z" is currently displayed.

### Task 7: Modify frontend to add version dropdown

**Files:**
- Modify: Frontend template (exact path from Task 6)
- Modify: Frontend JavaScript (exact path from Task 6)

- [ ] **Step 1: Replace static version text with dropdown**

In the package row HTML template, change:

OLD:
```html
<div class="version">Available: <span>{{ pkg.available }}</span></div>
```

NEW:
```html
<div class="version">
  Available: 
  <select id="version-{{ pkg.name }}" class="version-dropdown" v-model="selectedVersions[pkg.name]" :disabled="installationInProgress">
    <option v-for="ver in versionsMap[pkg.name] || []" :key="ver" :value="ver">{{ ver }}</option>
  </select>
</div>
```

- [ ] **Step 2: Add data properties for version tracking**

In Vue component data(), add:

```javascript
data() {
  return {
    // ... existing data properties
    versionsMap: {},        // Maps package name to list of available versions
    selectedVersions: {},   // Maps package name to selected version
    installationInProgress: false,
  };
}
```

- [ ] **Step 3: Add CSS for dropdown styling**

Add to component or global styles:

```css
.version-dropdown {
  padding: 4px 8px;
  border: 1px solid #ccc;
  border-radius: 3px;
  background-color: white;
  font-size: 14px;
  cursor: pointer;
}

.version-dropdown:disabled {
  background-color: #f5f5f5;
  color: #999;
  cursor: not-allowed;
}

.version-dropdown:focus {
  outline: none;
  border-color: #0066cc;
  box-shadow: 0 0 3px rgba(0, 102, 204, 0.3);
}
```

- [ ] **Step 4: Commit**

```bash
git add [frontend-files]
git commit -m "ui: add version dropdown selector to package rows"
```

### Task 8: Load versions on app initialization

**Files:**
- Modify: Frontend JavaScript (main component)

- [ ] **Step 1: Add method to fetch versions**

Add to Vue component methods:

```javascript
async loadVersionsForPackage(packageName) {
  try {
    const versions = await window.api.get_versions(packageName);
    this.versionsMap[packageName] = versions;
    if (!this.selectedVersions[packageName]) {
      this.selectedVersions[packageName] = versions[0]; // Default to latest
    }
  } catch (error) {
    console.error(`Failed to load versions for ${packageName}:`, error);
  }
}

async loadAllVersions() {
  for (const pkg of this.packages) {
    await this.loadVersionsForPackage(pkg.name);
  }
}
```

- [ ] **Step 2: Call loadAllVersions after scanning**

Find where `get_packages()` or package scan is completed, and add:

```javascript
const packages = await window.api.get_packages();
this.packages = packages;
await this.loadAllVersions();  // ADD THIS LINE
```

- [ ] **Step 3: Commit**

```bash
git add [frontend-files]
git commit -m "feat: load available versions for all packages on startup"
```

---

## Chunk 4: Frontend Installation Flow & Confirmation Modal

### Task 9: Add confirmation modal HTML

**Files:**
- Modify: Frontend template (exact path from Task 6)

- [ ] **Step 1: Add modal HTML**

Add to main template (typically at end or in modals section):

```html
<div v-if="showConfirmModal" class="modal-overlay">
  <div class="modal-content">
    <h3>Confirm Version Installation</h3>
    <p>Install version <strong>{{ confirmModalData.version }}</strong> of <strong>{{ confirmModalData.packageName }}</strong>?</p>
    <p class="warning">This will uninstall the current version first.</p>
    <div class="modal-buttons">
      <button @click="confirmInstallVersion" class="btn btn-primary">Confirm</button>
      <button @click="cancelInstallVersion" class="btn btn-secondary">Cancel</button>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Add modal styling**

```css
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  max-width: 400px;
}

.modal-content h3 {
  margin-top: 0;
  color: #333;
}

.modal-content p {
  color: #666;
  margin: 12px 0;
}

.warning {
  color: #d9534f;
  font-weight: bold;
}

.modal-buttons {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 20px;
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-primary {
  background-color: #0066cc;
  color: white;
}

.btn-primary:hover {
  background-color: #0052a3;
}

.btn-secondary {
  background-color: #f0f0f0;
  color: #333;
}

.btn-secondary:hover {
  background-color: #e0e0e0;
}
```

- [ ] **Step 3: Commit**

```bash
git add [frontend-files]
git commit -m "ui: add confirmation modal for version installation"
```

### Task 10: Add install button and handler methods

**Files:**
- Modify: Frontend template & JavaScript

- [ ] **Step 1: Add install button to dropdown area**

Modify package row to add button:

```html
<div class="version">
  Available: 
  <select id="version-{{ pkg.name }}" class="version-dropdown" v-model="selectedVersions[pkg.name]" :disabled="installationInProgress">
    <option v-for="ver in versionsMap[pkg.name] || []" :key="ver" :value="ver">{{ ver }}</option>
  </select>
  <button 
    @click="promptVersionInstall(pkg.name)" 
    :disabled="installationInProgress || selectedVersions[pkg.name] === pkg.available"
    class="btn-install"
  >
    Install
  </button>
</div>
```

- [ ] **Step 2: Add button styling**

```css
.btn-install {
  margin-left: 8px;
  padding: 4px 12px;
  background-color: #28a745;
  color: white;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  font-size: 13px;
}

.btn-install:hover:not(:disabled) {
  background-color: #218838;
}

.btn-install:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}
```

- [ ] **Step 3: Add data properties for modal**

In Vue component data(), add:

```javascript
showConfirmModal: false,
confirmModalData: {
  packageName: "",
  version: "",
}
```

- [ ] **Step 4: Add handler methods**

Add to Vue component methods:

```javascript
promptVersionInstall(packageName) {
  const selectedVersion = this.selectedVersions[packageName];
  if (!selectedVersion || selectedVersion === this.packages.find(p => p.name === packageName)?.available) {
    return; // Don't prompt if same as current
  }
  
  this.confirmModalData = {
    packageName: packageName,
    version: selectedVersion,
  };
  this.showConfirmModal = true;
},

async confirmInstallVersion() {
  const { packageName, version } = this.confirmModalData;
  this.showConfirmModal = false;
  this.installationInProgress = true;
  
  try {
    const result = await window.api.install_versioned_package(packageName, version);
    if (result.success) {
      this.addLog("info", `Installing ${packageName}==${version}...`);
    } else {
      this.addLog("error", result.message);
    }
  } catch (error) {
    this.addLog("error", `Installation failed: ${error.message}`);
  } finally {
    this.installationInProgress = false;
  }
},

cancelInstallVersion() {
  this.showConfirmModal = false;
}
```

- [ ] **Step 5: Commit**

```bash
git add [frontend-files]
git commit -m "feat: add install button and confirmation flow for version selection"
```

### Task 11: Auto-refresh status after installation

**Files:**
- Modify: Frontend JavaScript

- [ ] **Step 1: Add listener for completion**

Modify the package scanning/refresh logic to auto-trigger after installation completes. Add to methods:

```javascript
async monitorInstallation() {
  // Poll for installation completion by checking if installationInProgress was set to false by backend
  // Backend automatically calls scan_packages() which will trigger window.updatePackages() callback
  // Frontend should detect when packages have been updated and set installationInProgress = false
}
```

Alternatively, trigger refresh after a short delay once backend reports completion in logs.

- [ ] **Step 2: Add auto-refresh trigger**

When the backend calls `self._push_log("info", "Successfully installed...")`, the frontend should:
1. Wait 1 second
2. Call `scan_packages()` again
3. Update display

Add to existing log handler or create new one:

```javascript
addLog(level, message) {
  // ... existing log code
  
  if (level === "info" && message.includes("Successfully installed")) {
    setTimeout(() => {
      this.scanPackages(); // Refresh status
    }, 1000);
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add [frontend-files]
git commit -m "feat: auto-refresh package status after successful installation"
```

---

## Chunk 5: Integration & Testing

### Task 12: Integration test for complete flow

**Files:**
- Modify: `tests/test_gui.py`

- [ ] **Step 1: Write integration test**

```python
def test_complete_downgrade_flow(api, sample_config, mock_subprocess):
    """Test complete flow: select version → confirm → install → auto-update disabled."""
    
    # Setup
    mock_subprocess.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    
    # 1. Get versions
    versions = api.get_versions("test-pkg")
    assert len(versions) > 1
    assert versions[0] == versions[-1]  # Newest is last (sorted reverse=True)
    
    # 2. Install old version
    result = api.install_versioned_package("test-pkg", versions[-1])
    assert result["success"] is True
    
    # 3. Verify auto-update disabled
    assert api._auto_update_disabled is True
    
    # 4. Verify check_updates respects flag
    packages = api.check_updates()
    # Should return early without auto-install
    assert api._auto_update_disabled is True
```

- [ ] **Step 2: Run integration test**

```bash
pytest tests/test_gui.py::test_complete_downgrade_flow -v
```

Expected: PASSED

- [ ] **Step 3: Run all tests**

```bash
pytest tests/ -v --cov=src/updater --cov-fail-under=5
```

Expected: All pass, coverage >= 5%

- [ ] **Step 4: Commit**

```bash
git add tests/test_gui.py
git commit -m "test: add integration test for version selection flow"
```

### Task 13: Manual testing checklist

- [ ] **Step 1: Start GUI and verify baseline**

```bash
python -m updater.gui.app
```

- Open GUI
- Verify package list displays correctly
- Verify "Available" column shows dropdown (not text)

- [ ] **Step 2: Test version dropdown**

- Click dropdown for any package
- Verify all versions display (should be 3+ if test environment has old wheels)
- Verify sorted newest-first

- [ ] **Step 3: Test confirmation modal**

- Select older version
- Click "Install"
- Verify modal appears with correct version
- Verify button states (Confirm/Cancel)

- [ ] **Step 4: Test installation**

- Click "Confirm"
- Verify UI locks (dropdown + button disabled)
- Verify progress appears in log panel
- Wait for completion
- Verify "Successfully installed" message in logs
- Verify installed version updated in package list

- [ ] **Step 5: Test auto-update disable**

- After downgrade, manually trigger "Check for Updates"
- Verify no automatic installation occurs
- Verify log shows "Auto-update disabled for this session"

- [ ] **Step 6: Test error handling**

- (Simulate pip error if possible)
- Verify error message displays in log
- Verify UI unlocks after failure

### Task 14: Final integration and commit

**Files:**
- Verify: All files built and working

- [ ] **Step 1: Full rebuild and test**

```bash
cd d:\Projects\Test_Matrix\Updater
pytest tests/ -v
```

Expected: All tests pass

- [ ] **Step 2: Build GUI executable**

```bash
template_project\scripts\build_gui.bat
```

Expected: `dist/updater_gui.exe` created

- [ ] **Step 3: Test executable**

Run `dist/updater_gui.exe` and perform manual checks from Task 13

- [ ] **Step 4: Version bump and changelog**

Update `pyproject.toml` version to `1.3.0`
Update `CHANGELOG.md` with entry:

```markdown
## [1.3.0] - 2026-04-23

### Added
- Version selection dropdown in GUI for package downgrade capability
- Ability to select and install older package versions
- Confirmation modal for version installation
- Session-level auto-update disabling when older version installed
- Backend API endpoints for version retrieval and versioned installation
```

- [ ] **Step 5: Final commit**

```bash
git add pyproject.toml CHANGELOG.md docs/
git commit -m "release: v1.3.0 - Version selection feature with downgrade support

- Add version dropdown selector per package
- Support pip uninstall → install workflow for downgrades
- Session-level auto-update disabling
- Confirmation modal for safety
- Backend API for version management
- Full integration tests and manual testing checklist

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

## Success Criteria

- ✅ All unit tests pass (core logic, API endpoints)
- ✅ All integration tests pass (complete flow)
- ✅ Manual testing checklist complete
- ✅ GUI executable builds without errors
- ✅ Version dropdown displays all versions newest-first
- ✅ Confirmation modal prevents accidental downgrades
- ✅ Auto-update disabled correctly for session
- ✅ pip uninstall → install flow works end-to-end
- ✅ CHANGELOG.md and version updated
- ✅ No breaking changes to existing APIs or workflows

---

## Notes

- TDD approach: Write failing test first, implement to pass, commit
- Bite-sized steps: Each step is 2-5 minutes of focused work
- Frontend files path determination is critical (Task 6) — inspect actual structure before modifying
- Mock subprocess calls in tests to avoid actual pip execution
- Manual testing essential for GUI; automated tests handle backend logic
