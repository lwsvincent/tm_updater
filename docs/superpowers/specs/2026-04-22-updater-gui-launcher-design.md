# Updater GUI & Post-Update Launcher Design

## Overview

Evolve the Updater microservice with two features:
1. Post-update launcher that executes a configurable startup file after successful update
2. Industrial-style GUI using PyWebView(WebView2) + Vue to browse package versions and control updates

## Config Extensions (updater.toml)

```toml
[updater]
source = '\\pnt52\...\packages'
packages = [...]

[launcher]
enabled = true                           # default: false (opt-in)
executable = "start_api_server.py"   # .py or .exe, relative to updater.toml directory
args = ["--port", "5000"]            # optional arguments
mode = "on_success"                  # "on_success" = all packages ok, "on_complete" = always
auto_launch = false                  # auto-launch after update completes
auto_update = false                  # auto-start updating when GUI opens

[gui]
theme = "blueprint"                  # extensible theme system
```

All `[launcher]` and `[gui]` keys are optional. When a section or key is missing from `updater.toml`, the dataclass defaults apply. This ensures backward compatibility with existing config files that only have `[updater]`.

### Launcher modes

- `on_success` (default): launch only when every targeted package either updated successfully or was already up-to-date (zero failures).
- `on_complete`: launch whenever the updater finishes, regardless of results.

### Executable path resolution

`executable` is resolved relative to the directory containing `updater.toml`. For example, if `updater.toml` is at `D:\TestMatrix\updater.toml` and `executable = "start_api_server.py"`, the resolved path is `D:\TestMatrix\start_api_server.py`. Absolute paths are also supported.

### Executable handling

- `.py` files: executed via the target venv's `python.exe`.
- `.exe` files: executed directly via `subprocess.Popen`.
- Arguments from `args` array are passed as command-line arguments.

### Launcher in CLI vs GUI

Both `updater.exe` (CLI) and `updater_gui.exe` (GUI) honor the `[launcher]` config:
- **CLI**: after update completes, evaluate launch conditions per `mode`. If met and `enabled = true`, launch the executable. Print launch status to stdout. `auto_launch` and `auto_update` are ignored in CLI mode (CLI always updates immediately and launches if conditions are met).
- **GUI**: respects `auto_update` and `auto_launch` flags for automated flow. Manual buttons available when auto flags are off.

### Launcher error handling

When launch fails (file not found, permission denied, process crashes on startup):
- Log the error with full details (exception type, message, path attempted).
- In GUI: error appears in log console as a red line. Launch button resets to "Launch" (not stuck on "Running").
- In CLI: error printed to stderr, exit code 2 (distinct from update failure exit code 1).
- The updater does NOT retry launch. User must fix the config and retry.

## Architecture

### Project structure

```
src/updater/
  __init__.py              # version
  main.py                  # CLI entry point (argparse, calls core)
  core.py                  # extracted logic: scan, compare, install
  launcher.py              # startup file execution (py/exe with args)
  config.py                # toml loading, typed config dataclass
  gui/
    __init__.py
    app.py                 # PyWebView window + Python-JS bridge API
    frontend/              # Vue + Vite project
      package.json
      vite.config.js
      index.html
      src/
        App.vue            # root component
        main.js            # Vue mount
        components/
          PackageTable.vue
          ActionPanel.vue
          LogConsole.vue
        themes/
          blueprint.css    # default Light Industrial / Blueprint theme
      dist/                # vite build output, embedded by Nuitka
```

### Core refactoring

Extract from `main.py` into `core.py`:
- `scan_packages(source_path) -> dict` -- scan source for available whls
- `check_updates(python_exe, packages, available) -> list[PackageStatus]` -- compare installed vs available
- `install_updates(packages_to_update, python_exe, on_progress) -> UpdateResult` -- install and return structured results, calls `on_progress(log_line)` callback for each step

`main.py` becomes a thin CLI wrapper calling these functions with a print-based `on_progress` callback.

### Config module (config.py)

Typed dataclass loaded from `updater.toml`:

```python
@dataclass
class LauncherConfig:
    enabled: bool = False
    executable: str = ""
    args: list[str] = field(default_factory=list)
    mode: str = "on_success"      # "on_success" | "on_complete"
    auto_launch: bool = False
    auto_update: bool = False

@dataclass
class GuiConfig:
    theme: str = "blueprint"

@dataclass
class UpdaterConfig:
    source: str = _BUILTIN_SOURCE
    packages: list[str] = field(default_factory=lambda: list(_BUILTIN_PACKAGES))
    launcher: LauncherConfig = field(default_factory=LauncherConfig)
    gui: GuiConfig = field(default_factory=GuiConfig)
```

Defaults: `auto_launch = False`, `auto_update = False`. Users opt in via toml.

### Launcher module (launcher.py)

- Resolves `executable` path relative to `updater.toml` directory.
- Determines file type from extension.
- `.py`: runs via venv python (`[python_exe, executable] + args`).
- `.exe`: runs directly (`[executable] + args`).
- Returns `Popen` handle (non-blocking).
- `should_launch(mode, update_result) -> bool` evaluates whether launch conditions are met.
- Raises `LauncherError` on failure (file not found, permission denied, etc.).

## GUI Design

### Visual style

Light Industrial / Blueprint:
- Light grey background (#f5f5f5), white cards with subtle shadows
- Blue accent (#1565c0) for headers and primary actions
- Green (#66bb6a) for up-to-date status
- Orange/amber (#e65100, #ff9800) for updates available
- Red for failures
- CSS theming system: themes stored in `themes/` directory, switchable via `[gui] theme` config. Designed for future addition of dark/amber/SCADA themes.

### Layout: Side Panel

```
+-----------------------------------------------+
| [Header: Test Matrix Updater]    [status bar]  |
+----------------------------+------------------+
| Package Table              | Action Panel     |
|                            |                  |
| Name | Installed | Avail   | [Update All]     |
| ---- | --------- | -----   | [Launch]         |
| pkg1 | 2.1.0     | 2.1.0   |                  |
| pkg2 | 1.2.0     | 1.3.2*  |                  |
| ...  |           |         | Log Console      |
|                            | [14:30] Scan...  |
|                            | [14:31] OK       |
+----------------------------+------------------+
```

- Left panel (~65%): package table with columns: Name, Installed, Available, Status
- Right panel (~35%): action buttons at top, log console below
- Window size: ~900x550

### Python-JS bridge (pywebview.Api)

```python
class Api:
    def get_packages(self) -> list[dict]
    # Returns: [{"name": str, "installed": str|None, "available": str|None,
    #            "status": "up_to_date"|"update_available"|"not_in_source"|"not_installed"}]

    def run_update(self) -> None
    # Starts update in background thread. Pushes log lines to frontend
    # via window.evaluate_js('addLogLine(...)') as they occur.

    def launch_app(self) -> dict
    # Returns: {"success": bool, "error": str|None, "pid": int|None}

    def get_config(self) -> dict
    # Returns current config as dict (theme, auto flags, launcher settings)
```

### Log streaming mechanism

Python pushes log lines to the Vue frontend via `window.evaluate_js()`:

```python
def _push_log(self, level: str, message: str):
    import json
    payload = json.dumps({"level": level, "message": message, "timestamp": ts})
    self._window.evaluate_js(f"window.addLogLine({payload})")
```

The Vue app registers `window.addLogLine` as a global function that appends to a reactive log array. This is the standard PyWebView push pattern -- no polling needed.

When the update completes, Python pushes a completion signal:
```python
self._window.evaluate_js(f"window.onUpdateComplete({json.dumps(result_summary)})")
```
Where `result_summary` is `{"total": int, "updated": int, "failed": int, "should_launch": bool}`. The Vue app uses this to enable the Launch button and trigger auto-launch if configured.

### GUI behavior flow

1. Open GUI -> load config -> display package table (installed versions)
2. If `auto_update = true` -> immediately scan & update
3. If `auto_update = false` -> wait for "Update All" click
4. During update: real-time log streaming via `evaluate_js`, package status updates
5. On completion: if `auto_launch = true` and conditions met per `mode` -> auto-launch
6. If `auto_launch = false` -> user clicks "Launch" manually
7. Launch button disabled until update completes, or if `launcher.enabled = false`, or if `launcher.executable` is empty

### Log console

- Real-time timestamped lines pushed from Python
- Color-coded: blue (info), green (success), red (failure)
- Auto-scroll to bottom, scrollable

## Build & Entry Points

| Executable | Entry point | Build script | Description |
|---|---|---|---|
| `updater.exe` | `src/updater/main.py` | `scripts/build_updater.bat` | CLI headless (existing) |
| `updater_gui.exe` | `src/updater/gui/app.py` | `scripts/build_gui.bat` | GUI with PyWebView |

### pyproject.toml updates

```toml
[project.scripts]
updater = "updater.main:main"
updater-gui = "updater.gui.app:main"
```

### Nuitka build for GUI

```
nuitka --onefile --mingw64 ^
    --include-data-dir=src/updater/gui/frontend/dist=updater/gui/frontend/dist ^
    --include-package=webview ^
    --include-package=packaging ^
    --windows-console-mode=disable ^
    --output-filename=updater_gui.exe ^
    src/updater/gui/app.py
```

### WebView2 runtime

PyWebView on Windows uses WebView2 (Edge Chromium). WebView2 runtime is pre-installed on Windows 10 (April 2018 update+) and Windows 11. All target machines in the Test Matrix environment run Windows 10/11, so no bootstrapping is needed. If WebView2 is missing, PyWebView falls back to MSHTML (IE) -- the GUI will degrade but still function.

### Dependencies

```toml
dependencies = ["packaging>=22.0"]

[project.optional-dependencies]
gui = ["pywebview>=5.0"]
dev = ["nuitka>=1.0.0", "pywebview>=5.0", ...]
```

## Dev Workflow

### Frontend development (hot reload)

```bash
# Terminal 1: Vite dev server
cd src/updater/gui/frontend && npm run dev    # port 15173

# Terminal 2: PyWebView in dev mode
python -m updater.gui.app --dev               # loads localhost:15173
```

`vite.config.js` defaults to port 15173. In production, PyWebView loads bundled `dist/index.html`.

## Testing

### Mock startup file

`tests/mock_app.py`: prints "App launched with args: {args}" and exits after 3 seconds. Used to validate launcher with `.py` files.

### Test scope

- `core.py`: unit tests for scan, compare, install logic
- `launcher.py`: unit tests for py/exe dispatch, mode evaluation, error handling
- `config.py`: unit tests for toml parsing, defaults, missing sections
- GUI: manual testing via dev mode
