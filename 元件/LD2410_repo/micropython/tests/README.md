# tests：LD2410C 測試與實機診斷

這裡每一支程式都搭配上層 hardware/ld2410c.py（同一版驅動）。
腳位與 baud **以裝置上的 config.py 為優先**，讀不到才用下面的預設值（ESP32-S3）：

    UART_ID = 1            # 或 config.LD2410B_UART_ID
    TX_PIN  = 15           # 或 config.LD2410B_TX_PIN   （S2 Mini：36）
    RX_PIN  = 16           # 或 config.LD2410B_RX_PIN   （S2 Mini：38）
    OUT_PIN = 14           # 或 config.LD2410B_OUT_PIN  （S2 Mini：40）
    BAUD    = 115200       # 或 config.LD2410B_BAUDRATE

因此同一份檔案可直接用在 S2 Mini（板上有整合版 config.py）與 ESP32-S3（板上沒有 config.py），
不需要為了換板子改程式；重新上傳前請確認裝置根目錄有沒有 config.py。

| 檔案 | 跑在哪 | 用途 |
|------|--------|------|
| test_ld2410c.py | PC 或板上 | 28 項自動測試，不需硬體：封包編碼、ACK、重試、參數讀寫回讀、解析、重新同步、真實封包重播 |
| test_ld2410c_aio.py | **PC only** | 11 項 async 層測試：等待不阻塞、ACK 重試、參數讀寫驗證、firmware 解碼（需 CPython 的 unittest） |
| esp32_ld2410_aio_smoke.py | 板上 REPL | 用 uasyncio 驗證 `LD2410CAsync`：等待期間 ticker 持續累加、串流結束後再讀 firmware／參數 |
| esp32_ld2410_smoke.py | 板上 REPL | selfcheck() 腳位＋資料框、raw() 原始 bytes、stream() 距離表、info() 讀韌體/參數、command_probe() 看 0x00FF 回什麼、run() 全部跑一遍 |
| esp32_ld2410_check.py | 板上 REPL | 一次檢查接線、資料流、OUT、命令通道，最後給結論 |
| esp32_ld2410_full_test.py | 板上 REPL | 完整功能測試（PASS/WARN/FAIL 總表）：資料流速率、即時讀值、資料新鮮度、命令編碼、韌體與參數 |
| esp32_ld2410_write_test.py | 板上 REPL | **唯一會寫入參數**的測試：工程模式 round-trip、解析度唯讀、參數備份→寫入→回讀→還原→再驗證（失敗也會嘗試還原） |
| esp32_ld2410_tx_probe.py | 板上 REPL | 只查「資料正常但命令 timeout」：送 0x00FF 判斷是回音（15/16 短接）、真 ACK、還是完全沒到模組 |
| fixtures/*.dat | PC | 官方工具錄下的 533 個真實封包，供 test_ld2410c.py 重播 |

## 建議順序

1. 桌機先跑自動測試（不用板子）：

       python micropython/tests/test_ld2410c.py

2. 板上確認資料流：

       exec(open("tests/esp32_ld2410_smoke.py").read())
       selfcheck()
       raw(3)

3. 若出現 ACK timeout: 0x00ff，先跑：

       exec(open("tests/esp32_ld2410_tx_probe.py").read())
       run()

4. 命令通了之後（唯讀）：

       exec(open("tests/esp32_ld2410_check.py").read()); run()
       exec(open("tests/esp32_ld2410_full_test.py").read()); run()

5. 最後跑寫入測試（會暫時改參數並在結束前還原）：

       exec(open("tests/esp32_ld2410_write_test.py").read()); run()

換腳位測試（先把模組 RX 線改插 GPIO47）：

       run(47)

## 上傳

       mpremote cp -r hardware :
       mpremote cp tests/esp32_ld2410_smoke.py :tests/
       mpremote cp tests/esp32_ld2410_tx_probe.py :tests/
