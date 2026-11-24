"""One-shot LD2410C wiring and driver check (ESP32 + MicroPython).

Run in the device REPL:

    exec(open("tests/esp32_ld2410_check.py").read())
    run()

Only reads and queries; a failed command check cannot change the module.
"""
import time

from hardware.ld2410c import LD2410C

# --- pins: a config.py on the device wins; defaults are the ESP32-S3 wiring --
try:
    import config as _cfg
except ImportError:
    _cfg = None


def _setting(name, default):
    return getattr(_cfg, name, default) if _cfg is not None else default


UART_ID = _setting("LD2410B_UART_ID", 1)
TX_PIN = _setting("LD2410B_TX_PIN", 15)        # ESP32-S2 Mini uses 36
RX_PIN = _setting("LD2410B_RX_PIN", 16)        # ESP32-S2 Mini uses 38
OUT_PIN = _setting("LD2410B_OUT_PIN", 14)      # ESP32-S2 Mini uses 40
BAUD = _setting("LD2410B_BAUDRATE", 115200)

_radar = None


def get_radar():
    global _radar
    if _radar is None:
        _radar = LD2410C(uart_id=UART_ID, tx=TX_PIN, rx=RX_PIN,
                         baudrate=BAUD, out_pin=OUT_PIN)
    return _radar


def show_wiring():
    print("--- 接線規則 ---")
    print("ESP32 TX = GPIO%-2d  ->  模組 UART_RX" % TX_PIN)
    print("ESP32 RX = GPIO%-2d  <-  模組 UART_TX" % RX_PIN)
    print("LD2410C 由 VCC 端數：Pin-1 VCC, Pin-2 GND, Pin-3 OUT, "
          "Pin-4 UART_RX, Pin-5 UART_TX")
    print("因此 Pin-3 -> GPIO%d（OUT），Pin-4 -> GPIO%d（ESP32 TX），"
          "Pin-5 -> GPIO%d（ESP32 RX）" % (OUT_PIN, TX_PIN, RX_PIN))
    print("")


def check_stream(seconds=3):
    print("--- 1. 資料流（driver.poll）---")
    radar = get_radar()
    start = time.ticks_ms()
    end = time.ticks_add(start, int(seconds * 1000))
    frames = 0
    distances = []
    last = None
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        snap = radar.poll()
        if snap is not None:
            frames += 1
            last = snap
            distance = snap.get("moving_cm") or 0
            if distance:
                distances.append(distance)
        time.sleep_ms(5)
    elapsed = time.ticks_diff(time.ticks_ms(), start) / 1000.0
    if frames == 0:
        print("  FAIL: %.1f 秒內 0 frames" % elapsed)
        print("  先確認模組 Pin-5 (UART_TX) -> GPIO%d，以及 5V/GND" % RX_PIN)
        return False
    print("  OK: %d frames / %.1f 秒 = %.1f Hz"
          % (frames, elapsed, frames / elapsed))
    if distances:
        print("  距離 %d-%d cm，最新 mov=%s stat=%s 狀態=%s"
              % (min(distances), max(distances),
                 last.get("moving_cm"), last.get("stationary_cm"),
                 last.get("state_name")))
    return True


def check_out():
    print("--- 2. OUT 腳 ---")
    if OUT_PIN is None:
        print("  略過：未設定 OUT_PIN")
        return None
    radar = get_radar()
    level = radar.out_level()
    print("  GPIO%-2d -> out_level() = %s" % (OUT_PIN, level))
    print("  驗證方式：離開偵測範圍 2-3 公尺，觀察是否由 1 變 0；"
          "會穩定切換代表 OUT 確實有接")
    return level


def check_commands():
    print("--- 3. 命令通道（只查詢，不寫入）---")
    radar = get_radar()
    ok = False
    try:
        info = radar.firmware_version()
        ok = True
        print("  OK: firmware %s" % info["string"])
    except OSError as exc:
        print("  FAIL: firmware -", exc)
    try:
        cfg = radar.read_params()
        ok = True
        print("  OK: max gate %d (moving %d, stationary %d), no-target %d s"
              % (cfg["max_gate"], cfg["max_moving_gate"],
                 cfg["max_stationary_gate"], cfg["no_one_seconds"]))
    except OSError as exc:
        print("  FAIL: config -", exc)
    return ok


def verdict(stream_ok, command_ok):
    print("")
    print("--- 結論 ---")
    print("資料流  :", "OK" if stream_ok else "FAIL")
    print("命令通道:", "OK" if command_ok else "FAIL")
    if stream_ok and not command_ok:
        print("  形狀為「模組 TX 正常、RX 無回應」。依序檢查：")
        print("   1) 模組 Pin-4 (UART_RX) -> GPIO%d 的線是否真的導通" % TX_PIN)
        print("   2) 換一條杜邦線，或把兩端重插（含模組端接頭）")
        print("   3) 跑 tests/esp32_ld2410_tx_probe.py 的 run() 分辨回音/沒送到")
    elif stream_ok:
        print("  兩者都通，可以開始使用距離、OUT 與參數 API。")


def run(seconds=3):
    show_wiring()
    stream_ok = check_stream(seconds)
    check_out()
    command_ok = check_commands()
    verdict(stream_ok, command_ok)


print("esp32_ld2410_check 已載入；執行 run() 進行完整檢查")
