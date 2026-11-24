"""MicroPython driver for the HLK-LD2410 radar family (LD2410 / LD2410B / LD2410C).

UART frames (all multi-byte integers are little-endian):

    data : F4 F3 F2 F1 | length(2) | payload             | F8 F7 F6 F5
    cmd  : FD FC FB FA | length(2) | command(2) + value  | 04 03 02 01
    ack  : FD FC FB FA | length(2) | cmd_lo, cmd_hi+1, status(2), [data] | 04 03 02 01

Normal frame payload (13 bytes):

    0 type(0x02) | 1 0xAA | 2 target_state | 3..4 moving_cm | 5 moving_energy
    6..7 stationary_cm | 8 stationary_energy | 9..10 detection_cm | 11 0x55 | 12 0x00

Engineering frame (type 0x01, 35 bytes) appends:

    11..12 max moving/stationary gate | 13..21 moving gate energy
    22..30 stationary gate energy     | 31 light level | 32 out level

Design rules:

- only machine.UART / machine.Pin / time are required;
- one object owns one UART, and commands must not overlap data reads;
- a communication timeout is reported as "unknown", never as "absent".
"""

import time

try:
    from machine import UART
except ImportError:  # desktop syntax checks and fake-UART tests
    UART = None

try:
    from machine import Pin
except ImportError:
    Pin = None


def _sleep_ms(delay):
    """MicroPython sleeps in milliseconds; CPython only has seconds."""
    sleep_ms = getattr(time, "sleep_ms", None)
    if sleep_ms is not None:
        sleep_ms(delay)
    else:
        time.sleep(delay / 1000.0)


class LD2410Error(OSError):
    """Base class for radar communication failures."""


class LD2410Timeout(LD2410Error):
    """No expected frame arrived before the deadline."""


class LD2410CommandError(LD2410Error):
    """The module answered, but reported a non-zero status."""


class LD2410:
    DATA_HEAD = b"\xf4\xf3\xf2\xf1"
    DATA_TAIL = b"\xf8\xf7\xf6\xf5"
    CMD_HEAD = b"\xfd\xfc\xfb\xfa"
    CMD_TAIL = b"\x04\x03\x02\x01"

    TARGET_STATES = {
        0x00: "none",
        0x01: "moving",
        0x02: "stationary",
        0x03: "moving_and_stationary",
        0x04: "noise_checking",
        0x05: "noise_check_ok",
        0x06: "noise_check_failed",
    }

    CMD_ENTER_CONFIG = 0x00FF
    CMD_EXIT_CONFIG = 0x00FE
    CMD_SET_MAX = 0x0060
    CMD_READ_CONFIG = 0x0061
    CMD_ENGINEERING_ON = 0x0062
    CMD_ENGINEERING_OFF = 0x0063
    CMD_FIRMWARE = 0x00A0
    CMD_RESTART = 0x00A3

    MAX_PAYLOAD = 128

    def __init__(self, uart_id=1, tx=None, rx=None, uart=None, baudrate=256000,
                 out_pin=None, out=None, out_active_high=True,
                 command_timeout_ms=1000, stale_after_ms=2000,
                 restart_flush_ms=800):
        if uart is not None:
            self.uart = uart
        else:
            if UART is None:
                raise RuntimeError("machine.UART is unavailable")
            kwargs = {"baudrate": baudrate, "bits": 8, "parity": None, "stop": 1}
            if tx is not None:
                kwargs["tx"] = tx
            if rx is not None:
                kwargs["rx"] = rx
            self.uart = UART(uart_id, **kwargs)

        if out is not None:
            self.out = out
        elif out_pin is not None:
            if Pin is None:
                raise RuntimeError("machine.Pin is unavailable")
            self.out = Pin(out_pin, Pin.IN)
        else:
            self.out = None

        self.out_active_high = bool(out_active_high)
        self.baudrate = baudrate
        self.command_timeout_ms = command_timeout_ms
        self.stale_after_ms = stale_after_ms
        self.restart_flush_ms = restart_flush_ms

        self._buffer = bytearray()
        self._latest = None
        self._latest_ms = None
        self._frames = 0
        self._errors = 0

    # ---------------------------------------------------------------- encoding

    @staticmethod
    def _le16(value):
        return bytes((value & 0xFF, (value >> 8) & 0xFF))

    @staticmethod
    def _le32(value):
        return bytes((value & 0xFF, (value >> 8) & 0xFF,
                      (value >> 16) & 0xFF, (value >> 24) & 0xFF))

    @staticmethod
    def _u16(data, offset):
        return data[offset] | (data[offset + 1] << 8)

    # ------------------------------------------------------------------ framing

    def _append_uart_data(self):
        chunk = self.uart.read()
        if chunk:
            self._buffer.extend(chunk)

    def _discard_input(self):
        """Drop buffered bytes so a stale ACK cannot satisfy a new command."""
        self._buffer = bytearray()
        while True:
            chunk = self.uart.read()
            if not chunk:
                break

    def _extract_frame(self):
        while len(self._buffer) >= 6:
            data_start = self._buffer.find(self.DATA_HEAD)
            command_start = self._buffer.find(self.CMD_HEAD)
            starts = [item for item in (data_start, command_start) if item >= 0]
            if not starts:
                # Keep the tail: it may be the beginning of a split header.
                self._buffer = self._buffer[-3:]
                return None

            start = min(starts)
            is_command = command_start >= 0 and command_start == start
            tail = self.CMD_TAIL if is_command else self.DATA_TAIL
            if start:
                self._buffer = self._buffer[start:]
            if len(self._buffer) < 6:
                return None

            payload_length = self._u16(self._buffer, 4)
            if payload_length < 4 or payload_length > self.MAX_PAYLOAD:
                self._buffer = self._buffer[1:]
                continue

            frame_length = 10 + payload_length
            if len(self._buffer) < frame_length:
                return None
            if bytes(self._buffer[frame_length - 4:frame_length]) != tail:
                self._buffer = self._buffer[1:]
                continue

            frame = bytes(self._buffer[:frame_length])
            self._buffer = self._buffer[frame_length:]
            return frame
        return None

    def _read_frame(self, timeout_ms):
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        while time.ticks_diff(deadline, time.ticks_ms()) >= 0:
            self._append_uart_data()
            frame = self._extract_frame()
            if frame is not None:
                return frame
            _sleep_ms(1)
        raise LD2410Timeout("LD2410 frame timeout")

    # ----------------------------------------------------------------- parsing

    @classmethod
    def _parse_data_frame(cls, frame):
        payload = frame[6:-4]
        if len(payload) < 13 or payload[1] != 0xAA or payload[-2:] != b"\x55\x00":
            return None

        result = {
            "frame_type": payload[0],
            "target_state_code": payload[2],
            "target_state": cls.TARGET_STATES.get(payload[2], "unknown"),
            "moving_distance_cm": cls._u16(payload, 3),
            "moving_energy": payload[5],
            "stationary_distance_cm": cls._u16(payload, 6),
            "stationary_energy": payload[8],
            "detection_distance_cm": cls._u16(payload, 9),
        }

        # Engineering mode appends gates, per-gate energy, light and OUT.
        if payload[0] == 0x01 and len(payload) >= 35:
            result["max_moving_gate"] = payload[11]
            result["max_stationary_gate"] = payload[12]
            result["moving_gate_energy"] = list(payload[13:22])
            result["stationary_gate_energy"] = list(payload[22:31])
            result["light_level"] = payload[31]
            result["out_level"] = payload[32]
        return result

    # --------------------------------------------------------------- data read

    def read(self, timeout_ms=1000):
        """Block until one data frame is parsed; raises LD2410Timeout."""
        while True:
            frame = self._read_frame(timeout_ms)
            parsed = self._parse_data_frame(frame)
            if parsed is not None:
                self._store(parsed)
                return parsed

    def poll(self):
        """Consume every complete frame already in the buffer.

        Returns the newest snapshot, or None when no frame was available.
        Call this from the main loop instead of blocking on read().
        """
        self._append_uart_data()
        newest = None
        while True:
            frame = self._extract_frame()
            if frame is None:
                break
            parsed = self._parse_data_frame(frame)
            if parsed is not None:
                newest = parsed
        if newest is None:
            return None
        self._store(newest)
        return self.snapshot()

    def _store(self, parsed):
        self._latest = parsed
        self._latest_ms = time.ticks_ms()
        self._frames += 1

    # ---------------------------------------------------------------- snapshot

    def snapshot(self):
        """Latest reading plus freshness and the OUT pin level.

        state:
            "ok"      - a frame arrived within stale_after_ms
            "unknown" - no usable frame yet, or the last one is stale
        """
        result = dict(self._latest) if self._latest is not None else {}
        if self._latest is None:
            age = None
        else:
            age = time.ticks_diff(time.ticks_ms(), self._latest_ms)
        result["age_ms"] = age
        if age is None or age > self.stale_after_ms:
            result["state"] = "unknown"
        else:
            result["state"] = "ok"
        result["out"] = self.out_level()
        return result

    # -------------------------------------------------------------------- OUT

    def out_level(self):
        """True/False for the OUT pin, or None when no OUT pin is configured."""
        if self.out is None:
            return None
        level = 1 if self.out.value() else 0
        if self.out_active_high:
            return level == 1
        return level == 0

    def presence(self):
        """Presence from OUT when available, otherwise from the last frame.

        Returns None when neither source can answer; None means unknown and
        must not be treated as "absent".
        """
        out = self.out_level()
        if out is not None:
            return out
        if self._latest is None:
            return None
        return self._latest.get("target_state") != "none"

    def stats(self):
        return {"frames": self._frames, "errors": self._errors,
                "buffered": len(self._buffer)}

    # ---------------------------------------------------------------- commands

    @classmethod
    def _command_frame(cls, command, value=b""):
        body = cls._le16(command) + value
        return cls.CMD_HEAD + cls._le16(len(body)) + body + cls.CMD_TAIL

    @staticmethod
    def _ack_command(command):
        return bytes((command & 0xFF, ((command >> 8) + 1) & 0xFF))

    def send_command(self, command, value=b"", timeout_ms=None):
        """Send one command and return the bytes that follow the ACK status."""
        if timeout_ms is None:
            timeout_ms = self.command_timeout_ms
        self._discard_input()
        self.uart.write(self._command_frame(command, value))

        expected = self._ack_command(command)
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        while time.ticks_diff(deadline, time.ticks_ms()) >= 0:
            remaining = time.ticks_diff(deadline, time.ticks_ms())
            try:
                frame = self._read_frame(remaining if remaining > 0 else 1)
            except LD2410Timeout:
                break
            payload = frame[6:-4]
            if len(payload) < 4:
                continue
            if payload[0] != expected[0] or payload[1] != expected[1]:
                continue
            status = self._u16(payload, 2)
            if status != 0:
                self._errors += 1
                raise LD2410CommandError("LD2410 command failed: 0x%04x" % status)
            return payload[4:]
        self._errors += 1
        raise LD2410Timeout("LD2410 ACK timeout: 0x%04x" % command)

    def enter_config(self):
        return self.send_command(self.CMD_ENTER_CONFIG, self._le16(0x0001))

    def exit_config(self):
        return self.send_command(self.CMD_EXIT_CONFIG)

    def _in_config(self, command, value=b""):
        self.enter_config()
        try:
            return self.send_command(command, value)
        finally:
            try:
                self.exit_config()
            except LD2410Error:
                pass

    def current_config(self):
        """Raw configuration payload (offset decoding is not claimed yet)."""
        return self._in_config(self.CMD_READ_CONFIG)

    def firmware_version(self):
        """Raw firmware payload; field offsets still need device confirmation."""
        return self._in_config(self.CMD_FIRMWARE)

    def set_max_distance_and_timeout(self, moving_gate, stationary_gate,
                                     no_target_seconds):
        value = (self._le16(0x0000) + self._le32(moving_gate) +
                 self._le16(0x0001) + self._le32(stationary_gate) +
                 self._le16(0x0002) + self._le32(no_target_seconds))
        return self._in_config(self.CMD_SET_MAX, value)

    def engineering_mode(self, enabled=True):
        command = self.CMD_ENGINEERING_ON if enabled else self.CMD_ENGINEERING_OFF
        return self._in_config(command)

    def restart(self):
        """Restart the module and discard the garbage it emits afterwards."""
        self.send_command(self.CMD_RESTART)
        deadline = time.ticks_add(time.ticks_ms(), self.restart_flush_ms)
        self._discard_input()
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            _sleep_ms(20)
            self._discard_input()
        self._latest = None
        self._latest_ms = None

    def deinit(self):
        close = getattr(self.uart, "deinit", None)
        if close is not None:
            close()
        self.uart = None
