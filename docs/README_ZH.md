# Test Matrix 套件更新程式 (Updater)

這是專為 **Test Matrix** 微服務架構設計的獨立套件更新工具。它能自動掃描網路路徑（例如 `PNT52` 伺服器）中的 `.whl` 安裝檔，並將較新版本的套件安裝至本地的 Python 虛擬環境（venv）中。

## 🌟 主要功能

*   **雙模式支援**：提供 CLI (命令行) 與 GUI (視窗介面) 兩種操作方式。
*   **版本智慧比對**：遵循 PEP 440 標準進行語義化版本比對，確保僅在有新版本時才進行更新。
*   **批次效能優化**：利用 `pip list` 批次查詢已安裝套件，大幅縮短掃描時間。
*   **自動啟動機制**：支援在更新完成後自動啟動目標應用程式（例如 `test_matrix.exe`）。
*   **DPI 自適應視窗**：GUI 模式支援 Windows 系統縮放（DPI Awareness），視窗大小與啟動位置會根據螢幕解析度自動調整（預設佔據螢幕高度的 70%，水平置中）。
*   **獨立部署**：可使用 Nuitka 編譯成獨立的 `.exe` 檔案，無需在目標電腦安裝 Python。

## 🛠️ 開發環境設定

### 前置作業
*   Python 3.11
*   Node.js (用於開發 GUI 前端)

### 安裝步驟
1.  **建立虛擬環境**：
    ```powershell
    python -m venv .venv
    .\.venv\Scripts\activate
    ```
2.  **安裝依賴套件**：
    ```powershell
    pip install -e .
    pip install nuitka  # 用於打包 EXE
    ```
3.  **準備前端 (僅 GUI 開發需要)**：
    ```powershell
    cd src/updater/gui/frontend
    npm install
    ```

## 🚀 執行方式

### CLI 模式
```powershell
python src/updater/main.py --source "\\path\to\whl" --dry-run
```

### GUI 模式
```powershell
# 開發模式 (需啟動 Vite)
cd src/updater/gui/frontend
npm run dev
# 另開終端機執行後端
python src/updater/gui/app.py --dev
```

## 📁 指定要更新的資料夾 (一份 exe 服務多個專案)

exe 可以放任何位置（網路碟、工具碟），只要指出**要更新的專案資料夾**（其下有 `venv\`）：

```powershell
# CLI：指定專案
updater.exe --project D:\Work\TestMatrix --dry-run

# GUI：同樣的參數
updater_gui.exe --project D:\Work\TestMatrix

# 不給參數：從目前資料夾向上找含 venv 或 updater.toml 的專案，
# 找不到再用 exe 所在目錄（舊部署行為）
```

GUI 執行中也能換專案：視窗上方「目標資料夾」列會顯示目前的專案 / venv / source / 設定檔來源，
可輸入路徑按「套用」，或按「瀏覽…」選取資料夾，選完自動重掃。

完整規則與邊界條件：`docs/specs/target_resolution_spec.md`

## 📦 打包發佈 (Build)

專案提供了自動化腳本進行打包，打包過程會自動從 `pyproject.toml` 同步版本號：

*   **打包 CLI**：執行 `scripts\build_updater.bat` -> 產出 `dist\updater.exe`
*   **打包 GUI**：執行 `scripts\build_gui.bat` -> 同時產出
    *   `dist\updater_gui.dist\`（**onedir**，資料夾版，啟動最快）+ `dist\updater_gui.zip`
    *   `dist\onefile\updater_gui.exe`（**onefile**，單檔可攜）

單檔版預設採用對防毒較友善的設定：MSVC 編譯（不再強制 MinGW64）、完整版資訊
（產品名／公司名／版本）、固定且可重用的解壓目錄（`{CACHE_DIR}/{COMPANY}/{PRODUCT}/{VERSION}`，
不是每次隨機 `%TEMP%\onefile_xxx`)、**停用自解壓壓縮**（壓縮过的自解壓檔最容易被判定為可疑）。
若現場防毒仍封鎖單檔版，就直接用 onedir 資料夾版。

## ⚙️ 設定檔 (`updater.toml`)

你可以透過同目錄下的 `updater.toml` 自定義行為：

```toml
[updater]
source = "\\\\pnt52\\Research\\Packages"
packages = ["test-matrix", "scope-driver"]

[launcher]
enabled = true
executable = "test_matrix.exe"
auto_launch = true # 更新後自動啟動
```

**存檔編碼**：請用 **UTF-8（不含 BOM）**。舊版記事本的「UTF-8」會加 BOM、中文 Windows 的「ANSI」是
Big5/cp950，兩者過去都會讓程式直接啟動失敗（GUI 連視窗都不出現）。現在會自動判讀 BOM、UTF-16
與 cp950，真的無法解析時也會**保留內建預設值繼續運作**，並在 GUI 上方與 log 列出原因與實際編碼。
詳見 `docs/specs/config_encoding_spec.md`。

設定檔搜尋順序：`<專案資料夾>\updater.toml`（優先，`launcher.executable` 的相對路徑也以它為基準）
→ exe 同層/上兩層 → 內建預設。

## 📝 版本規範
本專案遵循 [語義化版本 (SemVer)](https://semver.org/)。版本號統一由 `pyproject.toml` 定義，打包時會自動硬寫進程式中。
