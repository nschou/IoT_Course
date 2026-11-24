# HLK-LD2410C MicroPython 驅動 + 測試程式

ESP32 + MicroPython 用的 LD2410C（24 GHz 雷達）驅動。這一版針對**實機**寫：
模組韌體 V2.44.24073110、UART **115200 8N1**，封包格式用官方 PC 工具錄下來的
1756 個真實 frame 驗證過，附 28 項不需要硬體的自動測試，以及 4 支上板用得上的實機測試／診斷程式。

## 目錄

```
micropython/
├── hardware/            ← 驅動套件（整包複製到板子）
│   ├── __init__.py
│   └── ld2410c.py
├── examples/            ← 範例程式
│   ├── 01_distance.py
│   ├── 02_read_params.py
│   ├── 03_set_and_save.py
│   └── 04_diagnose.py
├── tests/               ← 測試與實機診斷（全部跟著 hardware/ 的版本走）
│   ├── test_ld2410c.py         28 項自動測試（CPython 或板上，免硬體）
│   ├── esp32_ld2410_smoke.py   板上：資料流／參數／命令探測
│   ├── esp32_ld2410_check.py   板上：接線＋資料流＋命令一次檢查
│   ├── esp32_ld2410_full_test.py 板上：完整功能測試（Report 統計）
│   ├── esp32_ld2410_tx_probe.py  板上：指令送不進去時的方向診斷
│   ├── README.md               這些程式怎麼用、建議順序
│   └── fixtures/*.dat          533 個真實封包
└── v0/                  ← 舊版 v1、v2（256000 時代，只供對照）
```

| 檔案 | 用途 |
|------|------|
| `hardware/ld2410c.py` | 驅動本體：串流解析、指令重試、參數讀寫回讀、baud 診斷 |
| `examples/04_diagnose.py` | **先跑這支**：檢查接線與 baud（不會改設定） |
| `examples/01_distance.py` | 測試 1：距離、狀態、9 個距離門能量、光敏 |
| `examples/02_read_params.py` | 測試 2：讀韌體版本、最遠門、靈敏度、無人延遲、解析度 |
| `examples/03_set_and_save.py` | 測試 3：改參數 → 寫入 flash → 回讀驗證（可還原） |
| `tests/test_ld2410c.py` | 28 項自動測試（CPython 或板子上都能跑） |
| `tests/esp32_ld2410_smoke.py` | 板上：`selfcheck()` 腳位＋資料框、`stream()` 距離表、`info()` 讀參數、`command_probe()` 看 0x00FF |
| `tests/esp32_ld2410_check.py` | 板上：接線、資料流、OUT、命令通道一次檢查 |
| `tests/esp32_ld2410_full_test.py` | 板上：完整功能測試，PASS/FAIL 總表 |
| `tests/esp32_ld2410_tx_probe.py` | 板上：資料正常但命令 timeout 時，分辨回音／真 ACK／沒送到 |
| `tests/esp32_ld2410_write_test.py` | 板上：**唯一會寫參數**的測試——工程模式 round-trip、解析度唯讀、參數備份→寫入→回讀→還原 |

## 接線（ESP32 DevKit）

| ESP32 | LD2410C | 說明 |
|-------|---------|------|
| 5V / VIN | Pin1 VCC | **要 5V**，電流 > 200 mA（3.3V 可能還能收資料但指令不穩） |
| GND | Pin2 GND | 一定要共地 |
| GPIO14（選用） | Pin3 OUT | 有目標時輸出高電平（模組預設高電平觸發） |
| GPIO15（TX） | Pin4 UART_RX | 要交叉 |
| GPIO16（RX） | Pin5 UART_TX | 要交叉 |

模組 I/O 是 3.3 V，可以直接接 ESP32。上表是 UART1 自訂腳位（GPIO15/16），
程式上方都有一組常數（`TX_PIN`、`RX_PIN`、`OUT_PIN`、`BAUD`），換板子只改那裡。
GPIO15 是 strapping pin，開機瞬間的狀態不影響模組；若用 ESP32-WROVER（GPIO16 給 PSRAM）
或 ESP32-S3/C3，請改成可用腳位。

## 上傳與執行

把整個 `hardware/` 目錄複製到板子根目錄，範例放哪都可以：

    mpremote cp -r hardware :
    mpremote run examples/04_diagnose.py       # 先確認接線與 baud
    mpremote run examples/01_distance.py       # 測距離
    mpremote run examples/02_read_params.py    # 讀參數（安全）
    mpremote run examples/03_set_and_save.py   # 寫參數（會存進模組 flash）

Thonny：把 `hardware/` 整個資料夾上傳到板子，再開範例執行。

程式裡的 import 是：

    from hardware.ld2410c import LD2410C

## 先解決「ESP32 TX 送指令，LD2410 RX 沒回應」

這次卡關的原因不只一個，依重要性排列：

1. **baud 不一致**：模組出廠 256000，但 Windows 11 的 USB-轉-COM 驅動找不到這個速率。
   模組已用手機 App 改成 **115200**，所以 ESP32 這邊也必須是 115200。
   baud 不對時收到的會是亂碼（`04_diagnose.py` 會把前 12 個 byte 印出來），指令當然不會執行。
2. **指令要包在設定模式裡**：任何設定指令前都要先送 `0x00FF`（啟用設定），收到 ACK 後
   才送真正的指令，最後送 `0x00FE`（結束設定）。少這一步，模組直接不理。
3. **模組在連續輸出時會漏掉指令**：官方 PC 工具 log 出現
   `OpenCmdMode: CMDID(0x00FF) failed with:A002`，重送一次就成功（2026-11-21 14:37 的記錄）。
   所以 `enter_config()` 預設重試 6 次，指令本身也可以重送。
4. **接線**：TX/RX 要交叉、GND 共地、VCC 給 5V。只接 TX/RX 不共地，很常見「收得到資料、
   送不進指令」。

`04_diagnose.py` 會依序確認：資料流有沒有進來、指令通道有沒有 ACK、以及
9600～460800 之間哪個 baud 才對。

## 範例輸出

`02_read_params.py`（實機）：

    固件版本 : V2.44.24073110
    偵測精度 : 0.75 m / 門
    最遠運動距離門 : 8  (約 6.00 ~ 6.75 m)
    無人持續時間   : 5 秒

    門  距離範圍(m)   運動  靜止
     0    0.00~ 0.75     50    10
     ...

`01_distance.py`：

    狀態: moving+stationary  距離:  30 cm
    移動目標:  30 cm 能量 100    靜止目標:  30 cm 能量 100
    偵測距離(原始值):   0 cm   光敏: 36
    距離 |##......................................| 0~6 m

（實測會遇到「偵測距離 = 0 但目標距離 = 30 cm」的 frame，所以 `distance_cm`
會退回目標距離，原始值仍保留在 `detection_cm`。）

## API 速查

    from hardware.ld2410c import LD2410C

    radar = LD2410C(uart_id=1, tx=15, rx=16, baudrate=115200, out_pin=14)

| 方法 | 說明 |
|------|------|
| `poll()` | 非阻塞讀取，有新 frame 就回傳 dict（同一個 dict 重複使用） |
| `read(timeout_ms)` | 阻塞到收到 frame，逾時丟 `LD2410CTimeout` |
| `engineering(True/False)` | 開/關工程模式（多送 9 個門能量，斷電失效） |
| `read_params()` | 讀取已儲存的參數（0x0061） |
| `write_params(params, verify=True)` | 寫入參數並回讀驗證（0x0060 + 0x0064 ×9） |
| `read_resolution()` / `set_resolution(0.75/0.2)` | 每門距離解析度（0x00AB / 0x00AA，需重啟） |
| `firmware_version()` | 韌體版本（0x00A0） |
| `set_baudrate(115200)` | 改 baud 並存檔（0x00A1，會自動重啟、重開 UART） |
| `restart()` / `factory_reset()` | 重啟（0x00A3）/ 恢復出廠（0x00A2） |
| `diagnose()` | 接線與 baud 診斷（回傳 dict，不改設定） |
| `presence()` / `out_level()` | 有無人（優先看 OUT 腳，其次看 frame） |
| `is_connected()` / `age_ms()` | 最後一個 frame 距今多久 |

`poll()` 回傳的 dict：

| key | 說明 |
|-----|------|
| `state` / `state_name` | 0 無人、1 移動、2 靜止、3 移動+靜止 |
| `distance_cm` / `distance_m` | 對外距離（偵測距離，0 時退回目標距離） |
| `detection_cm` | 模組原始「偵測距離」 |
| `moving_cm` / `moving_energy` | 移動目標距離 / 能量 |
| `stationary_cm` / `stationary_energy` | 靜止目標距離 / 能量 |
| `max_moving_gate` / `max_stationary_gate` | 工程模式才有：最遠門 |
| `moving_gates` / `stationary_gates` | 工程模式才有：9 個門的能量（bytes） |
| `light` | 工程模式才有：光敏值（V2.44 尾端，0-255） |
| `engineering` | 這個 frame 是不是工程模式 |

## 參數怎麼理解

* **距離門（gate）**：每門 0.75 m（可改成 0.2 m，需重啟）。gate 0 = 0~0.75 m、
  gate 1 = 0.75~1.5 m……gate 8 = 6.0~6.75 m。
* **最遠門**：只輸出這個門以內的目標。設定範圍 1~8，實務上門 4 約等於 3 m。
* **靈敏度 0~100**：能量要超過這個值才判定有目標；**數字越小越靈敏**。
  設成 100 幾乎等於「這個門不偵測」，可以用來遮掉電風扇、窗簾之類的干擾區。
* **無人持續時間**：人離開後，還要持續幾秒才回報「無人」（0~65535 秒）。
* **偵測精度**：0.75 m（出廠）或 0.2 m；改完要重啟才生效。

參數寫入後**存在模組 flash，斷電不會消失**（0x0060 / 0x0064 都是非揮發性指令）。

`03_set_and_save.py` 會先備份到 `ld2410_params_backup.json`（在板子上），寫入後回讀比對，
不一致就自動還原；也可以執行 `03_set_and_save.py restore` 手動還原。

## 自動測試

**不需要硬體**（會重播 533 個真實封包）：

    python micropython/tests/test_ld2410c.py

在板子上也可以跑同一套：

    import test_ld2410c
    test_ld2410c.run_all()

沒有一併複製 `tests/fixtures/` 也可以：會印出
`(fixtures/ not installed - corpus replay skipped)` 並略過那一項。

目前 28 項全部通過，包含：封包組裝（與協議文件逐 byte 對照）、ACK 失敗、
0x00FF 被漏掉的重試、參數讀寫與回讀、真實封包重播、半包/雜訊/壞尾重新同步、
建構子開 UART 的參數、錯誤 ACK 忽略、資料新鮮度。

**需要實機**（板上執行，腳位寫在檔案頂端的常數）：

    exec(open("tests/esp32_ld2410_check.py").read()); run()
    exec(open("tests/esp32_ld2410_smoke.py").read()); selfcheck()
    exec(open("tests/esp32_ld2410_full_test.py").read()); run()
    exec(open("tests/esp32_ld2410_write_test.py").read()); run()   # 會寫參數，結束前還原

資料正常但命令 timeout 時，先跑 `tests/esp32_ld2410_tx_probe.py` 的 `run()`；
詳細用法見 `tests/README.md`。

這些測試都 import `hardware.ld2410c`，只跟本目錄的驅動搭配；不讀取任何外部 `config.py`，
腳位一律寫在每支檔案最上方的常數（預設 UART1、TX=GPIO15、RX=GPIO16、OUT=GPIO14、115200）。

## 已知限制

* **ESP32 → 模組的指令方向在實機上仍未打通**（2026-11-23）：資料流正常、PC 工具與手機 App 都能改參數，
  但 ESP32 送 `0x00FF` 收不到 ACK。目前狀態與已排除／待驗證項目記在
  [`tests/ISSUE-20261123-uart-tx-ack.md`](tests/ISSUE-20261123-uart-tx-ack.md)。

* **光敏聯動、底噪檢測、觸發電平**：這些是 V2.44 才有的功能，V1.00 協議
  （`docs/HLK-LD2410C_protocol.md`）沒有定義指令；`docs/` 裡的 V1.08 PDF 是掃描／
  子集字型、無法取字，所以這裡還沒有實作。需要的話可以用手機 App 改一次、
  再從 UART 抓封包比對出指令碼。
* 工程模式封包尾端在韌體 V2.44 多了 2 個 byte：`payload[31]` 是光敏值（0-255，
  與 App 的「光敏」一致），`payload[32]` 固定 `0x01`、語意未確認。
  解析器對長度做了保護，所以即使尾端格式改變也不會整包壞掉。
* 0.2 m 解析度、baud rate 都要**重啟**才生效；`set_baudrate()` 已經自動處理，
  但若中途斷線，模組可能停在「聽不到舊 baud」的狀態，請用 `04_diagnose.py` 找回來。
* 寫入參數是 19 個指令連續送出（約 0.7 秒），中途斷電可能只寫一半；
  重新執行一次 `03_set_and_save.py` 或 `restore` 即可。

## 舊版

`v0/` 放的是 256000 baud 時代的兩版驅動（v1 = Arduino API 直譯移植、v2 = 整合版），
只保留給對照，不再維護；說明見 [v0/README.md](v0/README.md)。
