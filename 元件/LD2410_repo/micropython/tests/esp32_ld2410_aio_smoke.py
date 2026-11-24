"""On-device asyncio check for LD2410CAsync (MicroPython only).

Run in the device REPL:

    exec(open("tests/esp32_ld2410_aio_smoke.py").read())
    run(10)        # 10 秒資料流 + 併發計數器 + 設定讀取

It proves three things at once:

  1. read_async() yields while waiting (the ticker keeps counting)
  2. the streaming loop never blocks the event loop
  3. firmware/params can be read after the loop (independent job)
"""
import time

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

try:
    from hardware.ld2410c_aio import LD2410CAsync
except ImportError:
    from ld2410c_aio import LD2410CAsync

try:
    import config as _cfg
except ImportError:
    _cfg = None


def _setting(name, default):
    return getattr(_cfg, name, default) if _cfg is not None else default


def make_radar():
    return LD2410CAsync(
        uart_id=_setting("LD2410B_UART_ID", 1),
        tx=_setting("LD2410B_TX_PIN", 15),
        rx=_setting("LD2410B_RX_PIN", 16),
        baudrate=_setting("LD2410B_BAUDRATE", 115200),
        out_pin=_setting("LD2410B_OUT_PIN", None),
    )


async def _ticker(stop, counter, period_ms=10):
    while not stop[0]:
        counter[0] += 1
        await asyncio.sleep_ms(period_ms)


async def _stream(counter, seconds):
    radar = make_radar()
    stop = [False]
    task = asyncio.create_task(_ticker(stop, counter))
    frames = 0
    start = time.ticks_ms()
    end = time.ticks_add(start, int(seconds * 1000))
    try:
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            frame = await radar.read_async(1000)
            frames += 1
            if frames % 10 == 0:
                print("%5.1fs frames=%-3d mov=%-4d stat=%-4d state=%-22s ticker=%d"
                      % (time.ticks_diff(time.ticks_ms(), start) / 1000.0,
                         frames, frame["moving_cm"], frame["stationary_cm"],
                         frame["state_name"], counter[0]))
    finally:
        stop[0] = True
        task.cancel()
    return radar, frames


async def _config(radar):
    print("--- 設定（獨立作業）---")
    try:
        info = await radar.firmware_version_async()
        print("firmware:", info["string"])
    except OSError as exc:
        print("firmware failed:", exc)
    try:
        params = await radar.read_params_async()
        print("gates: moving %d stationary %d no-one %d s"
              % (params["max_moving_gate"], params["max_stationary_gate"],
                 params["no_one_seconds"]))
        print("motion sens:", params["motion_sens"])
        print("static sens:", params["static_sens"])
    except OSError as exc:
        print("params failed:", exc)


async def main(seconds=10):
    counter = [0]
    radar, frames = await _stream(counter, seconds)
    print("--- 結果 ---")
    print("frames=%d ticker=%d （ticker 遠大於 0 代表等待期間事件迴圈仍在跑）"
          % (frames, counter[0]))
    await _config(radar)


def run(seconds=10):
    asyncio.run(main(seconds))


print("esp32_ld2410_aio_smoke 已載入；執行 run(10)")
