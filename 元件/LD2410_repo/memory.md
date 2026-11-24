# memory.md — LD2410_repo 長期記憶

> 本檔是這個專案的跨會話記憶（人可讀、可版控、跟著 repo 走）。
> 每有重要進展／決策／踩坑／待辦就更新對應分類；過時內容直接改寫或標「已完成」。
> 不要在這裡寫密碼、token、Wi-Fi 密碼。
> 公約：所有專案都要有這份 `memory.md`（由 2026-11-23 使用者指示）。

## 1. 專案概述

- Hi-Link **LD2410C** 24 GHz 雷達的 Arduino 庫（上游 fork：`src/`、`examples/`、`tests/`）
  ＋使用者自建的 MicroPython 驅動與測試（`micropython/`），供「物聯網軟體架構」課程使用。
- 教學資料：`00_Tools&Drivers/`（官方 PC 工具、sscom）、`docs/`（協議 PDF、實測記錄）、
  `工具畫面截圖/`。

## 2. 硬體與連線（實測）

- 板子：ESP32-S3（DevKitC-1 等級），MicroPython。
- 模組：LD2410C，韌體 V2.44.24073110，UART **115200 8N1**（出廠 256000，已用手機 App 改）。
- 接線：Pin1 VCC→5V/VIN、Pin2 GND→GND、Pin3 OUT→GPIO14、Pin4 UART_RX←GPIO15(TX)、
  Pin5 UART_TX→GPIO16(RX)。程式：`UART(1, tx=15, rx=16, baudrate=115200)`。
- 參數（2026-11-21 讀值）：最遠門 8/8、無人延遲 5 s、運動靈敏度 50/50/40/30/20/15/15/15/15、
  靜止 10/10/40/40/30/30/20/20/20、解析度 0.75 m。

## 3. 目錄結構（micropython/）

    micropython/
    ├── hardware/{__init__.py, ld2410c.py}   ← 唯一驅動正本（import hardware.ld2410c）
    ├── examples/01_distance.py … 04_diagnose.py
    ├── tests/
    │   ├── test_ld2410c.py                 28 項自動測試（免硬體）
    │   ├── esp32_ld2410_smoke.py           板上：資料流／參數／command_probe
    │   ├── esp32_ld2410_check.py           板上：接線＋資料流＋命令一次檢查
    │   ├── esp32_ld2410_full_test.py       板上：完整功能測試（唯讀）
    │   ├── esp32_ld2410_tx_probe.py        板上：命令方向診斷
    │   ├── esp32_ld2410_write_test.py      板上：參數寫入→回讀→還原
    │   ├── ISSUE-20261123-uart-tx-ack.md   未解問題紀錄
    │   └── fixtures/*.dat                  533 個真實封包
    └── v0/{v1, v2}                         舊版（256000 時代，只供對照）

板端測試一律 import `hardware.ld2410c`、不讀外部 `config.py`，腳位寫在檔案頂端常數。

## 4. 目前狀態

- 資料流：正常（10 Hz、23 bytes、errors 0、基本上報模式）。
- **未解**：ESP32 → 模組的指令方向不通，任何命令都是 `ACK timeout: 0x00ff`。
  PC 工具與手機 BLE App 都能讀寫模組參數 → 模組 RX、baud、供電已排除。
  嫌疑：GPIO15→Pin4 的線／腳、或 MicroPython UART 重配置。詳見 ISSUE 檔。

## 5. 重要決策

- 2026-11-21：模組 baud 由 256000 改 115200，全專案同步。
- 2026-11-21：指令一律以 `0x00FF`…`0x00FE` 包住，並對 ACK 失敗重試（官方工具也有 A002 重試）。
- 2026-11-21：目錄整理為 `hardware/`＋`examples/`＋`tests/`＋`v0/{v1,v2}`。
- 2026-11-23（方案 A）：`microPython/hardware/ld2410c.py` 是唯一正本；測試全部跟着它，
  不再在別的專案另養一份；99_All_07_refactor 只放同步副本＋相容層。
- 2026-11-23：在完整測試通過前，不把驅動與範例搬去 99_All_07_refactor。

## 6. 踩過的坑（lesson）

- MicroPython **沒有 `os.path`**：用字串切分；缺 fixtures 要能優雅略過。
- Asus WebStorage 雲端磁碟：`write`/`edit` 工具會 `EISDIR`（硬連結不支援），改用 node fs／pwsh；
  目錄 junction／symlink 也不支援（EISDIR／拒絕存取），所以記憶 DB 無法用連結指到本機。
- `git` 在這台磁碟要加 `-c safe.directory=<路徑>`。
- 搬移測試前先核對 import 與 API（舊 snapshot/target_state vs 新 poll/frame/read_params）。
- 用 run_code 產生存檔：避免在 `String.raw` 內放反引號；用單引號逐行陣列最穩；
  `py_compile` 會留 `__pycache__`，跑完要清。

## 7. 待辦

- [ ] 打通 ESP32 → LD2410C 的命令通道（邏輯分析儀量 CH1/CH2、量 Pin4 3.3 V、換 GPIO47、
      最小程式只開一次 UART）。
- [ ] 完整測試通過後，把 `hardware/ld2410c.py` 與 `examples/01~04` 移入 99_All_07_refactor。
- [ ] 記憶資料庫若持續 I/O 錯誤：重啟 DSH；必要時改走本機工作區（見 99_All_07_refactor/memory.md）。

## 8. 使用者偏好與規則

- 一律繁體中文；回覆要能直接上板、附接線與診斷步驟。
- 測試順序：先唯讀（smoke/check/full_test）→ 最後才寫入（write_test，會還原）。
- 相關程式（含測試）要跟它所搭配的驅動放在同一個地方。
- 改一個設定值時，全專案同步（設定、預設、fallback、測試、文件）。
- **所有專案都要有 `memory.md`**（本檔），重要事項先寫這裡。

## 9. 更新日誌

- 2026-11-23：建立本檔；記錄 ISSUE-20261123、方案 A、目錄與測試現況。
