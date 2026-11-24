# ISSUE 2026-11-23：ESP32 → LD2410C 的指令方向不通（未解）

狀態：**未解**。先記錄事實，解決方案待討論。
相關程式：`esp32_ld2410_smoke.py`（`command_probe()`）、`esp32_ld2410_tx_probe.py`、
`esp32_ld2410_check.py`、`esp32_ld2410_full_test.py`、`esp32_ld2410_write_test.py`。

## 症狀

- ESP32 送出任何設定命令（`0x00FF` 啟用設定、`0x0061` 讀參數、`0x0060`/`0x0064` 寫參數）都收不到 ACK，
  一律 `LD2410 ACK timeout: 0x00ff`。
- 同一條 UART 的**反方向**（模組 TX → ESP32 RX，GPIO16）完全正常：10 Hz、每框 23 bytes、
  header/tail 正確、`errors = 0`（基本上報模式，type `0x02`）。

## 已排除（實測）

| 假設 | 證據 |
|------|------|
| baud 不對 | 115200 下資料框可正確解出（10 Hz），兩端同一個 UART，baud 必然一致 |
| 模組 UART/韌體壞 | 用 USB 轉 UART（CP2102）＋官方 Windows 工具，115200 可以**讀寫參數**（2026-11-21 14:37 log 有 `SetParameter 0x0060`、`0x0064` Success） |
| 模組被鎖住 | 手機 App 以 BLE 連線也能改參數 |
| ESP32 接收方向 | GPIO16 收到完整資料流 |
| 供電／共地 | 模組有資料輸出、OUT 腳可讀，5V 供電正常 |
| 命令格式錯誤 | `command_frame()` 與協議文件逐 byte 對照（enter/exit/setmax/sens 都對） |

## 尚未排除（依可能性）

1. **GPIO15 → 模組 Pin4（UART_RX）這條線**：外觀正常但可能是冷焊、斷芯、排線插錯一排；
   之前的 GPIO15↔GPIO16 loopback 只證明 ESP32 這端能輸出，沒證明到模組那端。
2. **GPIO15 這支腳**：ESP32-S3 上是否有其他用途、或該腳驅動異常。
3. **模組 Pin4 只在被 ESP32 驅動時才出問題**：例如線路被拉到低電位、或該腳與 GND 短路；
   用 USB 轉 UART 時是另一條線路，所以不會顯現。
4. **MicroPython UART 重配置**：測試程式在前段用 `Pin(15, Pin.IN, PULL_UP)` 探測腳位，
   之後才建 `UART(1, tx=15, rx=16)`；同一 `UART(1)` 被多次建立、舊實例被 GC 時可能 deinit。
   需要用「最小程式、只建一次 UART」驗證。
5. **邏輯分析儀尚未上場**：可分辨「ESP32 有送出但模組沒回」與「ESP32 根本沒送出」。

## 下一步（待討論後執行）

1. 邏輯分析儀：CH1 = GPIO15（ESP32 TX）、CH2 = 模組 Pin5（模組 TX），共地，1 MHz 取樣，
   UART decoder 115200 8N1。跑「每 200 ms 送一次 0x00FF」的迴圈再看波形。
2. 三用電錶：量模組 Pin4 閒置電壓（應約 3.3 V；0 V 表示被拉低）；斷電量 GPIO15↔Pin4 導通。
3. 換腳：把模組 Pin4 的線改插 GPIO47，跑 `esp32_ld2410_tx_probe.py` 的 `run(47)`。
4. 最小程式（不跑 selfcheck、只開一次 UART）送 0x00FF，排除 UART 重配置因素。
5. 若以上都正常，換一顆模組或換一塊 ESP32-S3 交叉驗證。

## 補充

- 模組目前的參數（2026-11-21 讀值）：最遠門 8/8、無人延遲 5 s、運動靈敏度 50/50/40/30/20/15…、
  靜止靈敏度 10/10/40/40/30/30/20/20/20、解析度 0.75 m、baud 115200。
- 這些值是用 PC 工具／App 寫入的，不是 ESP32 寫的。

---

## 結論：已解（2026-11-23 16:40，ESP32-S2 Mini）

同一份驅動程式、同一顆 LD2410C，換成 **ESP32-S2 Mini（TX=GPIO36、RX=GPIO38、OUT=GPIO40）**
重新接線後，命令通道立刻恢復：

```text
ESP32 TX = GPIO36  ->  模組 UART_RX
ESP32 RX = GPIO38  <-  模組 UART_TX
GPIO40   = 模組 OUT
```

| 檢查項 | 結果 |
|---|---|
| 資料流 | 30 frames / 3.0 秒 = **10.0 Hz**，距離 30–95 cm |
| OUT | GPIO40 `out_level()` = True，離開範圍會切 0 |
| 命令通道 | **OK**：`firmware V2.68.24073110` |
| 參數讀回 | **OK**：max gate 8（moving 8、stationary 8）、no-target 5 s |

**原因判定：** ESP32-S3 那一組「GPIO15 → 模組 UART_RX」的實體路徑有問題（冷焊、斷芯或插錯排），
不是驅動邏輯、不是模組 UART、也不是 MicroPython UART 重配置。舊的 GPIO15↔GPIO16 loopback
是在開發板排針上做的，繞過了這段路徑，所以測不出來——這也是本 ISSUE 一直無法收斂的主因。

**附帶驗證：** 讀回的參數（8/8、無人 5 s）與 2026-11-21 用 PC 工具寫入的值一致，
代表 `read_params()`／`current_config()` 的位元組偏移解碼在實機是正確的；
固件字串 `V2.68.24073110` 也與原廠格式相符。

**後續：** S2 Mini 上已可使用 `write_params()`、`set_resolution()`、工程模式等寫入類 API；
`esp32_ld2410_write_test.py` 可直接用來做參數 round-trip 驗證。
