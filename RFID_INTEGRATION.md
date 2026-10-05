# RFID 整合、部署與版本恢復

此版沿用 `99_All-11-2.py` 的 `MFRC522Async`、`request(REQIDL)`、`anticoll()`、`to_hex_string(raw_uid)` 與 500 ms 輪詢，將單檔流程接入既有模組架構。桌面驗證已完成；2026-10-06 使用者回報本版 RFID 功能正常，並授權納入主分支。此實機結果來自使用者確認，未提供各項驗收步驟的詳細紀錄。

## 初始化與呼叫流程

1. `main.initialize_system()` 呼叫 `new_rfid_state()` 建立 RAM 字典，再建立 `RfidReader()`。
2. `hardware/rfid.py` 明確匯入 `mfrc522_async.MFRC522Async` 與 `aiot_tools.to_hex_string`。初始化參數來自 `config.RFID_SCK_PIN` 等現有配置：SCK 12、MOSI 11、MISO 10、RST 9、CS 13；`config.RFID_POLL_INTERVAL_MS` 為 500。
3. 成功初始化後，`main()` 將同一份狀態字典傳給 `tasks.rfid_read_task(rfid_reader, rfid_state)`，並指定給 `web_server.rfid_state`。由 `uasyncio.gather()` 排程讀卡、感測器、按鈕、MQTT 與 Web 任務。
4. `rfid_read_task()` 呼叫 `await rfid_reader.read_uid()`；封裝依序呼叫驅動 `await request(REQIDL)`、成功後 `await anticoll()`，再以 `to_hex_string(raw_uid)` 轉成大寫十六進位字串。
5. 成功後使用 `communication.wifi.get_current_time()` 的日期、時間更新快取並列印 `RFID：...`。每次循環最後 `await uasyncio.sleep_ms(500)`，讓其他協程繼續執行。驅動內部等待亦有非同步讓出排程。
6. 瀏覽器 `updateData()` 每秒 `fetch('/api/data')`；`web_server.api_data()` 使用 `json.dumps()` 序列化感測器資料與 RFID 字典快照。API 不讀 SPI；網頁以 `textContent` 更新最後 UID、時間、狀態及錯誤。

每輪實際耗時為讀卡通訊時間加上 500 ms，並非精準每 500 ms 完成一次。單一任務擁有讀卡器，避免兩個協程交錯操作 SPI。快取更新與 API 複製期間沒有 `await`，在目前單一事件迴圈下不會被其他協程插入；此保證不適用於新增執行緒或 IRQ 寫入同一狀態的設計。

## 資料與狀態生命週期

| 欄位 | 初始值與更新規則 |
|---|---|
| `last_uid` | `null`；每次成功讀卡覆寫，無回應不清空 |
| `last_read_at` | `null`；成功時存裝置格式化日期與時間；NTP 失敗時可能不是正確時刻 |
| `status` | `starting` 初始化中；`ready` 已初始化；`init_error` 初始化失敗；`read_error` 防碰撞或其他讀取例外 |
| `error` | `null`；例外時存訊息，成功讀卡後清除 |

快取只存在 ESP32 RAM，程式重啟即清空，不寫 Flash、不累積歷史。卡片持續靠近時，沿用範例每次成功都更新、列印，未加去重。移走卡片後保留最後結果，因此畫面不代表卡片仍在場。

此驅動 `anticoll()` 成功回傳 5 bytes（4-byte UID 加 BCC 檢查碼）。本版維持範例完整輸出，通常為 10 個十六進位字元，未移除 BCC；也未新增長 UID cascade 處理。後續若需以 UID 作識別鍵，應另行明確定義格式與支援卡片。

`request()` 會將無卡與部分通訊錯誤都轉為 `ERR`，封裝將這種結果視為「沒有有效讀取結果」，不能據此宣稱卡片不存在或硬體正常。初始化成功也沒有做晶片健康探測。讀取例外後保留最後結果與錯誤，持續輪詢；下一次成功讀卡才恢復 `ready`。初始化失敗則不啟動读卡，其他功能繼續運作；修正驅動／接線後需重啟。

API 的 `status: "ok"` 表示資料端點成功回應，RFID 狀態另見 `rfid.status`。網路失敗時瀏覽器保留舊畫面並標明資料連接失敗。

## 部署與實機驗收

保留裝置私人 `config.py`，確認上述腳位與輪詢參數存在。部署 `main.py`、`tasks.py`、`web_server.py`、`index.html`、新增的 `hardware/rfid.py`，以及必要硬體／通訊模組。裝置 `/lib` 需有 `mfrc522_async.py`、`aiot_tools.py`、Microdot 與原有依賴。

注意 `aiot_tools` 匯入時會使用 `machine`、`network`、`urequests`、`ujson`、`ntptime` 等模組，並初始化 GPIO 15；這是既有函式庫的行為。若缺少依賴，RFID 會呈現初始化失敗，請依錯誤訊息補齊，不用桌面型別存根取代裝置驅動。前端檔案由 Web Server 快取，部署後重啟 ESP32，再刷新網頁。

實機確認：啟動後開啟網頁，未刷卡顯示「尚未讀卡」；刷卡比對序列埠與網頁結果；移開卡片確認最後結果保留；更換卡片確認覆寫；同時操作 LED 與 MQTT 按鈕確認功能；重啟確認 RAM 紀錄清空。未新增 RFID MQTT 發布、門禁判斷或卡片寫入。

桌面驗證命令（使用實際可用的 Python／Node）：

```powershell
python -B -m unittest discover -s tests -v
node tests/test_rfid_ui.cjs
```

本次 6 個 Python 測試與網頁 JavaScript 測試通過。Python 使用 fake driver／GPIO，API 使用本專案 Microdot；JavaScript 使用模擬 DOM 與 fetch，未代表瀏覽器布局或 ESP32 SPI 驗證。

## GitHub 版本與回復

修改前基線是 `38a65fd`，標籤為 `baseline-before-rfid-20261006`。RFID 實作提交為 `6e341b6`，經使用者確認功能正常後，將功能分支快轉合併至 `main`，並建立 `rfid-validated-20261006` 標籤；該標籤包含本次驗證與版本保存紀錄。可用 `git ls-remote origin refs/heads/main 'refs/tags/rfid-validated-20261006*'` 核對遠端保存結果。

在沒有未提交工作時，建立獨立回復分支：

```powershell
git fetch origin --tags
git switch -c restore-before-rfid baseline-before-rfid-20261006
```

將該基線的應用檔案重新部署到 ESP32；新加入的 `hardware/rfid.py` 不會被舊程式匯入，可在裝置上保留。Git 切換不會自動回復 ESP32 Flash。

原本私人 `config.py`、`99_All-11-2.py`、`.vscode/settings.json` 的本機副本位於 `.local-backups/baseline-before-rfid-20261006`，GitHub 不含這些秘密與個人路徑。回復前比對檔案，避免覆蓋後續新增的私人配置；請自行將私人備份保存在適當的異地位置。
