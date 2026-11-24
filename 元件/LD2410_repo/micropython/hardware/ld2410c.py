"""MicroPython driver for the Hi-Link HLK-LD2410C 24 GHz radar module.

Hardware: ESP32 + MicroPython 1.19 or newer, UART 8N1.
Verified against firmware V2.44.24073110 running at 115200 baud.

The module continuously streams data frames:

    F4 F3 F2 F1 | len(2) | payload | F8 F7 F6 F5

and answers configuration frames:

    FD FC FB FA | len(2) | payload | 04 03 02 01

Any configuration command must be wrapped in "enable config" (0x00FF) and
"end config" (0x00FE).  The module sometimes swallows the first 0x00FF while
it is busy streaming (the official PC tool logs it as
"OpenCmdMode: CMDID(0x00FF) failed with:A002" and simply retries), therefore
every command here is retried and confirmed by its ACK.

Protocol reference: docs/HLK-LD2410C_protocol.md
Frame layout was checked against 1756 frames captured with the official tool
(see tests/fixtures).  All distances are centimetres unless a name says
otherwise.
"""

import time

try:
    from machine import UART, Pin
except ImportError:  # CPython: host-side test-suite only.
    UART = None
    Pin = None

try:
    from time import ticks_ms, ticks_add, ticks_diff
except ImportError:  # CPython
    def ticks_ms():
        return int(time.monotonic() * 1000)

    def ticks_add(value, delta):
        return value + delta

    def ticks_diff(first, second):
        return first - second

try:
    from time import sleep_ms
except ImportError:  # CPython
    def sleep_ms(delay):
        time.sleep(delay / 1000.0)


DATA_HEAD = b"\xf4\xf3\xf2\xf1"
DATA_TAIL = b"\xf8\xf7\xf6\xf5"
CMD_HEAD = b"\xfd\xfc\xfb\xfa"
CMD_TAIL = b"\x04\x03\x02\x01"

# Command words (see protocol section 2.2).
CMD_ENTER_CONFIG = 0x00FF
CMD_EXIT_CONFIG = 0x00FE
CMD_SET_MAX_GATES = 0x0060
CMD_READ_PARAMS = 0x0061
CMD_ENGINEERING_ON = 0x0062
CMD_ENGINEERING_OFF = 0x0063
CMD_SET_SENSITIVITY = 0x0064
CMD_FIRMWARE = 0x00A0
CMD_SET_BAUD = 0x00A1
CMD_FACTORY_RESET = 0x00A2
CMD_RESTART = 0x00A3
CMD_SET_RESOLUTION = 0x00AA
CMD_READ_RESOLUTION = 0x00AB

# Baud rate selection index, protocol table 6.
BAUD_INDEX = {9600: 1, 19200: 2, 38400: 3, 57600: 4,
              115200: 5, 230400: 6, 256000: 7, 460800: 8}
BAUD_RATES = (115200, 256000, 9600, 19200, 38400, 57600, 230400, 460800)

STATE_NAMES = {0x00: "none", 0x01: "moving", 0x02: "stationary",
               0x03: "moving+stationary"}


class LD2410CError(Exception):
    """Base class for every radar communication failure."""


class LD2410CTimeout(LD2410CError):
    """The radar did not answer before the deadline."""


class LD2410CCommandError(LD2410CError):
    """The radar answered a command with a non-zero (failure) status."""


def _le16(value):
    value = int(value)
    if value < 0 or value > 0xFFFF:
        raise ValueError("value out of 16-bit range: %r" % (value,))
    return bytes((value & 0xFF, (value >> 8) & 0xFF))


def _le32(value):
    value = int(value)
    if value < 0 or value > 0xFFFFFFFF:
        raise ValueError("value out of 32-bit range: %r" % (value,))
    return bytes((value & 0xFF, (value >> 8) & 0xFF,
                  (value >> 16) & 0xFF, (value >> 24) & 0xFF))


def _u16(data, offset=0):
    return data[offset] | (data[offset + 1] << 8)


def _u32(data, offset=0):
    return (data[offset] | (data[offset + 1] << 8) |
            (data[offset + 2] << 16) | (data[offset + 3] << 24))


def hexdump(data, limit=32):
    """Return 'F4 F3 F2 F1 ...' for logs and diagnostics."""
    if not data:
        return ""
    part = data[:limit]
    text = " ".join("%02X" % byte for byte in part)
    if len(data) > limit:
        text += " ..."
    return text


class LD2410C:
    """HLK-LD2410C driver.

    Parameters
    ----------
    uart : machine.UART, optional
        An existing UART.  When omitted a UART is created from uart_id/tx/rx.
    uart_id, tx, rx : int
        ESP32 defaults: UART1, TX=GPIO17 -> radar RX, RX=GPIO16 <- radar TX.
    baudrate : int
        The module default is 256000, but many USB-serial chips and this
        particular module are used at 115200.  diagnose() finds the value.
    out : machine.Pin, optional
        OUT pin of the module (presence signal, 3.3 V).
    out_pin : int, optional
        Create the OUT pin from a pin number.
    out_active_high : bool
        True when OUT is high while a target is present (module default).
    timeout_ms : int
        Default per-command ACK timeout.
    """

    DATA_HEAD = DATA_HEAD
    DATA_TAIL = DATA_TAIL
    CMD_HEAD = CMD_HEAD
    CMD_TAIL = CMD_TAIL

    def __init__(self, uart=None, uart_id=1, tx=17, rx=16, baudrate=115200,
                 out=None, out_pin=None, out_active_high=True,
                 timeout_ms=800):
        if type(uart) is int:  # LD2410C(1, tx=17, rx=16)
            uart_id = uart
            uart = None

        if uart is None:
            if UART is None:
                raise LD2410CError("machine.UART is not available; pass uart=")
            uart = UART(uart_id, baudrate=baudrate, bits=8, parity=None,
                        stop=1, tx=tx, rx=rx)
        self.uart = uart

        if out is not None:
            self.out = out
        elif out_pin is not None:
            if Pin is None:
                raise LD2410CError("machine.Pin is not available; pass out=")
            self.out = Pin(out_pin, Pin.IN)
        else:
            self.out = None

        self.out_active_high = bool(out_active_high)
        self.baudrate = baudrate
        self.timeout_ms = timeout_ms
        self.debug = False

        self._buf = bytearray()
        self.frame = {}
        self.frames = 0
        self.errors = 0
        self.frame_ms = None
        self.firmware = None
        self.last_params = None

    # ------------------------------------------------------------------ UART

    def _pump(self):
        """Move every byte that the UART holds into the frame buffer."""
        uart = self.uart
        if uart is None:
            return 0
        any_method = getattr(uart, "any", None)
        if any_method is not None:
            count = any_method()
            if not count:
                return 0
            data = uart.read(count)
        else:
            data = uart.read()
        if not data:
            return 0
        self._buf.extend(data)
        return len(data)

    def flush(self):
        """Drop everything that is already buffered."""
        self._buf = bytearray()
        if self.uart is None:
            return
        for _ in range(8):  # bounded, so a saturated stream cannot hang us
            if not self._pump():
                break

    def _next_frame(self):
        """Return the next complete frame, or None when more data is needed."""
        buf = self._buf
        while len(buf) >= 6:
            data_at = buf.find(DATA_HEAD)
            cmd_at = buf.find(CMD_HEAD)
            if data_at < 0 and cmd_at < 0:
                if len(buf) > 3:      # a partial header may still arrive
                    buf = buf[-3:]
                self._buf = buf
                return None
            if data_at < 0:
                start = cmd_at
            elif cmd_at < 0:
                start = data_at
            else:
                start = data_at if data_at < cmd_at else cmd_at
            if start:
                buf = buf[start:]
            if len(buf) < 6:
                self._buf = buf
                return None

            length = buf[4] | (buf[5] << 8)
            if length < 2 or length > 128:  # impossible size: resync
                buf = buf[1:]
                continue
            total = length + 10
            if len(buf) < total:
                self._buf = buf
                return None
            is_data = buf[0] == 0xF4 and buf[1] == 0xF3
            tail = DATA_TAIL if is_data else CMD_TAIL
            if bytes(buf[total - 4:total]) != tail:
                buf = buf[1:]
                continue
            frame = bytes(buf[:total])
            self._buf = buf[total:]
            return frame
        return None

    # -------------------------------------------------------------- data API

    def _parse_data(self, raw):
        payload = raw[6:-4]
        if len(payload) < 13:
            return False
        if payload[0] != 0x01 and payload[0] != 0x02:
            return False
        if payload[1] != 0xAA or payload[-2] != 0x55 or payload[-1] != 0x00:
            return False

        frame = self.frame
        frame["type"] = payload[0]
        frame["engineering"] = payload[0] == 0x01
        frame["state"] = payload[2]
        frame["state_name"] = STATE_NAMES.get(payload[2], "unknown")
        frame["presence"] = payload[2] != 0
        frame["moving_cm"] = _u16(payload, 3)
        frame["moving_energy"] = payload[5]
        frame["stationary_cm"] = _u16(payload, 6)
        frame["stationary_energy"] = payload[8]
        frame["detection_cm"] = _u16(payload, 9)
        # The module reports 0 as detection distance while it still knows the
        # target distance (seen in real captures), so fall back to the target
        # distance to keep a usable "how far is the person" value.
        distance = frame["detection_cm"]
        if not distance:
            distance = frame["moving_cm"]
            if frame["stationary_cm"] > distance:
                distance = frame["stationary_cm"]
        frame["distance_cm"] = distance
        frame["distance_m"] = distance / 100.0
        frame["max_moving_gate"] = 0
        frame["max_stationary_gate"] = 0
        frame["moving_gates"] = b""
        frame["stationary_gates"] = b""
        frame["light"] = None
        frame["extra"] = None

        if payload[0] == 0x01 and len(payload) >= 35:
            # Engineering frame: 2 max gates + 9 + 9 gate energies, then the
            # firmware V2.44 tail: light level (0-255) and one reserved byte.
            frame["max_moving_gate"] = payload[11]
            frame["max_stationary_gate"] = payload[12]
            frame["moving_gates"] = bytes(payload[13:22])
            frame["stationary_gates"] = bytes(payload[22:31])
            frame["light"] = payload[31]
            frame["extra"] = payload[32]

        self.frame_ms = ticks_ms()
        self.frames += 1
        return True

    def poll(self):
        """Consume what the UART already holds.

        Returns the frame dictionary when at least one new data frame was
        parsed, otherwise None.  The dictionary object is reused, so copy it
        if you need to keep a frame around.
        """
        if self.uart is None:
            return None
        self._pump()
        fresh = False
        while True:
            raw = self._next_frame()
            if raw is None:
                break
            if raw[0] != 0xF4:  # command ACK: handled by the caller
                continue
            if self._parse_data(raw):
                fresh = True
            else:
                self.errors += 1
        return self.frame if fresh else None

    def read(self, timeout_ms=None):
        """Blocking variant of poll(): wait for one data frame."""
        if timeout_ms is None:
            return self.poll()
        deadline = ticks_add(ticks_ms(), timeout_ms)
        while ticks_diff(deadline, ticks_ms()) > 0:
            frame = self.poll()
            if frame is not None:
                return frame
            sleep_ms(2)
        raise LD2410CTimeout("no data frame within %d ms" % timeout_ms)

    def age_ms(self):
        """Milliseconds since the last data frame, or None."""
        if self.frame_ms is None:
            return None
        return ticks_diff(ticks_ms(), self.frame_ms)

    def is_connected(self, within_ms=1500):
        age = self.age_ms()
        return age is not None and age <= within_ms

    def stats(self):
        """Frame/error counters plus the bytes still buffered."""
        return {"frames": self.frames, "errors": self.errors,
                "buffered": len(self._buf)}

    def out_level(self):
        """Presence level from the OUT pin, or None when not wired."""
        if self.out is None:
            return None
        level = self.out.value()
        return bool(level) if self.out_active_high else not bool(level)

    def presence(self):
        """OUT pin when available, otherwise the last data frame."""
        level = self.out_level()
        if level is not None:
            return level
        return bool(self.frame.get("presence"))

    # ---------------------------------------------------------- command layer

    @classmethod
    def command_frame(cls, command, value=b""):
        """Build one command/ACK frame (without touching the UART)."""
        body = _le16(command) + value
        return CMD_HEAD + _le16(len(body)) + body + CMD_TAIL

    @staticmethod
    def ack_word(command):
        """The command word that the ACK for command starts with."""
        return bytes((command & 0xFF, ((command >> 8) + 1) & 0xFF))

    def _send_frame(self, command, value=b""):
        self.uart.write(self.command_frame(command, value))

    def _wait_ack(self, command, timeout_ms):
        wanted = self.ack_word(command)
        deadline = ticks_add(ticks_ms(), timeout_ms)
        while ticks_diff(deadline, ticks_ms()) > 0:
            self._pump()
            while True:
                raw = self._next_frame()
                if raw is None:
                    break
                if raw[0] != 0xFD:
                    continue
                payload = raw[6:-4]
                if len(payload) < 4 or payload[:2] != wanted:
                    continue
                status = _u16(payload, 2)
                if status != 0:
                    raise LD2410CCommandError(
                        "command 0x%04X failed, status %d" % (command, status))
                return bytes(payload[4:])
            sleep_ms(2)
        return None

    def send(self, command, value=b"", timeout_ms=None, retries=1,
             flush=True):
        """Send one command and return the ACK payload after the status word.

        Raises LD2410CTimeout when no ACK arrives and LD2410CCommandError
        when the module answers with a failure status.
        """
        if self.uart is None:
            raise LD2410CError("UART is not configured")
        if timeout_ms is None:
            timeout_ms = self.timeout_ms
        for attempt in range(retries):
            if flush:
                self.flush()
            if self.debug:
                print("TX 0x%04X %s" % (command, hexdump(value)))
            self._send_frame(command, value)
            payload = self._wait_ack(command, timeout_ms)
            if payload is not None:
                if self.debug:
                    print("RX 0x%04X %s" % (command, hexdump(payload)))
                return payload
        raise LD2410CTimeout("command 0x%04X: no ACK" % command)

    def enter_config(self, retries=6, delay_ms=40):
        """Send 0x00FF; retry because the module ignores it now and then."""
        last = None
        for attempt in range(retries):
            try:
                self.send(CMD_ENTER_CONFIG, b"\x01\x00", retries=1)
                sleep_ms(20)
                return True
            except LD2410CError as error:
                last = error
                sleep_ms(delay_ms)
        raise LD2410CTimeout("enter config mode failed (%s)" % (last,))

    def exit_config(self, quiet=True):
        """Send 0x00FE and let the module resume normal output."""
        try:
            self.send(CMD_EXIT_CONFIG, b"", timeout_ms=400, retries=1)
            return True
        except LD2410CError:
            if not quiet:
                raise
            return False

    def _configured(self, operation):
        """Run operation() inside one enable/end configuration session."""
        self.enter_config()
        try:
            return operation()
        finally:
            self.exit_config()

    # -------------------------------------------------------------- parameters

    def read_params(self):
        """Read the saved configuration (command 0x0061).

        Returns a dictionary: gate limits, one sensitivity per gate and the
        "nobody here" delay.  The values come from the module flash and are
        the same after a power cycle.
        """
        payload = self._configured(
            lambda: self.send(CMD_READ_PARAMS, b"", timeout_ms=1000))
        if len(payload) < 24 or payload[0] != 0xAA:
            raise LD2410CCommandError(
                "unexpected parameter answer: %s" % hexdump(payload))
        n = payload[1]
        if n > 8:
            raise LD2410CCommandError("gate count %d out of range" % n)
        motion = list(payload[4:4 + n + 1])
        static = list(payload[4 + n + 1:4 + 2 * (n + 1)])
        idle_at = 4 + 2 * (n + 1)
        if len(payload) < idle_at + 2 or len(motion) != n + 1:
            raise LD2410CCommandError("short parameter answer")
        params = {
            "max_gate": n,
            "max_moving_gate": payload[2],
            "max_stationary_gate": payload[3],
            "motion_sens": motion,
            "static_sens": static,
            "no_one_seconds": _u16(payload, idle_at),
        }
        self.last_params = params
        return params

    def write_params(self, params, verify=True):
        """Write max gates, the nobody delay and all gate sensitivities.

        params must carry the keys returned by read_params():
        max_moving_gate, max_stationary_gate, no_one_seconds,
        motion_sens (9 values), static_sens (9 values).

        Sending 0x0060 / 0x0064 stores the values in the module flash, so
        they survive a power cycle.  With verify=True the whole block is read
        back and compared; the answer then contains
        {"verified": bool, "readback": dict, "diff": [...]}.
        """
        motion = list(params["motion_sens"])
        static = list(params["static_sens"])
        if len(motion) != 9 or len(static) != 9:
            raise ValueError("motion_sens/static_sens need 9 values (gate 0-8)")
        for value in motion + static:
            if value < 0 or value > 100:
                raise ValueError("sensitivity must stay in 0..100")
        max_moving = int(params["max_moving_gate"])
        max_static = int(params["max_stationary_gate"])
        idle = int(params["no_one_seconds"])
        if not 1 <= max_moving <= 8 or not 1 <= max_static <= 8:
            raise ValueError("maximum gate must stay in 1..8")

        def write():
            self.send(CMD_SET_MAX_GATES,
                      _le16(0) + _le32(max_moving) +
                      _le16(1) + _le32(max_static) +
                      _le16(2) + _le32(idle), timeout_ms=1000)
            sleep_ms(20)
            for gate in range(9):
                self.send(CMD_SET_SENSITIVITY,
                          _le16(0) + _le32(gate) +
                          _le16(1) + _le32(motion[gate]) +
                          _le16(2) + _le32(static[gate]), timeout_ms=1000)
                sleep_ms(20)

        self._configured(write)

        result = {"verified": None, "readback": None, "diff": []}
        if verify:
            back = self.read_params()
            diff = compare_params(params, back)
            result["verified"] = not diff
            result["readback"] = back
            result["diff"] = diff
        return result

    def read_resolution(self):
        """Distance per gate: 0.75 m (factory) or 0.2 m."""
        payload = self._configured(
            lambda: self.send(CMD_READ_RESOLUTION, b"", timeout_ms=800))
        if len(payload) < 2:
            raise LD2410CCommandError("short resolution answer")
        index = _u16(payload, 0)
        return {"index": index, "meters": 0.75 if index == 0 else 0.2}

    def set_resolution(self, meters, restart=True):
        """Set 0.75 or 0.2 metres per gate (takes effect after a restart)."""
        if meters not in (0.75, 0.2):
            raise ValueError("resolution must be 0.75 or 0.2")
        index = 0 if meters == 0.75 else 1
        self._configured(
            lambda: self.send(CMD_SET_RESOLUTION, _le16(index),
                              timeout_ms=800))
        if restart:
            self.restart()
        return index

    def firmware_version(self):
        """Read and format the firmware version (command 0x00A0)."""
        payload = self._configured(
            lambda: self.send(CMD_FIRMWARE, b"", timeout_ms=800))
        if len(payload) < 8:
            raise LD2410CCommandError("short firmware answer")
        self.firmware = {
            "type": _u16(payload, 0),
            "minor": payload[2],
            "major": payload[3],
            "bugfix": _u32(payload, 4),
            "string": "V%d.%02d.%08X" % (payload[3], payload[2],
                                         _u32(payload, 4)),
        }
        return self.firmware

    def set_baudrate(self, baud, restart=True):
        """Store a new UART baud rate (command 0x00A1).

        The module keeps the selection in flash and applies it after a
        restart, so this method restarts the module and re-opens the UART at
        the new rate.  If anything goes wrong the module may become
        unreachable at the old rate; diagnose() can find it again.
        """
        index = BAUD_INDEX.get(baud)
        if index is None:
            raise ValueError("unsupported baud rate: %r" % (baud,))
        self._configured(
            lambda: self.send(CMD_SET_BAUD, _le16(index), timeout_ms=800))
        if restart:
            self.restart()
            sleep_ms(300)
            self.uart.init(baudrate=baud, bits=8, parity=None, stop=1)
            self.baudrate = baud
            self.flush()
        return index

    def engineering(self, enabled=True):
        """Switch the per-gate energies on/off (0x0062 / 0x0063)."""
        command = CMD_ENGINEERING_ON if enabled else CMD_ENGINEERING_OFF
        self._configured(lambda: self.send(command, b"", timeout_ms=800))
        return bool(enabled)

    def restart(self):
        """Restart the module (command 0x00A3)."""
        ok = True
        try:
            self._configured(
                lambda: self.send(CMD_RESTART, b"", timeout_ms=600))
        except LD2410CError:
            ok = False
        self.frame_ms = None
        self.frames = 0
        sleep_ms(200)
        self.flush()
        return ok

    def factory_reset(self):
        """Restore the factory configuration and restart (0x00A2)."""
        ok = True
        try:
            self._configured(
                lambda: self.send(CMD_FACTORY_RESET, b"", timeout_ms=800))
        except LD2410CError:
            ok = False
        self.restart()
        return ok

    # ------------------------------------------------------------ diagnostics

    def _listen(self, duration_ms):
        """Count data frames for duration_ms and capture the raw header."""
        self._buf = bytearray()
        count = 0
        raw = b""
        deadline = ticks_add(ticks_ms(), duration_ms)
        while ticks_diff(deadline, ticks_ms()) > 0:
            self._pump()
            if not raw and self._buf:
                raw = bytes(self._buf[:12])
            while True:
                frame = self._next_frame()
                if frame is None:
                    break
                if frame[0] == 0xF4:
                    count += 1
            sleep_ms(1)
        return count, raw

    def _probe_command(self, tries=3):
        """Is the command channel answering?  (short timeout: probing)"""
        saved = self.timeout_ms
        self.timeout_ms = 250
        try:
            self.enter_config(retries=tries, delay_ms=30)
        except LD2410CError:
            return False
        finally:
            self.timeout_ms = saved
        self.exit_config()
        return True

    def diagnose(self, verbose=True):
        """Find out why the radar does not answer.

        Checks, in this order: does data arrive at the current baud rate,
        does the command channel answer, and if nothing arrives at all, which
        baud rate does respond.  Nothing is written to the module.

        Result keys: data_ok (frames arrive), cmd_ok (0x00FF is answered),
        ok (the link is usable for configuration), found_baud.
        """
        result = {"start_baud": self.baudrate, "frames": 0, "raw": "",
                  "data_ok": False, "cmd_ok": False, "ok": False,
                  "found_baud": None, "scan": []}
        if self.uart is None:
            raise LD2410CError("UART is not configured")

        frames, raw = self._listen(500)
        result["frames"] = frames
        result["raw"] = hexdump(raw)
        result["data_ok"] = frames > 0
        if verbose:
            print("baud %d: %d data frame(s) in 500 ms, first bytes: %s"
                  % (self.baudrate, frames, result["raw"] or "-"))

        result["cmd_ok"] = self._probe_command(tries=4)
        if verbose:
            print("baud %d: command channel %s"
                  % (self.baudrate, "OK" if result["cmd_ok"] else "no ACK"))

        # Something worked: that proves the baud rate, so do not scan away
        # from it.  Only the command channel is required to be usable.
        if result["data_ok"] or result["cmd_ok"]:
            result["ok"] = result["cmd_ok"]
            result["found_baud"] = self.baudrate
            return result

        for baud in BAUD_RATES:
            if baud == self.baudrate:
                continue
            try:
                self.uart.init(baudrate=baud, bits=8, parity=None, stop=1)
            except Exception:
                continue
            frames, raw = self._listen(400)
            entry = {"baud": baud, "frames": frames,
                     "raw": hexdump(raw), "cmd_ok": False}
            result["scan"].append(entry)
            if not frames:
                if verbose:
                    print("baud %d: no data, first bytes: %s"
                          % (baud, entry["raw"] or "-"))
                continue
            entry["cmd_ok"] = self._probe_command(tries=3)
            result["data_ok"] = True
            result["found_baud"] = baud
            result["ok"] = entry["cmd_ok"]
            self.baudrate = baud
            if verbose:
                print("baud %d: %d data frame(s), command %s, first bytes: %s"
                      % (baud, frames, "OK" if entry["cmd_ok"] else "no",
                         entry["raw"] or "-"))
            break

        if result["found_baud"] is None:
            try:
                self.uart.init(baudrate=result["start_baud"], bits=8,
                               parity=None, stop=1)
            except Exception:
                pass
            self.baudrate = result["start_baud"]
        return result

def compare_params(expected, actual):
    """Return a list of human readable differences (empty means equal)."""
    diff = []
    for key in ("max_moving_gate", "max_stationary_gate", "no_one_seconds"):
        if expected.get(key) is not None and expected.get(key) != actual.get(key):
            diff.append("%s: wanted %r, read %r"
                        % (key, expected[key], actual.get(key)))
    for key in ("motion_sens", "static_sens"):
        want = list(expected.get(key) or [])
        got = list(actual.get(key) or [])
        for gate in range(min(len(want), len(got))):
            if want[gate] != got[gate]:
                diff.append("%s[%d]: wanted %d, read %d"
                            % (key, gate, want[gate], got[gate]))
    return diff


def check_params(params):
    """Return a list of warnings for a parameter dictionary."""
    warnings = []
    if params.get("max_gate") not in (None, 8):
        warnings.append("max_gate is %r (the protocol allows gate 0-8)"
                        % (params.get("max_gate"),))
    for key in ("max_moving_gate", "max_stationary_gate"):
        value = params.get(key)
        if value is not None and not 1 <= value <= 8:
            warnings.append("%s=%r outside 1..8" % (key, value))
    idle = params.get("no_one_seconds")
    if idle is not None and not 0 <= idle <= 65535:
        warnings.append("no_one_seconds=%r outside 0..65535" % (idle,))
    for key in ("motion_sens", "static_sens"):
        for gate, value in enumerate(params.get(key) or []):
            if not 0 <= value <= 100:
                warnings.append("%s[%d]=%d outside 0..100"
                                % (key, gate, value))
    return warnings
