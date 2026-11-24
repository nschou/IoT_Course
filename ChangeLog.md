# 專案變更紀錄

本檔案記錄「物聯網軟體架構」教學專案的演變、修改原因、作法與驗證。時間一律使用台灣時間 `Asia/Taipei / UTC+08:00`，日期格式為 `YYYY-MM-DD`，時間格式為 `HH:mm:ss`。新紀錄放在最上方，保留既有歷史，不以最新結論覆蓋舊紀錄。

## 紀錄規則

每次修改程式、設定、測試、部署、文件或版控規則，都必須在同一個 Git commit 更新本檔案。紀錄至少包含：

- 變更 ID、版本或狀態。
- 修正／完成日期與時間，以及紀錄時間；不確定的時間明確註記，不得推估成精確時間。
- 原因類別：`BUG` 或 `需求變更`。
- 現象、原因分析、詳細作法、影響範圍、驗證與限制。
- 關聯檔案、測試方式、部署或回復方法。

`BUG` 表示行為不符合既有預期；`需求變更` 包含新功能、政策調整、文件與流程要求。一件工作若同時包含兩類，拆分紀錄或明確標示各項原因。

Git commit hash 由歷史查詢取得；不要求把包含本紀錄的 commit hash 寫回本紀錄，避免自我引用。既有程式中的 v1.1.x／v1.2 註解不是統一的專案版本，本次開始以 Git commit 與後續 tag 作為版本依據。
## CHG-20261124-079｜將元件/LD2410_repo 納入課程 repository 並同步 GitHub

- **類別：**需求變更（版本同步）。
- **日期／紀錄時間：**2026-11-24 14:50:16 +08:00，工具取得台北時間。
- **原因：**`元件/LD2410_repo` 內含獨立的 `.git` 資料夾，父層 `IoT_Course` 只將它視為未追蹤的嵌入 repository，因此元件內容沒有進入父層 GitHub repository。
- **作法：**將元件工作樹內容改以父 repository 的一般追蹤檔案納入，保留原有 Arduino、文件、MicroPython、測試與工具檔；依父層 `.gitignore` 排除 `.dsh-meow/` 與 `__pycache__/` 等本機產物，不納入巢狀 `.git` metadata。同步更新本紀錄並提交至目前分支。
- **影響：**GitHub 的父 repository 可直接取得 `元件/LD2410_repo` 內容；本機原有 LD2410 獨立 repository metadata 不作為父 repository 檔案。根專案既有未相關工作區變更不納入本次提交。
- **驗證：**檢查父 repository 遠端為 `https://github.com/nschou/IoT_Course.git`、目前分支為 `feature/ld2410b-integration`，確認最大待同步檔案小於 GitHub 單檔限制；執行 `git diff --cached --check`。本次未執行 Python 測試，因只同步元件檔案與版控紀錄。
- **部署／回復：**推送目前分支至 `origin`；回復時以本次提交的父 repository 反向提交移除 `元件/LD2410_repo`，不影響本機未追蹤的獨立 repository metadata。

## CHG-20261121-075｜LD2410 測試與驅動集中到 micropython 套件；專案改為相容層

- **類別：**需求變更（專案組織）。
- **日期／紀錄時間：**2026-11-21 17:50:00 +08:00（工具取得台北時間）。
- **原因：**板端測試與專案驅動各自演進，出現版本漂移；使用者要求「測試與驅動必須搭配」，以 `LD2410_repo/micropython/hardware/ld2410c.py` 為唯一驅動。
- **作法：**① `tests/` 的 LD2410 程式（`esp32_ld2410_smoke/check/full_test/tx_probe.py`、`test_ld2410.py`）移到 `LD2410_repo/micropython/tests/`，改 import `hardware.ld2410c`（`LD2410C` API）、移除 `config.py` 依賴，腳位改寫在檔案頂端常數（UART1、TX=15、RX=16、OUT=14、115200）。② `test_ld2410.py` 與 `test_ld2410c.py` 合併去重（新增建構子開 UART、半包頭、壞尾重新同步、錯誤 ACK 忽略、無 `any()` 的 UART、資料新鮮度），舊檔移除，自動測試 23 → 28 項。③ 專案 `hardware/ld2410c.py` 為 `micropython/hardware/ld2410c.py` 的同步副本；`hardware/ld2410.py` 改為相容層（保留 `snapshot()`、`current_config()`、`firmware_version()['version']`、舊 `poll()` 語義），`apps/elder_care` 與 `demos` 不需修改。④ 驅動新增 `command_frame()`、`ack_word()`、`stats()` 供測試與診斷使用。
- **影響：**板端部署需同時上傳 `hardware/ld2410.py` 與 `hardware/ld2410c.py`；專案 `tests/` 不再包含 LD2410 測試。
- **驗證：**`micropython/tests/test_ld2410c.py` → 28 項全過；以假 UART 驗證相容層的 `snapshot()`／`current_config()`／`firmware_version()`／新鮮度語義；專案 `python -B -m unittest discover -s tests` → Ran 52 tests OK。
- **部署／回復：**重新上傳 `hardware/`（兩個檔案）與 `micropython/tests/` 的板端程式；回復時還原舊 `hardware/ld2410.py` 並把測試搬回專案 `tests/`。

## CHG-20261121-073｜LD2410 UART baud 統一為 115200（模組實際設定）

- **類別：**BUG（設定不一致）。
- **日期／紀錄時間：**2026-11-21 17:10:00 +08:00（工具取得台北時間）。
- **現象：**ESP32-S3 收得到 LD2410C 的資料框（10 Hz、23 bytes/框），但送 0x00FF 一律 `LD2410 ACK timeout`，讀韌體與參數都失敗。
- **原因分析：**模組的 UART 已由手機 App（HLKRadarTool）改為 **115200 8N1**，但 config.py、驅動預設值、apps/tests 的 fallback 與文件仍寫 256000；ESP32 以 256000 送出、模組以 115200 收，指令自然不執行。
- **作法：**config.py／config.example.py 的 `LD2410B_BAUDRATE` 改為 115200 並更新註解；hardware/ld2410.py 預設值、apps/elder_care/*_demo.py、tests/esp32_ld2410_{check,full_test,smoke}.py 的 fallback、tests/test_ld2410.py 斷言、mdy_03／mdy_05／mdy_06 舊版與兩份元件文件同步。文件只改可操作段落，歷史紀錄保留並在開頭加註現況。
- **影響：**所有使用 LD2410 的程式與測試；接線不變（TX=GPIO15、RX=GPIO16、OUT=GPIO14）。
- **驗證：**`python -B -m unittest discover -s tests` → Ran 71 tests OK；全專案掃描舊字串已清除（僅剩「出廠預設 256000」的說明與歷史紀錄）。
- **部署／回復：**重新上傳 config.py 與 tests/*.py。回復方式是把上述檔案改回 256000，但模組已改為 115200，不建議。

## CHG-20261121-074｜新增 TX 方向診斷程式與 tests 索引；enter_config 加入重試

- **類別：**需求變更（測試與文件）。
- **日期／紀錄時間：**2026-11-21 17:10:00 +08:00（工具取得台北時間）。
- **原因：**資料流正常但命令 timeout 時，需要能分辨「短接回音／真 ACK／指令沒到模組」的工具；相關程式也應統一放在專案 tests/ 之下。
- **作法：**新增 tests/esp32_ld2410_tx_probe.py（pins()、probe(tx, rx, baud)、run()；送 0x00FF 後補送 0x00FE 還原）與 tests/README.md（五支測試程式的用途與執行順序）；hardware/ld2410.py 的 enter_config() 改為最多重送 3 次（每次 600 ms），對應官方工具 log 中 0x00FF 失敗（A002）後重送即成功的行為。
- **影響：**只影響測試與進入設定模式的重試；命令第一次就成功時行為不變。
- **驗證：**`python -B -m py_compile tests/esp32_ld2410_tx_probe.py` 通過；`python -B -m unittest discover -s tests` → Ran 71 tests OK。實機命令通道尚待驗證。
- **部署／回復：**上傳 tests/esp32_ld2410_tx_probe.py、tests/README.md、hardware/ld2410.py；回復時刪除新檔案並還原 enter_config。

## CHG-20261124-078｜補上板上用的 async 驗證腳本，並標示 test_ld2410c_aio.py 為 PC 專用

- **類別：**BUG（文件與工具說明不足）。
- **日期／紀錄時間：**2026-11-24 02:50:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**使用者在裝置上執行 `tests/test_ld2410c_aio.py` 得到 `ImportError: no module named 'unittest'`。該檔使用 `unittest` 與 CPython 的 `asyncio`，本來就只能跑在電腦上，但檔案與 README 沒有標明。
- **作法：**① `test_ld2410c_aio.py` 的 docstring 加上「PC ONLY」與替代方案說明。② 新增 `tests/esp32_ld2410_aio_smoke.py`：純 uasyncio 腳本，跑 10 秒資料流期間同時計數 ticker，結束後再讀 firmware 與參數，用來驗證「等待不阻塞」與「設定作業可獨立執行」。③ `tests/README.md` 的檔案表新增兩列，明確標示 PC 專用與板上用。
- **影響：**只新增工具與文件；驅動未變。
- **驗證：**`py_compile` 通過；桌面 `test_ld2410c_aio.py` 11 項仍通過。板上待實測。
- **部署／回復：**上傳 `tests/esp32_ld2410_aio_smoke.py` 與 `hardware/ld2410c_aio.py`，在 REPL 執行 `run(10)`。回復時刪除該腳本並保留本紀錄。

## CHG-20261124-077｜新增 asyncio 驅動層 LD2410CAsync 與「設定作業獨立」範例

- **類別：**需求變更（架構）。
- **日期／紀錄時間：**2026-11-24 01:20:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**專案架構以 asyncio 為主，但 `hardware/ld2410c.py` 是純同步（0 個 async/await），`read()` 與命令會阻塞 0.4–1 秒，會拖慢 LED（200 ms 節奏）、Web 與 MQTT。使用者要求底層驅動必須支援 asyncio，並要求「設定參數」為獨立作業，因為判斷必須以設定為依據。
- **作法：**① 新增 `hardware/ld2410c_aio.py`（repo 與工作區各一份）：`LD2410CAsync` 繼承同步驅動，僅重寫等待部分——`read_async()`、`send_async()`、`_wait_ack_async()`、`enter/exit_config_async()`、`_configured_async()`、`read_params_async()`、`write_params_async()`、`firmware_version_async()`、`read_resolution_async()`、`engineering_async()`、`restart_async()`；封包編碼與解析仍沿用核心，協定只有一份。② 新增 `examples/05_async.py`：`RadarSession` 以 `asyncio.Lock` 保護 UART，`configure()` 為獨立設定作業，`stream()` 在 `ready` 之前拒絕判斷。③ 新增 `tests/test_ld2410c_aio.py`（11 項）。
- **影響：**同步驅動與既有 28 項測試不變；新程式可改用 `LD2410CAsync`。`set_baudrate`／`set_resolution`（需重啟）尚未提供 async 版本，仍可用同步呼叫於設定階段。
- **驗證：**`python -B tests/test_ld2410c_aio.py` → 11 項通過，含「等待期間其他任務仍能執行」的非阻塞驗證、ACK 逾時重試、狀態錯誤、參數讀寫與回讀驗證、firmware 解碼、finally 送出結束設定。`py_compile` 通過。
- **部署／回復：**上傳 `hardware/ld2410c_aio.py`（裝置根目錄的 hardware/）與 `examples/05_async.py`；以 `uasyncio.run(main())` 執行。回復時刪除兩個新檔並保留本紀錄。

## CHG-20261123-076｜修正 write_test 的 __repr__（改用 tally()）並記錄寫入測試通過

- **類別：**BUG（測試程式）。
- **日期／紀錄時間：**2026-11-23 18:40:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**`CHG-20261123-075` 為 `Report` 加了 `__repr__`，但呼叫了不存在的 `counts()`（本檔的方法名是 `tally()`）。實機跑完 `run()` 後，REPL 顯示回傳值時拋出 `AttributeError: 'Report' object has no attribute 'counts'`。
- **作法：**`LD2410_repo/micropython/tests/esp32_ld2410_write_test.py` 的 `__repr__` 改為呼叫 `self.tally()`。
- **影響：**僅顯示層；測試判定與寫入/還原流程不受影響。
- **驗證：**`py_compile` 通過；以 CPython 載入模組並建立 Report，輸出 `<Report PASS=1 WARN=0 FAIL=1 SKIP=0>`。實機 `run()` 先前已通過 6 項：工程模式開啟/關閉、解析度讀取（0.75 m/門）、參數備份、寫入回讀 verified=True diff=0、還原回讀 verified=True diff=0。
- **部署／回復：**重新上傳 `tests/esp32_ld2410_write_test.py` 即可；回復時移除 `__repr__` 並保留本紀錄。

## CHG-20261123-075｜修正 write_test 的資料流誤判（單次 poll → 等待 frame）

- **類別：**BUG（測試程式）。
- **日期／紀錄時間：**2026-11-23 18:25:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**在 S2 Mini 執行 `esp32_ld2410_write_test.py` 的 `run()` 時，一開機就印「沒有資料流」並中止，但同一組接線先前已能穩定收到 10 Hz。原因是 `run()` 只呼叫一次 `radar.poll()` 就檢查 `radar.frame`；soft reboot 後 UART 緩衝為空，那一瞬間拿不到完整 frame，造成誤判。
- **作法：**在 `LD2410_repo/micropython/tests/esp32_ld2410_write_test.py` 新增 `_wait_for_frame(radar, timeout_ms=1500)`，以 20 ms 間隔等待第一個完整資料框，`run()` 改用它；訊息改為「1.5 秒內沒有完整 frame」。另外為 `Report` 加上 `__repr__`，避免 REPL 印出 `<Report object at ...>`。
- **影響：**只影響這支實機測試腳本；驅動與其他腳本未變（`check.py`／`full_test.py`／`smoke.py` 本來就是連續輪詢數秒，無此問題）。
- **驗證：**`py_compile` 通過；repo 驅動測試 `28 passed, 0 failed`。實機待重跑。
- **部署／回復：**重新上傳 `tests/esp32_ld2410_write_test.py` 後執行 `run()`。回復時改回單次 `poll()` 並保留本紀錄。

## CHG-20261123-074｜記錄 LD2410B 第 3 腳為 UART_RX（實測接 GPIO36）

- **類別：**需求變更（文件與腳位知識）。
- **日期／紀錄時間：**2026-11-23 16:50:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**使用者要在文件中明確記錄「LD2410B 第 3 腳接在 S2 Mini 的 GPIO36」，並確認該腳是否為 RX。依 UART 交叉原則（ESP32 TX 接模組 RX）與命令通道實測成功，可判定第 3 腳為 RX。
- **作法：**在 `元件/01_毫米波雷達/LD2410B_LD2410C_接線與實測記錄.md` 第 11 節新增「記憶法」段落：LD2410B 的中間腳（第 3 腳）為 `UART_RX`，從任一端數都相同；LD2410C 的中間腳反而是 `OUT`，其 RX 在第 4 腳；並記錄 S2 Mini 上第 3 腳接 GPIO36 的實測結果。
- **影響：**僅文件。日後換模組時可依「中間腳」快速判斷，避免把 C 的 OUT 接到 ESP32 TX。
- **驗證：**依 2026-11-23 S2 Mini 實測：資料流 10 Hz、`firmware V2.68.24073110`、`current_config()` 回 8／8／5 秒；命令成功即證明 GPIO36（ESP32 TX）所接的模組腳為 RX。
- **部署／回復：**文件隨版控發布；回復時移除該段落並保留本紀錄。

## CHG-20261123-073｜S2 Mini 實測通過：命令通道恢復，0x00FF 無 ACK 判定為接線問題

- **類別：**BUG（結案）＋ 需求變更（硬體驗證紀錄）。
- **日期／紀錄時間：**2026-11-23 16:40:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**先前在 ESP32-S3（GPIO15／16／14）上，資料流正常但所有命令都 `ACK timeout: 0x00ff`。改用 ESP32-S2 Mini（TX=GPIO36、RX=GPIO38、OUT=GPIO40）後，同一份驅動與同一顆 LD2410C 立即恢復。
- **作法：**① `LD2410_repo/micropython/tests/ISSUE-20261123-uart-tx-ack.md` 標記為「已解」，寫入實測數據與原因判定。② 工作區文件第 11 節新增「S2 Mini 實測結果」表。③ 未修改驅動或設定值。
- **影響：**命令層（`write_params()`、`set_resolution()`、工程模式、`set_baudrate()`）在 S2 Mini 上可正常使用；`apps/elder_care` 的參數調整不再只能靠手機 APP。
- **驗證：**S2 Mini 實機：資料流 30 frames / 3.0 秒 = 10.0 Hz；OUT 可切換；`firmware_version()` 回 `V2.68.24073110`；`current_config()` 回 max gate 8（moving 8、stationary 8）、no-target 5 s，與 2026-11-21 用 PC 工具寫入的值一致——同時驗證了參數解碼的位元組偏移。桌面測試仍為 repo 28 項、工作區 52 項全部通過。
- **部署／回復：**S2 Mini 需上傳 `config.py`（36／38／40）與 `hardware/ld2410c.py`；測試腳本已改為 config 優先，無需再改常數。回復僅需改回原板子的腳位。

## CHG-20261123-072｜雷達腳位改為 ESP32-S2 Mini（GPIO36／38／40）

- **類別：**需求變更（硬體設定）。
- **日期／紀錄時間：**2026-11-23 16:05:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**使用者要把 LD2410 整合到 ESP32-S2 Mini，改用 GPIO36／38／40 接模組的 TX／RX／OUT；原設定 15／16／14 是 ESP32-S3 的腳位。
- **作法：**`config.py` 與 `config.example.py` 的 `LD2410B_TX_PIN`／`RX_PIN`／`OUT_PIN` 改為 36／38／40，並加註 S2 Mini 的腳位限制（26–32 為 flash/PSRAM、39–42 為 JTAG、OUT 可用 GPIO34 替代）。`LD2410B_BAUDRATE` 維持 115200（模組已由 APP 改為 115200）。文件新增第 11 節「板子更換：ESP32-S2 Mini」，列出 B／C 兩種模組的對應腳位。
- **影響：**讀取路徑與照護服務不受影響（`hardware/ld2410.py` 相容層提供的 poll／snapshot／current_config／firmware_version／presence／out_level 皆與新驅動 `hardware/ld2410c.py` 相容）。已確認工作區內沒有呼叫已移除的 `set_max_distance_and_timeout`／`set_gate_sensitivity` 或舊私有 frame 方法的程式。
- **驗證：**`python -B -c "import config" ` 讀出 TX=36、RX=38、OUT=40、baud=115200；`python -B -m unittest discover -s tests` 52 項通過。**尚未實機驗證** S2 Mini 上的資料接收。
- **備註：**期間發現工作區的驅動已改為 `hardware/ld2410.py`（相容層）＋ `hardware/ld2410c.py`（實作），且 `tests/test_ld2410.py` 與 `tests/esp32_ld2410_*.py` 已不在本工作區。曾依舊 API 重建 `tests/test_ld2410.py`，因 API 不符導致 18 項錯誤，已立即移除，測試回到 52 項全綠。
- **部署／回復：**上傳 `config.py`（含 `hardware/ld2410c.py`、`hardware/ld2410.py`）。回復時把三個腳位改回 15／16／14，並保留本紀錄。

## CHG-20261120-071｜重構完整測試程式：以每次執行的 Report 物件取代模組層結果清單

- **類別：**BUG（測試程式架構）。
- **日期／紀錄時間：**2026-11-20 02:35:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**`CHG-20261120-070` 只在 `run()` 開頭加 `del RESULTS[:]`，是打補丁；根因是測試結果存放在模組層共用清單，任何呼叫順序都可能造成跨次殘留，也讓 `run()` 無法安全地被重複呼叫或巢狀使用。
- **作法：**移除模組層 `RESULTS` 與全域 `record()`，改為 `Report` 類別（`record()`、`counts()`、`names_with()`、`summary()`）。`run()` 每次建立新的 `Report` 並傳給 `show_configuration`／`test_stream`／`test_live`／`test_snapshot_semantics`／`test_encoder`／`test_commands`，最後印出總表並**回傳該 Report**，呼叫端可用 `report.counts()['FAIL']` 做自動判斷。輸出格式與檢查內容不變。
- **影響：**測試程式內部結構變更；對外行為（輸出與判定）相同。`run()` 現在可安全連續呼叫，且每次只統計該次結果。
- **驗證：**① `python -B -m py_compile tests/esp32_ld2410_full_test.py` 通過。② 桌面以 CPython 驗證隔離性：第一份 Report 記 2 PASS + 1 FAIL、第二份記 1 PASS，兩者計數互不影響，`isolated: True`。③ `python -B -m unittest discover -s tests` 71 項通過。尚未在裝置上重跑。
- **部署／回復：**重新上傳 `tests/esp32_ld2410_full_test.py`；單次 `run()` 應顯示 `PASS=6 FAIL=2` 並列出 `FAIL 項目: firmware_version(), current_config()`。回復時改回模組層清單版本，並保留本紀錄。

## CHG-20261120-070｜修正完整測試程式的結果累加與失敗項目顯示

- **類別：**BUG（測試程式）。
- **日期／紀錄時間：**2026-11-20 02:20:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**使用者回報總表顯示 `PASS=12 FAIL=4`，但畫面上只有 2 項 FAIL。原因是 `RESULTS` 為模組層清單，`run()` 每次呼叫都往同一個清單累加，連續執行兩次即變成兩輪合計。
- **作法：**`tests/esp32_ld2410_full_test.py` 的 `run()` 開頭加入 `del RESULTS[:]`，確保每次執行從空白結果表開始；`summary()` 在總表後列出 FAIL／WARN 的項目名稱，避免還要回頭找明細。
- **影響：**只影響測試程式的輸出統計，driver 與照護服務未變。
- **驗證：**`python -B -m py_compile tests/esp32_ld2410_full_test.py` 通過。依程式邏輯推算，重新上傳後單次 `run()` 應顯示 `PASS=6 FAIL=2`，並列出 `FAIL 項目: firmware_version(), current_config()`。尚未在裝置上重跑。
- **部署／回復：**重新上傳 `tests/esp32_ld2410_full_test.py`；回復時移除重置與項目列表，並保留本紀錄。

## CHG-20261120-069｜記錄參數設定策略：現階段改用 BLE APP，UART 命令列為延後項

- **類別：**需求變更（決策與文件）。
- **日期／紀錄時間：**2026-11-20 01:20:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**使用者提出「製造商已提供 BLE APP 調參，似乎沒必要堅持 UART TX」。經核對，廠商並未移除 UART 命令（協議 V1.08 仍維護、PC 工具與 Arduino 函式庫皆使用），命令不通屬本機線路／腳位問題；但以目前單台教學專案而言，確實不構成阻礙。
- **作法：**在 `apps/elder_care/README.md` 新增「參數設定策略」章節：說明現階段改用 HLKRadarTool（下載連結、廣播名、預設密碼、可調項目）、設定後必須人工記錄的表格（固件版本、兩個最大門、18 個靈敏度、無人延時、解析度、工程模式）、以及 UART 命令的取捨與三個值得回頭修的時機。未變更程式。
- **影響：**文件新增；`hardware/ld2410.py` 的命令編碼與 `set_*` API 保留不動，待線路修好即可使用。
- **驗證：**僅文件與決策紀錄，未新增硬體測試。既有的 71 項單元測試與 LD2410C 資料流驗證（10 Hz）不受影響。
- **部署／回復：**文件隨版控發布；回復時移除該章節並保留本紀錄。

## CHG-20261120-068｜記錄 LD2410C 的資料接收驗證（命令通道仍未通）

- **類別：**需求變更（驗證紀錄）。
- **日期／紀錄時間：**2026-11-20 01:10:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**使用者換用 LD2410C 並要求確認「ESP32 的 UART RX 能收到模組資料」即可，不需再追命令通道。
- **作法：**以 `tests/esp32_ld2410_full_test.py` 的 `run()` 在 LD2410C 上執行，記錄資料流、OUT 一致性、快照語義、命令編碼與命令通道的結果；文件第 4 節實測記錄新增一列。
- **影響：**僅文件與紀錄，程式未變。
- **驗證：**LD2410C 實機結果：資料流 **50 frames / 5.0 秒 = 10.0 Hz**、moving 30–140 cm、狀態 50 筆皆 moving_and_stationary；OUT 與 target_state 一致 0/10；快照 302 ms 轉 unknown；命令編碼四組全對；`firmware_version()`／`current_config()` 仍為 `ACK timeout: 0x00ff`。總計 PASS=6、FAIL=2（兩項皆命令通道）。
- **部署／回復：**文件隨版控發布；回復時移除該列並保留本紀錄。

## CHG-20261119-067｜將照護應用集中至 apps/elder_care 子目錄

- **類別：**需求變更（專案結構整理）。
- **日期／紀錄時間：**2026-11-19 23:40:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**照護相關程式原本散在 `services/` 與專案根目錄（兩個 demo），與一般服務混在一起不易辨識。使用者要求把應用程式與紀錄集中在一個子目錄。
- **作法：**新增 `apps/` 與 `apps/elder_care/`（含 `__init__.py`）。移動 `services/radar_care.py` → `apps/elder_care/radar_care.py`、`services/bed_monitor.py` → `apps/elder_care/bed_monitor.py`；`radar_care_demo.py` → `apps/elder_care/care_demo.py`、`radar_bed_demo.py` → `apps/elder_care/bed_demo.py`。新增 `apps/elder_care/README.md` 作為設計紀錄（安裝位置與距離帶、事件表、三級告警、校準步驟、限制）。測試檔維持在 `tests/`，僅把 import 改為 `apps.elder_care.*`，確保 `python -B -m unittest discover -s tests` 仍涵蓋全部測試。demo 的 import 改為「先試套件路徑、失敗則把 `apps/elder_care` 加入 `sys.path`」，相容裝置上的扁平部署。`config.py`／`config.example.py` 的註解同步指向新路徑。
- **影響：**對外 import 路徑變更：`services.radar_care` → `apps.elder_care.radar_care`、`services.bed_monitor` → `apps.elder_care.bed_monitor`。裝置上需上傳新的目錄結構；demo 執行路徑改為 `apps/elder_care/*.py`。設定值未變。
- **驗證：**`python -B -m unittest discover -s tests` 共 71 項通過；`py_compile` 對四個搬移後的檔案通過；確認四個檔案已無 `services.radar_care`／`services.bed_monitor` 殘留引用。尚未在裝置上以新路徑執行 demo。
- **部署／回復：**上傳 `apps/`、`config.py`；在 REPL 以 `exec(open('apps/elder_care/bed_demo.py').read())` 執行。回復時把兩個模組搬回 `services/`、demo 搬回根目錄並還原 import，同時保留本紀錄。

## CHG-20261119-066｜地板告警改為三級升級並加入確認機制

- **類別：**需求變更（告警策略）。
- **日期／紀錄時間：**2026-11-19 22:00:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**使用者指出照護場景應「寧可報錯、不可漏報」：長輩長時間停留在地板本身即值得關注，即使可能只是做地板運動。單一門檻無法兼顧「及早提醒」與「不讓照護者疲乏」，因此需要分級與確認。
- **作法：**① `services/bed_monitor.py` 將 `floor_dwell_ms` 改為三個門檻：`floor_notice_ms`（30 秒）、`floor_alert_ms`（2 分鐘）、`floor_critical_ms`（10 分鐘），分別發出 `floor_notice`／`floor_alert`／`floor_critical`，每個等級每次地板事件只發一次；離開地板距離帶後自動重新武裝。② 新增 `acknowledge()`：照護者確認後停止本輪升級，離開地板帶後解除；`state()` 增加 `floor_acknowledged`。③ `config.py`／`config.example.py` 改為三個 `RADAR_BED_FLOOR_*` 門檻。④ 測試改寫為 4 項：三級依序觸發且不重複、站立不誤判、離開後重新武裝、確認後停止升級。
- **影響：**事件名稱由 `floor_dwell` 改為三級，尚未接入主系統，故無外部相容性問題。`floor_alerts` 計數改為只計 alert 與 critical 兩級。
- **驗證：**`python -B -m unittest discover -s tests` 共 71 項通過（原 70 + 1）。尚未實機驗證門檻是否合用。
- **部署／回復：**上傳 `services/bed_monitor.py`、`config.py`；回復時改回單一 `floor_dwell_ms` 與單一事件，並保留本紀錄。

## CHG-20261119-065｜bed_monitor 新增地板距離帶與 floor_dwell 事件

- **類別：**需求變更（功能修正與擴充）。
- **日期／紀錄時間：**2026-11-19 21:30:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**先前在對話中以「床墊厚 25 cm」估算躺床與躺地板的距離差，低估了實際值。使用者指出一般家庭床面離地約 45 cm，加上彈簧墊後至少 60 cm；依此重算，天花板安裝時「躺床」與「躺地板」的徑向距離差約 **55–75 cm**，遠大於量測誤差，足以用距離帶區分。
- **作法：**① `services/bed_monitor.py` 新增 `floor_min_cm`／`floor_max_cm`／`floor_dwell_ms` 三個參數，當目標連續停留在「地板距離帶」超過門檻時發出 `floor_dwell` 事件，並在 `state()` 增加 `on_floor`、`floor_seconds`、`floor_alerts`。② 事件命名為 `floor_dwell` 而非 fall，語義是「長時間停留在這個高度，請人工確認」，避免宣稱跌倒偵測。③ `config.py` 與 `config.example.py` 新增 3 個 `RADAR_BED_FLOOR_*` 參數。④ `tests/test_bed_monitor.py` 新增 3 項測試：門檻到才觸發且不重複、站立距離不誤判、離開帶後可重新武裝。
- **影響：**新增事件與參數，原有 turn／sit_up／leave_bed／return_bed 行為不變；尚未接入主系統。
- **驗證：**`python -B -m unittest discover -s tests` 共 70 項通過（原 67 + 新增 3）。**尚未實機驗證**：地板距離帶需依實際天花板高度與床高校準，預設值 225–255 cm 只是範例。
- **部署／回復：**上傳 `services/bed_monitor.py`、`config.py`；回復時移除三個參數與 floor 相關邏輯，並保留本紀錄。

## CHG-20261119-064｜新增床鋪監測狀態機 bed_monitor 與校準示範程式

- **類別：**需求變更（新功能）。
- **日期／紀錄時間：**2026-11-19 20:30:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**使用者要為睡眠情境實作翻身／起床／下床／回床偵測，需要可測試的狀態機，而現有 `radar_care` 只做「存在、久無活動、離床未回」的粗粒度判斷，沒有翻身與坐起的區分。
- **作法：**① 新增 `services/bed_monitor.py`：以距離帶（`bed_min_cm`／`bed_max_cm`）、移動能量門檻、基線（躺著時的平滑距離）、去抖與確認時間推論四種事件（`turn`／`sit_up`／`leave_bed`／`return_bed`）；坐起判定採「移動能量達門檻且距離相對基線改變量 ≥ `sit_up_delta_cm`」，離床判定採「距離帶連續空 `exit_confirm_ms`」。② 新增 `tests/test_bed_monitor.py`（7 項，fake clock）：躺著建立基線、翻身、去抖、坐起、離床回床、unknown 不誤判、短暫離開不算離床。③ 新增 `radar_bed_demo.py` 校準／示範程式，每 200 ms 印出距離、能量、狀態與基線。④ `config.py` 與 `config.example.py` 新增 7 個 `RADAR_BED_*` 參數。
- **影響：**新增檔案與設定；未接入 `main.py`／`tasks.py`。`bed_monitor` 與 `radar_care` 可同時使用：前者管睡眠事件，後者管存在與久無活動。
- **驗證：**`python -B -m unittest discover -s tests` 共 67 項通過（原 60 + 新增 7）；`py_compile` 對 `services/bed_monitor.py`、`radar_bed_demo.py` 通過。**尚未在實機驗證**：床鋪距離帶與 `sit_up_delta_cm` 需依實際安裝位置校準，程式目前預設值只是起始值。
- **部署／回復：**上傳 `services/bed_monitor.py`、`radar_bed_demo.py`、`config.py`，在 REPL 執行 `run(60)` 進行校準。回復時刪除兩個新檔與 `RADAR_BED_*` 設定，並保留本紀錄。

## CHG-20261119-063｜補充 radar_care 床鋪判斷的設計說明

- **類別：**需求變更（程式註解）。
- **日期／紀錄時間：**2026-11-19 20:20:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**`_in_bed_range()` 同時檢查 `stationary_distance_cm` 與 `moving_distance_cm`，若不寫明理由，後續維護者容易誤以為其中一個是多餘的，或誤以為落後一個 frame 會影響判斷。
- **作法：**在 `services/radar_care.py` 的 `_in_bed_range()` 加上 docstring：說明躺著不動時由 stationary 回報、翻身或起身時 moving 先出現；單看一個欄位會漏掉一半情境；約 100 ms 的落後對「以分鐘為單位」的規則沒有影響。僅新增說明，邏輯未變。
- **影響：**無行為變更；8 項 `test_radar_care` 測試仍通過。
- **驗證：**`python -B -m py_compile services/radar_care.py` 通過；`python -B -m unittest tests.test_radar_care` 8 項通過。
- **部署／回復：**重新上傳 `services/radar_care.py` 即可；回復時移除該 docstring 並保留本紀錄。

## CHG-20261119-062｜修正「stationary 不適合即時判斷」的過度陳述

- **類別：**BUG（文件描述不精確）。
- **日期／紀錄時間：**2026-11-19 20:10:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**使用者指出 stationary 只落後一個 frame（約 100 ms），以人的尺度已足夠即時；原文件寫成「不適合做即時判斷」，容易被理解為延遲過大，與事實不符。
- **作法：**改寫文件兩處：① 第 8.3 節把原因由「延遲」改為「語意」——stationary 描述的是靜止目標、快速移動時單一 frame 位移可達數十公分、能量為 0 時距離為殘值；明確寫出 100 ms 對人類尺度與分鐘級照護門檻都不是問題。② 第 4 節的實測觀察同步改寫，避免沿用舊說法。
- **影響：**僅文件敘述修正，程式與參數未變；`services/radar_care.py` 的床鋪範圍判斷本來就同時檢查 stationary 與 moving，不受影響。
- **驗證：**以既有實測數據重新檢視：stationary 落後恰為一個 frame（10 Hz 下 100 ms），且 0.6 s 時 moving=75、stationary=137 的差值來自「靜止目標」語意而非延遲。未新增硬體測試。
- **部署／回復：**文件隨版控發布；回復時改回舊敘述並保留本紀錄。

## CHG-20261119-061｜新增獨居長者照護規則服務 radar_care 與示範程式

- **類別：**需求變更（新功能）。
- **日期／紀錄時間：**2026-11-19 20:05:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**使用者依 HLK 官方應用場景（人體感應燈控、生命防護、智慧安防等）挑選適合獨居長者照護的功能。經評估，現有雷達資料（距離、能量、目標狀態、OUT）已足以實作「久無活動」「離床未回」「夜間起身照明」三項，且不依賴尚未打通的命令通道（0x00FF 無 ACK，無法調參數）。
- **作法：**① 新增純邏輯服務 `services/radar_care.py`：輸入雷達 snapshot，輸出事件（movement／wake_up／night_light／inactivity／bed_exit_overdue／away_too_long）與狀態（present、in_bed、idle_seconds、次數統計）；通訊逾時（state=unknown）不視為無人，計時器照常累計。② 新增 `tests/test_radar_care.py`（8 項，fake clock）覆蓋去抖、夜間判定、告警只觸發一次、回床／回房解除、unknown 語義、每日計數。③ 新增 `radar_care_demo.py` 獨立示範程式（直接控制 RGB LED，與 `ld2410b_bed_monitor_test.py` 相同模式，不可與 `main.py` 同時執行）。④ `config.py` 與 `config.example.py` 新增 12 個 `RADAR_CARE_*` 門檻值。
- **影響：**新增檔案與設定；尚未接入 `main.py`、`tasks.py`、`web_server.py` 或 MQTT，因此不影響既有 LED single-owner 流程。事件設計為純資料，日後可由任務層轉成 LED 命令、Web API 或 MQTT 訊息。
- **驗證：**`python -B -m unittest discover -s tests` 共 60 項通過（原 52 + 新增 8）；`py_compile` 對 `services/radar_care.py`、`radar_care_demo.py` 通過。尚未在 ESP32 實機執行示範程式。
- **部署／回復：**上傳 `services/radar_care.py`、`radar_care_demo.py`、`config.py` 後，在 REPL 執行 `exec(open('radar_care_demo.py').read())` 再 `run(300)`。回復時刪除兩個新檔與 `RADAR_CARE_*` 設定，並保留本紀錄。

## CHG-20261119-060｜記錄 LD2410B 完整功能測試實機結果

- **類別：**需求變更（驗證紀錄）。
- **日期／紀錄時間：**2026-11-19 19:55:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**以 `tests/esp32_ld2410_full_test.py` 在 ESP32 + LD2410B 上完成一次端到端測試，需把結果留檔，作為「已驗證」與「未驗證」的分界。
- **作法：**文件第 4 節新增完整功能測試表（八個項目與數據），並補上兩個使用觀察：`stationary` 在快速移動時會跳動（0.6 s、1.8 s 兩個例子）、`detection_distance` 為變動值而非設定值。
- **影響：**僅文件新增，程式與設定未變。
- **驗證：**實機輸出：組態 PASS、資料流 50 frames / 5.0 s = 10.0 Hz、距離 69–123 cm、狀態分佈 39/11、OUT 一致 0/10、快照 ok→unknown（302 ms）、命令編碼四組全對、命令通道兩項 `ACK timeout: 0x00ff`；總計 PASS=6、FAIL=2。桌面 `python -B -m unittest discover -s tests` 52 項通過。
- **部署／回復：**文件隨版控發布；回復時移除該表並保留本紀錄。

## CHG-20261119-059｜新增 LD2410 完整功能測試程式 esp32_ld2410_full_test.py

- **類別：**需求變更（測試工具）。
- **日期／紀錄時間：**2026-11-19 19:45:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**先前 `selfcheck()`、`command_probe()`、`check.py` 各自只驗證片段功能，缺少一支能一次涵蓋「距離實際數值、狀態、OUT、快照語義、命令編碼、命令通道」並輸出 PASS／WARN／FAIL 總表的端到端測試。
- **作法：**新增 `tests/esp32_ld2410_full_test.py`，`run(stream_seconds=5, ticks=10, interval_ms=200)` 依序執行：① 組態與腳位檢查；② 資料流統計（frames、Hz、moving／stationary 距離範圍、狀態分佈）；③ 即時讀值逐筆印出 distance／energy／detect／out 實際數字；④ OUT 與 `target_state` 一致性統計；⑤ 快照新鮮度語義（`stale_after_ms` 暫時設 100 ms，停 300 ms 後應由 `ok` 轉 `unknown`）；⑥ 命令編碼比對原廠範例（0x00FF、0x00FE、0x0060、0x0064 與 ACK 推算，不送出）；⑦ 命令通道（僅 `firmware_version()` 與 `current_config()`）。最後印出 PASS／WARN／FAIL／SKIP 總表與 driver stats。
- **影響：**新增測試檔案，不改 driver 與設定。程式只送查詢類命令，不會寫入門檻或靈敏度。
- **驗證：**桌面以 CPython 載入 `hardware/ld2410.py`（dummy UART）比對四組命令框，與原廠 PDF 範例逐一位元組相符（enter／exit／setmax／gate 全部 OK，ACK 推算 `ff 01` 正確）；`python -B -m py_compile` 通過；`python -B -m unittest discover -s tests` 52 項通過。實機尚未執行，命令通道預期仍為 FAIL。
- **部署／回復：**上傳 `tests/esp32_ld2410_full_test.py` 至裝置根目錄，執行 `exec(open('esp32_ld2410_full_test.py').read())` 後呼叫 `run()`；回復時刪除該檔並保留本紀錄。

## CHG-20261119-058｜寫入 LD2410B 的最終確認接線表

- **類別：**需求變更（文件）。
- **日期／紀錄時間：**2026-11-19 19:35:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**使用者提供並要求確認最終接線：Pin-1 VCC→5V、Pin-2 GND→GND、Pin-3 UART_RX→GPIO15、Pin-4 UART_TX→GPIO16、Pin-5 OUT→GPIO14。五項皆有實測依據。
- **作法：**文件新增第 3 節「確認的接線（LD2410B）」，逐腳列出功能、接到的 GPIO 與驗證方式，並附對應的 `config.py` 設定；原「實測記錄」順移為第 4 節，其後章節編號依序調整。
- **影響：**文件結構變更，程式與設定未動。
- **驗證：**每一項均對應先前實機量測：Pin-4 有 10 Hz 資料、Pin-5 由 1 變 0、Pin-1/2 由模組可運作推得、Pin-3 方向正確但命令尚未送達。未新增硬體測試。
- **部署／回復：**文件隨版控發布；回復時移除該節並還原章節編號，保留本紀錄。

## CHG-20261119-057｜確認 LD2410B 的 OUT 實際接線並修正相關提示

- **類別：**BUG（文件與診斷訊息誤導）。
- **日期／紀錄時間：**2026-11-19 19:30:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**先前依據照片推論「4 線排線未帶 OUT」，因此把 `out_level()` 的 `True` 判定為浮接值。使用者指出 OUT 實際有接；實測以 `Pin(14, Pin.IN)` 每 200 ms 取樣，離開偵測範圍後由 1 變 0 並穩定維持，再回到範圍內會變回 1，證明是推挽輸出而非浮接。
- **作法：**① 文件第 3 節新增「LD2410B 的 OUT 已驗證」段落，記錄取樣結果與判讀依據，並移除「4 線排線」的錯誤推論。② `tests/esp32_ld2410_check.py` 的 OUT 提示由「未接 OUT、浮接不可信」改為「離開偵測範圍觀察 1→0，會穩定切換代表確實有接」。
- **影響：**`config.py` 的 `LD2410B_OUT_PIN = 14` 維持不變；`out_level()` 與 `presence()` 可視為可信來源。僅文件與診斷訊息變更，driver 行為未動。
- **驗證：**實機取樣 40 筆（每 200 ms）：774505–775506 為 1，775706 起轉為 0 並持續到 782308；符合人員離開偵測範圍的行為。`python -B -m py_compile tests/esp32_ld2410_check.py` 通過。
- **部署／回復：**重新上傳 `tests/esp32_ld2410_check.py`；文件隨版控發布。回復時改回舊提示並保留本紀錄。

## CHG-20261119-056｜更正 LD2410B 腳位順序（Pin-3=RX、Pin-4=TX）並記錄命令通道現況

- **類別：**BUG（文件腳位錯誤）。
- **日期／紀錄時間：**2026-11-19 19:15:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**先前文件與對話沿用「LD2410B 由 VCC 端數為 VCC/GND/TX/RX/OUT」，導致命令一直送進模組的 TX 腳而永遠等不到 ACK。實測顯示資料是從 GPIO16 進入，而 GPIO16 接的是 Pin-4，因此 Pin-4 必為模組的 UART_TX，Pin-3 為 UART_RX。
- **作法：**更新 `元件/01_毫米波雷達/LD2410B_LD2410C_接線與實測記錄.md`：① 2.1 節 B 模組順序改為 `VCC、GND、RX、TX、OUT`；② 加上判定依據與「先前寫法錯誤」的說明；③ 2.3 對照表 B 欄的 TX／RX 互換；④ 第 3 節實測記錄改為「資料流成功、命令通道失敗」並附數據；⑤ 新增「LD2410B 命令通道的現況」段落，列出已排除與未排除的原因。
- **影響：**文件與實機一致。程式（`config.py` 的 TX=15／RX=16）不需變更——方向本來就正確，錯的是模組端腳位的標註。
- **驗證：**依 `tests/esp32_ld2410_check.py` 的實機輸出判定：資料流 30 frames / 3 秒 = 10 Hz、距離 217 cm；命令通道 `firmware` 與 `config` 皆 `ACK timeout: 0x00ff`；GPIO15↔GPIO16 loopback 可收回 14 bytes。尚未定位是排線或模組 RX。
- **部署／回復：**文件隨版控發布；回復時改回舊版腳位表並保留本紀錄。

## CHG-20261119-055｜新增一次性接線與驅動自檢程式 esp32_ld2410_check.py

- **類別：**需求變更（診斷工具）。
- **日期／紀錄時間：**2026-11-19 19:05:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**實測出現「資料流正常、命令通道無 ACK」，且腳位方向（模組 Pin-3 究竟是 TX 或 RX）在對話中一度混亂。需要一支以 driver 為基礎、只讀不寫、能同時驗證資料流／OUT／命令並給出結論的程式。
- **作法：**新增 `tests/esp32_ld2410_check.py`：`run()` 依次印出接線規則（ESP32 TX → 模組 RX、ESP32 RX ← 模組 TX；LD2410B 由 VCC 端數為 VCC/GND/RX/TX/OUT）、以 `poll()` 統計 frames 與距離範圍、讀取 OUT、以 `firmware_version()` 與 `current_config()` 驗證命令通道（全部只查詢，不寫入設定），最後給出「資料流 / 命令通道」兩行結論與下一步檢查清單。
- **影響：**新增診斷檔案，不改 driver。因只呼叫查詢類命令，失敗時不會改動模組設定。
- **驗證：**`python -B -m py_compile` 通過；`python -B -m unittest discover -s tests` 52 項通過。尚未在裝置端執行。
- **部署／回復：**上傳 `tests/esp32_ld2410_check.py` 後在 REPL 執行 `exec(open('esp32_ld2410_check.py').read())` 再 `run()`；回復時刪除該檔並保留本紀錄。

## CHG-20261119-054｜command_probe() 加入回音辨識，區分「自己的命令」與「模組 ACK」

- **類別：**需求變更（診斷工具）。
- **日期／紀錄時間：**2026-11-19 17:50:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**實機執行 `command_probe()` 得到 `command frames: 1`，但收到的框與送出的框完全相同（`04 00`、命令字 `ff 00`），且 `data frames: 0`。這是 GPIO15／16 短接造成的回音，不是模組 ACK；原始輸出容易被誤讀成「模組回應了」。
- **作法：**`tests/esp32_ld2410_smoke.py` 的 `command_probe()` 逐框比對是否等於送出的 frame，統計 `echoes`，並在「只收到回音」時直接印出判讀提示（提示真正的 ACK 應為 `08 00 ff 01 00 00 …`）。
- **影響：**只影響診斷輸出，不改 driver。文件第 9.3 節後補一行說明回音的判讀方式。
- **驗證：**`python -B -m py_compile tests/esp32_ld2410_smoke.py` 通過。依實機輸出（`fd fc fb fa 04 00 ff 00 01 00 04 03 02 01` 原樣回傳、`data frames: 0`）判定為 TX/RX 短接或模組訊號線未接；尚未取得重新接線後的結果。
- **部署／回復：**重新上傳 `tests/esp32_ld2410_smoke.py`；回復時移除 echo 統計與提示即可。

## CHG-20261119-053｜測試程式改為不自動執行，並補上裝置端執行步驟

- **類別：**需求變更（測試程式可用性與文件）。
- **日期／紀錄時間：**2026-11-19 17:40:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**使用者在 Thonny Shell 以 `exec(open('esp32_ld2410_smoke.py').read())` 載入測試程式時，因檔案結尾的 `if __name__ == '__main__': run()` 立即執行完整 20 秒流程（selfcheck → info → raw → stream），才輪到想呼叫的 `command_probe()`，造成混淆與多餘等待。
- **作法：**移除 `tests/esp32_ld2410_smoke.py` 的自動執行區塊，改為載入時印出一行可用函式提示；各功能改由使用者明確呼叫。文件新增第 9 節「在 ESP32 上執行測試程式（Thonny）」：裝置端檔案配置、上傳步驟、各函式耗時對照、以及不用 Thonny 時的 `mpremote` 指令。
- **影響：**`exec()` 載入後不再自動跑 `run()`；若要完整流程仍可手動呼叫 `run()`。桌面端不受影響（本檔不在 unittest 清單內）。
- **驗證：**`python -B -m py_compile tests/esp32_ld2410_smoke.py` 通過；`python -B -m unittest discover -s tests` 52 項通過。尚未在裝置端重新執行。
- **部署／回復：**重新上傳 `tests/esp32_ld2410_smoke.py` 即可；回復時把 `if __name__ == '__main__': run()` 加回，並保留本紀錄。

## CHG-20261119-052｜新增 command_probe() 診斷命令通道，確認 0x00FF 無 ACK

- **類別：**需求變更（診斷工具）。
- **日期／紀錄時間：**2026-11-19 16:55:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**實機執行 `info()` 時 `firmware_version()` 與 `current_config()` 都回 `LD2410 ACK timeout: 0x00ff`，但資料串流正常（15 秒 150 frames、距離 30–154 cm、OUT 正常）。需要分辨「命令沒送到模組」與「ACK 有回但比對失敗」。
- **作法：**在 `tests/esp32_ld2410_smoke.py` 新增 `command_probe()`：繞過 ACK 比對，直接送出 `0x00FF` 原始命令框，印出 `uart.write()` 回傳值，並統計之後 800 ms 內收到的是命令框（`FD FC FB FA`）還是資料框，最後補送一次 `0x00FE` 讓模組回到工作模式。
- **影響：**只增加診斷函式，不改 driver 行為；需注意執行後務必讓 `0x00FE` 送出成功，否則模組會停留在設定模式並停止上報資料。
- **驗證：**已比對原廠 PDF：`0x00FF` 的成功 ACK 為 `FD FC FB FA 08 00 FF 01 00 00 01 00 40 00 04 03 02 01`，資料段前 4 bytes 為 `FF 01 00 00`，與 `_ack_command()` 的比對邏輯一致，因此 timeout 代表模組未回應而非比對錯誤。尚未取得實機的 probe 結果。
- **部署／回復：**上傳 `tests/esp32_ld2410_smoke.py` 後在 REPL 執行 `command_probe()`；回復時移除該函式即可。

## CHG-20261119-051｜實作 LD2410 參數與固件解碼、門靈敏度命令與 any() 讀取

- **類別：**需求變更（driver 功能擴充）。
- **日期／紀錄時間：**2026-11-19 16:45:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**`current_config()`／`firmware_version()` 原本只回原始位元組，設定類命令缺少門靈敏度；讀取迴圈使用無參數 `read()`，在 MicroPython 上會請求整個 RX 緩衝。原廠 PDF 與 `LD2410_repo` 已提供可核對的位元組配置。
- **作法：**① `current_config()` 依 0x0061 回傳配置解碼（0xAA 標記、最大距離門、兩個最大門、18 個靈敏度、無人延時），長度或標記不符時丟 `LD2410CommandError`。② `firmware_version()` 解出 type／major／minor／bugfix 與 `V1.07.22091516` 形式字串。③ 新增 `set_gate_sensitivity(gate, moving, stationary)`（0x0064），以 `0xFFFF` 表示全部門。④ `_read_available()` 改用 `uart.any()` + `uart.read(n)`，後端無 `any()` 時才退回無參數 `read()`。⑤ `tests/esp32_ld2410_smoke.py` 新增 `info()`，於 `run()` 中印出固件版本與門／靈敏度設定。⑥ 文件新增第 8 節命令層 API 與原廠腳位編號慣例說明。
- **影響：**`current_config()` 由回傳 bytes 改為回傳 dict（含 `raw`）；既有呼叫端需改讀欄位。其餘 API 不變。命令編碼與廠商文件一致，長度 18 bytes。
- **驗證：**`python -B -m unittest discover -s tests` 共 52 項通過（新增固件解碼、門靈敏度編碼、`any()` 讀取三項）。測試使用廠商文件範例值（config：門 8/8/8、靈敏度 20/25、無人 5 秒；firmware：V1.07.22091516）。**尚未在實機驗證**這三項命令的回傳值與寫入結果。
- **部署／回復：**上傳 `hardware/ld2410.py`、`tests/esp32_ld2410_smoke.py`；在 REPL 以 `info()` 核對。回復時改回僅回 `raw` 的版本並移除 `set_gate_sensitivity()`，保留本紀錄。

## CHG-20261119-050｜建立本機 PDF 文字擷取流程（pypdf）並排除於版控

- **類別：**需求變更（開發工具）。
- **日期／紀錄時間：**2026-11-19 16:35:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**先前無法讀取 `元件/01_毫米波雷達` 內的 5 份原廠 PDF，協定數值只能靠第三方 repo 交叉推測。`pip install pypdf` 兩次失敗，錯誤為 `Permission denied`（DSH sandbox 不允許寫入系統 Temp 與 site-packages），並非網路問題。
- **作法：**以 `--target .pdf-tools` 將 pypdf 7.1.1 安裝在工作區，並把 `TEMP`／`TMP` 指向工作區內的 `.tmp-pip`；新增 `.pdf-tools/pdf2txt.py`（pypdf → UTF-8 文字檔）與 `extract.py`。`.gitignore` 加入 `.pdf-tools/`、`.tmp-pip/`，避免把第三方套件與暫存檔提交。
- **影響：**本機可將 PDF 轉為 UTF-8 文字再以一般工具檢索；不影響專案程式、設定或裝置部署。純掃描影像的 PDF 仍無文字層（例如天線罩指南 8 頁僅取到 21 行），需 OCR 才能處理。
- **驗證：**已成功將 5 份 PDF 轉出：串口通信协议 22 頁、說明書 21 頁、底噪檢測 5 頁、APP 連結 1 頁可讀；天線罩指南無文字層。並以原廠 PDF 核對出 LD2410B 官方腳位定義表（1=OUT、2=UART_Tx、3=UART_Rx、4=GND、5=VCC），與使用者「由 VCC 端起算」的編號互為反向，兩者物理順序一致。
- **部署／回復：**移除 `.pdf-tools/` 與 `.tmp-pip/` 即可；`.gitignore` 中對應兩行可一併移除。不涉及裝置。

## CHG-20261119-049｜以實機擷取 frame 建立回歸 fixture，並記錄 stationary 落後一格

- **類別：**需求變更（測試 fixture 與文件）。
- **日期／紀錄時間：**2026-11-19 16:10:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**使用者以 `hardware/ld2410.py` 連續讀取時，觀察到 `stationary_distance` 恆等於上一個 frame 的 `moving_distance`。為排除解析偏移，需以原始位元組判定；同時既有測試只用自行捏造的封包，缺少真實樣本。
- **作法：**① 將使用者提供的 10 個實機 frame（LD2410C、256000 8N1、10 Hz）以 `REAL_CAPTURE` 納入 `tests/test_ld2410.py`，新增 `_frame_from_hex()` 與兩項測試：欄位偏移驗證、stationary 落後一格的行為固定。② 文件新增第 7 節「模組資料特性」，含 10 frame 對照表、結論（模組演算法延遲，非解析問題）、`detection_distance` 語義待確認、以及「能量 0 時距離為殘值」「stationary 不適合即時反應」兩個使用陷阱。
- **影響：**測試由 47 項增至 49 項；程式行為未變更。文件對 `detection_distance` 改採「待確認」，不再沿用舊指南的「目前採用的探測距離」說法。
- **驗證：**`python -B -m unittest discover -s tests` 共 49 項通過。落後一格在原始位元組即可直接觀察（第 2 個 frame 的 stationary = 0x5f = 95 = 第 1 個 frame 的 moving），因此判定為模組行為而非 driver 解析錯誤。尚未驗證：長時間穩定性、其他韌體版本的相同行為、`detection_distance` 確切語義。
- **部署／回復：**測試與文件隨版控發布，無需上傳裝置。回復時移除 `REAL_CAPTURE` 與該兩項測試、刪除文件第 7 節，並保留本紀錄。

## CHG-20261119-048｜同步 LD2410B 的 TX／RX 設定為 15／16，並讓測試與文件以 config 為準

- **類別：**需求變更（硬體設定）＋ BUG（測試寫死腳位、公開範本未同步）。
- **日期／紀錄時間：**2026-11-19 16:15:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**使用者以 LD2410B 實測成功，並將 `config.py` 改為 `LD2410B_TX_PIN = 15`、`LD2410B_RX_PIN = 16`。此設定使 GPIO16 成為 ESP32 的 RX，正好符合 LD2410B 的「Pin-3 TX → GPIO16」，也解釋了先前接線表與 `config.py` 的矛盾。
- **作法：**① `config.example.py` 同步為 `TX=15`、`RX=16`（AGENTS.md 要求非機密設定同步）。② `tests/test_ld2410.py` 的建構參數測試改為由 `config` 推導 `tx`／`rx`，不再寫死 16／15，避免同類不一致再次發生。③ 改寫 `元件/01_毫米波雷達/LD2410B_LD2410C_接線與實測記錄.md`：以 `config.py` 為判斷基準，列出 B／C 兩種模組在同一組設定下的接線對照、兩個模組各自的針腳順序、以及「換模型或改 TX／RX 後必須重新核對」的檢查順序。
- **影響：**預設接法變更為「模組 TX → GPIO16、模組 RX → GPIO15」。原本以 `TX=16`／`RX=15` 接線的 LD2410C 若沿用舊接法會變成 TX 對 TX，需改接（C 的 Pin-5 → GPIO16、Pin-4 → GPIO15）或把設定改回。程式邏輯未變。
- **驗證：**`python -B -m unittest discover -s tests -v` 共 47 項通過（含 14 項 LD2410）。LD2410B 實機成功為使用者提供之結果（2026-11-19，設定 TX=15／RX=16）；LD2410C 的實機成功記錄為較早的 TX=16／RX=15。設定命令 ACK、工程模式等仍未在實機驗證。
- **部署／回復：**上傳 `config.py`、`config.example.py`、`hardware/ld2410.py`、`tests/esp32_ld2410_smoke.py`。回復時把 `TX_PIN` 改回 16、`RX_PIN` 改回 15，並將模組兩條 UART 線對調；保留本紀錄。

## CHG-20261119-047｜修正 LD2410 接線記錄：B 與 C 的針腳順序不同

- **類別：**BUG（文件內容錯誤）＋ 需求變更（補充 LD2410B 實測接線）。
- **日期／紀錄時間：**2026-11-19 16:02:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**`CHG-20261119-046` 依「LD2410B 與 LD2410C 腳位設計相同」撰寫，但使用者補充：LD2410B 為 `VCC GND TX RX OUT`、LD2410C 為 `VCC GND OUT RX TX`（針腳朝上由左數），兩者順序不同；並提供 LD2410B 剛完成的實測接線（Pin-3 TX→GPIO16、Pin-4 RX→GPIO15、Pin-5 OUT→GPIO14）。
- **作法：**改寫並更名文件為 `元件/01_毫米波雷達/LD2410B_LD2410C_接線與實測記錄.md`：新增兩種模組各自的針腳序列、分別列出 B／C 接線表與對應 UART 設定、加入「換模組就要重新核對」的檢查順序。LD2410B 表加註唯一未定案點：表中模組 TX 接 GPIO16，但 `config.py` 將 GPIO16 視為 ESP32 TX，兩者需擇一，並列舉兩種可能與各自的解法。移除舊檔名 `LD2410C_接線與實測記錄.md`。
- **影響：**修正後的文件不再宣稱兩種模組腳位相同；程式與設定未變更。
- **驗證：**文件內容對照使用者提供的兩組接線與本次對話量測（LD2410C：GPIO15 收到資料框、GPIO14 OUT 變化）。LD2410B 的 TX／RX 方向與 `config.py` 的一致性仍未定案，文件中標為待確認，未宣稱單一結論。
- **部署／回復：**文件隨版控發布；回復時改回 `CHG-20261119-046` 的檔名與內容，並保留本紀錄。

## CHG-20261119-046｜新增 LD2410C 接線與實測記錄文件

- **類別：**需求變更（文件）。
- **日期／紀錄時間：**2026-11-19 15:38:06 +08:00，工具取得台北時間。
- **原因：**使用者提供兩天實測所得的供電與接線資訊（5V 接 VCC、GPIO 對應表），要求寫入文件保留，避免日後重複排查。
- **作法：**新增 `元件/01_毫米波雷達/LD2410C_接線與實測記錄.md`，內容包含供電要求、原廠絲印順序、使用者針腳編號表、實際跑通的接法、排查時序與教訓、待確認清單。使用者提供的針腳表以原文保留，並明確標註其 TX／RX 方向與已驗證接法相反、需以對調實驗確認，未擅自改寫成單一說法。
- **影響：**新增文件，不改程式、設定或部署。文件作為 `hardware/ld2410.py` 與 `config.py` 接線設定的說明來源。
- **驗證：**文件內容對照本次對話的量測數據（GPIO15 收到完整資料框、2 秒 253 bytes、GPIO14 OUT 取樣 `hi 211 / lo 39`、全腳位上拉掃描）。未執行新的硬體測試；TX／RX 方向尚未定案，因此文件標為「待確認」。
- **部署／回復：**文件隨版控發布；回復時刪除該檔並保留本紀錄。

## CHG-20261119-045｜將本機記憶庫目錄排除於版控之外

- **類別：**需求變更（版控規則）。
- **日期／紀錄時間：**2026-11-19 15:05:00 +08:00，工具取得台北時間。實際寫入時間以本次工具呼叫為準。
- **原因：**工作區初次建立 `.dsh-meow/memory.db` 記憶庫；該檔位於隱藏目錄、預設不進版控、誤刪無法從回收站復原，且 `git status` 已顯示為未追蹤，若執行 `git add -A` 可能被誤提交。
- **作法：**在 `.gitignore` 新增 `.dsh-meow/` 區塊並附註原因；未變更其他忽略規則。
- **影響：**記憶庫檔案不會進入版控，也不影響既有規則；若日後要把記憶資料納入備份，應使用工具自身的備份機制而非 Git。
- **驗證：**以 `git status --porcelain` 確認清單中不再出現 `.dsh-meow/`；未執行任何刪除或搬移。
- **部署／回復：**移除 `.gitignore` 中該三行即可回復；不涉及程式、設定或裝置部署。

## CHG-20261119-044｜改寫 LD2410 驅動為 ld2410.py，新增 OUT 讀取與 ESP32 實機測試程式

- **類別：**需求變更（驅動重構與實機測試程式）＋ BUG（舊驅動無法取得 OUT；命名綁定 B 版）。
- **日期／紀錄時間：**2026-11-19 14:48:55 +08:00，工具取得台北時間。
- **原因：**使用者要求依 `ncmreynolds/ld2410` 倉儲與 `元件/01_毫米波雷達` 目錄內原廠文件，重建 MicroPython driver，並提供可經 driver 取得「距離（UART）」與「OUT 值」的測試程式。排查過程中 LD2410B 的 UART 完全無輸出（疑似故障），改用 LD2410C 後才收到完整資料框。
- **現象與分析：**① `tests/test_ld2410b.py` 的 FakeUART 會依 `_ack_command()` 自行捏造 ACK，因此「桌面／裝置上測試通過」與「實機無任何資料」可以同時成立，測試無法證明接線。② 實機一度讀到 `len 0`、GPIO15/16 上拉仍為 0，最後確認為腳位／接線被拉低；恢復後 GPIO15 收到 `f4 f3 f2 f1 0d 00 02 aa 02 98 00 … 55 00 f8 f7 f6 f5`，2 秒共 253 bytes。③ 以 `src/ld2410.cpp` 核對後確認 ACK 為 `命令低位, 命令高位+1, 狀態(2)`，舊驅動假設正確，先前懷疑排除。
- **作法：**`hardware/ld2410b.py` 更名為 `hardware/ld2410.py`，類別改為 `LD2410`；新增 `LD2410Timeout`、`LD2410CommandError`、`poll()`（非阻塞）、`snapshot()`（含 `age_ms` 與 `state: ok|unknown`）、`out_level()`、`presence()`、`stats()`、`current_config()`、`firmware_version()`、`set_max_distance_and_timeout()`、`engineering_mode()`、`restart()`。命令送出前先清空輸入緩衝，避免殘留 ACK 誤判；通訊失敗一律回報 `unknown`，不當成無人。保留 `hardware/ld2410b.py` 作為 shim（別名 `LD2410B`），讓 `ld2410b_bed_monitor_test.py` 不必修改。新增 `tests/esp32_ld2410_smoke.py`（`selfcheck()`、`raw()`、`stream()`、`run()`），只讀不送命令。`tests/test_ld2410b.py` 更名為 `tests/test_ld2410.py` 並擴充至 14 項；`config.py` 與 `config.example.py` 新增 `LD2410B_OUT_ACTIVE_HIGH`。
- **影響：**`from hardware.ld2410b import LD2410B` 仍可用（shim），舊教材腳本不受影響；新程式建議 `from hardware.ld2410 import LD2410`。雷達尚未接入 `main.py`、`tasks.py` 或 Web 狀態。`current_config()` 與 `firmware_version()` 只回原始位元組，不宣稱欄位偏移。
- **驗證：**桌面 `python -B -m unittest discover -s tests -v` 共 47 項全部通過，其中 LD2410 為 14 項（新增半包、假包頭、錯誤尾碼重新同步、ACK 逾時、ACK 狀態錯誤、錯誤 opcode、`poll()`、快照過期、OUT 與 presence）。`python -B -m py_compile` 對四個檔案通過。**ESP32 實機（ESP32-S3 + LD2410C）：** GPIO15 於 256000 baud 收到完整資料框，2 秒 253 bytes、`has header: True`；GPIO14（OUT）5 秒取樣為 `hi 211 / lo 39`，隨動作變化；三支腳上拉皆為 1。**尚未驗證：**實機的設定命令 ACK、工程模式、firmware／config 欄位解碼、長時間穩定性與距離精度。
- **部署／回復：**上傳 `hardware/ld2410.py`（必要時含 `hardware/ld2410b.py`、`tests/esp32_ld2410_smoke.py`、`config.py`），在 REPL 執行 `exec(open('esp32_ld2410_smoke.py').read())` 後呼叫 `run()`。回復時以 `mdy_06/hardware/ld2410b.py` 還原舊驅動並移除 `hardware/ld2410.py`；`hardware/ld2410b.py` 在本次之前為未追蹤檔案，因此更名不涉及 Git 歷史改寫。不要覆蓋私人 `config.py`。

## CHG-20261117-043｜新增 LD2410B 床邊呼吸候選與離床黃燈測試程式

- **類別：**需求變更（LD2410B ESP32 實機情境測試）。
- **日期／紀錄時間：**2026-11-17 21:37:52 +08:00，工具取得台北時間。
- **原因：**需要先驗證約 0.5 m 床邊靜止目標的雷達資料、坐起／離床造成的距離與狀態變化，以及超出床鋪範圍時的三色 LED 黃燈反應。
- **作法：**新增 `ld2410b_bed_monitor_test.py`。以 `stationary_energy` 在床鋪距離範圍內標示「呼吸候選」；以 target state 改變為移動、距離連續超出範圍兩筆確認離床，將 `RgbLed.write(6)` 設為紅綠同亮的黃色；回到床鋪範圍內並連續靜止三筆後熄燈重新武裝。床鋪範圍預設 25–100 cm，可由 `config.py` 的選用設定覆蓋。
- **影響：**新增獨立測試程式，不接入 `main.py`、`tasks.py` 或既有 LED single-owner 流程；執行期間會直接控制 RGB LED，部署主程式時不可同時執行此測試。輸出使用「呼吸候選」，不宣稱醫療呼吸監測、跌倒偵測或照護警報。
- **驗證：**已以 fake LED／fake frame smoke scenario 覆蓋約 50 cm 靜止高 stationary energy、移動且超出範圍後黃色、回床靜止後熄燈；已完成 CPython 語法檢查。尚未執行 ESP32、真實 LD2410B、床墊／姿勢、供電、接線或 LED 電氣驗證。
- **部署／回復：**將 `ld2410b_bed_monitor_test.py`、`config.py`、`hardware/ld2410b.py` 與 `hardware/led.py` 上傳至 ESP32，確認雷達 TX/RX 交叉、共地、5 V 供電與 GPIO 電位後，在 REPL 執行 `exec(open('ld2410b_bed_monitor_test.py').read())`；測試結束以 Ctrl-C 停止並熄燈。回復時移除新增測試檔即可，不要覆蓋私人 `config.py`。

## CHG-20261117-042｜修正 ESP32 MicroPython 不支援 bytearray 刪除切片

- **類別：**BUG（ESP32 執行 fake-UART 測試時封包解析在 `del bytearray[...]` 失敗）。
- **日期／紀錄時間：**2026-11-17 21:14:54 +08:00，工具取得台北時間。
- **原因：**`hardware/ld2410b.py` 的 `_extract_frame()` 使用多處 `del self._buffer[...]`；使用者實際在 ESP32 執行測試時回報 `TypeError: 'bytearray' object doesn't support item deletion`。
- **作法：**將封包緩衝區的前綴、雜訊、錯誤封包與已解析 frame 消費改為 bytearray slicing 後重新指派；建立 `mdy_06/hardware/ld2410b.py` 保存修改前版本。
- **影響：**MicroPython 可繼續執行 LD2410B 分段封包、雜訊與命令 ACK fake-UART 測試；每次消費緩衝區會建立 slicing 結果，這是為了相容 ESP32 MicroPython，協定與 frame 邊界行為不變。
- **驗證：**使用者已提供修改前 ESP32 實機錯誤；修正後需重新在同一 ESP32 執行完整 6 項測試。桌面測試與 MicroPython runner 模擬應同步執行，尚未以本紀錄宣稱新的 ESP32 實機結果。
- **部署／回復：**重新上傳 `hardware/ld2410b.py` 後 soft reboot，再執行 `exec(open('test_ld2410b.py').read())`；回復時以 `mdy_06/hardware/ld2410b.py` 還原，並保留本紀錄。

## CHG-20261117-041｜讓 LD2410B fake-UART 測試可直接在 ESP32 執行

- **類別：**BUG（ESP32 執行測試時匯入桌面專用 `pathlib` 失敗）。
- **日期／紀錄時間：**2026-11-17 20:45:30 +08:00，工具取得台北時間。
- **原因：**`tests/test_ld2410b.py` 原本在檔案載入階段匯入 `pathlib` 與 `unittest.mock`，這些模組不屬於 ESP32 的 MicroPython 執行環境；使用者需要在裝置上執行同一組 LD2410B 協定 fake-UART 測試。
- **作法：**將 `tests/test_ld2410b.py` 改為共用測試本體：桌面以 `unittest` 執行，MicroPython 以內建 runner 逐項執行並輸出 `ok`／`PASS`；以手動保存／還原模組屬性取代 `unittest.mock`，並以手動 little-endian 編碼取代 `int.to_bytes`。建立 `mdy_05/test_ld2410b.py` 保存修改前公開版本；未包含私人設定。
- **影響：**可將 `test_ld2410b.py`、`config.py`、`hardware/ld2410b.py` 與 `hardware/__init__.py`（若部署環境需要）上傳到 ESP32 後執行 fake-UART 協定測試；測試仍不驗證真實 UART 接線、GPIO 電氣、雷達偵測、供電或實機時序。
- **驗證：**桌面 `python -B -m unittest tests.test_ld2410b -v` 通過 6/6；以 CPython 保留標準匯入機制並切換 `sys.implementation.name='micropython'` 執行 MicroPython runner 分支通過 6/6；`py_compile` 通過，且測試檔不再包含 `pathlib`、`unittest.mock`、`int.to_bytes` 或 `int.from_bytes`。尚未連接並執行 ESP32 實機，不能宣稱實機通過。
- **部署／回復：**建議將測試檔上傳至裝置根目錄為 `test_ld2410b.py`，並確保 `config.py` 與 `hardware/ld2410b.py` 可匯入，再於 REPL 執行 `exec(open('test_ld2410b.py').read())`；測試完成後不需保留測試檔。回復時以 `mdy_05/test_ld2410b.py` 還原，並保留本紀錄；不要覆蓋私人 `config.py`。

## CHG-20261117-040｜新增 LD2410B 腳位組態與基本功能測試

- **類別：**需求變更（毫米波雷達硬體組態與測試）。
- **日期／紀錄時間：**2026-11-17 15:23:59 +08:00，工具取得台北時間。
- **原因：**LD2410B 已移入 `hardware/`，需要把 UART、OUT 與預設 256000 baud 的接線設定納入本專案組態，並以測試固定官方文件所述的基本通訊行為。
- **作法：**在本機 `config.py` 與公開 `config.example.py` 新增 `LD2410B_UART_ID`、`LD2410B_TX_PIN`、`LD2410B_RX_PIN`、`LD2410B_OUT_PIN` 與 `LD2410B_BAUDRATE`；目前選用尚未被既有配置使用的 GPIO 16、15、14。新增 `tests/test_ld2410b.py`，使用 fake UART 驗證正常／工程模式資料解析、雜訊與分段封包、UART 8N1 建構參數、進入／讀取／離開設定流程，以及最大距離門與無人時間命令編碼。公開原始設定快照保存於 `mdy_04/config.example.py`。
- **影響：**應用程式可依組態建立 UART1：TX=16、RX=15、OUT=14；尚未將雷達加入 `main.py`、`tasks.py` 或 Web 狀態。GPIO 選擇是依目前專案配置避開衝突的初始接線方案，仍須依實際 ESP32-S2FN4R2-S2-Mini 板腳位與接線確認。
- **驗證：**`python -B -m unittest tests.test_ld2410b -v` 通過，6 項測試全部通過。測試是桌面 fake UART；未驗證 OUT 電氣高低、UART TX/RX 實際接線、雷達偵測距離、電源、ESP32 排程或實機命令結果。
- **部署／回復：**部署前依組態將模組 TX 接 ESP32 RX、模組 RX 接 ESP32 TX，並確認 5 V 供電、共地與 3.3 V UART 電位；上傳 `config.py` 與 `hardware/ld2410b.py`。回復時移除新增組態與 `tests/test_ld2410b.py`，或依 `mdy_04/config.example.py` 還原公開範本；不要覆蓋本機私人 WiFi profiles。

## CHG-20261117-039｜將 LD2410B 驅動移至硬體抽象目錄

- **類別：**需求變更（依專案架構整理程式位置）。
- **日期／紀錄時間：**2026-11-17 15:18:24 +08:00，工具取得台北時間。
- **原因：**新增的 `driver/ld2410b.py` 不符合目前架構；專案以 `hardware/` 放置實體周邊硬體抽象，且沒有 `driver/` 層級。
- **作法：**將檔案移至 `hardware/ld2410b.py`；保留本輪原始檔快照於 `mdy_03/driver/ld2410b.py`，供學生比較與回復。
- **影響：**檔案內容與 LD2410B UART 協定行為不變；後續應用程式應由 `from hardware.ld2410b import LD2410B` 匯入。尚未將雷達整合進 `main.py` 或任務流程。
- **驗證：**已確認原始路徑不存在、目標路徑建立；`python -B -m py_compile hardware/ld2410b.py` 通過。未執行 ESP32、UART 電氣或雷達實機驗證。
- **部署／回復：**部署時將 `hardware/ld2410b.py` 上傳至 ESP32 的對應硬體模組路徑；回復時可依本輪 `mdy_03/driver/ld2410b.py` 快照還原，並同步保留本紀錄。

## CHG-20261117-038｜發布新增毫米波雷達長照應用建議文件

- **類別：**需求變更（GitHub 文件發布）。
- **日期／紀錄時間：**2026-11-17 14:03:11 +08:00，工具取得台北時間。
- **原因：**使用者通知 `元件/01_毫米波雷達` 新增一份文件，要求再次同步至 GitHub。
- **作法：**納入 `LD2410B_銀髮居家照護應用方向_建議作法.md`；未修改文件內容，未納入其他目錄的工作區修改或未追蹤檔案。
- **影響：**GitHub `main` 將新增 LD2410B 銀髮居家照護應用、感測限制與整合建議文件；不改變 ESP32 韌體、設定、部署清單或私人 WiFi profiles。
- **驗證：**確認該文件位於指定目錄且不含私人 WiFi profiles；提交前檢查限定路徑的 staged diff，推送後以 `git ls-remote origin refs/heads/main` 核對遠端提交。未執行文件內容的硬體、ESP32 實機或醫療／長照場域驗證。
- **部署／回復：**GitHub `main` 推送完成後即可取得該文件；回復時使用 Git revert 本次提交，保留 `ChangeLog.md` 歷史紀錄。

## CHG-20261117-037｜完整發布毫米波雷達元件資料

- **類別：**需求變更（GitHub 資料發布）。
- **日期／紀錄時間：**2026-11-17 13:53:27 +08:00，工具取得台北時間。
- **原因：**使用者要求將 `元件/01_毫米波雷達` 目錄內目前尚未追蹤的毫米波雷達資料完整發布至 GitHub；先前 `main` 僅已發布 MicroPython 指南與驅動程式兩個檔案。
- **作法：**納入該目錄的 5 份 HLK-LD2410B 原廠 PDF，連同先前已提交的指南與 Python 驅動程式一併確認；依既有 `.gitignore` 排除 `__pycache__/ld2410b_micropython.cpython-314.pyc` 編譯快取。未納入其他目錄的工作區修改或未追蹤檔案。
- **影響：**GitHub `main` 將可取得毫米波雷達目錄的公開文件、安裝／開發指南與 MicroPython 驅動程式；不改變 ESP32 韌體、設定、部署清單或私人 WiFi profiles。
- **驗證：**確認目錄檔案清單與 Git 忽略規則；提交前檢查限定路徑的 staged diff，推送後以 `git ls-remote origin refs/heads/main` 核對遠端提交。未執行 ESP32 實機、雷達硬體、原廠工具或 APP 驗證。
- **部署／回復：**GitHub `main` 推送完成後即可透過該目錄取得資料；回復時使用 Git revert 本次提交，保留 `ChangeLog.md` 歷史紀錄。

## CHG-20261116-036｜整理 HLK-LD2410B 毫米波雷達安裝與 MicroPython 開發資料

- **類別：**需求變更（元件文件整理與開發範例）。
- **日期／紀錄時間：**2026-11-16 22:40:15 +08:00，工具取得台北時間。
- **原因：**使用者要求閱讀 `元件/01_毫米波雷達` 內的 5 份 HLK-LD2410B 原廠 PDF，整理成可快速安裝模組並開始 MicroPython 開發的操作基線。
- **作法：**在 `元件/01_毫米波雷達/` 新增 `LD2410B_MicroPython_快速安裝與開發指南.md`，整理供電、接線、安裝環境、PC／APP 驗證、UART 256000 8N1 協定、資料欄位、ACK 命令流程、底噪調校、故障排除與 uasyncio 架構；新增 `ld2410b_micropython.py`，提供半包／黏包容忍的資料與命令封包解析、正常／工程模式欄位、設定進入／離開、參數讀取與最大距離／無人時間設定範例。未修改 ESP32 主專案韌體、設定或部署清單。
- **影響：**後續可先依指南完成 5 V、共地、TX/RX 交叉接線，再以 OUT、原廠工具或 MicroPython UART 逐層驗證；驅動範例不依賴第三方套件。兩個新增檔案位於目前 Git 專案的未追蹤 `元件/01_毫米波雷達/`，需與本紀錄一起提交。
- **驗證：**以 CPython `py_compile` 檢查 `ld2410b_micropython.py`；以 fake UART smoke test 驗證分段資料封包解析、little-endian 距離欄位、命令 ACK 解析與啟用設定命令封包；檢查 Markdown fenced code block 成對。未執行 Mermaid parser（新指南沒有 Mermaid 區塊）、ESP32 實機、實際電源／GPIO 電氣、PC 工具、藍牙 APP、OTA 或真實安裝場域驗證。
- **部署／回復：**將兩個新增檔案複製到目標 `元件/01_毫米波雷達` 目錄即可；先使用獨立 UART 或斷開 PC／APP，再接入 ESP32。回復時移除該目錄新增的兩個檔案；不得用公開範例覆蓋任何含私人設定的檔案。


## CHG-20261110-035｜產生 ESP32 IoT 系統資料流程圖

- **類別：**需求變更（架構視覺化）。
- **日期／紀錄時間：**2026-11-10 21:03:17 +08:00，工具取得台北時間。
- **原因：**使用者要求使用 `archify` skill，依目前專案原始碼產生系統資料流程圖，說明感測輸入、Web／MQTT 介接、RAM 快照、LED 命令邊界與裝置／網路輸出。
- **作法：**新增 `.archify/dataflow-esp32-iot-20261110-205717/candidate.json` 與 `iot-system-dataflow.html`；以 repository HEAD `43875f0515e839184731595d6a86bde075f929e5` 的 `main.py`、`tasks.py`、`web_server.py`、`services/`、`hardware/` 與 `communication/` 實作建立節點、資料流、來源行號與 RAM 非持久化限制。圖中保留 `CommandService` 與 `LedController` 的單一 LED owner 邊界，未把未實作的功能或資料庫加入目前流程。
- **影響：**新增可在瀏覽器開啟的獨立資料流程圖，不改變 ESP32 韌體、API、組態或部署內容；圖中資料流是目前程式的責任與資料方向，不代表實機效能或端到端網路驗證。
- **驗證：**Archify `finalize dataflow --quality showcase` 的 `validate`、`deliver`、`check` 與 `browser-check` 全部通過；產出 HTML SHA-256 為 `c0eccdf789f93920ede934a4768c7a607ae632f7ed34b2b5c59c1beb16028122`。未進行人工視覺審查、ESP32 實機、GPIO、WiFi 或真 MQTT Broker 驗證。
- **部署／回復：**不需上傳 ESP32；分享或開啟 `.archify/dataflow-esp32-iot-20261110-205717/iot-system-dataflow.html`。回復時移除該 `.archify` 產出資料夾與本紀錄；不得以圖中的架構描述取代實機驗證。

## CHG-20261027-034｜新增 `uasyncio` 教學講義與學生操作手冊

- **類別：**需求變更（教學文件）。
- **日期／紀錄時間：**2026-10-27 01:15:22 +08:00，工具取得台北時間。
- **原因：**使用者要求根據本專案 `config.py` 的硬體配置，建立一份詳細的 MicroPython `uasyncio` 教學講義與學生操作手冊，並涵蓋 `uasyncio` 的重要功能、目前系統的非同步任務與可操作的硬體實驗。
- **作法：**新增 `UASYNCIO_LECTURE.md`，說明 coroutine、`await`、事件迴圈、`run`、`create_task`、`gather`、`sleep`／`sleep_ms`、`Event`、`Lock`、timeout、取消、Queue、PIR 狀態機、SensorSnapshot、MQTT callback bridge、Web Server 與 LED single owner；新增 `UASYNCIO_STUDENT_MANUAL.md`，依目前 GPIO、I2C、SPI、ADC、PWM 與輪詢參數安排接線檢查、非同步任務、按鈕、感測器、PIR、喇叭、LED、MQTT、RFID、Web、錯誤注入、取消與綜合實作。文件明確區分目前已實作、延伸練習、桌面 fake 測試與 ESP32 實機驗證；未修改韌體、`config.py` 或部署設定，也未寫入私人 WiFi profiles。
- **影響：**學生可用目前專案的實際程式路徑學習 `uasyncio`，並依硬體設定逐步操作；新增文件不改變裝置執行行為。教材中的 GPIO、門檻與輪詢時間以目前設定為基準，開發板變體、電氣接線、MicroPython 韌體、真 Broker 與實機長時間運作仍須另行驗證。
- **驗證：**以 Mermaid 11.13.0 實際解析兩份教材的 11/11 個 Mermaid 區塊通過（講義 7/7、學生手冊 4/4）；Markdown fenced code block 平衡與文件結構檢查通過；新教材無私人 WiFi assignment strings，且非刻意尾端空白檢查通過；`python -B -m unittest discover -s tests -v` 通過 33/33；`node tests/test_led_polling.cjs` 與 `node tests/test_rfid_ui.cjs` 通過。未執行 ESP32 實機、真 Broker、GPIO 電氣或周邊端到端驗證。
- **部署／回復：**只需同步 `UASYNCIO_LECTURE.md`、`UASYNCIO_STUDENT_MANUAL.md` 與 `ChangeLog.md`，不需上傳 ESP32。回復時以 Git revert 移除兩份教材與本紀錄；不得以教材中的公開範例覆蓋私人 `config.py`。

## CHG-20261020-033｜記錄實體按鈕事件與 handler 架構決策

- **類別：**需求變更（教學架構文件）。
- **日期／紀錄時間：**2026-10-20 16:05:16 +08:00，工具取得台北時間。
- **原因：**目前按鈕程式主要以 `wait_press()`／`wait_release()` 支援單次按下動作；使用者要求保存按下、放開、單擊、雙擊、長按、handler 非同步契約與事件派送責任的完整架構討論，避免未來擴充時把應用政策寫回硬體 driver。
- **作法：**在 `SYSTEM_ARCHITECTURE.md` 第 7.1 節新增實體按鈕架構決策，區分硬體 driver、監測 task、bounded `ButtonEvent` queue、async dispatcher 與應用 handler；定義去彈跳後的 `pressed`／`released`、延遲判斷的 `single_click`／`double_click`、`long_press` 語意與事件順序；決定按鈕 handler 統一採 `async def handler(event)` 契約、預設依序執行，並記錄 polling、IRQ、handler 自動猜測及直接等待 handler 等替代方案的取捨。文件明確標示此為目標架構，尚未修改目前 ESP32 程式。
- **影響：**只增加架構與教學說明，不改變目前按鈕、LED、MQTT 或部署行為；未來若實作，需另行新增 fake GPIO／fake clock 測試，並分開進行 ESP32 實際按鍵與電氣去彈跳驗證。
- **驗證：**`git diff --check -- SYSTEM_ARCHITECTURE.md ChangeLog.md` 通過；以 Mermaid 11.13.0 解析 `SYSTEM_ARCHITECTURE.md` 的 1/1 個 Mermaid 區塊通過；`python -B -m unittest discover -s tests -v` 通過 33/33。未執行 ESP32 實機按鍵、GPIO 電氣或完整手勢 dispatcher 驗證。
- **部署／回復：**只需同步 `SYSTEM_ARCHITECTURE.md` 與 `ChangeLog.md`，不需上傳 ESP32。回復時移除本紀錄及 `SYSTEM_ARCHITECTURE.md` 第 7.1 節；不得將尚未實作的手勢功能當成目前韌體能力。

## CHG-20261020-032｜保存 omp 免費 LLM API 評估指南

- **類別：**需求變更（教學文件）。
- **日期／紀錄時間：**2026-10-20 14:53:14 +08:00，工具取得台北時間。
- **原因：**前一輪免費 LLM API 的比較與 omp 串接建議只存在對話中，使用者要求保存為專案 Markdown 文件，供後續查閱與更新。
- **作法：**新增 `FREE_LLM_API_OMP_GUIDE.md`，整理 Google Gemini、Groq、OpenRouter、Mistral、Ollama、Cerebras、Cloudflare Workers AI 與 Hugging Face Inference Providers 的適用情境、免費限制、弱點、官方來源及 omp 設定範例；明確區分永久／固定免費層、試用額度與本機 API。未修改程式、設定或部署清單。
- **影響：**學生與維護者可在 repository 中查閱免費 API 選擇、資料隱私注意事項與 PowerShell 設定方式；文件明確提醒模型 ID、額度與政策可能變動。
- **驗證：**檢查新增 Markdown 的 staged 差異與 `git diff --check`；文件未包含 Mermaid 區塊，因此不需 Mermaid parser 驗證。未執行各供應商 API 實測或本機硬體 benchmark。
- **部署／回復：**只需同步 `FREE_LLM_API_OMP_GUIDE.md` 與 `ChangeLog.md`，不需上傳 ESP32。回復時使用 Git revert 移除本次文件與紀錄；API key 不得寫入文件或 repository。


## CHG-20261020-031｜將投影片納入 Git 版控並推送 main

- **類別：**需求變更（教材檔案與版控規則）。
- **日期／紀錄時間：**2026-10-20 14:13:02 +08:00，工具取得台北時間。
- **原因：**使用者要求將根目錄投影片檔推送至 GitHub `main`，並讓後續 `.pptx` 更新可由 Git 追蹤；Office 產生的 `~$*.pptx` 暫存鎖定檔不應納入版控。
- **作法：**將 `多個來源控制一個三色 LED：先懂問題，再懂單一擁有者.pptx` 納入追蹤；在 `.gitattributes` 將 `*.pptx` 標示為二進位檔，避免文字換行轉換；在 `.gitignore` 排除 `~$*.pptx` 鎖定檔。只提交本次投影片、版控規則與本紀錄，不納入其他未追蹤工作檔。
- **影響：**投影片內容及後續同一路徑的版本更新可透過 Git 歷史與 GitHub `main` 保存；Office 開啟檔案產生的暫存鎖定檔不會污染狀態。
- **驗證：**提交前以 staged diff 檢查檔案清單、二進位投影片大小與 `git diff --cached --check`；推送後以 `git ls-tree`／`git ls-remote` 確認 GitHub `main` 包含投影片。未執行投影片視覺渲染或內容審查。
- **部署／回復：**不部署至 ESP32；回復時可用 Git revert 移除本次追蹤規則與投影片提交，或從 Git 歷史取回投影片。不得納入 `~$*.pptx` 暫存鎖定檔。


## CHG-20261013-030｜將輪次備份納入 Git 版控並推送 main

- **類別：**需求變更（版控規則與教學資料）。
- **日期／紀錄時間：**2026-10-13 12:19:06 +08:00，工具取得台北時間。
- **原因：**`mdy_01/`、`mdy_02/` 原本只作本機回復快照，學生無法從 Git 歷史取得修改前版本比較；使用者要求將不含秘密的輪次備份納入版控，並將已 merge 的 `main` 推送到 `origin`。
- **作法：**更新 `GIT_VERSION_CONTROL.md`，規定 `mdy_N/` 公開快照應納入 Git、不得部署到 ESP32、不得包含私人設定或秘密，且與該輪程式變更及 `ChangeLog.md` 一起提交；檢查 `mdy_01/`、`mdy_02/` 僅含公開程式、測試與 `config.example.py` placeholder，未加入私人 `config.py`。本次將兩個備份目錄與版控規則、ChangeLog 建立 commit，之後推送 `main` 到 `origin`。
- **影響：**學生可在 Git 中比較 `mdy_01/`、`mdy_02/` 與後續主流程；備份檔仍只是來源快照，不屬於 ESP32 部署清單。`.manus/`、`manus-slides/`、PPTX 等既有未追蹤項目不納入。
- **驗證：**備份內容已檢查未發現私人 `config.py`、WiFi profiles、token、密碼或金鑰；`GIT_VERSION_CONTROL.md` 與 `ChangeLog.md` 的 staged diff check 通過。`mdy_N/` 保留原始來源快照，因此其中既有檔案的 trailing whitespace 未被重排；完整 staged diff check 會列出這些歷史空白，但不代表本次新增規則文件產生格式錯誤。已建立備份與版控 commit `af2770b`，merge commit `305c876` 已在其祖先歷史中；`origin/main` 已驗證為 `af2770b`（2026-10-13 12:20:33 +08:00）。commit／merge／push 均完成。
- **部署／回復：**不部署 `mdy_01/`、`mdy_02/`；回復程式時可從對應輪次快照取回修改前檔案。版控規則或備份提交若需撤回，使用 Git revert，不刪除學生比較所需的歷史。

## CHG-20261013-029｜擴充 MQTT 同步 callback 詳細教材

- **類別：**需求變更（教學文件）。
- **日期／紀錄時間：**2026-10-13 10:47:20 +08:00，工具取得台北時間。
- **原因：**前一版已補上同步 callback 的結論與責任邊界，但說明過於濃縮，未充分交代原始錯誤如何形成、`async def` 呼叫後為何只得到 coroutine、handler 為何會在 adapter 斷路、命令受理與 LED 套用為何不是同一時間點；學生缺少完整的因果鏈就難以自行診斷類似問題。
- **作法：**擴充 `IOT_ARCHITECTURE_EVOLUTION.md` 的 S2 段落，加入原始事故、同步／非同步呼叫對照、錯誤與修正路徑、handler 保存原因、callback 工作範圍、完成階段、`wait_connected()` 邊界、測試證據與學生檢查問題；擴充 `SYSTEM_ARCHITECTURE.md`，以 `led:4` 逐步追蹤 Broker、`mqtt_as`、adapter、`tasks.py`、`CommandService` 與 `LedController`；擴充 `IOT_ARCHITECTURE_TECH_TREE.md` E02，改以契約推導 adapter 並連結物聯網的網路／時間／資源／硬體驗證差異。未修改程式、設定、API 或部署清單。
- **影響：**教材現在同時說明「發生了什麼」、「為什麼會發生」、「修正放在哪一層」及「測試能證明什麼」，不再只給同步 callback 的規則結論。
- **驗證：**以 Mermaid 11.13.0 實際解析三份修改文件的全部 Mermaid 區塊：`IOT_ARCHITECTURE_EVOLUTION.md` 4/4、`SYSTEM_ARCHITECTURE.md` 1/1、`IOT_ARCHITECTURE_TECH_TREE.md` 1/1，共 6/6 通過；`python -B -m unittest tests.test_mqtt -v` 通過 10/10，`python -B -m unittest discover -s tests -v` 通過 33/33，`git diff --check` 通過。未進行 ESP32 實機、真 Broker 或外部訂閱者端到端驗證。
- **部署／回復：**只需同步三份 Markdown 文件與 `ChangeLog.md`，不需上傳 ESP32。回復時移除本紀錄及本回合新增段落；不得覆蓋私人 `config.py`。

## CHG-20261013-028｜補充 MQTT 同步 callback 教材說明

- **類別：**需求變更（教學文件）。
- **日期／紀錄時間：**2026-10-13 10:26:00 +08:00，工具取得台北時間。
- **原因：**既有文件已記錄 `mqtt_as` 的同步 callback 修正，但尚未完整說明同步呼叫契約、`async def` 未被 `await` 時只產生 coroutine、adapter 保存 handler、callback 與命令完成語意的差異；學生容易把「收到 callback」誤認為「命令已執行」。
- **作法：**在 `IOT_ARCHITECTURE_EVOLUTION.md` 的 S2 P0 演進段落新增同步 callback 的契約、錯誤示例、bridge 邊界、handler 保存、快速派送與 fake MQTT 驗證方式；在 `SYSTEM_ARCHITECTURE.md` 新增目前實作的 callback 責任表與 `wait_connected()`／重連重新訂閱界線；在 `IOT_ARCHITECTURE_TECH_TREE.md` 的 E02 MQTT 節點加入第一性原理與測試教學交叉連結。未修改程式、設定、API 或部署清單。
- **影響：**MQTT 教材可區分底層同步 callback、非同步 task 排程、命令受理與 LED 套用；讀者也能理解訂閱 callback 保存與重連恢復是兩個不同問題。
- **驗證：**以 Mermaid 11.13.0 實際解析三份修改文件的全部 Mermaid 區塊：`IOT_ARCHITECTURE_EVOLUTION.md` 4/4、`SYSTEM_ARCHITECTURE.md` 1/1、`IOT_ARCHITECTURE_TECH_TREE.md` 1/1，共 6/6 通過；`python -B -m unittest tests.test_mqtt -v` 通過 10/10，`python -B -m unittest discover -s tests -v` 通過 33/33，`git diff --check` 通過。未進行 ESP32 實機、真 Broker 或外部訂閱者端到端驗證。
- **部署／回復：**只需同步三份 Markdown 文件與 `ChangeLog.md`，不需上傳 ESP32。回復時移除本紀錄及三份文件新增段落；不得覆蓋私人 `config.py`。

## CHG-20261012-027｜新增物聯網軟體架構演進教學文件

- **類別：**需求變更（教學文件）。
- **日期／紀錄時間：**2026-10-12 22:01:27 +08:00，工具取得台北時間。
- **原因：**既有 `IOT_ARCHITECTURE_TECH_TREE.md` 說明技術能力與第一性原理，但學生仍需要一份沿著本專案歷史，理解「原始直接控制」如何因控制競爭、感測品質、MQTT 契約、資源限制與部署差異逐步演進的教材；也需要明確比較物聯網軟體架構與純軟體架構的核心差異。
- **作法：**新增 `IOT_ARCHITECTURE_EVOLUTION.md`，依 S0 原始版本、S1 模組化基線、S2 P0 MQTT 修正、S3 P1 命令／感測架構與 S4 P2 待實作方向整理演進；逐項說明狀態擁有權、協同多工、去彈跳與遲滯、`SensorSnapshot`、callback bridge、accepted／applied、`CommandService`、`LedController`、bounded queue、request ID、部署相依、連線恢復、監督與安全的「是什麼、為什麼、做什麼、怎麼做」；另以表格與 Mermaid 圖比較物理閉環、時間、資源、網路、部署與驗證差異。
- **影響：**新增一份以目前程式與歷史變更為證據的架構演進教材；不修改韌體、設定、API 或部署檔案。文件明確區分 P1 已實作、P2 待實作，以及桌面測試與 ESP32 實機驗證的界線。
- **驗證：**以 Mermaid 11.13.0 實際解析 `IOT_ARCHITECTURE_EVOLUTION.md` 的 4/4 個圖表區塊；其餘 Python／Node 測試沿用前一個程式變更回合的已驗證結果，本次未修改程式。
- **部署／回復：**本次只新增教學文件與本紀錄，不需重新上傳 ESP32。回復時移除 `IOT_ARCHITECTURE_EVOLUTION.md` 與本紀錄段落；不得回復或覆蓋私人 `config.py`。
## CHG-20261012-026｜同步 LED 講義與裝置私人配置至 P1

- **類別：**需求變更（文件與裝置部署配置同步）。
- **日期／紀錄時間：**2026-10-12 20:44:01 +08:00，工具取得台北時間。
- **原因：**P1 已將舊 `LedService` 介面替換為 `CommandService`／`LedController`，但 `LED_SINGLE_OWNER_GUIDE.md` 與 `LIGHT_LED_ALERT_GUIDE.md` 仍有舊版 token、事件任務、MQTT callback 未接通及部署清單描述；私人 `config.py` 也缺少新的 `LED_CONTROL_MODE` 設定，無法直接以目前 P1 程式配置部署。
- **作法：**更新兩份 LED 講義，將目前實作改以 `SensorSnapshot`、`CommandService`、`LedController`、MQTT callback bridge、命令 receipt、bounded queue、AUTO／MANUAL、Web 快照與目前部署清單為準；未實作的按鈕 3 綠閃保留並明確標示為提案。更新本機私人 `config.py`，新增 `LED_CONTROL_MODE = 'AUTO'`，保留原有 WiFi SSID／密碼及裝置專屬 `LIGHT_ALERT_TRIGGER_ADC = 500` 校準值；公開 `config.example.py` 的 placeholder WiFi 與 1000／1100 範例值不被私人設定覆蓋。
- **影響：**ESP32 可直接上傳目前 P1 程式與本機 `config.py`；WiFi／密碼仍保留。私人 `config.py` 仍被 Git 忽略，不納入 commit、備份或公開文件；`mdy_01/`、`mdy_02/` 與 `lib_backup/` 不屬於 ESP32 部署檔案。
- **驗證：**私人配置匯入檢查確認 `LED_CONTROL_MODE = 'AUTO'` 且 WiFi profiles／裝置專屬 500／1100 閾值未被替換；Python unittest 33/33 通過；`node tests/test_led_polling.cjs`、`node tests/test_rfid_ui.cjs` 通過；指定 Python 檔案 `py_compile` 通過；LED 講義 Mermaid 11.13.0 實際解析 `LED_SINGLE_OWNER_GUIDE.md` 21/21，`LIGHT_LED_ALERT_GUIDE.md` 0 個，共 21/21 通過。未進行 ESP32 實機、真 Broker、外部訂閱者或硬體 GPIO 電氣驗證。
- **部署／回復：**部署 `main.py`、`tasks.py`、`web_server.py`、`index.html`、`hardware/led.py`、`hardware/sensors.py`、`communication/mqtt_client.py`、`services/command_service.py`、`services/led_controller.py`、`services/sensor_snapshot.py`、`config.py` 與必要的 `lib/` 檔案；不要部署 `mdy_01/`、`mdy_02/`、`lib_backup/`。回復時還原兩份講義與 `config.py` 的 `LED_CONTROL_MODE`，並保留私人 WiFi／密碼。

## CHG-20261012-025｜實作 P1 SensorSnapshot、CommandService 與 LedController

- **類別：**需求變更（P1 核心架構改善）。
- **日期／紀錄時間：**2026-10-12 16:53:00 +08:00，工具取得台北時間。
- **原因：**P0 已修復 MQTT callback 與發佈狀態語意，但按鈕、Web、MQTT、光感仍需要以一致的 LED 命令邊界與狀態模型協作；感測資料也需要與硬體讀取解耦，避免 Web／OLED／MQTT 各自讀取或重複觸發感測器。
- **作法：**新增 `services/sensor_snapshot.py`，集中保存溫度、濕度、光照的 last-good value、valid、quality、age、error 與 sample sequence；新增 `services/command_service.py`，產生遞增 request ID 並提供共同命令入口；以 `services/led_controller.py` 取代 `services/led_service.py`，成為唯一 LED GPIO owner，建立 bounded queue／result history、desired／enabled／applied 分離、AUTO／MANUAL 模式、低光警示保存／恢復與命令 receipt。更新 `main.py` 組裝並注入三個核心服務；更新 `tasks.py` 將按鈕、光感與 MQTT 訂閱遷移到 CommandService，DHT／光感 producer 更新 SensorSnapshot，且光感讀值失敗或未知時不提交 LED 警示命令，OLED／MQTT 發佈讀取快照；更新 `web_server.py` 讓 `/api/data` 只讀快照，LED toggle、canonical commands、mode、status、result 路由共用 CommandService。更新 `hardware/sensors.py` 保留感測 last-good 值與錯誤；更新 `config.example.py` 的 `LED_CONTROL_MODE`；刪除舊 `services/led_service.py`。保留 MQTT 既有 `led:4`／`led=4` payload 邊界，未在本次加入重連重新訂閱、權限／TLS、Broker ACK 或 supervisor。
- **輪次備份：**在本回合任何既有程式檔案修改前建立 `mdy_02/`，保存本回合涉及的 `main.py`、`tasks.py`、`web_server.py`、`config.example.py`、`hardware/sensors.py`、`hardware/led.py`、`services/led_service.py` 與既有測試原始版本；未備份私人 `config.py`，未建立或覆蓋 `mdy_03/`。新增的 P1 核心檔案與測試沒有「修改前既有版本」。
- **影響：**四個 LED 命令來源共用 request ID、輸入驗證、有限佇列與結果語意；owner frame 以外不直接寫 GPIO。光感 AUTO 低光警示完成後恢復使用者 desired state，MANUAL 拒絕光感覆蓋；感測失敗不再以 `-1` 覆蓋 last-good value，而由 Snapshot 明確表達品質與年齡，未知光感值也不會觸發控制命令。Web 仍保留舊 LED toggle 與 MQTT wire format，HTTP `202` 僅代表命令已受理。
- **文件：**同步更新 `IOT_ARCHITECTURE_TECH_TREE.md`、`SYSTEM_ARCHITECTURE.md`、`WEB_UI_EXECUTION_GUIDE.md`，將 P1 實作狀態、資料／命令流、歷史 P0 討論與驗收界線分開記錄。
- **驗證：**`python -B -m unittest discover -s tests -v` 通過 33/33；`node tests/test_led_polling.cjs` 通過；`node tests/test_rfid_ui.cjs` 通過；指定 P1 Python 檔案 `py_compile` 通過。桌面 fake GPIO／fake MQTT／Microdot TestClient 已覆蓋單一 owner、AUTO 警示恢復、MANUAL 拒絕、last-good snapshot、未知光感不提交警示、bounded queue、request ID、Web command result 與 MQTT command adapter。Mermaid 11.13.0 實際解析 `IOT_ARCHITECTURE_TECH_TREE.md` 1/1、`SYSTEM_ARCHITECTURE.md` 1/1、`WEB_UI_EXECUTION_GUIDE.md` 12/12，共 14/14 個 Mermaid 區塊通過。未進行 ESP32 實機、真 Broker、外部訂閱者或硬體 GPIO 電氣驗證。
- **部署／回復：**部署 `main.py`、`tasks.py`、`web_server.py`、`hardware/sensors.py`、`hardware/led.py`、`config.example.py`、`services/command_service.py`、`services/sensor_snapshot.py`、`services/led_controller.py`、對應 `tests/` 與文件；不要部署 `mdy_02/`，不要覆蓋私人 `config.py`。回復時以 `mdy_02/` 對應快照還原既有檔案，並移除本回合新增服務／測試；若回復至 P0，需同步恢復 `services/led_service.py` 及其呼叫者契約。

## CHG-20261012-024｜實作 P0 MQTT callback、指令派送與發佈狀態語意

- **類別：**BUG（MQTT 入站 callback 斷路、連線結果未檢查、HTTP 發佈完成語意錯誤）。
- **日期／紀錄時間：**2026-10-12 15:43:08 +08:00，工具取得台北時間。
- **原因：**`lib/mqtt_as.py` 以同步三參數呼叫收訊 callback，但 adapter 原本使用非同步 `on_message()`；訂閱時傳入的 callback 未被保存；MQTT 任務忽略 `wait_connected()`；`POST /api/publish` 將 Event 受理誤報成已完成發佈，且前端只依 HTTP 成功顯示已發布。
- **作法：**修改 `communication/mqtt_client.py`：建立同步 callback bridge、保存並派送訂閱 handler、以連線 callback／Event確認 `wait_connected()`、追蹤發佈 `accepted`／`publishing`／`published`／`failed`／`unavailable`。修改 `tasks.py`：訂閱 callback 維持既有 `led:4`／`led=4` 格式，解析後交給 `LedService.submit()`；發佈任務檢查連線並更新結果。修改 `web_server.py`：`/api/publish` 回傳 JSON 與 HTTP 202／503，新增 no-store 的 `/api/publish/status`。修改 `index.html`：依 JSON status 顯示「已受理」或錯誤，不把 accepted 宣稱成完成。同步更新 `IOT_ARCHITECTURE_TECH_TREE.md`、`SYSTEM_ARCHITECTURE.md`、`WEB_UI_EXECUTION_GUIDE.md`。未修改 `lib/mqtt_as.py`，未提前建立 P1 完整 `CommandService`。
- **輪次備份：**在本回合程式修改前建立 `mdy_01/`，保存 `communication/mqtt_client.py`、`tasks.py`、`web_server.py`、`index.html` 與 `tests/test_mqtt.py` 的修改前版本；不含私人設定與秘密。下次程式修改輪次應使用 `mdy_02/`。
- **影響：**MQTT 入站 LED 指令現在到達既有單一 `LedService.submit()` 受理邊界；HTTP 發佈可區分受理與背景任務最近結果；既有 MQTT payload 格式與 QoS 0 不變。Event 仍是單一旗標，重複觸發可能合併；重連後重新訂閱、完整 P1 `CommandService`、Broker ACK 與權限安全仍未納入。
- **驗證：**MQTT 專項測試 10/10 通過；完整 Python 測試 33/33 通過；`node tests/test_led_polling.cjs` 與 `node tests/test_rfid_ui.cjs` 通過；`python -B -m py_compile communication/mqtt_client.py tasks.py web_server.py tests/test_mqtt.py` 通過；Mermaid 11.13.0 實際解析 `IOT_ARCHITECTURE_TECH_TREE.md` 1/1、`SYSTEM_ARCHITECTURE.md` 1/1、`WEB_UI_EXECUTION_GUIDE.md` 12/12；`git diff --check` 無差異錯誤；桌面 fake MQTT／fake LED 已確認同步 callback、`LedService.submit()` 派送、連線逾時與 HTTP JSON 狀態分層。ESP32 實機、真 Broker、外部訂閱者與斷線重連尚未驗證。
- **部署／回復：**部署 `communication/mqtt_client.py`、`tasks.py`、`web_server.py`、`index.html`，並依專案既有部署清單重啟裝置；不部署 `mdy_01/`。回復時以 `mdy_01/` 對應快照還原上述檔案，或使用 Git 差異回復；不要覆蓋私人 `config.py`。

## CHG-20261012-023｜記錄 P0 MQTT 與 P1 共用命令入口討論及程式輪次備份規則

- **類別：**需求變更（架構決策與版控流程）。
- **日期／紀錄時間：**2026-10-12 15:29:46 +08:00，工具取得台北時間。
- **原因：**兩輪討論釐清IOT架構技術樹P0的MQTT修正邊界，以及是否要提前導入P1的MQTT／Web／按鈕共用命令入口；同時使用者要求未來每一輪程式修改先保存原始版本，依序放入`mdy_01`、`mdy_02`等目錄。
- **討論紀錄：**第一輪確認目前`mqtt_as`以同步方式呼叫`subs_cb(topic, msg, retained)`，但`MqttManager.on_message()`為非同步函式；`MqttManager.subscribe()`忽略傳入callback；MQTT任務忽略`wait_connected()`結果；`POST /api/publish`把事件觸發誤報為資料已發佈。第二輪決定P0只修正callback bridge、指令派送、連線結果及accepted／published／failed語意，保留現行`lib/mqtt_as.py`，並讓MQTT指令進入既有`LedService.submit()`；P1才建立完整`CommandService`，一次遷移按鈕、Web與MQTT，避免P0形成半套第二命令入口。
- **作法：**將上述兩輪討論詳記於`IOT_ARCHITECTURE_TECH_TREE.md`的P0／P1段落；將程式修改前的輪次備份規則加入`GIT_VERSION_CONTROL.md`。第一次程式修改回合使用`mdy_01/`，下一回合使用`mdy_02/`，備份保留相對路徑且排除私人`config.py`與所有秘密。本次只有文件修改，尚未建立`mdy_01/`，也未修改程式。
- **影響：**後續P0實作必須以`LedService.submit()`作為現有單一LED命令受理邊界，不得由MQTT callback直接寫GPIO或複製仲裁政策；P1再引入完整`CommandService`。每一輪程式修改均可由對應`mdy_N/`回復，且封存備份不得部署到ESP32。
- **驗證：**已檢查文件內容與目前P0／P1方案一致；`git diff --check`無差異錯誤；Mermaid 11.13.0實際解析`IOT_ARCHITECTURE_TECH_TREE.md`的1/1個圖表區塊；本次未修改程式，因此不宣稱完成MQTT修正，也未建立`mdy_01/`，未執行程式測試。
- **部署／回復：**本次只納入文件變更，不需上傳ESP32。回復時還原`IOT_ARCHITECTURE_TECH_TREE.md`、`GIT_VERSION_CONTROL.md`與`ChangeLog.md`本次段落；未來程式回合須先備份再修改，回復優先使用對應`mdy_N/`快照。

## CHG-20261012-022｜整理 lib 重複函式庫並建立封存目錄

- **類別：**需求變更（架構與部署結構）。
- **日期／紀錄時間：**2026-10-12 14:49:29 +08:00，工具取得台北時間。
- **原因：**`lib/`同時存在3個MFRC522、2個Queue與2個MQTT實作；多份可替代模組會讓部署選擇、import 路徑與後續架構調整的基線不明。
- **作法：**保留`lib/mfrc522_async.py`、`lib/async_queue.py`與`lib/mqtt_as.py`；建立`lib_backup/`，將`mfrc522.py`、`mfrc522_async_sync.py`、`queue_ns_async.py`與`mqtt_async.py`移入封存。更新`SYSTEM_ARCHITECTURE.md`的目錄、部署清單與選擇理由；未修改目前主流程的import。
- **選擇理由：**RFID保留`mfrc522_async.py`，因`hardware/rfid.py`明確使用`MFRC522Async`及非同步`request`／`anticoll`，且測試契約相同；Queue保留較小且單一責任的`async_queue.py`，兩者目前都無呼叫者，而`queue_ns_async.py`額外含未使用且`task_done()`為空實作的`SimpleQueue`；MQTT保留`mqtt_as.py`，因`communication/mqtt_client.py`明確匯入其`MQTTClient`與`config`，是現行主流程契約。
- **影響：**目前裝置程式的有效函式庫集合只保留上述三個檔案；封存檔不應上傳ESP32。既有RFID、MQTT與桌面測試的import路徑不變；Queue仍未接入目前主流程。
- **驗證：**靜態分析確認現行程式沒有引用移入封存的模組；檢查確認`lib/`保留3個指定模組且`lib_backup/`存在4個封存檔；`python -B -m unittest discover -s tests -v`通過24/24；`git diff --check`無差異錯誤；Mermaid 11.13.0實際解析`SYSTEM_ARCHITECTURE.md`與`IOT_ARCHITECTURE_TECH_TREE.md`共2/2個圖表區塊。未進行ESP32實機部署或讀卡／Broker端到端驗證。
- **部署／回復：**部署時只帶`lib/`內仍被主流程需要的檔案，不上傳`lib_backup/`。回復時可將封存檔移回`lib/`，但恢復任何替代MQTT／RFID實作前必須重新確認import與API契約；不覆蓋私人`config.py`。

## CHG-20261012-021｜以第一性原理重整完整技術樹六問格式

- **類別：**需求變更（教學文件）。
- **日期／紀錄時間：**2026-10-12 13:02:37 +08:00，工具取得台北時間。
- **原因：**既有技術樹已涵蓋物聯網架構能力，但每個節點的欄位名稱使用「使用時機」，未完全對齊使用者要求的「使用前提、使用情境、是什麼、為什麼、做什麼、怎麼做」六問格式；文件開頭也未明確說明技術點／知識點及提案與現況的界線。
- **作法：**重整`IOT_ARCHITECTURE_TECH_TREE.md`標題與導言，明確由物理限制、時間、資源、信任與可驗證性推導A01～H04共32個技術點／知識點；將全部32個節點的欄位統一為六問格式，並補充每一欄的閱讀定義與尚未部署的提案標示原則。未修改韌體、設定、API或測試程式。
- **影響：**學生可依A→H閱讀完整技術樹，逐點回答採用條件、問題情境、概念定義、必要性、責任與實作方式；既有系統架構與程式行為不變。
- **驗證：**已以Mermaid 11.13.0實際解析`IOT_ARCHITECTURE_TECH_TREE.md`的1/1個圖表區塊；已檢查32個節點均具有六個欄位，且不再使用`使用時機`欄位；`git diff --check`無差異錯誤；`python -B -m unittest discover -s tests -v`通過24/24。未進行ESP32實機驗證。
- **部署／回復：**只需納入`IOT_ARCHITECTURE_TECH_TREE.md`與`ChangeLog.md`，不需重新上傳ESP32。回復時還原這兩個文件的本次變更；不應回復或覆蓋私人`config.py`。

## CHG-20261012-020｜縮短PIR重新武裝等待

- **類別：**BUG（實機已能偵測並播放，但下一次移動需等待過久）。
- **日期／紀錄時間：**2026-10-12 01:52:10 +08:00，工具取得台北時間。
- **原因：**上一版`PIR_LOW_REARM_MS = 5000`要求PIR低電位連續穩定5秒後才重新武裝，因此一次事件結束後的下一次偵測會顯得遲鈍。
- **作法：**將私人`config.py`與公開`config.example.py`的`PIR_LOW_REARM_MS`由5000調整為1500 ms；`tasks.py`缺少設定時的預設值同步調整為1500。保留100 ms輪詢與200 ms高電位確認，仍以穩定低電位重新武裝，避免退回500 ms時較容易出現同一次靠近重複觸發的問題；同步更新兩份架構文件。
- **影響：**PIR在低電位穩定1.5秒後可再次偵測；短暫低／高抖動仍不會重新計數。1500 ms是防重複與回應速度的折衷值，若實機模組仍有分離脈衝，需再依波形或實測調整。
- **驗證：**PIR專項測試6/6通過；完整Python測試24/24通過；前端LED／RFID／移動狀態測試通過；指定Python檔案`py_compile`通過；Mermaid 11.13.0解析兩份文件共13/13個圖表區塊通過；`git diff --check`無差異錯誤。測試驗證穩定低電位重新武裝後仍可再次觸發；未進行ESP32實機驗證。
- **部署／回復：**重新上傳`tasks.py`與私人`config.py`並重啟ESP32；`config.example.py`、文件與`ChangeLog.md`供版控／教學使用，不上傳到裝置。回復時將兩個裝置檔案的`PIR_LOW_REARM_MS`改回5000。

## CHG-20261012-019｜讓移動／喇叭狀態獨立更新網頁

- **類別：**BUG（PIR已觸發並播放音樂，但網頁的移動狀態未及時更新）。
- **日期／紀錄時間：**2026-10-12 01:40:10 +08:00，工具取得台北時間。
- **原因：**前端原本只透過`GET /api/data`取得移動狀態；該API同時讀取DHT與ADC，慢感測或回應延遲時，PIR／喇叭RAM快照也會被一起延遲。此項以程式路徑分析定位，未宣稱已在ESP32重現每一個阻塞時序。
- **作法：**新增`GET /api/motion/status`，只複製`motion_state`快照並回`Cache-Control: no-store`；`index.html`新增獨立的`updateMotionStatus()`／`pollMotionStatus()`，每1000 ms輪詢且同一時間只保留一筆請求。`/api/data`仍保留`motion`欄位以維持既有API相容性。
- **影響：**PIR偵測時間、去抖與喇叭播放邏輯不變；網頁移動文字、最近5次紀錄、次數與喇叭狀態不再依賴完整感測資料API完成。同步更新前端測試、API測試、`WEB_UI_EXECUTION_GUIDE.md`與`SYSTEM_ARCHITECTURE.md`。
- **驗證：**前端RFID／移動狀態測試與LED輪詢測試通過；完整Python測試24/24通過，指定檔案`py_compile`通過，Mermaid 11.13.0解析兩份文件共13/13個圖表區塊通過，`git diff --check`無差異錯誤。測試確認獨立API快照可更新移動文字與喇叭狀態。未進行ESP32實機驗證。
- **部署／回復：**重新上傳`index.html`與`web_server.py`並重啟ESP32，使`HTML_PAGE`重新載入；不需上傳`tasks.py`或`config.py`。若需回復，還原上述兩個程式檔案與前端／API測試、文件變更。

## CHG-20261012-018｜修正MicroPython MQTT例外診斷遮蔽原始錯誤

- **類別：**BUG（MQTT連線錯誤被缺少的`traceback`模組再次覆蓋）。
- **日期／紀錄時間：**2026-10-12 01:30:05 +08:00，工具取得台北時間。
- **原因：**`mqtt_client.py`捕捉到`[Errno 104] ECONNRESET`後匯入桌面Python的`traceback`；ESP32的MicroPython環境沒有該模組，因此原始網路錯誤被替換成`no module named 'traceback'`並冒泡到`main.py`。`main.py`最外層也有相同不相容匯入。
- **作法：**移除`communication/mqtt_client.py`與`main.py`的`traceback`匯入／呼叫；連線失敗改以`type(e).__name__`與`str(e)`輸出原始例外並回傳`False`，主程式致命錯誤路徑也採相容字串輸出。新增MQTT測試替身，確認`OSError(104, 'ECONNRESET')`不再被`ModuleNotFoundError`遮蔽。
- **影響：**ESP32將看到類似`OSError: [Errno 104] ECONNRESET`的真正連線錯誤，MQTT初始連線仍依`main.py`既有3次嘗試與其他功能繼續運行政策處理；未改變Broker、TLS或重連策略。
- **驗證：**MQTT例外回歸測試通過；完整Python測試24/24通過，Node前端測試通過，指定Python檔案`py_compile`通過，Mermaid 11.13.0解析兩份文件共13/13個圖表區塊通過。測試以fake MQTT client重現`OSError(104, 'ECONNRESET')`並確認回傳`False`且不再拋出`ModuleNotFoundError`。未進行ESP32實機或Broker端到端驗證。
- **部署／回復：**重新上傳`communication/mqtt_client.py`與`main.py`，重啟ESP32；若只需恢復診斷文字，還原這兩個檔案即可。`lib/mqtt_as.py`與私人`config.py`不需因本修正變更。

## CHG-20261012-017｜延長PIR穩定低電位重新武裝時間

- **類別：**BUG（實機仍出現同一次靠近的兩次事件）。
- **日期／紀錄時間：**2026-10-12 01:22:04 +08:00，工具取得台北時間。
- **原因：**上一版非同步狀態機只要求低電位穩定500 ms；實際PIR模組在同一次手部靠近期間可能產生間隔超過500 ms但仍屬同一反應的第二個高脈衝，因此狀態機已重新武裝後再次計數。
- **作法：**將`PIR_LOW_REARM_MS`由500調整為5000，保留100 ms非同步取樣與200 ms穩定高電位確認。只有低電位連續穩定5秒才重新武裝，避免PIR模組的分離脈衝被當成兩次移動；同步更新私人設定指引、公開設定範例、測試時序與兩份文件。
- **影響：**一次移動事件結束後，需持續無移動5秒才允許下一次事件；5秒內的第二次真實移動會合併為同一事件。5秒是目前針對使用者實機現象的保守參數，仍可依PIR模組輸出調整。
- **驗證：**PIR／音樂測試6/6通過；完整Python測試23/23通過；Node前端測試通過；指定Python檔案`py_compile`通過；Mermaid 11.13.0解析13/13通過。測試涵蓋tick回繞、短暫低／高抖動、穩定低5秒重新武裝與最近5筆歷史。未進行ESP32實機驗證。
- **部署／回復：**更新`tasks.py`，並在裝置私人`config.py`將`PIR_LOW_REARM_MS`改為5000；不可用公開範例覆蓋私人WiFi設定。重啟ESP32後再觀察實際PIR；回復時將此參數還原為500（若要回復上一版狀態機行為，也需同步還原`tasks.py`）。

## CHG-20261012-016｜實作PIR非同步穩定邊緣防抖

- **類別：**需求變更（PIR事件判斷改善）。
- **日期／紀錄時間：**2026-10-12 01:09:45 +08:00，工具取得台北時間。
- **原因：**固定`PIR_RETRIGGER_COOLDOWN_MS = 5000`只能以時間抑制重複事件，無法判斷移動是否真正結束；它可能吞掉5秒內真正分開的第二次移動。使用者要求實作較好的非同步防抖機制。
- **作法：**`tasks.py`改用非阻塞穩定邊緣狀態機：每100 ms取樣，PIR高電位連續200 ms才觸發一次；觸發後保持未武裝，低電位連續500 ms才重新武裝；短暫低／高抖動不會重新計數。新增`PIR_HIGH_DEBOUNCE_MS`、`PIR_LOW_REARM_MS`與`MOTION_DETECTED_HOLD_MS`設定，移除固定冷卻參數；`MOTION_DETECTED_HOLD_MS`只保留網頁顯示保持語意。更新`config.example.py`、PIR測試與兩份文件。
- **影響：**一次手部靠近的PIR訊號必須先穩定高才計數；同一次事件內的高電位持續或短暫低／高抖動不會重複觸發。下一次事件必須先完成穩定低重新武裝。輪詢由500 ms改為100 ms，增加取樣頻率但仍使用uasyncio非同步睡眠，不阻塞其他任務。
- **驗證：**PIR／音樂測試6/6通過；完整Python測試23/23通過；Node前端測試通過；指定Python檔案`py_compile`通過；Mermaid 11.13.0解析13/13通過；測試涵蓋初始高電位、tick回繞、短暫低／高抖動、穩定低重新武裝與最近5筆歷史。未進行ESP32實機驗證。
- **部署／回復：**更新`tasks.py`；在裝置私人`config.py`同步加入`PIR_POLL_INTERVAL_MS = 100`、`PIR_HIGH_DEBOUNCE_MS = 200`、`PIR_LOW_REARM_MS = 500`、`MOTION_DETECTED_HOLD_MS = 5000`，不可用公開範例覆蓋私人WiFi設定。同步更新時可上傳`config.example.py`僅作公開基線；重啟ESP32後觀察實際PIR，再依硬體輸出調整三個時間參數。回復時還原`tasks.py`與私人設定的新增欄位。

## CHG-20261012-015｜補充PIR冷卻值來源與狀態機改進提案

- **類別：**需求變更（文件澄清）。
- **日期／紀錄時間：**2026-10-12 01:05:19 +08:00，工具取得台北時間。
- **原因：**使用者詢問`5000ms`的來源及是否存在比固定冷卻時間更好的PIR判斷方式；現行文件只描述5秒行為，沒有明確標示它是沿用的啟發式，也沒有區分尚未實作的狀態機提案。
- **作法：**同步更新`WEB_UI_EXECUTION_GUIDE.md`與`SYSTEM_ARCHITECTURE.md`：明確說明5000 ms來自既有`detected`保持時間、不是硬體校正值；補充「穩定高電位確認、觸發一次、穩定低電位重新武裝」狀態機作為改進提案，並標示目前尚未實作。
- **影響：**只修改教學／架構說明，不改變目前ESP32行為；現行程式仍使用`PIR_RETRIGGER_COOLDOWN_MS = 5000`。提案不可當成已部署功能。
- **驗證：**Mermaid 11.13.0解析兩份文件共13/13個圖表區塊通過；本次沒有修改程式，因此沿用CHG-20261012-014已記錄的23/23 Python、Node與語法驗證。未進行ESP32實機驗證。
- **部署／回復：**不需重新上傳韌體；同步納入兩份文件與`ChangeLog.md`即可。回復時還原本紀錄涉及的文件段落。

## CHG-20261012-014｜抑制單次移動造成的重複PIR偵測

- **類別：**BUG（一次手靠近被計為兩次移動）。
- **日期／紀錄時間：**2026-10-12 00:56:11 +08:00，工具取得台北時間。
- **原因：**`pir_monitor_task()`只依前一輪的高／低電位判斷低到高邊緣；PIR輸出若在同一次靠近期間短暫低再回高，500 ms輪詢會把抖動視為第二次移動。原本的5秒`detected`顯示保持時間沒有阻止事件計數再次增加。
- **作法：**新增`PIR_RETRIGGER_COOLDOWN_MS = 5000`（同步更新`config.example.py`），`tasks.py`在低到高邊緣觸發前檢查距離上次有效偵測的時間；冷卻期間只更新目前感測狀態，不設定新的`motion_event`、不增加`count`、不加入`recent_detections`。冷卻後的新低到高才視為新事件。
- **影響：**同一次移動造成的短暫低／高抖動不再重複播放音樂或增加網頁移動次數；目前5秒內的第二次真實靠近也會被視為同一事件，需依實機感測器特性調整`PIR_RETRIGGER_COOLDOWN_MS`。預設值與既有5秒顯示保持時間一致。
- **驗證：**PIR／音樂測試6/6通過，新增測試確認冷卻期間的第二個低到高被抑制、冷卻後可重新計數；完整Python測試23/23通過，Node前端測試通過，指定Python檔案`py_compile`通過；Web／系統文件Mermaid 11.13.0解析13/13通過。未進行ESP32實機驗證。
- **部署／回復：**需更新`tasks.py`；建議在裝置私人`config.py`加入`PIR_RETRIGGER_COOLDOWN_MS = 5000`，不可用公開`config.example.py`覆蓋私人WiFi設定；`config.py`未加入版本控制。`index.html`與`web_server.py`本次不因PIR去重而必須更新，除非尚未部署前一版狀態API／網頁修改。回復時還原`tasks.py`與設定範例，並重啟ESP32。

## CHG-20261012-013｜修正閃紅次數為完整警示事件次數

- **類別：**BUG（LED閃紅計數語意不符合需求）。
- **日期／紀錄時間：**2026-10-12 00:44:14 +08:00，工具取得台北時間。
- **原因：**前一版把低光警示內的每一次紅燈閃爍當成一筆紀錄，因此完整閃紅5次會顯示為5次；使用者定義「完整閃紅5次才算閃紅1次」。
- **作法：**`services/led_service.py`改為只有完成整組`LIGHT_ALERT_BLINK_COUNT`次閃紅後才增加`alert_flash_count`，並以整組完成時間建立一筆`alert_flash_log`；未完成的警示不計入。事件序號保留最近5筆，序號仍以裝置開機後完成的事件總數遞增。`index.html`移除`次數／5`顯示，改顯示完成事件總數；`web_server.py`沿用相同欄位名稱但同步新的語意。測試、Web／系統架構文件補充完整事件定義。
- **影響：**例如LED完整閃紅5次後顯示`閃紅次數：1`與`閃紅1：完成時間`；第二次完整警示才顯示`閃紅次數：2`。`alert_flash_total`仍代表一個事件內的閃爍動作數，不是事件次數。
- **驗證：**`node tests/test_led_polling.cjs`與`node tests/test_rfid_ui.cjs`通過；`python -B -m unittest discover -s tests -v`通過22/22，包含兩個完整警示事件序號驗證；指定Python檔案`py_compile`通過；Chromium以事件級mock確認顯示`閃紅次數：1`與`閃紅1：完成時間`，且uPlot Canvas存在；Mermaid 11.13.0解析兩份文件共13/13個圖表區塊通過。未進行ESP32實機驗證。
- **部署／回復：**需同步部署`index.html`、`web_server.py`、`services/led_service.py`、測試與兩份同步文件；不需重新部署RFID／PIR程式。回復時同步還原本紀錄涉及的檔案，避免前端把事件次數誤顯示為單次閃爍次數。

## CHG-20261012-012｜顯示LED閃紅、RFID與移動偵測最近紀錄

- **類別：**需求變更（狀態可觀測性與網頁卡片顯示）。
- **日期／紀錄時間：**2026-10-12 00:26:20 +08:00，工具取得台北時間。
- **原因：**使用者要求LED狀態區顯示閃紅次數及「閃紅序號：時間」，RFID只顯示最近5次「卡號：讀卡時間」，移動偵測只顯示最近5次偵測時間；原本API只保留單筆RFID／PIR摘要，LED也沒有閃紅事件時間。
- **作法：**`services/led_service.py`在每次低光閃紅開始時以裝置時間記錄`alert_flash_log`，snapshot新增`alert_flash_count`、`alert_flash_total`與紀錄清單；`hardware/rfid.py`與`tasks.py`保留最多5筆`recent_reads`；`hardware/motion.py`與`tasks.py`保留最多5筆`recent_detections`；`web_server.py`的LED fallback同步提供新欄位。`index.html`新增LED閃紅次數／時間列表，RFID與移動卡片改以最近5筆資料重繪。兩份架構／Web教學文件補充API欄位、RAM生命週期與畫面對應；測試加入歷史資料與LED時間紀錄驗證。
- **影響：**`/api/data`與`/api/led/status`新增LED閃紅紀錄欄位，RFID／PIR快照新增最近紀錄欄位，不移除既有最後一筆欄位。歷史只存在ESP32 RAM，重啟清空；前端不另行累積。LED閃紅紀錄最多依設定的警示次數保存，RFID與移動偵測固定最多5筆。
- **驗證：**`node tests/test_led_polling.cjs`與`node tests/test_rfid_ui.cjs`通過；`python -B -m unittest discover -s tests -v`通過22/22；指定Python檔案`py_compile`通過；Chromium以模擬API實際檢查LED顯示5筆序號／時間、RFID只顯示輸入6筆中的最後5筆、移動偵測只顯示輸入6筆中的最後5筆，且uPlot Canvas存在；完整文件13/13個Mermaid區塊以Mermaid 11.13.0解析通過。未進行ESP32實機驗證。
- **部署／回復：**需同步部署`index.html`、`web_server.py`、`services/led_service.py`、`hardware/rfid.py`、`hardware/motion.py`、`tasks.py`及其相依版本文件，重啟ESP32後強制重新整理瀏覽器；不可只上傳`index.html`，因為新欄位由裝置端狀態與API提供。回復時同步還原上述程式、測試、文件與本紀錄，避免前端與API契約不一致。

## CHG-20261012-011｜由/api/data提供光照遲滯門檻

- **類別：**需求變更（API與網頁圖表設定同步）。
- **日期／紀錄時間：**2026-10-12 00:05:15 +08:00，工具取得時間。
- **原因：**確認光照紅線不應在`index.html`重複寫死1000／1100；實際裝置`config.py`的觸發值為500、復位值為1100，前端必須使用同一份裝置設定。
- **作法：**`web_server.py`匯入`config`，讓`/api/data`新增`light_thresholds.trigger`與`light_thresholds.reset`；`index.html`新增`updateLightThresholds()`，從API回應更新uPlot紅線與數字標籤，初次缺少有效欄位時不繪製、已取得有效值後暫時缺欄位則保留最後值。更新Python／Node測試與兩份uPlot整合文件。
- **影響：**`/api/data`回應新增欄位，不移除既有欄位；光照紅線會顯示裝置實際門檻，例如目前`暗 500`／`亮 1100`。不改變80筆歷史、移動平均（仍未加入）、ADC取樣或LED後端控制。
- **驗證：**`node tests/test_led_polling.cjs`與`node tests/test_rfid_ui.cjs`通過；Python桌面回歸測試20/20通過；`py_compile web_server.py`通過；Chromium以模擬API先提供500／1100、再改提供700／1200，確認前端門檻診斷值同步更新且uPlot圖表仍正常；Mermaid 11.13.0解析兩份文件共13/13個圖表區塊通過。未進行ESP32實機驗證。
- **部署／回復：**同步部署`web_server.py`與`index.html`，重啟ESP32並強制重新整理；回復時兩者與文件、`ChangeLog.md`需同步還原，避免前端期待不存在的`light_thresholds`欄位。

## CHG-20261011-010｜在光照圖加入亮暗遲滯紅線

- **類別：**需求變更（網頁圖表操作提示）。
- **日期／紀錄時間：**2026-10-11 23:52:01 +08:00，工具取得時間。
- **原因：**使用者希望在光照折線圖中直接看見亮暗控制的緩衝區，並以數字標示兩條邊界。
- **作法：**`index.html`新增`LIGHT_ALERT_TRIGGER_ADC = 1000`與`LIGHT_ALERT_RESET_ADC = 1100`，透過uPlot`hooks.draw`繪製兩條紅色實線，分別標示`暗 1000`與`亮 1100`；1000～1099的遲滯區間不加入移動平均，也不改變原始光照資料與LED後端判斷。
- **影響：**圖表在目前0～2048或高值時0～4095的Y軸內顯示兩條操作參考線；前端門檻常數必須與裝置端`config.py`保持一致。API、80筆歷史視窗、uPlot資產與ESP32控制邏輯不變。
- **驗證：**`node tests/test_led_polling.cjs`與`node tests/test_rfid_ui.cjs`通過；Chromium以本機uPlot資產及模擬API確認0～2048與擴展至4095時，1000／1100兩條紅色實線及標籤都有Canvas紅色像素；未進行ESP32實機驗證。
- **部署／回復：**只需部署更新後的`index.html`；回復時還原本紀錄前的`index.html`、文件與`ChangeLog.md`即可。

## CHG-20261011-009｜光照歷史折線改顯示最近80筆

- **類別：**需求變更（網頁圖表顯示範圍）。
- **日期／紀錄時間：**2026-10-11 23:32:39 +08:00，工具取得時間。
- **原因：**使用者希望利用整列光照卡片顯示較長的光照歷史，先觀察80筆原始資料的折線效果；本次不加入移動平均或其他濾波。
- **作法：**`index.html`將`LIGHT_HISTORY_LIMIT`由20改為80，光照卡片說明文字、`WEB_UI_EXECUTION_GUIDE.md`與`SYSTEM_ARCHITECTURE.md`同步改為最近80筆，X軸滑動視窗同步維持`0～79`；資料仍限制在0～4095並沿用2048／4095自適應Y軸。
- **影響：**以目前約每秒一次的感測輪詢，圖表約涵蓋80秒；歷史仍只存在瀏覽器RAM，`/api/data`、ESP32後端與uPlot資產不變。80筆增加的是觀察時間範圍，不等同數學上的平滑處理。
- **驗證：**`node tests/test_led_polling.cjs`與`node tests/test_rfid_ui.cjs`通過；Chromium以本機uPlot資產及模擬API加入81筆原始樣本，確認保留80筆、X軸為`0～79`、Canvas存在且最後資料仍為原始值，未套用移動平均。未進行ESP32實機驗證。
- **部署／回復：**只需部署更新後的`index.html`；文件同步納入版本庫。回復時還原本紀錄前的`index.html`、`WEB_UI_EXECUTION_GUIDE.md`、`SYSTEM_ARCHITECTURE.md`與`ChangeLog.md`即可。

## CHG-20261011-008｜補充uPlot與Web資產整合教學文件

- **類別：**需求變更（文件補充）。
- **日期／紀錄時間：**2026-10-11 23:24:01 +08:00，工具取得時間。
- **原因：**使用者要求詳細說明uPlot如何整合進`index.html`與`web_server.py`（使用者訊息中的`web_server.ph`依目前專案實際檔名更正為`.py`），讓載入順序、資料生命週期、軸範圍、靜態資產路由、快取與ESP32部署責任清楚可追蹤。
- **作法：**在`WEB_UI_EXECUTION_GUIDE.md`新增uPlot整合專節，說明HTML引用、`updateLightChart()`資料流、20筆瀏覽器歷史、X／Y軸設定、Canvas更新、錯誤定位與`Response.send_file()`路由；在`SYSTEM_ARCHITECTURE.md`新增裝置資料／頁面應用／繪圖函式庫的責任分層、部署檢核與故障邊界。
- **影響：**只修改教學與架構文件，不改變程式、API、部署資產或裝置行為；兩份Markdown的整理時間更新為2026-10-11 23:23:20 +08:00。
- **驗證：**Mermaid 11.13.0實際解析`WEB_UI_EXECUTION_GUIDE.md` 12/12、`SYSTEM_ARCHITECTURE.md` 1/1，共13/13個圖表區塊通過；uPlot URL、路由、函式名稱與部署檔案以目前`index.html`／`web_server.py`實作交叉檢查一致。未進行ESP32實機驗證。
- **部署／回復：**文件可直接納入版本庫；回復時還原本紀錄前的`WEB_UI_EXECUTION_GUIDE.md`、`SYSTEM_ARCHITECTURE.md`與`ChangeLog.md`即可。

## CHG-20261011-007｜修正uPlot光照折線只顯示前兩點

- **類別：**BUG（光照圖表更新）。
- **日期／紀錄時間：**2026-10-11 22:53:23 +08:00，工具取得時間。
- **原因：**使用者回報uPlot折線只顯示前兩點且不再向後延伸。原因是更新資料時保留`setData(..., false)`，但X軸仍使用自動範圍；初始範圍未同步到新增資料，造成後續點落在可視範圍外。
- **作法：**將uPlot X軸改為明確的非自動範圍，依目前最近20筆資料同步設定`0`至`length - 1`（單點時至少保留`0～1`）；Y軸既有自適應2048／4095邏輯不變。測試替身同步記錄X軸範圍，加入點數增加時X軸上限擴展的回歸檢查。
- **影響：**光照折線會隨新資料延伸，超過20筆後保留最近20筆並維持可視寬度；不改變感測資料契約或其他卡片。
- **驗證：**`node tests/test_led_polling.cjs`與`node tests/test_rfid_ui.cjs`通過；Python桌面回歸測試20/20通過；`py_compile web_server.py`通過；Chromium以本機uPlot資產及模擬API加入光照樣本後，確認資料長度達20且X軸範圍為0～19，折線會持續向後延伸。未進行ESP32實機上傳與實機瀏覽器驗證。
- **部署／回復：**部署更新後的`index.html`與`ChangeLog.md`；回復時還原本紀錄前的`index.html`即可。

## CHG-20261011-006｜部署本機uPlot並改用自適應光照圖表

- **類別：**需求變更（網頁圖表與部署資產）。
- **日期／紀錄時間：**2026-10-11 22:27:21 +08:00，工具取得時間。
- **原因：**使用者同意以輕量圖表函式庫取代自製SVG光照圖，並要求光照Y軸聚焦在實際常用的2048以下區間；同時必須把函式庫下載並隨ESP32 Web資源部署，不依賴外部CDN。
- **作法：**固定採用uPlot 1.6.32，從npm官方tarball下載並以npm metadata的SHA-512 integrity驗證通過；部署`assets/uplot/1.6.32/uPlot.iife.min.js`（51081 bytes）、`uPlot.min.css`（1857 bytes）及MIT `LICENSE`。`web_server.py`新增兩個固定資產路由，使用`Response.send_file()`串流與長效快取。`index.html`改以uPlot Canvas繪製最近20筆光照資料；Y軸平時為0～2048並使用0／512／1024／1536／2048刻度，資料出現大於2048時擴展至4095並使用完整刻度，超出ADC邊界的資料限制到0～4095。
- **同步更新：**`tests/test_led_polling.cjs`、`tests/test_rfid_ui.cjs`加入uPlot測試替身與自適應Y軸範圍驗證；`WEB_UI_EXECUTION_GUIDE.md`、`SYSTEM_ARCHITECTURE.md`與`GIT_VERSION_CONTROL.md`補充本機資產生命週期、路由、ESP32部署結構及資產納入版控的指令。
- **影響：**新增約51 KB JavaScript與約2 KB CSS的本機Web資產；不改變`/api/data`、LED快速狀態、LED owner、RFID或移動偵測資料契約。資產版本固定於URL路徑，升級函式庫時需同步新增版本目錄、路由與部署檔案。
- **驗證：**uPlot tarball integrity通過；`node tests/test_led_polling.cjs`與`node tests/test_rfid_ui.cjs`通過；Python桌面回歸測試20/20通過；`py_compile web_server.py`通過；修改後的`WEB_UI_EXECUTION_GUIDE.md`與`SYSTEM_ARCHITECTURE.md`全部13個Mermaid區塊以Mermaid 11.13.0 parser解析通過。Chromium以本機靜態資產及模擬API實際驗證uPlot載入、Canvas建立、0～2048一般刻度、超過2048時4095刻度、折線繪製及窄螢幕布局。未進行ESP32實機上傳、MicroPython資產路由與實機瀏覽器驗證。
- **部署／回復：**上傳`index.html`、`web_server.py`、`assets/uplot/1.6.32/`、測試與文件；重啟ESP32並強制重新整理瀏覽器。回復時需同步移除uPlot資產路由與資產，或還原本紀錄前的`index.html`與`web_server.py`，避免頁面請求不存在的資產。

## CHG-20261011-005｜放大光照折線圖並補充Y軸刻度

- **類別：**需求變更（網頁介面）。
- **日期／紀錄時間：**2026-10-11 21:52:05 +08:00，工具取得時間。
- **原因：**使用者希望光照卡片撐滿整列，並透過Y軸刻度與水平虛線清楚辨識光照數值所在區域及變化。
- **作法：**`index.html`讓光照卡片跨滿感測卡片區整列；SVG圖表擴大為全列寬度，新增固定0～4095 ADC的Y軸刻度（4095、3072、2048、1024、0）與五條水平虛線；折線改依ESP32 12-bit ADC固定範圍繪製，超出範圍的顯示值限制在圖表邊界內。`tests/test_led_polling.cjs`新增0與4095邊界位置驗證。
- **影響：**只改變光照網頁呈現與瀏覽器繪圖座標，不改變光照API、警示閾值、LED owner或其他卡片資料。固定Y軸讓不同時間的圖表可直接比較，但低幅度變化可能比自動縮放更不明顯。
- **驗證：**已執行 `node tests/test_led_polling.cjs`、`node tests/test_rfid_ui.cjs`，兩項均通過；`python -B -m unittest discover -s tests -v` 執行20個測試，20/20通過。以模擬API回應完成Chromium實際檢查：桌面光照卡片跨滿整列、Y軸刻度與水平虛線可見，變化資料可依固定ADC範圍繪製；窄螢幕光照卡片寬度符合單欄布局。未進行ESP32實機驗證。
- **部署／回復：**部署時更新 `index.html` 與前端測試檔；瀏覽器強制重新整理。可回復本次修改前的 `index.html`、`tests/test_led_polling.cjs` 與本紀錄新增段落。

## CHG-20261011-004｜重新配置網頁儀表板卡片與光照折線圖

- **類別：**需求變更（網頁介面）。
- **日期／紀錄時間：**2026-10-11 21:39:33 +08:00，工具取得時間。
- **原因：**使用者要求將光照卡片改為折線顯示，RFID 與移動偵測卡片並列，將 LED 狀態區移到控制按鈕上方，並放大主要文字。
- **作法：**`index.html`新增不依賴外部套件的 SVG 光照折線圖，保留最近 20 次有效 ADC 讀值並由既有感測輪詢更新；RFID／移動偵測改用雙欄卡片布局，窄螢幕自動改為單欄；LED 狀態與命令提示合併成狀態區並移到按鈕列上方；同步放大卡片、系統狀態、LED 狀態與按鈕文字。`tests/test_led_polling.cjs`及`tests/test_rfid_ui.cjs`補充折線圖更新與空圖提示驗證。
- **影響：**只改變網頁呈現與瀏覽器內的光照歷史快取，不改變後端 API、LED 權限／busy 檢查、RFID／PIR資料契約或 ESP32 控制流程。光照折線歷史於頁面重新載入後清空。
- **驗證：**已執行 `node tests/test_led_polling.cjs`、`node tests/test_rfid_ui.cjs`，兩項均通過；`python -B -m unittest discover -s tests -v` 執行 20 個測試，20/20 通過。以本機靜態頁面及模擬 API 回應完成 Chromium 實際布局檢查：桌面 RFID／移動偵測同列、LED 狀態在按鈕上方、光照折線圖可見；窄螢幕兩卡片改為單欄。未進行 ESP32 實機驗證。
- **部署／回復：**部署時更新 `index.html`，瀏覽器強制重新整理以取得新頁面；可由本次修改前的 `index.html` 與兩個測試檔案回復，後端不需重新上傳。

## CHG-20261011-003｜補充新增LED效果需求的快速整合方法

- **類別：**需求變更（文件）。
- **日期／紀錄時間：**2026-10-11 16:51:48 +08:00，工具取得時間。
- **原因：**使用者要求將「增加按鈕 3、按下時綠閃 3 次」的擴充說明整合進單一 LED owner 講義，說明目前機制如何在不新增第二個控制者的情況下快速加入新需求。
- **作法：**`LED_SINGLE_OWNER_GUIDE.md` 新增 0.8 節，說明綠閃效果規格、紅閃／綠閃同時發生時採先接受者完成、後來者以 `busy` 拒絕的政策；補充正常／效果狀態流程、按鈕去彈跳與按住拒絕、`main.py`／`tasks.py`／`config.example.py`／`services/led_service.py`／測試的整合點，以及新增效果所需的測試清單。
- **已實作／提案：**本次只更新文件，沒有新增按鈕 3、綠閃效果或任何韌體程式；`_EFFECTS` 表與相關程式片段是後續實作建議，不代表目前程式已支援綠閃。
- **驗證：**既有文件的 21 個 Mermaid 區塊使用 Mermaid 11.13.0 parser 實際解析，21/21 通過；桌面回歸測試執行 20 個測試，20/20 通過。未進行新增按鈕 3 的 ESP32 實機驗證，因本次未修改程式。
- **影響／部署／回復：**只更新教學文件與變更紀錄，不需重新上傳韌體。可由本次修改前的 Git 版本回復 `LED_SINGLE_OWNER_GUIDE.md`；既有 LED 控制機制不變。

## CHG-20261011-002｜以國中生比喻與第一性原理重整LED單一擁有者講義

- **類別：**需求變更（文件與教學順序）。
- **日期／紀錄時間：**2026-10-11 15:33:16 +08:00，工具取得時間。
- **原因：**使用者要求先清楚說明三種需求共用一個三色 LED 所造成的紅閃、恢復、禁用與時序錯亂，再說明目前解法；並以費曼式、國中生可理解的比喻建立第一性原理技術樹，明確區分目前實機操作良好與尚未完整測試。
- **作法：**重整 `LED_SINGLE_OWNER_GUIDE.md` 開頭閱讀路線，新增「問題→解法→第一性原理技術樹→技術點逐一解釋→證據界線」；用受理窗口、待辦清單、LED 工作員、號碼牌、火警演習與公告欄等比喻對應 `submit`、`queue`、`LedService.run`、receipt、reserved／busy、狀態機、快照與後端權威；保留後續案例、網頁狀態、附錄規格與部署參考。
- **已實作／提案：**本次只修改講義，不修改 LED 控制程式；目前架構仍是實體按鈕、網頁按鈕與光感警示共用單一 LED owner。更好的仲裁機制仍是後續比較題目；MQTT callback 未接通與實機測試不完整的限制已在講義中明確標示。
- **驗證：**`LED_SINGLE_OWNER_GUIDE.md` 全部 21 個 Mermaid 區塊使用 Mermaid 11.13.0 parser 實際解析，21/21 通過；`python -B -m unittest discover -s tests -v` 執行 20 個桌面回歸測試，20/20 通過。未宣稱已完成 ESP32 實機、長時間、多來源壓力、網路或所有故障時序驗證。
- **影響／部署／回復：**只更新教學文件與變更紀錄，不需重新上傳韌體。可由本次修改前的 Git 版本回復 `LED_SINGLE_OWNER_GUIDE.md`；既有 `CHG-20261011-001` 與歷史紀錄保留。

## CHG-20261011-001｜從 main.py 重整 ESP32 系統架構文件

- **類別：**需求變更（文件）。
- **日期／紀錄時間：**2026-10-11 14:32:36 +08:00，工具取得時間。
- **原因：**使用者要求從 `main.py` 開始解析 ESP32 IoT 專案，並將分析整合回 `SYSTEM_ARCHITECTURE.md`；原文件仍含九個任務、LED 直接寫入、RFID／PIR／喇叭未整合等過時描述。
- **作法：**重整 `SYSTEM_ARCHITECTURE.md`，補充 `boot.py`→`main.py` 啟動鏈、硬體初始化順序、共享事件與狀態、目前 13 個應用協程、`LedService` 單一 owner、DHT／光感／PIR／RFID／OLED／喇叭資料流、HTTP API、MQTT callback 未接通的實作限制、部署相依與實機檢核順序。同步移除已不符合目前程式的舊 LED `off()`／自動控制描述。
- **已實作／提案：**本次只更新文件；文件中的 MQTT 修正、感測資料品質、健康監控、任務 supervisor、安全與部署改善仍是待後續實作的提案，未宣稱已修正程式。
- **驗證：**`SYSTEM_ARCHITECTURE.md` 的全部 1 個 Mermaid 區塊已使用 Mermaid 11.13.0 parser 實際解析，1/1 通過；`python -B -m unittest discover -s tests -v` 執行 20 個桌面回歸測試，20/20 通過。未進行 ESP32 實機、GPIO 接線、WiFi、MQTT、Microdot 或周邊驗證。
- **影響／部署／回復：**只需更新教學文件，不需重新上傳韌體。可由本次修改前的 Git 版本回復 `SYSTEM_ARCHITECTURE.md`；`ChangeLog.md` 保留本紀錄與既有歷史。


## CHG-20261007-006｜實測後補充狀態有效期限講義

- **類別：**需求變更（講義與後續協作規則）。
- **日期／紀錄時間：**2026-10-07 14:35:19 +08:00，工具取得時間。
- **原因與實測來源：**使用者回報瀏覽器重新整理後不再因連線失敗訊息讓按鈕1瞬間失能，依先前約定補入講義。精確實測時間、持續時間與HTTP數據未提供；不宣稱偶發查詢失敗根因已修正。
- **作法：**LED_SINGLE_OWNER_GUIDE.md新增8C，以比較表、角色／變數表、決策圖、時序案例說明內容相同仍重新確認、連線健康與LED有效性分離、5秒期限、200ms監視、1秒timeout、診斷RAM與部署快取。8A前加版本提示，標示單次失敗立即停用已被取代；AGENTS.md優先規則同步引用8C及期限原則。
- **已實作／提案：**程式沿用5f3807c，不修改程式或參數；5秒是目前值並非普遍安全保證。PIR輸出仍沿用ab5465f，尚無新實機確認。本次沒有新增推送或事件歷史。
- **驗證：**講義全部20張Mermaid圖已使用11.13.0實際解析，20/20通過；未Typora／VS Code視覺布局驗證。純文件／規則修改不重跑程式測試，桌面結果與使用者實機回報分開記錄。
- **影響／部署／回復：**無需重新上傳ESP32；只更新教學與後續設計規則。ab5465f保存文件修改前版本，留在refactor/led-single-owner本機提交，未推送或合併。

## CHG-20261007-005｜PIR終端輸出改為帶時間的移動事件

- **類別：**需求變更。
- **日期／紀錄時間：**2026-10-07 14:25:22 +08:00，工具取得時間。
- **原因：**使用者希望Thonny不再被GPIO讀值0洗版，移動時顯示偵測時間。
- **作法：**tasks.py移除GPIO變化／每20次輪詢的診斷輸出與其計數器；首次高電位或低轉高時輸出偵測日期時間，沿用get_current_time，與網頁last_detected_at共用該次時間。持續高電位不重複輸出。啟動與錯誤訊息保留，偵測、音樂與網頁狀態政策不變。
- **驗證：**4個PIR／音樂桌面回歸測試通過；未ESP32／Thonny實機驗證。時間依裝置現有時鐘，未同步NTP時不保證實際時間準確。
- **部署／回復：**上傳tasks.py後重啟；5f3807c保存修改前版本。同步維護無狀態參數的測試時間來源，未修改講義；本機提交，未推送。

## CHG-20261007-004｜短暫LED查詢失敗與連線健康分開判斷（待實機確認）

- **類別：**BUG。
- **日期／內容紀錄時間：**2026-10-07 14:21:02 +08:00，工具取得時間。
- **原因：**使用者確認無操作時仍常見「LED狀態回應逾時或連接失敗」瞬閃；光照持續有資料。前端單次查詢失敗立即停用、下一次成功立即恢復，造成操作混淆。頻繁失敗根因尚未量測，不能宣稱網路或排程問題已修復。
- **比較基線：**修改前工作目錄乾淨，既有commit f6b8e53已保存立即停用版本，無需建立空提交；本次可用git diff f6b8e53比較。
- **作法：**index.html以performance.now單調時間分開記錄最近LED成功確認與任一資料API成功時間；LED內容即使相同也更新確認時間。單次失敗保留原狀態，LED超過5秒未確認才停用；光照API成功只能確認連線，不延長LED有效期限或回寫LED副本。獨立200ms監視有效期限，不必等HTTP回應才發現過期。紅閃／服務不可用仍立即停用，後端busy檢查不變。
- **參數與診斷：**5秒為待實測的容忍值，1秒單筆timeout及200ms輪詢保留；getLedDiagnostics提供连续失敗數、最近錯誤與兩種資料年齡，成功清除連續失敗數但保留最近錯誤。只存一筆錯誤與快照，不累積歷史。未取得新狀態時可能暫時保留過去可操作提示，後端仍拒絕紅閃改色。
- **驗證：**2組桌面JavaScript測試及20個Python回歸測試通過，涵蓋單次失敗不閃動、感測成功不延長LED期限、整體連線過期、相同快照刷新期限、晚到回應忽略與原RFID／PIR功能。未實機測試，講義依使用者要求待確認後再更新。
- **部署／回復：**僅需上傳index.html並強制重新整理，沿用已部署快速狀態API。可由f6b8e53取得舊index.html回復比較。只在本機分支實作／提交，未推送或合併。

## CHG-20261007-003｜講義比較網頁狀態架構並建立優先設計規則

- **類別：**需求變更（講義與協作規則）。
- **日期／內容紀錄時間：**2026-10-07 13:28:35 +08:00，工具取得當前時間。
- **原因：**使用者確認更新後即時反應良好，要求說明前後架構、改良思路與舊設計缺點，並優先沿用此方式。實機測試精確時間與量測數據未提供，不宣稱200ms上限或所有情況穩定。
- **作法：**LED_SINGLE_OWNER_GUIDE.md新增8B，包含雙架構圖、比較表、取樣／HTTP等待、重疊與舊回應風險、完整紅閃案例、RAM／JSON／Promise生命週期、逾時與權威控制、適用前提及流量／短事件限制。AGENTS.md增加網頁狀態顯示規則，優先輕量快照分流、單筆在途與逾時處理；200ms不作為通用固定值。
- **已實作與提案：**程式沿用2d62a2c，這次只修改文件／規則；事件紀錄、SSE／WebSocket僅說明替代方案，未實作。未以推論取代實測，舊回應亂序是程式風險而非已證實實機根因。
- **驗證：**講義全部18張Mermaid圖已使用11.13.0實際解析，18/18通過；未做Typora／VS Code視覺布局驗證。純文件修改，不重跑程式測試；先前20個Python與2組JavaScript測試結果見前次紀錄，實機反應良好由使用者本次回報。
- **影響／部署／回復：**不需上傳ESP32；講義與後續協作設計優先規則改變。以2d62a2c可取得本次文件修改前版本。留在refactor/led-single-owner本機提交，未合併或推送GitHub。

## CHG-20261007-002｜LED網頁狀態獨立快速輪詢，避免舊感測回應覆蓋

- **類別：**BUG。
- **日期／開始時間：**2026-10-07 13:01:16 +08:00。
- **桌面測試／內容紀錄時間：**2026-10-07 13:04:21 +08:00。
- **現象：**使用者回報實機紅閃開始約2秒後網頁才顯示警示／disable按鈕1，因效果已結束，提示瞬閃又恢復可操作。未取得HTTP時間線或ESP32排程量測，不能確認所有延遲來源。
- **確認的程式風險：**LED提示綁每秒/api/data；該端點包含感測資料處理，前端setInterval可使多筆請求重疊。較舊回應可能在較新回應之後更新LED。這不表示owner的busy檢查失效，提示與實際控制權應區分。
- **作法：**新增/api/led/status，只複製LedService RAM快照、不操作ADC／DHT／SPI／GPIO，回no-store。前端LED獨立完成後等200ms輪詢，單筆在途Promise共用；感測完成後等1000ms再取並防重疊，不再由感測回應更新LED或因感測失敗覆蓋LED通道。切色後亦刷新快速LED狀態。
- **逾時／資料生命週期：**LED請求1秒未完成用AbortController中止，顯示未知並停用；Promise.race忽略逾時後晚到回應，成功新快照才恢復。在途請求結束釋放Promise與timer；不持續累積setInterval請求。不變更命令佇列、owner仲裁或實體按鈕規則。
- **驗證：**20個Python測試通過，Microdot實際路由驗證新端點不調用ADC與no-store；原網頁JavaScript測試與新增延遲fetch測試通過，涵蓋慢感測不擋警示、舊感測不重新啟用、單筆在途、Abort逾時、晚到忽略與恢复。未實機重測、瀏覽器布局或HTTP延遲量測。講義新增通道圖，全部17張Mermaid圖已使用11.13.0實際解析，17/17通過。
- **影響與限制：**正常情況LED輪詢更密集、每頁最多約5次每秒，仍有HTTP與事件迴圈延遲，不保證200ms內更新。同步阻塞、WiFi或背景節流仍可能延遲，不能宣稱2秒根因完全解決；後端拒絕政策保持權威，未知狀態不放行。
- **文件／部署／回復：**LED_SINGLE_OWNER_GUIDE.md新增案例8A分流機制；更新web_server.py、index.html後重啟並強制刷新瀏覽器。不需更改config.py。回復4778911可取得原前端／API，須成對部署。本次留在refactor/led-single-owner本地提交，未推送。

## CHG-20261007-001｜以案例與分層圖解深化單一 owner 講義

- **類別：**需求變更（教學內容深化）。
- **日期／開始時間：**2026-10-07 02:57:54 +08:00。
- **內容紀錄時間：**2026-10-07 03:02:08 +08:00；16張Mermaid圖已於提交前確認解析通過。
- **需求與驗證來源：**使用者回報目前實機測試情況良好，要求降低認知負荷，詳細說明要素、邏輯與實際情境。實機時間、逐項測試與壓力數據未提供，不推論所有情境已驗證；本次沒有程式變更。
- **教學順序：**LED_SINGLE_OWNER_GUIDE.md 改成角色→資料→初始化→案例→進階附錄，前半先教提出要求、受理窗口、待辦清單、唯一工作者與GPIO工具，再對應實際函式。原完整規格保留於附錄供查表，不要求初次一次理解全部欄位。
- **資料機制：**分清命令、正常狀態、effect、receipt與實際GPIO；說明submit在來源task執行，run在唯一owner task執行，但共用同一LedService物件。queue與results引用同一receipt，來源拿副本，結果查詢再複製；queue移除不會立即刪掉結果，最近16筆之外才過期。
- **新增案例：**實體按鈕按下、ADC900觸發、兩事件接近同時、紅閃第三次期間按下並按住、網頁刷新前誤送POST、閃完後1100解除。各主案例有初始假設、Mermaid時序圖、函式／參數與資料位置、狀態表、最終結果及自我檢查。
- **競爭情境分解：**按鈕已執行則警示保存新綠色；按鈕已受理仍排隊則警示受理把它標rejected/alert_started，恢復舊藍色；警示先受理則按下被消耗或submit回busy。強調accepted不等於executed，不把感覺同時誤當同時執行，也不把所有拒絕路徑都說成產生命令ID。
- **保留課堂易錯點：**busy=false不等於armed=true；首次受理時busy已生效但effect可能仍None；持續按住不會在警示後補執行；必须警示後取樣ADC>=1100再ADC<1000。約20ms是檢查節奏、300ms是亮滅階段，不把理想時間表誤當精準實機量測。
- **驗證範圍：**逐項对照現有LedService、Button、tasks、main與Web程式。講義共有16張Mermaid圖，已使用11.13.0實際解析全部區塊，16/16通過。未做Typora／VS Code視覺布局驗證。純文件修改，不重跑程式測試；先前20個桌面測試及使用者實機回報仍按來源區分。
- **部署／回復：**無需重新上傳ESP32。留在refactor/led-single-owner本地提交，未合併或推送；原講義可由da7f007取得比較。先前卡鈍觀察不在此次處理範圍，沒有宣稱修正。

## CHG-20261006-012｜單一 LED owner 與命令仲裁實驗

- **類別：**需求變更（架構教學與獨立分支實驗）。
- **日期／開始時間：**2026-10-06 23:32:51 +08:00。
- **驗證／紀錄時間：**2026-10-06 23:46:02 +08:00。
- **需求：**使用者要求把多元控制單一LED方案寫成講義與Mermaid圖，再切分支實作，評估理解、實作與功能穩定性。不是處理卡鈍；先前卡鈍仍待觀測。
- **基線與狀態：**由乾淨main的88ca2fb建立refactor/led-single-owner；只本地實驗、未合併／推送。73d693f與light-led-alert-validated-20261006仍可回復已確認功能。

### 討論結論與實作

1. **責任集中：**新增services/led_service.py與套件__init__.py。RgbLed改為只轉色碼到GPIO且避免重複輸出；初始化安全熄燈後，正常操作与關機輸出都由唯一LedService.run流程執行。main只建立owner與提出停止，不直接寫GPIO。
2. **生產者：**實體按鈕與Web提交cycle，光照提交low_light_alert；既有MQTT改色分支亦提交set_color以避免留下旁路，但不修改既有MQTT callback接線，也未broker實機驗證。來源不讀改寫正常色碼，不執行效果。
3. **仲裁：**同步submit只做受理控制面，無await／GPIO；普通命令FIFO上限8。受理警示即reserved=true，將尚未執行的普通receipt改rejected/alert_started並清除，避免警示後補執行；忙碌時新改色與新警示立即拒絕、不排隊。cycle是相對變更，兩次不合併。警示先於待執行改色，已執行命令不撤銷。
4. **雙層狀態：**正常色碼／亮滅與effect分開；effect保存phase、次數、階段時間、原狀與receipt。owner每20ms讓出排程，每輪最多4筆，使用ticks_diff推進亮滅。延遲時每輪最多一個效果轉換，不跳過肉眼可見階段，可能延長總時間。五次完成先恢復GPIO，再解除busy並標executed。
5. **結果與生命週期：**receipt有id、kind、source、status、reason；受理副本不會自動變完成，最近16筆結果保留RAM可查，重啟清空。accepted→executing→executed；亦可能rejected、failed、cancelled。記錄可過期，查不到不等於未執行。有界清單不依賴uasyncio.Queue套件，不可從IRQ／thread直接使用。
6. **Web：**POST既有/api/led/toggle回202與ID表示受理，而非已改色；busy409、queue_full429、停止／未初始化503。新增GET /api/led/commands/<int:command_id>；前端區分受理、執行、後續拒絕、過期与斷線未知，不等待警示完成才回HTTP。每秒狀態快照仍顯示警示忙碌並停用按鈕。
7. **停止與錯誤：**request_stop停止受理／拒絕待處理；owner finally標未完效果cancelled、熄燈並set stopped Event。main等待owner完成清理。GPIO錯誤標failed並退出；硬體若連熄燈也失敗，不能承諾實際輸出。只有同一迴圈、經命令入口的來源才符合此所有權約定。
8. **保持功能政策：**完整五次期間拒絕改色、按鈕須放開重按；光照armed仍需警示結束後ADC>=1100才重新允許，再ADC<1000才觸發，未加冷卻或連續確認。未採背景改色／通用搶占，維持先前確認需求。

### 講義、理解成本與替代方案

- 新增LED_SINGLE_OWNER_GUIDE.md，以四張圖表示要素、HTTP受理到結果、警示競爭時機與狀態機，說明參數來源、快取生命週期、仲裁表、部署與驗收。旧LIGHT_LED_ALERT_GUIDE.md加版本提示，保留token方案供比較。
- 講義說明critical section、一致性、所有權、仲裁是互補層次；非同步for+await不阻塞整個迴圈也可取消，本次選狀態機是集中仲裁，不是將其誤當無法中斷。
- 可讀性初步判斷：硬體與來源更簡單、責任集中；owner增加有界佇列、狀態機與結果協定，整體不一定更短，初學者需理解accepted不等於executed。是否更容易教學或實機更穩定仍需驗收，未宣稱結論已成立。
- 未選等待式Lock（會延後操作）、背景desired更新（會不恢復原狀）與泛用優先權搶占框架（目前規則不需要）；單一owner本身不能替代仲裁政策。

### 驗證與可觀察差異

- **20個Python測試通過：**FIFO、兩次cycle、預約警示競爭、拒絕待執行／新命令、完整五次／熄滅恢復、tick回繞、延遲不跳階段、容量／歷史上限、取消／關機、GPIO錯誤、實際main錯誤後owner清理、真正Button去彈跳拒絕與PIR／RFID回歸。固定隨機種子1000輪混合命令加200輪收尾驗證有界與結束。以本專案Microdot TestClient驗證實際路由202、結果查詢與429，另驗證handler409／404。
- **網頁JavaScript模擬測試通過：**受理／執行、受理後拒絕、busy停用、重啟可用以及原RFID／PIR顯示。未真實瀏覽器布局、ESP32 SPI/GPIO、broker或實機壓力驗證。
- **Mermaid：**原暫存解析器依賴缺損，另在暫存目錄建立mermaid11.13.0+jsdom，四張圖實際解析4/4通過；未做Typora／VS Code視覺布局驗證，不增加專案執行依賴。
- **差異：**白色7改由owner於完整初始化後首次渲染，WiFi／NTP／MQTT等待期間LED保持安全熄滅；Web受理成功從200改202；正常命令至少等待owner下一輪，不再同步完成。這些需納入實機驗收。

### 部署與回復

部署main.py、tasks.py、web_server.py、index.html、hardware/led.py與services整個目錄，保留已確認Button、PIR／RFID／sensors及私人config.py。本次未新增配置，既有LIGHT_ALERT_*沿用。重啟重新載入HTML。詳見新講義。

實驗不推送或合併。回復git switch main後須整套部署main/tasks/web_server/index與hardware/led，不可混用舊token控制器和新owner介面；私人配置未改。旧services可留在裝置，但舊main不匯入。每次提交包含此紀錄，實際commit由Git查詢。

## CHG-20261006-011｜講義強調光照警示的重新允許条件

- **類別：**需求變更（教學說明補充）。
- **日期／紀錄時間：**2026-10-06 15:48:55 +08:00。
- **原因：**使用者在教室誤以為紅閃功能失效，後確認是未考慮「先回升至1100或以上，再降到1000以下」的重新允許條件，要求講義強調，避免學生誤解。此項不代表版本BUG或已確認的卡鈍根因。
- **作法：**LIGHT_LED_ALERT_GUIDE.md 在操作規則開頭增加醒目提示、四步實驗流程、五組ADC序列比較與邊界值說明。清楚區分「紅閃結束」和「armed重新允許」，說明遲滯機制、警示期間變亮不算重新允許、教室環境可能達不到解除閾值。
- **機制：**觸發要求ADC<1000且armed；觸發後armed=false。警示結束後背景取樣到ADC>=1100才armed=true；接著低於1000才再觸發。1100可解除，1000不能觸發；一秒保持只是課堂觀察建議，不是程式計時要求。
- **影響／驗證：**僅改講義與本紀錄，按現有tasks.py邏輯核對例子；無程式或配置變更，不重跑測試。修改文件沒有Mermaid圖。先前偶有卡鈍仍待觀測，本次不處理或宣稱已解決。
- **部署／回復：**不需上傳ESP32或重新部署；講義使用新版即可。此文件修改保存本地提交，未另推送GitHub；可透過Git歷史取回旧文件。

## CHG-20261006-010｜保存紅閃確認版並記錄待觀測卡鈍

- **類別：**需求變更（版本發布）；另記錄疑似 BUG，尚未確定或修正。
- **日期／紀錄時間：**2026-10-06 10:26:24 +08:00；實機測試精確時間未提供。
- **需求：**使用者確認紅閃五次相關功能與觸發時機測試正確，要求先合併推送 GitHub。
- **已確認與待觀測的區分：**紅閃結果由使用者實機回報；同時回報移動偵測與實體按鈕偶有卡鈍感受，但尚未詳細觀測。沒有量測、日誌或可重現步驟，未確認根因或與警示的關聯，未修正；依使用者要求後續再調查，不宣稱全系統即時性／效能已通過驗證。
- **作法：**fetch 確認遠端 main 無新增提交；更新 LIGHT_LED_ALERT_GUIDE.md 的驗證範圍與待觀測事項，提交後將 feature/light-led-alert 快轉合併 main，建立帶註解標籤 light-led-alert-validated-20261006，推送 main、功能分支與標籤至原 origin，核對遠端 SHA。
- **驗證與影響：**既有17個Python桌面測試通過，前次網頁JavaScript測試通過；本次無程式邏輯變更，不重複執行。保留五次警示、忙碌拒絕／不排隊、恢復原狀與舊配置相容修正，私人config.py不推送，討論及替代方案仍保留於CHG-20261006-008。
- **部署／回復：**依LIGHT_LED_ALERT_GUIDE.md部署；標籤light-led-alert-validated-20261006保存此次版本，前一版pir-music-web-validated-20261006保留供回復／比較。乾淨工作目錄建立回復分支後重新部署到ESP32，私人配置需另保留；回復舊sensors時恢復舊閾值參數。Git refs 為推送結果依據。

## CHG-20261006-009｜修正舊裝置配置導致感測器匯入失敗

- **類別：**BUG。
- **日期／開始紀錄時間：**2026-10-06 10:05:08 +08:00。
- **現象／原因：**使用者回報 hardware/sensors.py 載入 LightSensor 時缺少 LIGHT_ALERT_TRIGGER_ADC。方法預設參數直接引用 config 屬性，會在定義類別時求值；裝置尚未新增參數或使用舊配置，就在 main 初始化前發生 AttributeError。光照任務的 getattr 預設值無法補救更早的類別匯入錯誤。
- **作法：**is_dark/is_bright 的預設 threshold 改為 None，在實際呼叫時才用 getattr 讀配置，缺少鍵時分別使用 1000／1100；顯式 threshold 仍優先，保留原本 <／> 判斷。未改私人 WiFi 或警示控制規則。
- **驗證：**新增實際載入 sensors 模組的舊配置回歸測試，覆蓋缺少新鍵仍可匯入、預設閾值、顯式參數與動態配置；本次17個Python測試全部通過。桌面 fake ADC，不是 ESP32 實機驗證。
- **部署／回復：**重新上傳 hardware/sensors.py 後重啟；仍建議同步更新裝置 config.py 的 LIGHT_ALERT_*，確保自訂閾值生效，保留私人 WiFi。若撤回此修正，必須先補齊新參數才能避免相同匯入錯誤。本次本地 feature/light-led-alert 提交，未合併或推送。

## CHG-20261006-008｜光照紅閃五次與 LED 操作完整性

- **類別：**需求變更。
- **日期／開始時間：**2026-10-06 09:51:01 +08:00。
- **測試與文件紀錄時間：**2026-10-06 09:59:16 +08:00。
- **實作狀態：**本地 feature/light-led-alert 分支；桌面測試通過，尚未 ESP32 實機確認、合併或推送。

### 需求、討論與最終決策

使用者要求 ADC 低於閾值時先保存 RGB LED 狀態、紅閃五次後恢復，並要求先討論同時控制與分支策略。最初提案將正常狀態與警示輸出分離：警示占用輸出，按鈕更新背景選擇，完成後顯示最新選擇。這種覆蓋機制其實可以避免綠燈插入紅閃，但使用者看不到按下的立即效果，而且完成後不再嚴格恢復原狀。

使用者提出「紅燈閃了三次突然變綠，再閃兩次」會混淆，詢問五次警示是否應為 atomic operation。經討論後，使用者明確同意「警示期間拒絕改色、不排隊、完成後恢復原狀」，並要求本檔記錄討論、實作機制及替代方案優劣。上述背景更新方案未採用。

最終行為：低於 1000 觸發一次，红亮／全滅各 300 ms，五次後恢復 `(色碼, 亮滅狀態)`。警示期間拒絕實體按鈕1、網頁按鈕1與 MQTT 改色；實體按鈕必須放開再重新按下。持續暗不重複，警示完成後取樣到 ADC >= 1100 才重新允許下一次低於 1000 的觸發。開機已暗亦警示一次。系統清理可中止警示並熄燈。

### 如何實現 atomic 行為與資源控制

1. **單一控制入口：**hardware/led.py 的一般方法 set_color_by_index、next_color、on、off、toggle 都經過 `_require_available()`。警示中丟出 LedBusyError，立即拒絕，不等待鎖、不存待執行改色命令。不是只靠網頁停用。
2. **在通知前取得控制權：**light_sensor_task 在觸發時同步 begin_alert，保存 current_color_index 與 is_on，建立唯一 object token，再 Event.set；這段沒有 await，因此一般協程無法在檢查與取得控制權之間插入。警示任務尚未取得排程，入口也已 busy。
3. **取樣與閃爍分離：**main 建立獨立 light_alert_event，將光照取樣與警示任務加入 gather。取樣保持50 ms；警示任務 wait/clear 後取 token，紅亮／熄滅各 await 300 ms。RFID、PIR音樂、按鈕、Web、MQTT仍可取得排程。
4. **不污染正常狀態：**alert_step 只寫 GPIO，紅色為索引4，全滅為0，不改正常色碼／is_on。五次正常完成、普通例外或取消都由 finally/end_alert 恢復快照後才釋放 token。原本關燈時恢復熄滅並保留原選定色碼。
5. **關機優先：**main 使用 shutdown，使 token 失效、清除快照並永久熄燈。晚到的警示步驟或 finally 先檢查 token，不再恢復舊顏色。不是讓一般 off 繞過警示封鎖。
6. **實體輸入消耗：**Button.wait_press 新增 reject_if，最初讀到按下與去彈跳期間記住 press_rejected；即使警示在去彈跳途中結束，仍拒絕該次按下。button1_task 保留 wait_release，不因警示完成後仍按住而補執行。控制器的最終檢查仍封鎖警示於呼叫前開始的競爭情況。
7. **Web／MQTT回應：**/api/data 加入 led.alert_active、available、正常色碼與is_on，網頁每秒刷新停用LED按鈕並提示警示中。POST直接呼叫控制器，忙碌回HTTP409，即使舊頁面、刷新延遲或其他客戶端亦無法繞過。MQTT改色分支捕捉同一錯誤並記錄未執行、不排隊；未做broker端到端測試。
8. **遲滯與RAM：**armed只在警示結束後且讀到解除閾值才重設；警示中亮暗交替不排隊。快照、token、Event、armed都在RAM，重啟清空，不寫Flash。配置同步至私人config.py與公開config.example.py，不修改WiFi秘密。

這裡的 atomic 是應用層排他控制與可見操作完整性，不是三秒內禁止排程，也不是硬體三個GPIO同時切換。保證前提為所有一般LED操作經同一物件、單一uasyncio迴圈、同步檢查／寫入無await；新增執行緒、IRQ或直接寫GPIO需另設同步。取消、例外與關機允許中止五次序列，不能宣稱故障時也必定完成五次。

### 替代方案與優劣（以下未採用者皆僅提案）

| 方案 | 優點 | 缺點／決策 |
|---|---|---|
| 忙碌立即拒絕、不排隊 | 警示完整、恢復原狀、記憶體小、操作結果明確 | 約3秒不能改色，需提示；本次實作 |
| 紅閃覆蓋＋保存最新使用者意圖 | 不插入綠燈，也不丟掉最後選擇 | 按下無即時反應，完成後不恢復原狀；討論後否決 |
| FIFO排隊改色 | 每個命令都可稍後執行 | 延遲後突然連續換色，需上限／過期／回應設計；否決 |
| await互斥鎖 | 可協調共用資源 | 會等待並延後執行，違反不排隊；鎖本身不決定UX／優先權；否決 |
| 手動操作優先並中止紅閃 | 立即反應 | 五次警示可能不完整，需取消與恢復政策；否決 |
| 不協調直接写GPIO | 程式最少 | 紅／綠交錯、狀態恢復競爭，不符合需求；否決 |
| 單一LED工作任務＋命令佇列 | 可擴充多種效果／優先權 | 改造較大，仍需設計忙碌拒絕、佇列與取消；未實作，未來效果增加可考慮 |

### 影響、驗證與部署／回復

- **配置變更：**移除旧 LIGHT_AUTO_CONTROL_ENABLED 與 LIGHT_THRESHOLD_ON/OFF，用 LIGHT_ALERT_ENABLED、LIGHT_ALERT_TRIGGER_ADC、LIGHT_ALERT_RESET_ADC、LIGHT_ALERT_BLINK_COUNT、LIGHT_ALERT_ON_MS、LIGHT_ALERT_OFF_MS 取代自動亮滅模式；sensors輔助方法同步新閾值。保留 LIGHT_POLL_INTERVAL_MS=50。
- **測試：**16個Python測試與網頁JavaScript模擬測試通過，涵蓋五次輸出序列、亮／滅快照恢復、所有一般方法拒絕、去彈跳期間拒絕、實體按下消耗、HTTP409、防止排隊、閾值邊界／遲滯、取消清理與shutdown阻止晚到恢復；LED／RFID／PIR回歸通過。網頁驗證停用、409競爭時機、恢復可用及斷線。未ESP32實機、實際時序、broker或瀏覽器布局驗證。
- **限制：**ADC閾值仍需實際校準；原LightSensor讀取失敗可能返回上次值，未新增量測健康判斷；網頁停用通常有約一秒延遲，後端拒絕才是權威。若對GPIO直接寫值或硬體故障，軟體閘門不能保證輸出。
- **文件／部署：**LIGHT_LED_ALERT_GUIDE.md 詳述機制與替代方案。上傳main、tasks、web_server、index.html及hardware/led、button、sensors，更新装置私人config.py的新參數後重啟刷新，勿以公開範本覆蓋WiFi。
- **版本回復：**保留 pir-music-web-validated-20261006 基線，乾淨工作目錄建立回復分支再部署。Git不恢復私人config.py；回到舊版sensors時須一併恢復該版LIGHT_THRESHOLD_ON/OFF與LIGHT_AUTO_CONTROL_ENABLED=False，WiFi秘密另保留。本次提交本地功能分支，待使用者實機确认才合併／推送。

## CHG-20261006-007｜發布使用者確認正常的 PIR 音樂與網頁版本

- **類別：**需求變更（版本發布與驗證紀錄）。
- **日期／紀錄時間：**2026-10-06 08:56:09 +08:00；使用者實際測試時間未提供。
- **原因：**使用者確認測試都正確，明確授權合併至 GitHub。
- **作法：**fetch 確認遠端 main 未有新增提交；更新 PIR_MUSIC_GUIDE.md 的驗證／版本狀態，提交後將 feature/pir-music 快轉合併至 main，建立帶註解標籤 pir-music-web-validated-20261006，推送 main、功能分支與標籤至既有 origin；以遠端 SHA 核對結果。
- **驗證：**實機正確由使用者回報，未提供逐項情境紀錄，不推論所有卡片、故障情境或瀏覽器皆已驗證。先前 10 個 Python 與網頁 JavaScript 模擬測試通過，詳見 CHG-20261006-006。本次僅更新文件與版本指標，無程式邏輯變更，不重複執行既有測試。
- **影響：**保留首次高電位／後續低→高觸發、非同步音樂、5 秒網頁提示與 RAM 次數／時間快取；私人 config.py 不上傳，公开 config.example.py 包含部署所需參數。
- **部署／回復：**詳見 PIR_MUSIC_GUIDE.md；確認版以 pir-music-web-validated-20261006 標籤取得，整合前已確認 RFID 版仍為 rfid-validated-20261006。乾淨工作目錄使用 git switch -c restore-pir-web pir-music-web-validated-20261006 建立回復分支，再部署至 ESP32；私人配置另行保留，不使用 force push 或 reset --hard。

## CHG-20261006-006｜網頁顯示移動提示與音樂狀態

- **類別：**需求變更。
- **日期／開始時間：**2026-10-06 02:41:04 +08:00。
- **測試完成／紀錄時間：**2026-10-06 02:43:22 +08:00。
- **先前故障確認：**使用者表示原先未重新上傳 config.py，更新後 PIR 與音樂已正常；實機測試精確時間未提供。CHG-20261006-005 的首次高電位與診斷修正仍保留，不將可能原因誤記為已確認實機根因。
- **原因：**使用者同意在同一偵測事件播放 ESP32 音樂並於網頁顯示「偵測到移動物」，保留提示至少 5 秒及最後時間、次數、播放狀態。
- **作法／呼叫：**新增 hardware/motion.py 狀態工廠；main 建立共享 RAM 字典，注入 Web Server 並傳給 PIR／播放任務。PIR 更新高電位、狀態、偵測提示、最後裝置時間與次數；播放任務更新 playing/completed/error/stopped。/api/data 加入 motion 快照；index.html 用既有每秒 fetch 與 textContent 顯示新卡片，網路失敗標示資料與播放狀態未知。
- **資料生命週期：**首次高或低→高每次觸發增加 count，播放 Event 仍合併待播，因此計數不是播放次數。提示在高電位持續，回低後使用 ticks_ms/ticks_diff 檢查至少 5000 ms 保留期；下次輪詢才清除。錯誤優先顯示異常。最後時間、次數、事件與狀態僅存 RAM，重啟清空，不寫 Flash 或保留完整歷史。
- **驗證：**10 個 Python 測試通過，新增提示時間邊界／tick 回繞／持續高／計數快取驗證並檢查 API motion 預設 JSON；網頁實際 JavaScript 在模擬 DOM/fetch 下驗證提示、等待、次數、時間、播放狀態、錯誤與斷線恢復通過。未做新版網頁的 ESP32 實機或瀏覽器布局驗證。
- **影響／限制：**ESP32 喇叭仍為唯一播放來源，未加瀏覽器音訊或移動 MQTT。播放狀態不保證實際有聲，短狀態可能被 1 秒輪詢略過。私人配置本次不需新增參數。
- **部署／回復：**部署 main.py、tasks.py、web_server.py、index.html、hardware/motion.py，保留已正常的其他硬體模組與 config.py，重啟以更新 HTML 快取。詳見 PIR_MUSIC_GUIDE.md；回到網頁整合前可使用 7f2c0d4，完整 RFID 基線仍為 rfid-validated-20261006。Git 不會自動恢復裝置 Flash 與私人配置。
- **版控：**提交本地 feature/pir-music；待使用者確認新網頁實機結果再合併／推送。

## CHG-20261006-005｜修正首次高電位不觸發並增加 PIR／喇叭診斷

- **類別：**BUG。
- **日期／紀錄時間：**2026-10-06 02:32:54 +08:00（開始檢查時間）。
- **現象：**使用者回報整合後感測不到、沒有聲音；尚未取得實機啟動日誌，不能宣稱已確定或排除接線／部署問題。
- **已確認的程式問題：**首次高電位被當基準忽略，持續高電位時永遠不觸發；喇叭初始化失敗也使 PIR 被略過，缺少診斷訊息。裝置未更新 config 或載入 ns_tools 的其他依賴失敗也是可能原因，並非已確認的實機根因。
- **作法：**首次高電位觸發一次，後續仍採低→高且持續高不重播；main 分開初始化 PIR／喇叭；印出腳位、初始／變化／每 20 次取樣讀值、任務啟動或略過，以及播放完成。Speaker 僅保留範例五個音符頻率，不再依賴 ns_tools；PWM 使用與範例相同的先建立、再 duty/freq 設定方式，設定失敗釋放資源。新增參數缺少時使用範例預設值，避免未更新裝置私人 config 直接停用功能。
- **影響：**開機或感測錯誤恢復後首次為高也可能播放一次；暖機訊號仍可能觸發。其他功能與私人配置不變；自訂音符需擴充模組頻率表。Web 與 MQTT 未修改。
- **驗證：**9 個桌面 Python 測試通過，調整首次高電位預期，保留事件合併、非同步播放與清理測試；未實機驗證。PIR_MUSIC_GUIDE.md 更新機制與獨立 PWM 測試方式。
- **部署／回復：**更新 main.py、tasks.py、hardware/sensors.py、hardware/speaker.py 後重啟；回報初始化與讀值日誌以進一步定位。仍可用 rfid-validated-20261006 回到已確認 RFID 版，或 1735948 檢視修正前 PIR 版。提交本地 feature/pir-music，不合併或推送。

## CHG-20261006-004｜整合 PIR 移動與非同步音樂播放

- **類別：**需求變更。
- **日期／作業開始時間：**2026-10-06 02:22:36 +08:00。
- **測試完成／紀錄時間：**2026-10-06 02:24:45 +08:00。
- **原因：**使用者同意參考單檔範例將 PIR 與無源喇叭接入 main；原範例同步 sleep 會阻塞其他協程，持續高電位也會反覆觸發，採用已確認的非同步播放與低→高觸發策略。
- **作法：**hardware/sensors.py 新增 PirSensor（GPIO 4）；新增 hardware/speaker.py（GPIO 6 PWM），沿用 ns_tools.NOTE_FREQS，以 await uasyncio.sleep 播放 C4/E4/D4/G3 各 0.3 秒加 0.2 秒休止。config.py 與 config.example.py 同步非機密腳位、500 ms 輪詢、512 占空比與旋律，私人 WiFi 值保留。
- **呼叫／生命週期：**main 初始化兩個硬體與獨立 Event，加入 PIR 偵測及播放任務。首次取樣建立基準，後續低→高才 set；播放任務 wait 後先 clear，再播放。Event 合併播放中多次觸發為最多一次待播，不累積計數或歷史；重啟清空事件與基準。播放 finally 靜音，main finally 釋放 PWM；初始化失败略過該功能，讀取／播放例外記錄並延遲重試。
- **影響：**不變更 RFID／LED／Web／MQTT 行為，未新增網頁或移動 MQTT 發布；ns_tools 原同步播放函式及单檔範例不改。500 ms 取樣可能漏掉短脈衝，未新增 PIR 暖機遮蔽；PWM 與音量需實機確認。
- **驗證：**9 個 Python 測試通過（3 個新增 PIR／音樂測試與 6 個 LED／RFID 回歸），涵蓋邊緣觸發、初始高電位、持續高電位、事件合併、協程讓出、音符與休止、錯誤／取消後靜音及重複釋放。既有 RFID 網頁 JavaScript 測試通過。均為桌面 fake 測試，未執行 ESP32 聲音、接線或時序實機驗證。
- **部署／回復：**詳見 PIR_MUSIC_GUIDE.md；部署 main/tasks/sensors/speaker 並新增裝置私人配置。回復使用 rfid-validated-20261006 標籤，重新部署舊應用；私人 config.py 不由 Git 回復。
- **版控：**在 feature/pir-music 本地提交；依已確認方案，等待使用者實機確認再合併與推送。main 與 GitHub RFID 標籤保持既有版本。

## CHG-20261006-003｜保存使用者確認正常的 RFID 版本

- **類別：**需求變更（版本發布與驗證紀錄）。
- **日期／紀錄時間：**2026-10-06 01:29:37 +08:00；實際實機測試時間未提供。
- **原因：**使用者回報目前 RFID 功能正常，明確要求進版本並推送 GitHub。
- **驗證來源：**ESP32 實機正常由使用者確認；未提供逐項驗收紀錄，不推論所有錯誤情境、卡片種類或瀏覽器皆已驗證。先前桌面 6 個 Python 測試及 JavaScript 測試結果仍見 CHG-20261006-002。本次沒有程式邏輯變更，不重複執行相同測試。
- **作法：**fetch 核對遠端；更新 RFID_INTEGRATION.md 的驗證／版本狀態；提交紀錄後，將 feature/rfid-integration 快轉合併至 main，建立帶註解標籤 rfid-validated-20261006，推送 main、功能分支與標籤至既有 origin。保留原基線標籤，完成後核對遠端 SHA 與工作目錄。
- **影響：**RFID 實作維持 6e341b6 的內容，只更新文件與版本指標；私人設定與備份仍排除於 GitHub。版本及 push 成功以 Git refs 為準。
- **回復：**乾淨工作目錄執行 git switch -c restore-before-rfid baseline-before-rfid-20261006 可取得整合前基線；執行 git switch -c restore-rfid rfid-validated-20261006 可取得此次確認版本。Git 切換後仍需自行部署到 ESP32，私人 config.py 另行保留／回復，不採 reset --hard 或 force push。

## CHG-20261006-002｜將 RFID 接入模組化程式與 Web 顯示

- **類別：**需求變更；連帶修正 API JSON 與網頁零值顯示 BUG。
- **日期／紀錄時間：**2026-10-06 00:31:46 +08:00。
- **需求原因：**使用者同意參考單檔範例整合 RFID，並保存可恢復的修改前版本。
- **作法：**新增 hardware/rfid.py，延後明確匯入 MFRC522Async、to_hex_string，沿用配置腳位與 request(REQIDL) → anticoll() → 完整 raw_uid 轉換。main 初始化 RFID 與共享字典，注入 Web Server 並加入 gather；tasks 每輪讀取後等待 500 ms，成功更新最後識別碼與装置時間，例外保留最後紀錄並持續重試。
- **Web 資料：**/api/data 回傳 rfid.status、last_uid、last_read_at、error；API 只複製快取、不直接讀 SPI。以 ujson/json.dumps 取代手組 JSON，避免 None 產生非法 JSON，並跳脫字串。index.html 新增最後讀取卡片區，沿用每秒刷新，以 textContent 顯示；零值使用 ?? 保留，檢查 HTTP 狀態，成功恢復連線顯示。
- **生命週期／影響：**最後紀錄只在 RAM，成功覆寫、無回應保留、重啟清空；讀取例外後下一次成功才清除錯誤。初始化失敗跳過讀卡、保留其他功能。沿用驅動 5-byte 結果（含 BCC），未新增長 UID、刷卡歷史、寫卡、RFID MQTT 或門禁。request 無法區分無卡與部分通訊失敗，ready 只代表已初始化。
- **驗證：**6 個 Python 測試通過（3 個原有 LED 測試及 3 個 RFID／API 測試）；實際網頁 JavaScript 在模擬 DOM/fetch 下驗證初始值、讀卡顯示、零值、錯誤字串、連線失敗與恢复通過。未做 ESP32 實機、SPI 接線或瀏覽器視覺驗證。
- **部署／回復：**詳見 RFID_INTEGRATION.md；部署新硬體模組及四個應用檔案，確認 /lib 驅動與 aiot_tools 依賴後重啟。修改前標籤 baseline-before-rfid-20261006 已推送，基線 commit 為 38a65fd；使用乾淨工作目錄建立回復分支並重新部署。私人配置由本機備份另行處理。
- **版控：**在 feature/rfid-integration 提交並推送；待 ESP32 實機驗證後再合併 main。Git refs 為推送結果依據。

## CHG-20261006-001｜保存 RFID 整合前基線

- **類別：**需求變更。
- **日期／紀錄時間：**2026-10-06 00:26:05 +08:00。
- **原因：**使用者同意 RFID 整合與 GitHub 版本保存；原提交未包含新加入的 Microdot 與個人 VS Code 設定。
- **作法：**納入本機既有 Microdot 2.4.0 套件；同步去除私人 WiFi profiles 的單檔範例；保留個人 settings.json，新增可攜的 settings.example.json；排除 typings 與 .local-backups。私人 config.py、單檔原稿及 settings.json 複製至 .local-backups/baseline-before-rfid-20261006（只留本機）。
- **版本保存：**提交後建立 baseline-before-rfid-20261006 標籤並推送 main 與標籤；以 Git refs 核對實際結果。
- **影響／限制：**此基線不變更應用邏輯；Microdot 是使用者已有的檔案，尚未驗證 ESP32 實機。GitHub 不含私人配置；本機備份不是異地備份。
- **回復：**在乾淨工作目錄使用 git switch -c restore-before-rfid baseline-before-rfid-20261006；需部署時以此版本覆蓋裝置檔案，私人配置另從本機備份取回。個人 VS Code 設定不由 Git 恢復。

## CHG-20261005-003｜納入教學文件與公開範例，推送 GitHub

- **類別：**需求變更。
- **日期／作業開始時間：**2026-10-05 21:49:32 +08:00。
- **紀錄時間：**2026-10-05 21:49:32 +08:00。
- **目的地：**`https://github.com/nschou/IoT_Course.git`。
- **需求來源：**使用者已建立 repository，明確要求將此專案推送至該目的地。

### 原因與作法

1. 檢查遠端既有 refs，確認目前無分支，使用本地 `main` 建立遠端基線，不採 force push。
2. 將獨立 `WEB_UI_EXECUTION_GUIDE.md` 講義與 `AGENTS.md` 中的 Mermaid 11.13.0 規則納入版本快照。講義前次建立及修正時依使用者指示未更新 ChangeLog；本項只記錄此次納入版控／交付，保留先前紀錄方式。
3. 講義的 `Loop` 參與者名稱已改成 `Scheduler`；時序訊息中的分號已改為 `#59;`。講義 12 個圖已用 Mermaid 11.13.0 實際解析通過；這不等於已在所有編輯器驗證視覺布局。
4. 納入現有的 `ESP32上無源按鈕的asyncio版本.md` 教學文件，保留原內容。此項不代表已實作或驗證文件內的按鈕範例。
5. 檢查新單檔範例 `99_All-11-2.py`，發現其 WiFi profiles 含私人值；保留原檔不修改，新增 ignore 規則並建立 `99_All-11-2.example.py`，僅以示範 SSID／密碼取代 profiles，保留其餘程式內容。
6. 在版控指南補充此次 GitHub 目的地及單檔範例部署方式。推送前檢查暫存內容與全部 commit 中的已知私人 WiFi 值及常見 token／私鑰特徵。
7. 設定 `origin` 為使用者指定的網址，提交交付檔案並推送 `main`，完成後核對本地 HEAD 與遠端 main 是否一致；提交／推送結果以 Git refs 為準。

### 影響與驗證範圍

不變更目前裝置應用邏輯或本機連線配置。本機 `config.py` 與 `99_All-11-2.py` 不在 Git 內，新環境需使用相應範本建立設定／範例並自行填入 profiles。單檔範例只是去除私人設定，尚未做 ESP32 實機驗證。秘密掃描只涵蓋已知值與指定模式，不宣稱可辨識所有機密。

## CHG-20261005-002｜建立變更追蹤與本地 Git 版控流程

- **類別：**需求變更。
- **日期：**2026-10-05。
- **作業開始／首次紀錄時間：**12:52:56 +08:00。
- **狀態：**本地 `main` 已初始化；本紀錄隨初始基線提交保存，實際 commit 以 `git log` 查詢。
- **文件與驗證完成時間：**2026-10-05 12:58:12 +08:00；初始提交時間由 Git 記錄。
- **需求來源：**使用者要求所有修正持續記錄日期、時間、原因與作法，並提供每個版控目的所需的指令。

### 原因與目的

先前修改只存在於對話與檔案內容，缺少集中、持續、可追溯的變更歷史。工作目錄檢查時尚未建立 Git repository。另發現 `config.py` 包含實際 WiFi 密碼，不適合直接納入可能分享的版本庫。

### 作法

1. 新增本檔案，追記本次 LED BUG，並定義後續紀錄欄位與時間規則。
2. 新增 `GIT_VERSION_CONTROL.md`，說明初始化、檢查差異、暫存、提交、分支、合併、撤回、標籤、遠端協作與備份的目的及 PowerShell 指令。
3. 新增根目錄 `AGENTS.md`，要求後續協作者／代理在修改時同步更新 ChangeLog，並記錄測試結果，不得捏造時間或驗證。
4. 新增 `.gitignore`，排除本機 `config.py`、秘密、Python 快取與暫存輸出；新增 `.gitattributes` 統一文字檔案儲存為 LF，並將 `.12` 點陣字型標示為 binary，避免改寫二進位內容。
5. 從目前 `config.py` 製作 `config.example.py`，保留非機密設定，只以示範 SSID／密碼替代 WiFi profiles，作為可追蹤的設定範本。
6. 準備本地 `main` 分支與初始快照；不建立未經指定的遠端，也不自動 push。本機仍使用原有 `config.py`，不變更裝置連線設定。

### 影響與限制

- 此項主要改善變更追溯與交付流程，不修改 LED 或感測器的執行邏輯。
- 因排除整份本機 `config.py`，任何非機密設定修正必須同步到 `config.example.py` 才會進入 Git 歷史。
- 新 clone 的環境需由範本建立 `config.py`，填入本機 WiFi 設定；其內容不由 Git 備份。
- 原始修正前的版本未在 Git 中保存，初始提交只能記錄目前修正後基線，不能當作具有完整歷史的前後差異。
- 本地 Git 歷史不等於異地備份；遠端網址未提供，遠端建立與上傳留待設定。

### 驗證方式

三項 LED 桌面回歸測試再次通過。`config.example.py` 的 WiFi profiles 已驗證只有示範值；`git check-ignore` 確認本機 `config.py` 被排除。暫存內容掃描未找到原 WiFi 密碼或常見 GitHub token／私鑰特徵；新文件與測試的空白檢查通過。此掃描只涵蓋上述模式，不代表能辨識所有機密。字型指定為 binary，提交前比對暫存與工作檔 bytes；實機驗證仍未執行。

在不提供檔案擁有權的 G 槽上，部分 Git 執行環境回報 dubious ownership；版控操作僅用 `git -c safe.directory='<本專案確切路徑>' ...` 指定本次指令信任，未設全域萬用信任。

## CHG-20261005-001｜按鈕 1 換色索引反覆為 1，LED 閃爍後熄滅

- **類別：**BUG。
- **修正日期：**2026-10-05。
- **修正時間：**前一輪修正未記錄精確時間，無法可靠追溯；不補造時間。
- **追記時間：**2026-10-05 12:52:56 +08:00。
- **版本／狀態：**目前工作目錄已套用修正；此修正在建立 Git 前完成。

### 預期行為

按鈕 1 每次按下，LED 色碼應以 0～7 循環，並保持該顏色直到下一次操作；色碼 0 為黑色／全滅。開機初始化顯示白色 7，因此第一次按下會切換到 0，之後依序 1、2、3、4、5、6、7、0。

### 實際現象

使用者回報每次都印出藍色／索引 1，LED 短暫閃亮後熄滅：

```text
[Button] 按鈕 1 被按下
[LED] 顏色改變為: 藍 (索引: 1)
[Button] 按鈕 1 被釋放
```

### 原因分析

1. `button1_task()` 呼叫 `rgb_led.next_color()`，依目前色碼計算 `(current_color_index + 1) % 8`。
2. `light_sensor_task()` 同時每 50ms 讀取 ADC；亮度大於 1100 時呼叫 `rgb_led.off()`。
3. 修正前 `off()` 呼叫 `set_color_by_index(0)`，同時熄滅 GPIO 並把目前色碼改成 0。
4. 結果是按鈕短暫設定色碼 1，隨後被光感任務清除；下一次又從 0 切換到 1。

根因為兩個任務共同寫入同一 LED，且「暫時熄燈」與「選擇黑色」共用同一狀態。問題不是 `% 8` 的循環公式。

### 詳細作法

| 檔案 | 修改 | 目的 |
|---|---|---|
| `config.py` | 新增 `LIGHT_AUTO_CONTROL_ENABLED = False` | 預設保留手動選色，不讓光感覆寫 |
| `tasks.py` | 持續讀取 ADC，但只在上述開關為 True 時執行光感控制 | 保留亮度功能，分離感測與控制 |
| `hardware/led.py` | 新增 `is_on`，色碼設定時同步更新 | 分開所選顏色與輸出開關狀態 |
| `hardware/led.py` | `off()` 只將三個 GPIO 設為 0，保留 `current_color_index` | 熄燈不重設循環起點，允許自動亮燈恢復原色 |
| `hardware/led.py` | `toggle()` 依 `is_on` 判斷開關；重新開啟使用所選色碼，色碼為 0 時用白色 7 | 配合新的狀態語意 |
| `tests/test_led_control.py` | 新增 fake GPIO 與光感任務回歸測試 | 驗證循環、保持、恢復與 toggle |
| `SYSTEM_ARCHITECTURE.md`、`IOT_ARCHITECTURE_TECH_TREE.md` | 加入 2026-10-05 修正說明 | 保留修正前架構分析並註明現況差異 |

此處採最小修正，尚未建立完整 LedController、命令佇列或 AUTO／MANUAL 仲裁。若再次啟用光感自動控制，亮時仍會熄燈，這是設定所允許的自動行為；只有色碼不再被清除。

### 訊息位置

修改當時，`tasks.py` 第 33 行印出該訊息：

```python
print(f"[LED] 顏色改變為: {color_name} (索引: {next_color})")
```

後續行號可能變動，可用 `rg -n '顏色改變為' tasks.py` 重新查詢。

### 驗證與結果

已在桌面 Python 使用 fake GPIO 執行三項回歸測試，全部通過：

1. `test_button_colors_survive_light_polling_and_wrap`：1～7→0→1 循環，在亮／暗／遲滯區間讀取後仍維持索引與輸出。
2. `test_auto_off_preserves_color_and_dark_restores_it`：啟用自動控制時，亮處熄燈但保留紅色索引 4，暗處恢復紅色。
3. `test_toggle_restores_selected_color`：關閉再開啟，恢復選定黄色索引 6。

```powershell
python -B -m unittest discover -s tests -v
```

測試使用實際 LED 類別與從 `tasks.py` 擷取的光感任務，在桌面模擬執行；沒有驗證按鈕電氣訊號、實機排程或 LED 接線。使用者尚未回報上傳後的實機結果。

### 部署與回復

- 將更新的 `config.py`、`tasks.py`、`hardware/led.py` 上傳 ESP32 後重新啟動；第一次按下由白色 7 切至黑色 0，屬預期行為。
- 若要測試自動照明，在本機設定與範本將 `LIGHT_AUTO_CONTROL_ENABLED` 改為 True，另開變更紀錄；這不是完整撤回此次 BUG 修正。
- 此修正前沒有 Git commit；不能使用 `git revert` 取得原始修正前版本。日後已提交的修正可依 Git 指南使用 revert，並記錄原因。

## 後續紀錄範本

```text
## CHG-YYYYMMDD-NNN｜變更摘要
- 類別：BUG | 需求變更（實際選一項）
- 修正／完成日期：YYYY-MM-DD
- 修正／完成時間：HH:mm:ss +08:00
- 紀錄時間：YYYY-MM-DD HH:mm:ss +08:00
- 版本／狀態：分支、版本標籤或待提交

### 原因
預期、現象、根因，或需求來源與目的。
### 作法
修改檔案、行為差異、選擇理由與取捨。
### 驗證
指令、結果、實機／模擬範圍、未驗證項目。
### 影響與部署／回復
相容性、需要上傳的檔案、設定與回復方式。
```
