# Change Log

### [2026-10-28 17:55] 發佈 1.5.0：版號升級、重新打包、打 tag 並推到 fork

- **對應規格 (Spec/Schema)**：
  - `pyproject.toml` `[project] version = "1.5.0"`（單一版號來源；`scripts/update_version.py` 同步 `src/updater/__init__.py.__version__`）
  - `docs/CHANGELOG.md`：`[Unreleased]` → `[1.5.0] - 2026-10-28`，補 `[1.5.0]` 比較連結
  - SemVer：新增 `--project`、GUI 目標資料列、`get_target/set_target/choose_target_folder` API → **minor** bump（1.4.0 → 1.5.0）
- **修改原因 (Why)**：
  - 1.4.x 的 exe 只能待在專案目錄內，且單檔版曾被防毒封鎖；本次功能層變更需正式版本與 tag，讓發佈 repo 的成品可追溯。
  - `git tag -l` 與 `git ls-remote --tags` 皆為空 → CHANGELOG 引用的 `updater-1.4.0` 等 tag 實際不存在，需從 `updater-1.5.0` 開始建立。
- **解耦與修改方式 (Decoupling & How)**：
  - 版號只改 `pyproject.toml`，由既有 `update_version.py`  propagating 到 `__init__.py`，避免多处硬寫（build 脚本已自動執行）。
  - exe 內嵌版由 `scripts/print_version.py` → `dist\tm_version.txt` → `--product-version/--file-version`，與 `__version__` 同源。
  - 推送目標：`origin`（`lwsvincent/tm_updater`）對 `aron0803` 為 403 唯讀，改推 `fork`（`aron0803/tm_updater`，`main` track `fork/main`），CLAUDE.md 已記錄；`gitlab` remote 尚未設定。
- **驗證與測試 (Verification & Testing)**：
  - `pytest`：155 passed / 7 failed（既有失敗）/ 3 skipped；`npx vitest run`：5 files / 57 passed（注意 `--reporter=basic` 在此 vitest 版本已移除，會造成 startup error）。
  - `scripts\build_gui.bat` → exit 0；`dist\updater_gui.dist\updater_gui.exe` 14,149,120 B、`dist\onefile\updater_gui.exe` 30,464,000 B，兩版 `ProductVersion/FileVersion = 1.5.0.0`，`dist\tm_version.txt` = `1.5.0`。
- **結果 (Result)**：1.5.0 已打 tag `updater-1.5.0` 並推送 `fork/main`；發佈 repo 的 `packages/updater*` 已換成 1.5.0 成品。未涵蓋：`origin` 寫入權限與 `gitlab` remote。

### [2026-10-28 15:45] Updater 打包：onedir + onefile 雙產物、版號寫入、防毒友善單檔

- **對應規格 (Spec/Schema)**：
  - `docs/README.md` / `docs/README_ZH.md`「打包發佈 (Build)」段落
  - 產物契約：`dist\updater_gui.dist\updater_gui.exe` + `dist\updater_gui.zip`（onedir）、`dist\onefile\updater_gui.exe`（onefile）
- **修改原因 (Why)**：
  - 上一次 build 結束碼 0 但只有 onefile 檔存在：`dist\updater_gui.dist` 與 `updater_gui.zip` 遺失，`Compress-Archive` 報 `ArchiveCmdletPathNotFound`。
  - exe 版資訊為 `ProductVersion/FileVersion = 0.0.0.0`、Company 空，現場無法辨識版本。
- **解耦與修改方式 (Decoupling & How)**：
  - 受影響檔案：`scripts/build_gui.bat`、`scripts/build_updater.bat`、`scripts/print_version.py`
  - 根因 1：兩個 build 都以 `app.py` 為模組名，Nuitka 都輸出到同一個 `dist\app.dist`；`move ... >nul` 與 `Compress-Archive` 的錯誤被吞掉。修法：各自獨立 `--output-dir`（`dist\onedir_build` / `dist\onefile_build`），並對每個產物做 `if not exist ... exit /b 1`。
  - 根因 2：`for /f ('"python.exe" "print_version.py"')` 的引號被 `cmd /c` 剝除，`TM_VER` 恆為空 →  fallback `0.0.0`。修法：版號寫到 `dist\tm_version.txt`，再用 `set /p` 讀入。
  - 單檔版防毒設定：移除 `--mingw64`（改用 MSVC，一般連結的 PE）、補齊 `--product-name/--company-name/--product-version/--file-version/--file-description/--copyright`、`--onefile-tempdir-spec="{CACHE_DIR}/{COMPANY}/{PRODUCT}/{VERSION}"`（固定可重用目錄，非隨機 `%TEMP%\onefile_*`）、`--onefile-cache-mode=cached`、`--onefile-no-compression`（壓縮自解壓最容易被判定可疑）。
  - 保留 onedir 作為現場防毒封鎖單檔時的備援方案。
- **驗證與測試 (Verification & Testing)**：
  - `cmd /c scripts\build_gui.bat` → exit 0；`dist\updater_gui.dist\updater_gui.exe` 14,149,120 B、`dist\updater_gui.zip` 11,412,087 B、`dist\onefile\updater_gui.exe` 30,464,000 B。
  - 兩版 `(Get-Item exe).VersionInfo`：`ProductName=Test Matrix Updater`、`ProductVersion=FileVersion=1.4.0.0`、`CompanyName=Test Matrix`。
  - 防毒實測（本機 Windows Defender，RealTimeProtectionEnabled=True）：單檔版複製到 `%TEMP%\tm_onefile_test` 後以 `--project` 啟動 → 程序存活、`MainWindowTitle="Test Matrix Updater"`、exe 未被移除、`Get-MpThreatDetection` 前後皆 0 筆；解壓目錄 `%LOCALAPPDATA%\Test Matrix\Test Matrix Updater\1.4.0`（38 檔 / 28.9 MB），第二次啟動沿用同一目錄。
  - 編譯報表：`dist\build_report_onedir.txt`、`dist\build_report_onefile.txt`。
- **結果 (Result)**：兩版產物如契約建立，版資訊正確；單檔版在本機 Defender 下存活。未涵蓋：程式碼签章（免費版 Nuitka 無 signing 選項）、其他廠牌防毒與實際 PNT52 分享路徑。

### [2026-10-28 15:20] updater.toml 編碼容錯：BOM / UTF-16 / Big5(cp950) 不再讓程式啟動失敗

- **對應規格 (Spec/Schema)**：
  - 新增 `docs/specs/config_encoding_spec.md`
  - `UpdaterConfig` 新增唯讀欄位：`parse_error: str = ""`、`encoding: str = ""`
  - 新函式契約：`read_toml_text(path) -> tuple[str, str]`（回傳內容與實際編碼）
- **修改原因 (Why)**：
  - 現場以记事本「ANSI」（zh-TW = cp950/Big5）或含 BOM 的 UTF-8 存檔時，`tomllib.loads` 直接丟例外（`tomllib` 只接受不帶 BOM 的 UTF-8）。
  - GUI 以 `--windows-console-mode=disable` 打包，例外發生在視窗建立前 → 視窗不出現、也看不到錯誤，使用者判斷為「無法使用」。
- **解耦與修改方式 (Decoupling & How)**：
  - 受影響檔案/函式：`src/updater/config.py` (`read_toml_text`, `load_config`)、`src/updater/main.py` (`main`)
  - 解耦設計：把「讀位元組 + 判編碼」與「解析 TOML」拆成兩個純函式，`load_config` 只做決策；`read_toml_text` 不依賴全域狀態，可直接測試。
  - 細節：先比對 BOM 旗標（UTF-32 LE/BE、UTF-16 LE/BE、UTF-8-sig）**手動剝除 BOM 再解碼**（留著 BOM 会让 `tomllib` 在 line 1 column 1 失敗）→ 再試 UTF-8 → 再試 `cp950`、`cp1252`；全失敗才丟 `ValueError`。
  - 解析失敗改為**不中斷**：使用內建預設值、設定 `parse_error`，CLI 印到 stderr、GUI 推一筆 log 並在 TargetBar 以橘色警示顯示原因與偵測到的編碼。
- **驗證與測試 (Verification & Testing)**：
  - `pytest tests/test_config.py -k Encoding` → 7 passed：UTF-8、UTF-8+BOM（`encoding == "utf-8-sig"`）、cp950（內容含 `\\pnt52\研發本部_技術服務處\packages`）、UTF-16、語法錯誤仍保留預設值、完全無法解碼 → 訊息含「編碼不支援」、`read_toml_text` 回傳編碼。
  - 全量 `pytest`：155 passed / 7 failed（既有失敗，以 `git stash` 跑 HEAD 基準確認為 124 passed / 同 7 failed）/ 3 skipped。
- **結果 (Result)**：設定檔編碼問題依規格收斂，實作與契約一致且模組可獨立測試；文件已於 `docs/README*.md` 標存檔應用「UTF-8 不含 BOM」。

### [2026-10-28 15:05] 目標資料夾解析：一份 exe 可更新任意專案（CLI + GUI）

- **對應規格 (Spec/Schema)**：
  - 新增 `docs/specs/target_resolution_spec.md`
  - 契約：`UpdateTarget{project_root, config, python_exe, config_origin}`；`config_origin ∈ {project, exe, builtin}`
  - 解析順序：project root = `--project` → 自 cwd 向上 4 層找含 venv 或 `updater.toml` 的目錄 → exe 所在鏈路；config = `<project>/updater.toml` → exe 層級 → 內建；venv = `--venv`（嚴格）→ `<project>/<venv_name>/Scripts/python.exe` → 上層 → 舊鏈路
- **修改原因 (Why)**：
  - `find_config()` 以 `sys.argv[0]` 為基準、venv 由 exe 目錄推估、`launcher.executable` 相對於設定檔 → exe 必須實體放在每個專案裡，無法放網路碟或工具碟。
- **解耦與修改方式 (Decoupling & How)**：
  - 新增 `src/updater/target.py`：純函式、`exe_dir`/`cwd` 由參數注入（可 Mock、不碰本機）；`resolve_source()` 對 UNC 與磁碟機開頭的設定值**完全不 re-anchor**（Python 3.11 `Path(r"\\server\share").is_absolute()` 為 False、`splitdrive` 為空，且 `resolve()` 會附加尾端 `\`），相對路徑才以 `config_dir` 為基準。
  - 「venv 擁有者」回溯 (`python_exe.parents[2]`) 僅在**未**給 `--project` 時啟用，保留舊佈局（exe 位於 `<project>\updater\`）的行為。
  - `src/updater/main.py`：新增 `--project`，改由 `resolve_target()` 取得目標，`TargetError` → stderr + `exit 2`。
  - `src/updater/gui/app.py`：`Api(config, python_exe, target)`、`get_target()`、`set_target()`（換目标後清 pip cache 並重掃；失敗保留原目標）、`choose_target_folder()`（`webview.FOLDER_DIALOG`）。
  - 前端 `TargetBar.vue` + `main.js`：顯示專案/venv/source/設定檔來源，可輸入路徑或選資料夾，`reloadTarget()` 重置套件與更新狀態。
- **驗證與測試 (Verification & Testing)**：
  - 新增 `tests/test_target.py`（24 案例）：明確 `--project`、專案 toml 優先、舊佈局迴歸（`project_root == TestMatrix` 且 `config_origin == exe`）、向上探索、`--venv` 嚴格模式、UNC source 不被改寫、exe 層級設定檔搜尋、`get_target/set_target` 重新綁定與錯誤路徑保留舊值。
  - 前端 `tests`：57 passed（5 files，含 `TargetBar.spec.js`）；`npm run build` 成功（index.html 0.39 kB / css 8.25 kB / js 78.81 kB）。
  - 端到端：於 `%TEMP%` 執行 `python -m updater.main --project C:\Github\acbel\tm_updater --source C:\Github\Test-Matrix_Release_whl\packages --dry-run` → 解析到 `.venv`、載入專案 toml、找到 16 個 wheel 套件。
- **結果 (Result)**：exe 與被更新資料夾解耦，舊部署行為由迴歸測試保障；實作 100% 對齊規格。
