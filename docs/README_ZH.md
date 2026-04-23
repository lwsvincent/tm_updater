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

## 📦 打包發佈 (Build)

專案提供了自動化腳本進行打包，打包過程會自動從 `pyproject.toml` 同步版本號：

*   **打包 CLI**：執行 `scripts\build_updater.bat` -> 產出 `dist\updater.exe`
*   **打包 GUI**：執行 `scripts\build_gui.bat` -> 產出 `dist\updater_gui.exe`

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

## 📝 版本規範
本專案遵循 [語義化版本 (SemVer)](https://semver.org/)。版本號統一由 `pyproject.toml` 定義，打包時會自動硬寫進程式中。
