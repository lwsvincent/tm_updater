# 規格：目標專案解析 (Target Resolution) v1

定義「這一次更新要作用在哪個資料夾」的唯一解析規則。目的：讓 `updater.exe` / `updater_gui.exe`
可以放在任何位置（網路碟、工具碟、單一 Portable 資料夾），只要指定或推斷出**目標專案根目錄**，
就能正確更新該專案的 venv。

實作模組：`src/updater/target.py`（純函式、無 I/O 全域狀態，可獨立 mock/測試）

## 1. 術語

| 術語 | 定義 |
|---|---|
| `exe_dir` | 編譯產物（entry module）所在目錄；開發模式為 `src/updater/gui` 或 `src/updater` |
| `project_root` | 被更新物件：其底下含 `venv\`（或 `.venv\`）的專案根目錄 |
| `config_dir` | 生效的 `updater.toml` 所在目錄；`launcher.executable` 相對路徑的基準 |
| `source` | `.whl` 來源目錄（預設 PNT52 網路碟） |

## 2. 輸入契約

| 輸入 | 來源 | 備註 |
|---|---|---|
| `--project <path>` | CLI / GUI 啟動參數 | 可為絕對路徑或相對於 cwd |
| `--venv <path>` | CLI | 覆蓋 venv 目錄（保留既有行為） |
| `--source <path>` | CLI | 覆蓋 whl 來源 |
| GUI 執行期選取 | `Api.select_target()` → `FOLDER_DIALOG` | 選完後整個 target 重新解析並熱替換 |

## 3. `project_root` 解析優先序（第一命中即停止）

1. **`--project`**：必須存在且為目錄，否則 `TargetError` → CLI `exit 2`、GUI 寫入 error log（不靜默）。
2. **cwd 向上搜尋**（最多 4 層）：第一个含「任何 `venv_names` 目錄」或含 `updater.toml` 的祖先目錄。
3. **`exe_dir` 鏈**（現行行為）：`exe_dir`、`exe_dir.parent` — 保證「updater 放在專案內」的舊部署不破。

## 4. `config` 解析優先序

1. `<project_root>/updater.toml` — **專案層設定優先**，因為現場每台機器可能不同（venv 名稱、launcher 目標）。
2. `find_config()`（exe 同層與上 2 層）— 现行行為，作為全域預設。
3. 內建預設值（`config.py:_BUILTIN_*`）。

`config_dir` = 實際載入的 toml 所在目錄。
註：載入到專案層 toml 時，`launcher.executable` 的相對路徑基準會一併變成 `project_root`，
這是預期行為（讓一份 exe 可服務多個專案）。

## 5. `python_exe`（venv）解析優先序

1. `--venv <dir>` → `<dir>\Scripts\python.exe`（不存在即報錯，不再無聲退回）。
2. `<project_root>\<venv_name>\Scripts\python.exe`（依 `config.venv_names` 順序）
3. `<project_root>\..\<venv_name>\Scripts\python.exe`
4. `find_venv_python(None, exe_dir, venv_names)` 舊候選鏈（相容）

找不到 → CLI 印 `[ERROR]` + `exit 1`；GUI 顯示「未找到 venv：請用 --project 或選取資料夾」，
**不可**空白視窗無訊息。

## 6. `source` 解析優先序

1. `--source`
2. `config.source`；若為**相對路徑** → 以 `config_dir` 為基準解析
3. 內建 `_BUILTIN_SOURCE`

**anchored 判別（實作陷阱）**：Python 3.11 對 UNC 路徑 `\\pnt52\packages` 回傳
`Path.is_absolute() == False` 且 `.drive == ''`，若只用 `is_absolute()` 會把網路碟當成
相對路徑而錯誤拼接。故以 `raw.startswith("\\\\")` 或 `ntpath.splitdrive(raw)[0]` 判定
「已錨定」，这类值**一律不經 `Path.resolve()`**（pathlib 會為 UNC 追加尾端 `\`，
且可能改寫大小寫）。比較一律用 `Path == Path`，不用字串比對。

## 6.5 舊佈局的 root 重錨（僅在未給 `--project` 時）

解析到 `python_exe` 後，若 `project_root` 與 venv 擁有者不同（例：exe 與他的 toml
放在 `<project>/updater/`，venv 在 `<project>/venv/`），則 `project_root` 改錨為
`python_exe.parents[2]`（= venv 的上一層）。給定 `--project` 時**不**做此重錨，
以使用者指定的目錄為準。

## 7. 輸出契約

```python
@dataclass(frozen=True)
class UpdateTarget:
    project_root: Path
    config: UpdaterConfig
    python_exe: Path | None
    config_origin: str   # "project" | "exe" | "builtin"
```

## 8. 邊界條件

| 情境 | 期望結果 |
|---|---|
| `--project` 指向檔案而非目錄 | `TargetError`，訊息含實際路徑 |
| `--project` 是 UNC 路徑 | 正常運作（`source` 已是 UNC 使用案例） |
| 專案無 `updater.toml` | 退回 exe 層 toml，`config_origin="exe"`，GUI 顯示實際載入來源 |
| 專案與 exe 都有 toml | 用專案層 |
| 無 venv 但指定了專案 | `python_exe=None` + 明確錯誤訊息（不退回內建預設 venv） |
| GUI 執行期換專案 | `clear_pip_cache()`、重新綁定 `config`/`python_exe`、自動重跑 scan |

## 9. 驗收（契約測試對應 `tests/test_target.py`）

1. `--project` 命中時，venv 一定來自 `<project>/venv`，不受 cwd 影響。
2. 舊佈局（exe 在 `<proj>/updater/`、無參數）解析結果與改版前相同（回歸測試）。
3. 專案層 toml 覆蓋 exe 層 toml 的 `source`/`packages`/`launcher`。
4. 相對 `source` 依 `config_dir` 解析為絕對路徑。
5. `--project` 不存在 → 非零 exit code 且訊息可定位。
