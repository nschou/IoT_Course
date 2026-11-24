"""TX-direction probe for the LD2410C (ESP32 + MicroPython).

Why: data frames arrive but every command times out with
"ACK timeout: 0x00ff" -> the ESP32 -> module RX direction is the suspect.

It sends the enable-config frame (0x00FF) raw on one chosen TX pin and
classifies what comes back:

  echo     the TX frame came back -> GPIO15/GPIO16 shorted (loopback jumper
           still in place), or the module TX/RX pins are bridged
  ack      a command frame that is not our echo -> the module did answer; the
           driver ACK matching or timing is the bug
  nothing  no command frame at all -> the command never reached the module
           (wire, GPIO, or module RX pin)

It always sends 0x00FE (end config) afterwards so the module keeps working.

Usage from the REPL:

    exec(open("tests/esp32_ld2410_tx_probe.py").read())
    pins()
    run()                  # probe the configured TX pin
    run(47)                # probe GPIO47 instead (move the wire first)
    probe(15, 16, 115200)  # full control
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

CMD_HEAD = LD2410C.CMD_HEAD
DATA_HEAD = LD2410C.DATA_HEAD
ENTER = LD2410C.command_frame(0x00FF, bytes((0x01, 0x00)))
EXIT = LD2410C.command_frame(0x00FE)


def _hex(data):
    if not data:
        return "(none)"
    return " ".join("%02x" % b for b in data)


def _split_frames(data):
    """Return (command_frames, data_frame_count) found in raw bytes."""
    commands = []
    data_frames = 0
    i = 0
    size = len(data)
    while i + 6 <= size:
        head = data[i:i + 4]
        if head == CMD_HEAD or head == DATA_HEAD:
            length = data[i + 4] | (data[i + 5] << 8)
            total = length + 10
            if 2 <= length and i + total <= size:
                if head == CMD_HEAD:
                    commands.append(data[i:i + total])
                else:
                    data_frames += 1
                i += total
                continue
        i += 1
    return commands, data_frames


def probe(tx=None, rx=None, baudrate=None, wait_ms=600):
    """Send 0x00FF on tx and classify what comes back."""
    from machine import UART, Pin

    if tx is None:
        tx = TX_PIN
    if rx is None:
        rx = RX_PIN
    if baudrate is None:
        baudrate = BAUD

    uart = UART(UART_ID, baudrate=baudrate, bits=8, parity=None, stop=1,
                tx=Pin(tx), rx=Pin(rx))
    time.sleep_ms(50)
    uart.read()
    uart.write(ENTER)

    buf = bytearray()
    end = time.ticks_add(time.ticks_ms(), int(wait_ms))
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        chunk = uart.read()
        if chunk:
            buf.extend(chunk)

    uart.write(EXIT)
    time.sleep_ms(40)
    uart.read()
    deinit = getattr(uart, "deinit", None)
    if deinit is not None:
        deinit()

    data = bytes(buf)
    commands, data_frames = _split_frames(data)
    echoes = 0
    others = []
    for frame in commands:
        if frame == ENTER:
            echoes += 1
        else:
            others.append(frame)

    print("probe tx=GPIO%d rx=GPIO%d baud=%d" % (tx, rx, baudrate))
    print("  sent : " + _hex(ENTER))
    print("  got  : %d bytes / %d data frame(s) / %d command frame(s)"
          % (len(data), data_frames, len(commands)))
    if data:
        print("  head : " + _hex(data[:40]))

    if echoes:
        print("  => 收到自己的回音：GPIO%d 與 GPIO%d 被短接（loopback 跳線沒拔），"
              % (tx, rx))
        print("     或模組 TX/RX 接到同一點。")
    elif others:
        print("  => 有非回音的命令框，模組真的回了；問題在驅動的比對或時序：")
        for frame in others:
            print("     " + _hex(frame))
    else:
        print("  => 沒有任何命令框：指令沒送到模組。檢查順序：")
        print("     1) 量模組 UART_RX 腳閒置電壓，應約 3.3 V（0 V 表示被拉低）")
        print("     2) 斷電後量 GPIO%d 到模組 RX 腳是否導通" % tx)
        print("     3) 把模組 RX 線改插別支腳（例如 GPIO47），再跑 run(47)")
    return data


def run(tx=None, rx=None, baudrate=None):
    """Probe once with the given (or configured) pins."""
    return probe(tx, rx, baudrate)


def pins():
    """Show the pins this project uses, without touching the UART."""
    print("uart=%d TX=GPIO%d -> module RX   RX=GPIO%d <- module TX"
          % (UART_ID, TX_PIN, RX_PIN))
    print("OUT=GPIO%s  baud=%d" % ("-" if OUT_PIN is None else OUT_PIN, BAUD))


print("esp32_ld2410_tx_probe 已載入；可用：pins() run() probe(tx, rx, baud)")
