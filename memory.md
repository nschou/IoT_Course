# memory.md — 99_All_07_refactor 長期記憶

> 本檔是這個專案的跨會話記憶（人可讀、可版控、跟著 repo 走）。重要進展／決策／踩坑／待辦都更新這裡。
> 公約：所有專案都要有這份 `memory.md`（2026-11-23 使用者指示）。不要寫密碼或 token。

## 1. 專案概述

- 「物聯網軟體架構」（114-1 NUU 資工）的 ESP32-S3 + MicroPython 課程主專案。
- 功能：RGB LED、按鈕、DHT11、光感（ADC）、PIR、喇叭、I2C OLED、SPI RFID、MQTT、Wi-Fi、
  長者照護（雷達活動／離床／夜燈）與床鋪監測。

## 2. 腳位（唯一來源：config.py）

| 用途 | GPIO |
|---|---|
| RGB LED | 37 / 35 / 33 |
| 按鈕 | 17 / 21 |
| DHT11 | 18 | TEMT 光感 ADC | 8 |
| PIR | 4 | 喇叭 | 6 |
| I2C（OLED） | SCL 7 / SDA 5 |
| RFID SPI | SCK 12 / MOSI 11 / MISO 10 / RST 9 / CS 13 |
| LD2410 UART1 | TX 15 → 模組 RX、RX 16 ← 模組 TX、OUT 14、baud 115200 |

`config.py` 被 gitignore，版控樣板是 `config.example.py`。

## 3. 結構

    config.py / config.example.py
    hardware/            ld2410.py（舊 snapshot API 相容層）＋ ld2410c.py（micropython 套件同步副本）
    apps/elder_care/     radar_care.py（純邏輯）、bed_monitor.py、*_demo.py
    tests/               桌機 unittest 52 項（LD2410 的測試已移到 micropython/tests）
    元件/01_毫米波雷達/  datasheet、LD2410B_LD2410C 接線與實測記錄
    mdy_01…mdy_06        歷次迭代舊版（含舊驅動 ld2410b.py）
    ChangeLog.md         ★ 每次修改都要記錄

## 4. 規則（本專案特有）

- **ChangeLog.md**：每次改程式／設定／測試／文件，都要在同一個 commit 新增
  `CHG-YYYYMMDD-序號`（最新在上），含類別（BUG／需求變更）、現象、原因、作法、影響、
  驗證、部署與回復。
- 文件只改「可操作段落」；歷史紀錄保留，改動時在開頭加註現況與日期。
- 使用者要求相關程式（含測試）集中在同一個地方，測試要跟驅動版本配對。

## 5. 目前狀態

- 桌機測試：`python -B -m unittest discover -s tests` → 52 項 OK。
- LD2410：資料流正常；**ESP32 → 模組的指令方向未通**（`ACK timeout: 0x00ff`）。
  詳細紀錄在 LD2410_repo 的 `micropython/tests/ISSUE-20261123-uart-tx-ack.md`。
- 驅動以 LD2410_repo 的 `micropython/hardware/ld2410c.py` 為正本；本專案的 `hardware/ld2410c.py`
  是同步副本，`hardware/ld2410.py` 是保留舊介面的相容層（apps 不用改）。

## 6. 重要決策

- 2026-11-21：LD2410 baud 全專案改 115200（模組已由 App 改）。
- 2026-11-23：採方案 A（micropython 套件為驅動正本）；本專案留副本＋相容層。
- 2026-11-23：完整測試通過後，才把驅動與範例移入本專案。

## 7. 踩過的坑

- 這個資料夾在 Asus WebStorage：`write` 工具會 EISDIR、git 要 `-c safe.directory`；
  也不支援 junction／symlink，記憶 DB 無法用連結指到本機。
- 之前的舊測試（esp32_ld2410_*）在搬進 micropython 套件前是寫給舊驅動 API，
  要改 import 與 API 才能跑。

## 8. 待辦

- [ ] LD2410 命令通道打通（見 LD2410_repo 的 ISSUE 檔）。
- [ ] 完整測試通過 → 把 `ld2410c.py` 與 `examples/01~04` 移入本專案並補 ChangeLog。
- [ ] 記憶資料庫若持續 I/O 錯誤：重啟 DSH；或改以本機工作區（本檔＋LD2410_repo/memory.md 為備援紀錄）。

## 9. 更新日誌

- 2026-11-23：建立本檔（與 LD2410_repo/memory.md 同一天）。
