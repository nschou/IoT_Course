# v0：舊版驅動（不再維護）

這裡放的是 2026-11 之前的兩版 MicroPython 驅動，都假設模組 UART 還是 **256000 8N1**。
目前請用上層的 [`hardware/ld2410c.py`](../hardware/ld2410c.py)（說明見 [`../README.md`](../README.md)）。

| 版本 | 目錄 | 內容 |
|------|------|------|
| v1 | [`v1/`](v1/README.md) | 最早的版本：Arduino 函式的直譯移植（`LD2410` 類別、蛇形命名＋駝峰別名、`ld2410_esp32.py` 的 ESP32 包裝） |
| v2 | [`v2/`](v2/README.md) | 把 v1 與 ESP32 版整合：`snapshot()` dict、`read_frame()`、OUT 腳、型別化例外 |

兩版目錄結構相同：

    v0/v1/  (v2 相同)
    ├── hardware/    驅動（ld2410.py，v1 另有 ld2410_esp32.py）
    ├── examples/    範例
    └── tests/       測試（用假 UART，不需要硬體）

## 為什麼被換掉

1. baud 寫死 256000（模組已改成 115200，且 Windows 驅動找不到 256000）。
2. 沒有 baud 診斷，接錯時只會「完全沒畫面」。
3. 指令送出後沒有重試；模組在串流時會漏掉第一發 `0x00FF`（官方工具 log 的 `A002`），
   舊版因此偶爾完全沒有回應。
4. 舊版沒有「寫入參數＋回讀驗證」與備份／還原。

## 執行舊版測試（不需要硬體）

    PYTHONPATH=micropython/v0/v1 python micropython/v0/v1/tests/test_ld2410.py
    PYTHONPATH=micropython/v0/v2 python micropython/v0/v2/tests/test_ld2410.py
