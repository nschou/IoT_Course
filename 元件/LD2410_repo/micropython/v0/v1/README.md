# LD2410 MicroPython v1

> **舊版。** 假設 baud = 256000，沒有 baud 自動偵測，也沒有「`0x00FF` 被模組漏掉
> 就重送」的處理。目前請用 [`../../hardware/ld2410c.py`](../../hardware/ld2410c.py)。

`hardware/ld2410.py` 是 Arduino 函式的直譯移植：基本模式與工程模式封包、
移動／靜止／偵測距離、韌體與設定查詢、工程模式、靈敏度、最遠門、恢復出廠、
重啟指令，以及壞封包後的重新同步。驅動是被動的：自己建好 UART 後不斷呼叫 `read()`。

    from machine import UART, Pin
    from hardware import LD2410

    uart = UART(1, baudrate=256000, bits=8, parity=None, stop=1,
                tx=Pin(16), rx=Pin(15))
    radar = LD2410(uart)          # 非阻塞；要查韌體再呼叫 radar.begin()

    while True:
        radar.read()
        if radar.is_connected():
            print(radar.presence_detected(),
                  radar.moving_target_distance(),
                  radar.moving_target_energy(),
                  radar.stationary_target_distance(),
                  radar.stationary_target_energy())

* `hardware/ld2410_esp32.py`：ESP32 專用包裝（代建 UART、讀 OUT 腳）。
* `examples/basic_sensor.py`：最小範例。
* `tests/test_ld2410.py`：unittest + 假 UART，不需要硬體。

## 注意

v1 的範例用 `tx=16, rx=15`，與新版預設 `tx=17, rx=16` 不同——接線以實際接的腳位為準。
公開 API 是蛇形命名，另外保留 Arduino 風格的駝峰別名（例如
`presenceDetected()`、`requestFirmwareVersion()`）方便對照。

## 執行測試

    PYTHONPATH=micropython/v0/v1 python micropython/v0/v1/tests/test_ld2410.py
