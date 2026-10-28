# 規格：`updater.toml` 編碼與解析失敗行為 v1

實作模組：`src/updater/config.py:read_toml_text()` / `load_config()`

## 1. 問題（現場實際狀況）

`updater.toml` 由現場人員用記事本手改，內容含中文 UNC 路徑
（`\\pnt52\研發本部_技術服務處_...\packages`）。`tomllib` 的契約是**僅接受 UTF-8、且不接受 BOM**：

| 存檔方式（Windows 記事本） | 結果（修訂前） |
|---|---|
| ANSI（zh-TW = cp950/Big5） | `UnicodeDecodeError` → 拋例外 |
| UTF-8 **含 BOM** | `TOMLDecodeError`（BOM 視為非法字元） |
| UTF-16（部分編輯器/網路碟另存） | `UnicodeDecodeError` |
| 語法打錯（漏 `]`、引號） | `TOMLDecodeError` |

GUI 版以 Nuitka `--windows-console-mode=disable` 打包，**沒有 console**，例外在開視窗之前拋出
→ 雙擊後視窗不出現，現場只能描述成「無法使用」，無法除錯。

## 2. 契約

### 2.1 解碼順序（`read_toml_text`）

1. 依 BOM 判別並**移除 BOM 位元組**：UTF-32 LE/BE、UTF-16 LE/BE、UTF-8 BOM。
   （必須手動移除：`utf-16-le` 等 codec 會把 BOM 留成 `U+FEFF`，tomllib 會拒收。）
2. `utf-8` 嚴格解碼。
3. 依序退回 `cp950`（zh-TW ANSI/Big5）、`cp1252`。
4. 全部失敗 → `ValueError`（由 `load_config` 收斂，不外洩）。

回傳 `(text, encoding_used)`；非 `utf-8` 時印 `[DEBUG] updater.toml decoded as <enc>`。

### 2.2 解析失敗不中斷執行

`load_config()` 對 `ValueError` / `TOMLDecodeError` / `OSError` **不丟例外**：

- `UpdaterConfig.parse_error` 填入「路徑 + 原因」的可讀訊息；
- `UpdaterConfig.encoding` 記錄實際解碼；
- 其餘欄位使用內建預設（`_BUILTIN_SOURCE` / `_BUILTIN_PACKAGES`），更新仍可繼續；
- 同時寫入 stderr（CLI 可見）。

### 2.3 呈現（不可靜默）

| 介面 | 位置 |
|---|---|
| CLI | `main.py` 印 `[WARNING] <parse_error>` |
| GUI | `Api.get_target()["config_error"]`/`["encoding"]` → `TargetBar.vue` 以橘色列顯示；`_do_scan()` 首次掃描再推一張 log（`_config_error_logged` 防重複） |

## 3. 建議的正確存檔方式（文件層面）

以 **UTF-8 無 BOM** 儲存。要在中文 Windows 上避免被存成 ANSI，用 VS Code / Notepad++ 選
「UTF-8」（Notepad 1903+ 的「UTF-8」已是無 BOM，舊版「UTF-8」含 BOM）。

## 4. 驗收對應（`tests/test_config.py::TestTomlEncoding`）

1. UTF-8 無 BOM → `encoding == "utf-8"`、`parse_error == ""`
2. UTF-8 含 BOM → 正常解析，`encoding == "utf-8-sig"`
3. cp950 + 中文路徑 → 正常解析且 `source` 等於原字串（中文不變形）
4. UTF-16（含 BOM）→ 正常解析
5. 語法錯誤 → `parse_error` 非空且 `source` 仍為內建預設
6. 完全無法解碼的位元組 → `parse_error` 含「編碼不支援」，`packages` 仍為預設
7. `read_toml_text()` 回傳實際使用的 encoding
