"""MicroPython driver for the Hi-Link LD2410/LD2410C radar sensor.

The driver uses a caller-driven UART model: call ``read()`` regularly from the
main loop, then read the cached properties or helper methods.  It depends only
on the standard MicroPython ``UART`` methods ``any()``, ``read()`` and
``write()``; pass an already-configured UART instance to ``LD2410``.
"""

try:
    import time
except ImportError:  # pragma: no cover - MicroPython always provides time.
    time = None

import struct


DATA_HEADER = b"\xf4\xf3\xf2\xf1"
DATA_FOOTER = b"\xf8\xf7\xf6\xf5"
COMMAND_HEADER = b"\xfd\xfc\xfb\xfa"
COMMAND_FOOTER = b"\x04\x03\x02\x01"


try:
    _ticks_ms = time.ticks_ms
    _ticks_diff = time.ticks_diff
    _sleep_ms = time.sleep_ms
except AttributeError:  # CPython fallback for host-side tests.
    import time as _host_time

    def _ticks_ms():
        return int(_host_time.monotonic() * 1000)

    def _ticks_diff(a, b):
        return a - b

    def _sleep_ms(value):
        _host_time.sleep(value / 1000.0)


class LD2410:
    """Control and read an LD2410 radar over a configured UART.

    Args:
        uart: MicroPython UART-like object.
        wait_for_radar: If true, query the firmware during construction.
        command_timeout_ms: Timeout for one command acknowledgement.
        max_frame_length: Maximum accepted protocol frame size.
        command_delay_ms: Delay between configuration commands, normally 50 ms.
    """

    def __init__(self, uart, wait_for_radar=False, command_timeout_ms=100,
                 max_frame_length=128, command_delay_ms=50):
        if max_frame_length < 10:
            raise ValueError("max_frame_length must be at least 10")
        self.uart = uart
        self.command_timeout_ms = command_timeout_ms
        self.max_frame_length = max_frame_length
        self.command_delay_ms = command_delay_ms
        self._debug_stream = None

        self._frame = bytearray(max_frame_length)
        self._frame_pos = 0
        self._frame_kind = None
        self._expected_total = 0
        self._last_frame = b""
        self._last_valid_frame_ms = None
        self._last_read_had_data = False

        self._target_type = 0
        self._moving_target_distance = 0
        self._moving_target_energy = 0
        self._stationary_target_distance = 0
        self._stationary_target_energy = 0
        self._detection_distance = 0
        self._engineering_motion_energy = [0] * 9
        self._engineering_stationary_energy = [0] * 9
        self._engineering_data_received = False

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
            self.begin(True)

    def begin(self, wait_for_radar=True):
        """Reset parser state and optionally verify the radar firmware."""
        self._reset_parser()
        if not wait_for_radar:
            return True

        deadline = _ticks_ms() + 1000
        while _ticks_diff(deadline, _ticks_ms()) > 0:
            if self.request_firmware_version():
                return True
        return False

    def debug(self, stream):
        """Send diagnostic text to a stream with a ``write()`` method."""
        self._debug_stream = stream

    def _log(self, text):
        if self._debug_stream is None:
            return
        try:
            self._debug_stream.write(text)
        except TypeError:
            self._debug_stream.write(text.encode())

    @property
    def target_type(self):
        return self._target_type

    def presence_detected(self):
        return self._target_type != 0

    def stationary_target_detected(self):
        return bool((self._target_type & 0x02) and
                    self._stationary_target_distance > 0 and
                    self._stationary_target_energy > 0)

    def stationary_target_distance(self):
        return self._stationary_target_distance

    def stationary_target_energy(self):
        return self._stationary_target_energy

    def moving_target_detected(self):
        return bool((self._target_type & 0x01) and
                    self._moving_target_distance > 0 and
                    self._moving_target_energy > 0)

    def moving_target_distance(self):
        return self._moving_target_distance

    def moving_target_energy(self):
        return min(self._moving_target_energy, 100)

    def detection_distance(self):
        return self._detection_distance

    def moving_energy_at_gate(self, gate):
        if not 0 <= gate < 9:
            return 0
        return self._engineering_motion_energy[gate]

    def stationary_energy_at_gate(self, gate):
        if not 0 <= gate < 9:
            return 0
        return self._engineering_stationary_energy[gate]

    def engineering_retrieved(self):
        return self._engineering_data_received

    def is_connected(self, timeout_ms=100):
        """Return true when a valid frame was received within ``timeout_ms``."""
        self.read()
        if self._last_valid_frame_ms is None:
            return False
        return _ticks_diff(_ticks_ms(), self._last_valid_frame_ms) < timeout_ms

    def is_auto_read_task_running(self):
        """MicroPython has no background task in this driver."""
        return False

    def read(self):
        """Drain and parse available UART data.

        Returns true when bytes were read or a complete valid frame was parsed.
        """
        had_data = False
        processed = False
        any_method = getattr(self.uart, "any", None)
        if any_method is None:
            data = self.uart.read()
            if data:
                had_data = True
                processed = self._consume(data) or processed
        else:
            available = any_method()
            while available:
                data = self.uart.read(available)
                if not data:
                    break
                had_data = True
                processed = self._consume(data) or processed
                available = any_method()
        self._last_read_had_data = had_data
        return had_data or processed

    def get_frame_data(self):
        """Return the most recently accepted data frame as immutable bytes."""
        return self._last_frame

    def _consume(self, data):
        processed = False
        for value in data:
            if self._consume_byte(value):
                processed = True
        return processed

    def _consume_byte(self, value):
        value &= 0xFF
        pos = self._frame_pos

        if pos == 0:
            if value == DATA_HEADER[0]:
                self._start_frame(False, value)
            elif value == COMMAND_HEADER[0]:
                self._start_frame(True, value)
            return False

        if pos < 4:
            header = COMMAND_HEADER if self._frame_kind else DATA_HEADER
            if value == header[pos]:
                self._frame[pos] = value
                self._frame_pos = pos + 1
            elif value == DATA_HEADER[0]:
                self._start_frame(False, value)
            elif value == COMMAND_HEADER[0]:
                self._start_frame(True, value)
            else:
                self._reset_parser()
            return False

        if pos >= self.max_frame_length:
            self._reset_parser()
            return False
        self._frame[pos] = value
        self._frame_pos = pos + 1

        if pos == 5:
            intra_length = self._frame[4] | (self._frame[5] << 8)
            total = intra_length + 10
            if intra_length == 0 or total > self.max_frame_length:
                self._reset_parser()
            else:
                self._expected_total = total
            return False

        if pos < 6:
            return False

        if self._frame_pos < self._expected_total:
            return False

        footer = COMMAND_FOOTER if self._frame_kind else DATA_FOOTER
        valid = bytes(self._frame[self._expected_total - 4:self._expected_total]) == footer
        parsed = False
        if valid:
            parsed = (self._parse_command_frame() if self._frame_kind
                      else self._parse_data_frame())
        self._reset_parser()
        return parsed

    def _start_frame(self, command, first_byte):
        self._reset_parser()
        self._frame_kind = command
        self._frame[0] = first_byte
        self._frame_pos = 1

    def _reset_parser(self):
        self._frame_pos = 0
        self._frame_kind = None
        self._expected_total = 0

    def _parse_data_frame(self):
        intra_length = self._frame[4] | (self._frame[5] << 8)
        if self._frame_pos != intra_length + 10 or intra_length < 13:
            return False
        if self._frame[6] not in (0x01, 0x02) or self._frame[7] != 0xAA:
            return False
        if self._frame[intra_length + 4] != 0x55 or self._frame[intra_length + 5] != 0x00:
            return False

        self._target_type = self._frame[8]
        self._moving_target_distance = self._u16(9)
        self._moving_target_energy = self._frame[11]
        self._stationary_target_distance = self._u16(12)
        self._stationary_target_energy = self._frame[14]
        self._detection_distance = self._u16(15)

        if self._frame[6] == 0x01 and intra_length >= 33:
            self._engineering_motion_energy[:] = self._frame[19:28]
            self._engineering_stationary_energy[:] = self._frame[28:37]
            self._engineering_data_received = True

        self._last_frame = bytes(self._frame[:self._frame_pos])
        self._last_valid_frame_ms = _ticks_ms()
        return True

    def _parse_command_frame(self):
        intra_length = self._frame[4] | (self._frame[5] << 8)
        if intra_length < 4 or self._frame_pos != intra_length + 10:
            return False
        opcode = self._frame[6]
        success = self._frame[8] == 0 and self._frame[9] == 0
        if not success:
            return False

        if opcode == 0x61 and intra_length >= 28:
            self.max_gate = self._frame[11]
            self.max_moving_gate = self._frame[12]
            self.max_stationary_gate = self._frame[13]
            self.motion_sensitivity[:] = self._frame[14:23]
            self.stationary_sensitivity[:] = self._frame[23:32]
            self.sensor_idle_time = self._u16(32)
        elif opcode == 0xA0 and intra_length >= 12:
            self.firmware_minor_version = self._frame[12]
            self.firmware_major_version = self._frame[13]
            self.firmware_bugfix_version = self._u32(14)

        self._last_valid_frame_ms = _ticks_ms()
        self._ack_opcode = opcode
        self._ack_success = True
        self._log("ACK 0x{:02x}\n".format(opcode))
        return True

    def _u16(self, offset):
        return self._frame[offset] | (self._frame[offset + 1] << 8)

    def _u32(self, offset):
        return (self._frame[offset] | (self._frame[offset + 1] << 8) |
                (self._frame[offset + 2] << 16) |
                (self._frame[offset + 3] << 24))

    def _flush_uart(self):
        any_method = getattr(self.uart, "any", None)
        if any_method is None:
            self.uart.read()
            return
        while any_method():
            count = any_method()
            if not self.uart.read(count):
                break

    def _begin_command(self, expected_opcode):
        self._ack_opcode = None
        self._ack_success = False
        self._reset_parser()
        self._flush_uart()
        self._expected_opcode = expected_opcode

    def _wait_for_ack(self, expected_opcode, timeout_ms=None):
        if timeout_ms is None:
            timeout_ms = self.command_timeout_ms
        deadline = _ticks_ms() + timeout_ms
        while _ticks_diff(deadline, _ticks_ms()) > 0:
            self.read()
            if self._ack_opcode == expected_opcode:
                return self._ack_success
            _sleep_ms(1)
        return False

    def _send_frame(self, opcode, payload=b""):
        body = struct.pack("<H", opcode) + payload
        self.uart.write(COMMAND_HEADER + struct.pack("<H", len(body)) + body + COMMAND_FOOTER)

    def _command(self, opcode, payload=b""):
        if not self._enter_configuration_mode():
            return False
        if self.command_delay_ms:
            _sleep_ms(self.command_delay_ms)
        self._begin_command(opcode)
        self._send_frame(opcode, payload)
        ok = self._wait_for_ack(opcode)
        if self.command_delay_ms:
            _sleep_ms(self.command_delay_ms)
        self._leave_configuration_mode()
        return ok

    def _enter_configuration_mode(self):
        self._begin_command(0xFF)
        self._send_frame(0xFF, b"\x01\x00")
        return self._wait_for_ack(0xFF)

    def _leave_configuration_mode(self):
        self._begin_command(0xFE)
        self._send_frame(0xFE)
        return self._wait_for_ack(0xFE)

    def request_start_engineering_mode(self):
        return self._command(0x62)

    def request_end_engineering_mode(self):
        return self._command(0x63)

    def request_current_configuration(self):
        return self._command(0x61)

    def request_firmware_version(self):
        return self._command(0xA0)

    def request_factory_reset(self):
        return self._command(0xA2)

    def request_restart(self):
        ok = self._command(0xA3)
        if not ok:
            return False
        self._flush_uart()
        _sleep_ms(800)
        self._flush_uart()
        self._reset_parser()
        return True

    def set_max_values(self, moving, stationary, inactivity_timer):
        payload = struct.pack("<HHIHHIHHI", 0, moving, 1, stationary,
                              2, inactivity_timer)
        return self._command(0x60, payload)

    def set_gate_sensitivity_threshold(self, gate, moving, stationary):
        payload = struct.pack("<HHIHHIHHI", 0, gate, 1, moving,
                              2, stationary)
        return self._command(0x64, payload)


# Arduino-style spellings retained as small migration aliases.
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
