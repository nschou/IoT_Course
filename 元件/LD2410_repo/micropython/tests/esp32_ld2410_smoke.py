"""On-device smoke test for the LD2410C driver (ESP32 + MicroPython).

Upload next to the hardware/ folder and run from the REPL:

    exec(open("tests/esp32_ld2410_smoke.py").read())

    selfcheck()      # pin levels + is a data frame arriving within 1.5 s
    raw(3)           # bypass the driver and print raw UART bytes (hex)
    stream(15)       # print distance and OUT through the driver every 200 ms
    info()           # firmware version + saved parameters (read only)
    command_probe()  # send 0x00FF raw and classify what comes back
    run()            # selfcheck -> info -> raw -> stream

Only reads and queries; it never writes module settings.
"""
import time

from hardware.ld2410c import LD2410C

# --- wiring of this project (see README) -----------------------------------
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

ENTER = LD2410C.command_frame(0x00FF, bytes((0x01, 0x00)))
EXIT = LD2410C.command_frame(0x00FE)


def make_radar():
    return LD2410C(uart_id=UART_ID, tx=TX_PIN, rx=RX_PIN, baudrate=BAUD,
                   out_pin=OUT_PIN)


def selfcheck(seconds=1.5):
    """Report pin levels and whether any data frame arrives."""
    print("config: uart=%d tx=%d rx=%d out=%s baud=%d"
          % (UART_ID, TX_PIN, RX_PIN, OUT_PIN, BAUD))

    try:
        from machine import Pin
        for name, pin in (("TX", TX_PIN), ("RX", RX_PIN), ("OUT", OUT_PIN)):
            if pin is None:
                continue
            probe = Pin(pin, Pin.IN, Pin.PULL_UP)
            time.sleep_ms(10)
            print("  GPIO%-2d %-3s pull-up -> %d" % (pin, name, probe.value()))
        print("  註：RX 腳在模組 TX 閒置時應為 1；若為 0，先查供電與接線。")
    except Exception as exc:
        print("  pin check skipped:", exc)

    radar = make_radar()
    snap = None
    end = time.ticks_add(time.ticks_ms(), int(seconds * 1000))
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        snap = radar.poll()
        if snap is not None:
            break
        time.sleep_ms(20)

    if snap is None:
        print("RESULT: no data frame within %.1f s" % seconds)
        print("        check VCC=5V, common GND, and module TX -> GPIO%d" % RX_PIN)
    else:
        print("RESULT: frame ok, moving=%s cm, state=%s, out=%s"
              % (snap.get("moving_cm"), snap.get("state_name"),
                 radar.out_level()))
    print("stats:", radar.stats())
    return snap


def raw(seconds=3):
    """Print raw UART bytes without the driver (diagnostic only)."""
    from machine import UART, Pin

    uart = UART(UART_ID, baudrate=BAUD, bits=8, parity=None, stop=1,
                tx=Pin(TX_PIN), rx=Pin(RX_PIN))
    buf = bytearray()
    end = time.ticks_add(time.ticks_ms(), int(seconds * 1000))
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        chunk = uart.read()
        if chunk:
            buf.extend(chunk)
        time.sleep_ms(5)
    data = bytes(buf)
    deinit = getattr(uart, "deinit", None)
    if deinit is not None:
        deinit()

    print("raw: %d bytes in %.1f s" % (len(data), seconds))
    if data:
        print("  head:", data[:32])
        print("  has data header:", data.find(b"\xf4\xf3\xf2\xf1") >= 0)
    else:
        print("  no bytes: check power, ground, TX/RX crossing and baudrate")
    return data


def stream(seconds=15, interval_ms=200):
    """Print distance and OUT through the driver."""
    radar = make_radar()
    start = time.ticks_ms()
    end = time.ticks_add(start, int(seconds * 1000))
    last_report = 0
    frames = 0
    unknown = 0
    distances = []

    print("t(s)  state      dist   moving  stationary  detect  out")
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        snap = radar.poll()
        now = time.ticks_diff(time.ticks_ms(), start)
        if snap is not None:
            frames += 1
            distance = snap.get("moving_cm") or 0
            if distance:
                distances.append(distance)
        if now - last_report >= interval_ms:
            last_report = now
            frame = radar.frame
            out = radar.out_level()
            if not frame:
                unknown += 1
                print("%.1f  unknown     -      -       -           -       %s"
                      % (now / 1000.0, out))
            else:
                print("%.1f  %-10s %-6s %-7s %-11s %-7s %s"
                      % (now / 1000.0, frame.get("state_name"),
                         frame.get("moving_cm"), frame.get("moving_energy"),
                         frame.get("stationary_energy"),
                         frame.get("detection_cm"), out))
        time.sleep_ms(20)

    print("--- summary ---")
    print("frames: %d, unknown reports: %d, stats: %s"
          % (frames, unknown, radar.stats()))
    if distances:
        print("moving distance cm: min=%d max=%d"
              % (min(distances), max(distances)))
    print("out now:", radar.out_level())
    return radar.stats()


def info():
    """Read and print firmware version plus the saved parameters."""
    radar = make_radar()
    try:
        fw = radar.firmware_version()
        print("firmware: %s" % fw["string"])
    except OSError as exc:
        print("firmware: failed -", exc)
    try:
        cfg = radar.read_params()
        print("max gate %d (moving %d, stationary %d)"
              % (cfg["max_gate"], cfg["max_moving_gate"],
                 cfg["max_stationary_gate"]))
        print("moving sensitivity:", cfg["motion_sens"])
        print("stationary sensitivity:", cfg["static_sens"])
        print("no-target seconds:", cfg["no_one_seconds"])
    except OSError as exc:
        print("config: failed -", exc)


def command_probe(timeout_ms=800):
    """Send the enter-config command raw and report what comes back.

    - command frames > 0 and not an echo -> the module answered
    - only echoes -> GPIO15 and GPIO16 are shorted (loopback jumper)
    - no command frame while data keeps coming -> the command never arrived
    """
    radar = make_radar()
    print("tx frame:", " ".join("%02x" % b for b in ENTER))
    radar.flush()
    written = radar.uart.write(ENTER)
    print("uart.write returned:", written, "(expected", len(ENTER), ")")

    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    command_frames = 0
    data_frames = 0
    echoes = 0
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        radar._pump()
        while True:
            got = radar._next_frame()
            if got is None:
                break
            if got[:4] == LD2410C.CMD_HEAD:
                command_frames += 1
                if got == ENTER:
                    echoes += 1
                    print("  echo of our own frame")
                else:
                    print("  cmd frame:", " ".join("%02x" % b for b in got))
            else:
                data_frames += 1
        time.sleep_ms(5)

    print("command frames:", command_frames, " data frames:", data_frames,
          " echoes:", echoes)
    if echoes and echoes == command_frames:
        print("  -> 只收到自己的回音：GPIO15 與 GPIO16 短接（跳線未拔）。")
    elif command_frames and not echoes:
        print("  -> 收到非回音的命令框，很可能是真正的 ACK。")
    elif data_frames:
        print("  -> 資料持續進來但沒有任何命令框：指令沒送到模組。")
    if radar._buf:
        print("leftover:", " ".join("%02x" % b for b in bytes(radar._buf[:32])))
    radar.uart.write(EXIT)
    print("sent exit-config")
    return command_frames, data_frames


def run():
    selfcheck()
    info()
    raw(3)
    return stream(15)


print("esp32_ld2410_smoke 已載入；可用：selfcheck() info() raw() stream() command_probe() run()")
