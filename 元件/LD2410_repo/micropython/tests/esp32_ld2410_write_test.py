"""Read/write/restore test for the LD2410C (ESP32 + MicroPython).

Run in the device REPL:

    exec(open("tests/esp32_ld2410_write_test.py").read())
    run()

This is the only test that WRITES module settings. It works like this:

    1. read the saved parameters and keep them in RAM as the backup
    2. engineering mode on -> frame type 1 with 9 gates, off -> type 2
    3. read the distance resolution (read only, changing it needs a restart)
    4. write a temporary configuration (max gate 4/4, no-one 10 s, flat curve)
    5. read back and compare every field
    6. restore the backup and verify it again

If a step fails it still tries to restore the backup. Everything written by
this test is put back before it returns, so a power cycle is only needed if
the restore step itself fails.
"""
import time

from hardware.ld2410c import LD2410C, compare_params

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

TEMP_MAX_MOVING = 4
TEMP_MAX_STATIONARY = 4
TEMP_NO_ONE_SECONDS = 10
TEMP_MOTION = [45, 45, 45, 45, 45, 45, 45, 45, 45]
TEMP_STATIC = [35, 35, 35, 35, 35, 35, 35, 35, 35]


class Report:
    def __init__(self):
        self.items = []

    def record(self, name, status, detail=""):
        self.items.append((name, status, detail))
        line = "[%-4s] %s" % (status, name)
        if detail:
            line += "  -  " + detail
        print(line)

    def tally(self):
        out = {"PASS": 0, "WARN": 0, "FAIL": 0, "SKIP": 0}
        for _n, status, _d in self.items:
            out[status] = out.get(status, 0) + 1
        return out

    def __repr__(self):
        tally = self.tally()
        return "<Report PASS=%d WARN=%d FAIL=%d SKIP=%d>" % (
            tally["PASS"], tally["WARN"], tally["FAIL"], tally["SKIP"])

    def summary(self):
        t = self.tally()
        print("")
        print("=== 結果總表 ===")
        print("PASS=%d  WARN=%d  FAIL=%d  SKIP=%d"
              % (t["PASS"], t["WARN"], t["FAIL"], t["SKIP"]))
        names = [n for n, s, _d in self.items if s == "FAIL"]
        if names:
            print("FAIL 項目:", ", ".join(names))
        if t["FAIL"] == 0:
            print("結論: 寫入/還原全部通過")
        else:
            print("結論: 有 %d 項失敗；若還原也失敗，請重跑 03_set_and_save.py restore"
                  % t["FAIL"])


def make_radar():
    return LD2410C(uart_id=UART_ID, tx=TX_PIN, rx=RX_PIN, baudrate=BAUD,
                   out_pin=OUT_PIN)


def wait_frame(radar, engineering, timeout_ms=2000):
    """Poll until a frame of the requested mode arrives."""
    end = time.ticks_add(time.ticks_ms(), timeout_ms)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        if (radar.poll() is not None
                and radar.frame.get("engineering") == engineering):
            return radar.frame
        time.sleep_ms(20)
    return None


def test_engineering(report, radar):
    print("")
    print("=== 1. 工程模式 round-trip（斷電會自動關閉，不影響存檔）===")
    frame = wait_frame(radar, False, 1000)
    if frame is None:
        report.record("工程模式", "SKIP", "收不到基本上報 frame")
    else:
        print("  基本上報: type=0x%02x gates=%d"
              % (frame.get("type", 0), len(frame.get("moving_gates") or b"")))
    try:
        radar.engineering(True)
        eng = wait_frame(radar, True, 2000)
        gates = len(eng.get("moving_gates") or b"") if eng else 0
        ok = eng is not None and gates == 9
        print("  工程模式: frame=%s gates=%d" % ("yes" if eng else "no", gates))
        report.record("工程模式開啟", "PASS" if ok else "FAIL",
                      "9 個門能量" if ok else "沒有 9 個門能量")
    except OSError as exc:
        report.record("工程模式開啟", "FAIL", str(exc))
        return
    try:
        radar.engineering(False)
        basic = wait_frame(radar, False, 2000)
        ok = basic is not None and not basic.get("engineering")
        report.record("工程模式關閉", "PASS" if ok else "FAIL")
    except OSError as exc:
        report.record("工程模式關閉", "FAIL", str(exc))


def test_resolution(report, radar):
    print("")
    print("=== 2. 距離解析度（只讀；切換需要重啟，故不改）===")
    try:
        res = radar.read_resolution()
        print("  目前: index=%d  meters=%.2f" % (res["index"], res["meters"]))
        report.record("解析度讀取", "PASS", "%.2f m/門" % res["meters"])
    except OSError as exc:
        report.record("解析度讀取", "FAIL", str(exc))


def test_write_restore(report, radar):
    print("")
    print("=== 3. 參數寫入 / 回讀 / 還原 ===")
    backup = None
    try:
        backup = radar.read_params()
        print("  備份: max moving=%d stationary=%d no-one=%d s"
              % (backup["max_moving_gate"], backup["max_stationary_gate"],
                 backup["no_one_seconds"]))
        report.record("參數備份", "PASS")
    except OSError as exc:
        report.record("參數備份", "FAIL", str(exc))
        return

    wanted = {
        "max_gate": backup["max_gate"],
        "max_moving_gate": TEMP_MAX_MOVING,
        "max_stationary_gate": TEMP_MAX_STATIONARY,
        "no_one_seconds": TEMP_NO_ONE_SECONDS,
        "motion_sens": list(TEMP_MOTION),
        "static_sens": list(TEMP_STATIC),
    }
    try:
        result = radar.write_params(wanted)
        diff = result["diff"]
        print("  寫入回讀: verified=%s diff=%d" % (result["verified"], len(diff)))
        for line in diff:
            print("    ! " + line)
        report.record("寫入並回讀", "PASS" if result["verified"] else "FAIL",
                      "" if result["verified"] else "回讀與寫入不一致")
    except OSError as exc:
        report.record("寫入並回讀", "FAIL", str(exc))
    finally:
        print("  還原備份 ...")
        try:
            restored = radar.write_params(backup)
            diff = compare_params(backup, restored["readback"] or {})
            print("  還原回讀: verified=%s diff=%d"
                  % (restored["verified"], len(diff)))
            for line in diff:
                print("    ! " + line)
            report.record("還原備份", "PASS" if restored["verified"] else "FAIL",
                          "" if restored["verified"] else "還原後回讀不一致")
        except OSError as exc:
            report.record("還原備份", "FAIL", str(exc))


def _wait_for_frame(radar, timeout_ms=1500):
    """Wait for the first complete data frame (UART buffer is empty after boot)."""
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        if radar.poll() is not None:
            return True
        time.sleep_ms(20)
    return bool(radar.frame)


def run():
    radar = make_radar()
    report = Report()
    print("=== LD2410C 寫入/還原測試 ===")
    print("uart=%d TX=GPIO%d RX=GPIO%d OUT=GPIO%d baud=%d"
          % (UART_ID, TX_PIN, RX_PIN, OUT_PIN, BAUD))
    print("（這支會暫時修改模組參數，結束前會還原）")
    if not _wait_for_frame(radar):
        print("沒有資料流（1.5 秒內沒有完整 frame），先跑 esp32_ld2410_smoke.py 的 selfcheck()")
        return report
    test_engineering(report, radar)
    test_resolution(report, radar)
    test_write_restore(report, radar)
    report.summary()
    return report


print("esp32_ld2410_write_test 已載入；執行 run()（會暫時改參數並還原）")