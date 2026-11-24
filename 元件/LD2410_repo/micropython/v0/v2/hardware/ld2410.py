"""Unified MicroPython driver for the HLK-LD2410 radar family.

This version combines the caller-driven Arduino-compatible API with the
ESP32-oriented UART construction, snapshots, OUT pin support, typed command
errors, and blocking frame reads.
"""

import time

try:
    from machine import UART, Pin
except ImportError:  # Host-side tests and syntax checks.
    UART = None
    Pin = None


DATA_HEAD = b"\xf4\xf3\xf2\xf1"
DATA_TAIL = b"\xf8\xf7\xf6\xf5"
COMMAND_HEAD = b"\xfd\xfc\xfb\xfa"
COMMAND_TAIL = b"\x04\x03\x02\x01"


try:
    _ticks_ms = time.ticks_ms
    _ticks_add = time.ticks_add
    _ticks_diff = time.ticks_diff
except AttributeError:  # CPython test fallback.
    def _ticks_ms():
        return int(time.monotonic() * 1000)

    def _ticks_add(value, delta):
        return value + delta

    def _ticks_diff(first, second):
        return first - second


def _sleep_ms(delay):
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
    """The radar answered a command with a non-zero status."""


class LD2410:
    DATA_HEAD = DATA_HEAD
    DATA_TAIL = DATA_TAIL
    CMD_HEAD = COMMAND_HEAD
    CMD_TAIL = COMMAND_TAIL

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
    CMD_SET_SENSITIVITY = 0x0064
    CMD_FIRMWARE = 0x00A0
    CMD_FACTORY_RESET = 0x00A2
    CMD_RESTART = 0x00A3

    MAX_PAYLOAD = 128

    def __init__(self, uart=None, wait_for_radar=False, uart_id=1, tx=None,
                 rx=None, baudrate=256000, out_pin=None, out=None,
                 out_active_high=True, command_timeout_ms=1000,
                 stale_after_ms=2000, restart_flush_ms=800,
                 command_delay_ms=50):
        # Also accept the ESP32-style LD2410(1, tx=..., rx=...) form.
        if type(uart) is int:
            uart_id = uart
            uart = None

        if uart is None:
            if UART is None:
                raise RuntimeError("machine.UART is unavailable")
            kwargs = {"baudrate": baudrate, "bits": 8,
                      "parity": None, "stop": 1}
            if tx is not None:
                kwargs["tx"] = tx
            if rx is not None:
                kwargs["rx"] = rx
            uart = UART(uart_id, **kwargs)
        self.uart = uart

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
        self.command_delay_ms = command_delay_ms

        self._buffer = bytearray()
        self._latest = None
        self._latest_ms = None
        self._last_frame = b""
        self._frames = 0
        self._errors = 0
        self.last_error = None

        self.firmware_major_version = 0
        self.firmware_minor_version = 0
        self.firmware_bugfix_version = 0
        self.max_gate = 0
        self.max_moving_gate = 0
        self.max_stationary_gate = 0
        self.sensor_idle_time = 0
        self.motion_sensitivity = [0] * 9
        self.stationary_sensitivity = [0] * 9

        if wait_for_radar:
            self.begin()

    # ---------------------------------------------------------------- startup

    def begin(self, wait_for_radar=True):
        """Reset buffered input and optionally query the firmware."""
        self._buffer = bytearray()
        if not wait_for_radar:
            return True
        deadline = _ticks_add(_ticks_ms(), 1000)
        while _ticks_diff(deadline, _ticks_ms()) > 0:
            if self.request_firmware_version():
                return True
        return False

    def deinit(self):
        close = getattr(self.uart, "deinit", None)
        if close is not None:
            close()
        self.uart = None

    # ---------------------------------------------------------------- framing

    @staticmethod
    def _le16(value):
        value = int(value)
        if not 0 <= value <= 0xFFFF:
            raise ValueError("value is not an unsigned 16-bit integer")
        return bytes((value & 0xFF, value >> 8))

    @staticmethod
    def _le32(value):
        value = int(value)
        if not 0 <= value <= 0xFFFFFFFF:
            raise ValueError("value is not an unsigned 32-bit integer")
        return bytes((value & 0xFF, (value >> 8) & 0xFF,
                      (value >> 16) & 0xFF, value >> 24))

    @staticmethod
    def _u16(data, offset):
        return data[offset] | (data[offset + 1] << 8)

    @staticmethod
    def _u32(data, offset):
        return (data[offset] | (data[offset + 1] << 8) |
                (data[offset + 2] << 16) | (data[offset + 3] << 24))

    @classmethod
    def _command_frame(cls, command, value=b""):
        body = cls._le16(command) + value
        return cls.CMD_HEAD + cls._le16(len(body)) + body + cls.CMD_TAIL

    @staticmethod
    def _ack_command(command):
        return bytes((command & 0xFF, ((command >> 8) + 1) & 0xFF))

    def _read_uart_data(self):
        any_method = getattr(self.uart, "any", None)
        if any_method is None:
            return self.uart.read()
        count = any_method()
        if not count:
            return None
        return self.uart.read(count)

    def _append_uart_data(self):
        if self.uart is None:
            return False
        chunk = self._read_uart_data()
        if not chunk:
            return False
        self._buffer.extend(chunk)
        return True

    def _discard_input(self):
        self._buffer = bytearray()
        while True:
            chunk = self._read_uart_data()
            if not chunk:
                break

    def _extract_frame(self):
        while len(self._buffer) >= 6:
            data_start = self._buffer.find(DATA_HEAD)
            command_start = self._buffer.find(COMMAND_HEAD)
            starts = [start for start in (data_start, command_start) if start >= 0]
            if not starts:
                self._buffer = self._buffer[-3:]
                return None

            start = min(starts)
            is_command = command_start == start
            if start:
                self._buffer = self._buffer[start:]
            if len(self._buffer) < 6:
                return None

            payload_length = self._u16(self._buffer, 4)
            if payload_length < 4 or payload_length > self.MAX_PAYLOAD:
                self._buffer = self._buffer[1:]
                continue

            frame_length = payload_length + 10
            if len(self._buffer) < frame_length:
                return None
            tail = COMMAND_TAIL if is_command else DATA_TAIL
            if bytes(self._buffer[frame_length - 4:frame_length]) != tail:
                self._buffer = self._buffer[1:]
                continue

            frame = bytes(self._buffer[:frame_length])
            self._buffer = self._buffer[frame_length:]
            return frame
        return None

    def _read_frame(self, timeout_ms):
        deadline = _ticks_add(_ticks_ms(), timeout_ms)
        while _ticks_diff(deadline, _ticks_ms()) >= 0:
            self._append_uart_data()
            frame = self._extract_frame()
            if frame is not None:
                return frame
            _sleep_ms(1)
        raise LD2410Timeout("LD2410 frame timeout")

    # ---------------------------------------------------------------- parsing

    @classmethod
    def _parse_data_frame(cls, frame):
        payload = frame[6:-4]
        if len(payload) < 13 or payload[0] not in (0x01, 0x02):
            return None
        if payload[1] != 0xAA or payload[-2:] != b"\x55\x00":
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
            "moving_gate_energy": [],
            "stationary_gate_energy": [],
            "light_level": None,
            "out_level": None,
        }

        if payload[0] == 0x01 and len(payload) >= 35:
            result["max_moving_gate"] = payload[11]
            result["max_stationary_gate"] = payload[12]
            result["moving_gate_energy"] = list(payload[13:22])
            result["stationary_gate_energy"] = list(payload[22:31])
            result["light_level"] = payload[31]
            result["out_level"] = payload[32]
        return result

    def _store(self, parsed, frame):
        self._latest = parsed
        self._latest_ms = _ticks_ms()
        self._last_frame = frame
        self._frames += 1

    def poll(self):
        """Consume all complete data frames already available.

        Returns the newest snapshot, or ``None`` if no valid data frame exists.
        """
        self._append_uart_data()
        newest = None
        while True:
            frame = self._extract_frame()
            if frame is None:
                break
            if frame[:4] != DATA_HEAD:
                continue
            parsed = self._parse_data_frame(frame)
            if parsed is None:
                self._errors += 1
                continue
            self._store(parsed, frame)
            newest = parsed
        return self.snapshot() if newest is not None else None

    def read(self, timeout_ms=None):
        """Read data without blocking, or wait when ``timeout_ms`` is given.

        With no timeout this keeps the original driver contract and returns a
        boolean. With a timeout it returns a complete snapshot.
        """
        if timeout_ms is None:
            return self.poll() is not None
        return self.read_frame(timeout_ms)

    def read_frame(self, timeout_ms=1000):
        """Block until one valid data frame is parsed."""
        deadline = _ticks_add(_ticks_ms(), timeout_ms)
        while _ticks_diff(deadline, _ticks_ms()) >= 0:
            remaining = _ticks_diff(deadline, _ticks_ms())
            frame = self._read_frame(remaining if remaining > 0 else 1)
            if frame[:4] != DATA_HEAD:
                continue
            parsed = self._parse_data_frame(frame)
            if parsed is None:
                self._errors += 1
                continue
            self._store(parsed, frame)
            return self.snapshot()
        raise LD2410Timeout("LD2410 data frame timeout")

    # ---------------------------------------------------------------- snapshot

    def snapshot(self):
        result = dict(self._latest) if self._latest is not None else {}
        if self._latest_ms is None:
            age = None
        else:
            age = _ticks_diff(_ticks_ms(), self._latest_ms)
        result["age_ms"] = age
        result["state"] = "ok" if age is not None and age <= self.stale_after_ms else "unknown"
        result["out"] = self.out_level()
        return result

    def stats(self):
        return {"frames": self._frames, "errors": self._errors,
                "buffered": len(self._buffer)}

    def get_frame_data(self):
        return self._last_frame

    # --------------------------------------------------------------- readings

    def out_level(self):
        if self.out is None:
            return None
        level = 1 if self.out.value() else 0
        return bool(level) if self.out_active_high else not bool(level)

    def presence(self):
        out = self.out_level()
        if out is not None:
            return out
        if self._latest is None:
            return None
        return self._latest["target_state_code"] != 0

    def presence_detected(self):
        return self._latest is not None and self._latest["target_state_code"] != 0

    def stationary_target_detected(self):
        return bool(self._latest and
                    self._latest["target_state_code"] & 0x02 and
                    self.stationary_target_distance() > 0 and
                    self.stationary_target_energy() > 0)

    def stationary_target_distance(self):
        return self._latest["stationary_distance_cm"] if self._latest else 0

    def stationary_target_energy(self):
        return self._latest["stationary_energy"] if self._latest else 0

    def moving_target_detected(self):
        return bool(self._latest and
                    self._latest["target_state_code"] & 0x01 and
                    self.moving_target_distance() > 0 and
                    self.moving_target_energy() > 0)

    def moving_target_distance(self):
        return self._latest["moving_distance_cm"] if self._latest else 0

    def moving_target_energy(self):
        return min(self._latest["moving_energy"], 100) if self._latest else 0

    def detection_distance(self):
        return self._latest["detection_distance_cm"] if self._latest else 0

    def moving_energy_at_gate(self, gate):
        if not self._latest or not 0 <= gate < len(self._latest["moving_gate_energy"]):
            return 0
        return self._latest["moving_gate_energy"][gate]

    def stationary_energy_at_gate(self, gate):
        if not self._latest or not 0 <= gate < len(self._latest["stationary_gate_energy"]):
            return 0
        return self._latest["stationary_gate_energy"][gate]

    def engineering_retrieved(self):
        return bool(self._latest and self._latest["frame_type"] == 0x01)

    def is_connected(self, timeout_ms=100):
        self.poll()
        return self._latest_ms is not None and _ticks_diff(_ticks_ms(), self._latest_ms) < timeout_ms

    def is_auto_read_task_running(self):
        return False

    # ---------------------------------------------------------------- commands

    def send_command(self, command, value=b"", timeout_ms=None):
        """Send one command and return bytes after the ACK status.

        Raises ``LD2410Timeout`` when no matching ACK arrives and
        ``LD2410CommandError`` when the radar reports a failure status.
        """
        if timeout_ms is None:
            timeout_ms = self.command_timeout_ms
        self._discard_input()
        self.uart.write(self._command_frame(command, value))
        expected = self._ack_command(command)
        deadline = _ticks_add(_ticks_ms(), timeout_ms)

        while _ticks_diff(deadline, _ticks_ms()) >= 0:
            remaining = _ticks_diff(deadline, _ticks_ms())
            try:
                frame = self._read_frame(remaining if remaining > 0 else 1)
            except LD2410Timeout:
                break
            if frame[:4] != COMMAND_HEAD:
                continue
            payload = frame[6:-4]
            if len(payload) < 4 or payload[:2] != expected:
                continue
            status = self._u16(payload, 2)
            if status != 0:
                self._errors += 1
                raise LD2410CommandError("LD2410 command failed: 0x%04x" % status)
            return payload[4:]

        self._errors += 1
        raise LD2410Timeout("LD2410 ACK timeout: 0x%04x" % command)

    def enter_config(self):
        return self.send_command(self.CMD_ENTER_CONFIG, self._le16(1))

    def exit_config(self):
        return self.send_command(self.CMD_EXIT_CONFIG)

    def _in_config(self, command, value=b""):
        self.enter_config()
        try:
            if self.command_delay_ms:
                _sleep_ms(self.command_delay_ms)
            result = self.send_command(command, value)
        except Exception:
            try:
                self.exit_config()
            except LD2410Error:
                pass
            raise
        if self.command_delay_ms:
            _sleep_ms(self.command_delay_ms)
        self.exit_config()
        return result

    def read_firmware_version(self):
        payload = self._in_config(self.CMD_FIRMWARE)
        if len(payload) < 8:
            raise LD2410CommandError("short firmware response")
        self.firmware_minor_version = payload[2]
        self.firmware_major_version = payload[3]
        self.firmware_bugfix_version = self._u32(payload, 4)
        return {"major": self.firmware_major_version,
                "minor": self.firmware_minor_version,
                "bugfix": self.firmware_bugfix_version}

    def firmware_version(self):
        return self.read_firmware_version()

    def request_firmware_version(self):
        return self._safe(self.read_firmware_version)

    def read_current_configuration(self):
        payload = self._in_config(self.CMD_READ_CONFIG)
        if len(payload) < 24 or payload[0] != 0xAA:
            raise LD2410CommandError("invalid configuration response")
        self.max_gate = payload[1]
        self.max_moving_gate = payload[2]
        self.max_stationary_gate = payload[3]
        self.motion_sensitivity = list(payload[4:13])
        self.stationary_sensitivity = list(payload[13:22])
        self.sensor_idle_time = self._u16(payload, 22)
        return self.configuration()

    def current_config(self):
        return self.read_current_configuration()

    def configuration(self):
        return {
            "max_gate": self.max_gate,
            "max_moving_gate": self.max_moving_gate,
            "max_stationary_gate": self.max_stationary_gate,
            "motion_sensitivity": list(self.motion_sensitivity),
            "stationary_sensitivity": list(self.stationary_sensitivity),
            "sensor_idle_time": self.sensor_idle_time,
        }

    def request_current_configuration(self):
        return self._safe(self.read_current_configuration)

    def _safe(self, operation):
        try:
            operation()
            self.last_error = None
            return True
        except LD2410Error as error:
            self.last_error = error
            return False

    def set_max_values(self, moving, stationary, inactivity_timer):
        value = (self._le16(0) + self._le32(moving) +
                 self._le16(1) + self._le32(stationary) +
                 self._le16(2) + self._le32(inactivity_timer))
        return self._safe(lambda: self._in_config(self.CMD_SET_MAX, value))

    def set_gate_sensitivity_threshold(self, gate, moving, stationary):
        value = (self._le16(0) + self._le32(gate) +
                 self._le16(1) + self._le32(moving) +
                 self._le16(2) + self._le32(stationary))
        return self._safe(lambda: self._in_config(self.CMD_SET_SENSITIVITY, value))

    def request_start_engineering_mode(self):
        return self._safe(lambda: self._in_config(self.CMD_ENGINEERING_ON))

    def request_end_engineering_mode(self):
        return self._safe(lambda: self._in_config(self.CMD_ENGINEERING_OFF))

    def request_factory_reset(self):
        return self._safe(lambda: self._in_config(self.CMD_FACTORY_RESET))

    def request_restart(self):
        try:
            self.enter_config()
            if self.command_delay_ms:
                _sleep_ms(self.command_delay_ms)
            self.send_command(self.CMD_RESTART)
        except LD2410Error as error:
            self.last_error = error
            try:
                self.exit_config()
            except LD2410Error:
                pass
            return False

        try:
            self.exit_config()
        except LD2410Error:
            pass
        self._discard_input()
        deadline = _ticks_add(_ticks_ms(), self.restart_flush_ms)
        while _ticks_diff(deadline, _ticks_ms()) > 0:
            _sleep_ms(20)
            self._discard_input()
        self._latest = None
        self._latest_ms = None
        self.last_error = None
        return True


# Arduino-style migration aliases.
LD2410.presenceDetected = LD2410.presence_detected
LD2410.stationaryTargetDetected = LD2410.stationary_target_detected
LD2410.stationaryTargetDistance = LD2410.stationary_target_distance
LD2410.stationaryTargetEnergy = LD2410.stationary_target_energy
LD2410.movingTargetDetected = LD2410.moving_target_detected
LD2410.movingTargetDistance = LD2410.moving_target_distance
LD2410.movingTargetEnergy = LD2410.moving_target_energy
LD2410.detectionDistance = LD2410.detection_distance
LD2410.movingEnergyAtGate = LD2410.moving_energy_at_gate
LD2410.stationaryEnergyAtGate = LD2410.stationary_energy_at_gate
LD2410.engineeringRetrieved = LD2410.engineering_retrieved
LD2410.isConnected = LD2410.is_connected
LD2410.isAutoReadTaskRunning = LD2410.is_auto_read_task_running
LD2410.getFrameData = LD2410.get_frame_data
LD2410.requestStartEngineeringMode = LD2410.request_start_engineering_mode
LD2410.requestEndEngineeringMode = LD2410.request_end_engineering_mode
LD2410.requestCurrentConfiguration = LD2410.request_current_configuration
LD2410.requestFirmwareVersion = LD2410.request_firmware_version
LD2410.requestFactoryReset = LD2410.request_factory_reset
LD2410.requestRestart = LD2410.request_restart
LD2410.setMaxValues = LD2410.set_max_values
LD2410.setGateSensitivityThreshold = LD2410.set_gate_sensitivity_threshold
