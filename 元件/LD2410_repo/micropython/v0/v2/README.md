# LD2410 MicroPython v2

> **舊版。** 這個版本假設 baud = 256000，沒有 baud 自動偵測，也沒有
> 「`0x00FF` 被模組漏掉就重送」的處理。目前請用 `../../hardware/ld2410c.py`（說明見 `../../README.md`）。

This version combines the two earlier drivers without replacing them.

## Advantages

- Accepts an existing `machine.UART` or creates one from ESP32 UART settings.
- Non-blocking `read()`/`poll()` for main loops and blocking `read_frame()` for
  applications that want a timeout.
- Robust length-driven frame parsing with partial-frame buffering and recovery
  from noise or malformed frames.
- Original getter API plus `snapshot()` dictionaries.
- Basic and engineering frames, per-gate energies, light level, and OUT state.
- Optional physical OUT pin with active-high or active-low configuration.
- Full command set: firmware, configuration, maximum distance, sensitivity,
  engineering mode, factory reset, and restart.
- Typed low-level exceptions while compatibility `request_*()` methods return
  `True` or `False`.
- Firmware and configuration responses are decoded into public fields.
- Arduino-style method aliases remain available.

## ESP32 example

```python
from machine import Pin, UART
from hardware import LD2410

uart = UART(1, baudrate=256000, bits=8, parity=None, stop=1,
            tx=Pin(15), rx=Pin(16))
radar = LD2410(uart=uart, out_pin=4, wait_for_radar=False)

while True:
    snapshot = radar.poll()
    if snapshot is not None:
        print(snapshot)
```

Copy `micropython/v0/v2/hardware` to the board as `hardware`. The v2 test suite
uses a fake UART and does not require radar hardware. It runs directly on
MicroPython:

```python
import test_ld2410
test_ld2410.run_all()
```

It can also run on CPython with:

```text
PYTHONPATH=micropython/v0/v2 python micropython/v0/v2/tests/test_ld2410.py
```
