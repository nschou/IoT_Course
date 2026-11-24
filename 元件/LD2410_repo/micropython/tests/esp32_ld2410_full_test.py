"""Full functional test for the LD2410C driver (ESP32 + MicroPython).

Run in the device REPL:

    exec(open("tests/esp32_ld2410_full_test.py").read())
    run()

Every run() builds its own Report object, so results never leak between runs.
Only read/query commands are sent: a failure cannot change the module setup.
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


class Report:
    """Per-run results. Never shared between runs, so no stale counts."""

    def __init__(self):
        self.items = []

    def record(self, name, status, detail=""):
        self.items.append((name, status, detail))
        line = "[%-4s] %s" % (status, name)
        if detail:
            line += "  -  " + detail
        print(line)

    def counts(self):
        tally = {"PASS": 0, "WARN": 0, "FAIL": 0, "SKIP": 0}
        for _name, status, _detail in self.items:
            tally[status] = tally.get(status, 0) + 1
        return tally

    def names_with(self, status):
        return [name for name, state, _detail in self.items if state == status]

    def summary(self, radar):
        tally = self.counts()
        print("")
        print("=== 結果總表 ===")
        print("PASS=%d  WARN=%d  FAIL=%d  SKIP=%d"
              % (tally["PASS"], tally["WARN"], tally["FAIL"], tally["SKIP"]))
        for status in ("FAIL", "WARN"):
            names = self.names_with(status)
            if names:
                print("%s 項目: %s" % (status, ", ".join(names)))
        if radar is not None:
            print("driver stats:", radar.stats())
        if tally["FAIL"] == 0:
            print("結論: 全部關鍵功能通過")
        else:
            print("結論: 有 %d 項失敗，見上方明細" % tally["FAIL"])


_radar = None


def get_radar():
    global _radar
    if _radar is None:
        _radar = LD2410C(uart_id=UART_ID, tx=TX_PIN, rx=RX_PIN,
                         baudrate=BAUD, out_pin=OUT_PIN)
    return _radar


def show_configuration(report):
    print("=== 0. 組態 ===")
    print("uart=%d  TX(GPIO%d) -> 模組 RX   RX(GPIO%d) <- 模組 TX   "
          "OUT=GPIO%s   baud=%d" % (UART_ID, TX_PIN, RX_PIN, OUT_PIN, BAUD))
    if TX_PIN == RX_PIN:
        report.record("組態檢查", "FAIL", "TX 與 RX 不可相同")
        return False
    report.record("組態檢查", "PASS")
    return True


def test_stream(report, seconds=5):
    print("")
    print("=== 1. 資料流（%d 秒）===" % seconds)
    radar = get_radar()
    start = time.ticks_ms()
    end = time.ticks_add(start, int(seconds * 1000))
    frames = 0
    moving = []
    stationary = []
    states = {}
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        snap = radar.poll()
        if snap is not None:
            frames += 1
            if snap.get("moving_cm"):
                moving.append(snap["moving_cm"])
            if snap.get("stationary_cm"):
                stationary.append(snap["stationary_cm"])
            state = snap.get("state_name")
            states[state] = states.get(state, 0) + 1
        time.sleep_ms(5)
    elapsed = time.ticks_diff(time.ticks_ms(), start) / 1000.0
    if frames == 0:
        report.record("資料流", "FAIL", "0 frames / %.1f 秒" % elapsed)
        return False
    hz = frames / elapsed
    print("  frames=%d  經過=%.1f s  速率=%.1f Hz" % (frames, elapsed, hz))
    if moving:
        print("  moving 距離: min=%d max=%d cm" % (min(moving), max(moving)))
    if stationary:
        print("  stationary 距離: min=%d max=%d cm"
              % (min(stationary), max(stationary)))
    print("  狀態分佈:", states)
    ok = 4.0 <= hz <= 15.0
    report.record("資料流", "PASS" if ok else "WARN",
                  "%.1f Hz" % hz if ok else "%.1f Hz（預期約 10 Hz）" % hz)
    return True


def test_live(report, ticks=10, interval_ms=200):
    print("")
    print("=== 2. 即時讀值（每 %d ms 一筆，共 %d 筆）===" % (interval_ms, ticks))
    radar = get_radar()
    print("  t(s)   state                  moving  energy  stationary  energy  detect  out")
    mismatch = 0
    seen = 0
    for index in range(ticks):
        radar.poll()
        frame = radar.frame
        out = radar.out_level()
        if frame:
            present = bool(frame.get("presence"))
            if out is not None:
                seen += 1
                if bool(out) != present:
                    mismatch += 1
            print("  %4.1f   %-22s %-7s %-7s %-11s %-7s %-7s %s"
                  % (index * interval_ms / 1000.0,
                     str(frame.get("state_name")),
                     str(frame.get("moving_cm")),
                     str(frame.get("moving_energy")),
                     str(frame.get("stationary_cm")),
                     str(frame.get("stationary_energy")),
                     str(frame.get("detection_cm")),
                     str(out)))
        time.sleep_ms(interval_ms)
    if seen == 0:
        report.record("即時讀值", "SKIP", "未設定 OUT")
    else:
        ratio = mismatch / float(seen)
        report.record("OUT 與狀態一致",
                      "PASS" if ratio <= 0.2 else "WARN",
                      "不一致 %d/%d 筆" % (mismatch, seen))
        report.record("即時讀值", "PASS", "%d 筆" % ticks)


def test_freshness(report):
    print("")
    print("=== 3. 資料新鮮度（不輪詢後 age 會變大）===")
    radar = get_radar()
    radar.poll()
    fresh_age = radar.age_ms()
    fresh_ok = radar.is_connected(within_ms=500)
    print("  剛更新: age_ms=%s connected=%s" % (fresh_age, fresh_ok))
    time.sleep_ms(300)
    stale_age = radar.age_ms()
    stale_ok = radar.is_connected(within_ms=150)
    print("  停 300 ms: age_ms=%s connected(150ms)=%s"
          % (stale_age, stale_ok))
    ok = fresh_ok and not stale_ok
    report.record("資料新鮮度", "PASS" if ok else "FAIL",
                  "fresh -> stale" if ok else "預期 fresh 後變 stale")


def test_encoder(report):
    print("")
    print("=== 4. 命令編碼（比對原廠範例，不送出）===")
    radar = get_radar()
    cases = [
        ("enter config",
         LD2410C.command_frame(0x00FF, bytes((0x01, 0x00))),
         "fd fc fb fa 04 00 ff 00 01 00 04 03 02 01"),
        ("exit config",
         LD2410C.command_frame(0x00FE),
         "fd fc fb fa 02 00 fe 00 04 03 02 01"),
        ("set max 8/8/5",
         LD2410C.command_frame(0x0060,
                               bytes((0, 0, 8, 0, 0, 0,
                                      1, 0, 8, 0, 0, 0,
                                      2, 0, 5, 0, 0, 0))),
         "fd fc fb fa 14 00 60 00 00 00 08 00 00 00 01 00 08 00 00 00 "
         "02 00 05 00 00 00 04 03 02 01"),
        ("gate 3 sensitivity 40/40",
         LD2410C.command_frame(0x0064,
                               bytes((0, 0, 3, 0, 0, 0,
                                      1, 0, 40, 0, 0, 0,
                                      2, 0, 40, 0, 0, 0))),
         "fd fc fb fa 14 00 64 00 00 00 03 00 00 00 01 00 28 00 00 00 "
         "02 00 28 00 00 00 04 03 02 01"),
    ]
    ok = True
    for name, frame, expected in cases:
        actual = " ".join("%02x" % b for b in frame)
        match = actual == expected
        ok = ok and match
        print("  %-26s %s" % (name, "OK" if match else "MISMATCH"))
        if not match:
            print("    實際:", actual)
            print("    預期:", expected)
    ack = LD2410C.ack_word(0x00FF)
    ack_ok = bytes(ack) == b"\xff\x01"
    print("  ACK 推算 0x00FF -> %02x %02x %s"
          % (ack[0], ack[1], "OK" if ack_ok else "MISMATCH"))
    report.record("命令編碼", "PASS" if (ok and ack_ok) else "FAIL")


def test_commands(report):
    print("")
    print("=== 5. 命令通道（只查詢）===")
    radar = get_radar()
    try:
        info = radar.firmware_version()
        print("  firmware: %s" % info["string"])
        report.record("firmware_version()", "PASS", info["string"])
    except OSError as exc:
        print("  firmware: FAIL -", exc)
        report.record("firmware_version()", "FAIL", str(exc))
    try:
        cfg = radar.read_params()
        print("  max gate=%d  moving_gate=%d  stationary_gate=%d  no-target=%d s"
              % (cfg["max_gate"], cfg["max_moving_gate"],
                 cfg["max_stationary_gate"], cfg["no_one_seconds"]))
        print("  moving sensitivity    :", cfg["motion_sens"])
        print("  stationary sensitivity:", cfg["static_sens"])
        report.record("read_params()", "PASS")
    except OSError as exc:
        print("  config: FAIL -", exc)
        report.record("read_params()", "FAIL", str(exc))


def run(stream_seconds=5, ticks=10, interval_ms=200):
    """Run every check once, with a fresh report for this invocation."""
    report = Report()
    if not show_configuration(report):
        report.summary(get_radar())
        return report
    if test_stream(report, stream_seconds):
        test_live(report, ticks, interval_ms)
        test_freshness(report)
    test_encoder(report)
    test_commands(report)
    report.summary(get_radar())
    return report


print("esp32_ld2410_full_test 已載入；執行 run() 進行完整功能測試")
