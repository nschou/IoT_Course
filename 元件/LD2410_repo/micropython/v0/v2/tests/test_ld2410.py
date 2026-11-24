"""MicroPython-compatible host tests for the v2 LD2410 driver.

Run on a board with:
    import test_ld2410
    test_ld2410.run_all()

The file intentionally does not use CPython's unittest module.
"""

from hardware.ld2410 import (COMMAND_HEAD, COMMAND_TAIL, DATA_HEAD,
                             DATA_TAIL, LD2410, LD2410CommandError)


class FakeUART:
    def __init__(self, auto_ack=True):
        self.rx = bytearray()
        self.writes = []
        self.auto_ack = auto_ack

    def any(self):
        return len(self.rx)

    def read(self, count=None):
        if count is None:
            count = len(self.rx)
        count = min(count, len(self.rx))
        result = bytes(self.rx[:count])
        self.rx = self.rx[count:]
        return result

    def write(self, data):
        data = bytes(data)
        self.writes.append(data)
        if self.auto_ack:
            self._ack(data[6] | (data[7] << 8))
        return len(data)

    def inject(self, data):
        self.rx.extend(data)

    def _ack(self, command):
        if command == 0xA0:
            body = bytes([0xA0, 0x01, 0, 0, 1, 0, 7, 1,
                          0x16, 0x15, 0x09, 0x22])
        elif command == 0x61:
            body = bytes([0x61, 0x01, 0, 0, 0xAA, 8, 8, 8] +
                         [20] * 9 + [25] * 9 + [5, 0])
        else:
            body = bytes([command & 0xFF, 0x01, 0, 0])
        self.inject(COMMAND_HEAD + _le16(len(body)) + body + COMMAND_TAIL)


def _le16(value):
    return bytes((value & 0xFF, (value >> 8) & 0xFF))


def basic_frame():
    payload = bytes([0x02, 0xAA, 0x02, 0x51, 0, 0, 0, 0, 0x3B,
                     0, 0, 0x55, 0])
    return DATA_HEAD + _le16(len(payload)) + payload + DATA_TAIL


def engineering_frame():
    payload = bytes([0x01, 0xAA, 0x03, 0x1E, 0, 0x3C, 0, 0, 0x39,
                     0, 0, 8, 8,
                     0x3C, 0x22, 5, 3, 3, 4, 3, 6, 5,
                     0, 0, 0x39, 0x10, 0x13, 6, 6, 8, 4,
                     3, 5, 0x55, 0])
    return DATA_HEAD + _le16(len(payload)) + payload + DATA_TAIL


def test_poll_and_snapshot():
    uart = FakeUART()
    radar = LD2410(uart)
    uart.inject(b"\x00\x7f" + basic_frame() + engineering_frame())

    snapshot = radar.poll()
    assert snapshot["moving_distance_cm"] == 30
    assert snapshot["moving_gate_energy"] == [60, 34, 5, 3, 3, 4, 3, 6, 5]
    assert snapshot["stationary_gate_energy"] == [0, 0, 57, 16, 19, 6, 6, 8, 4]
    assert snapshot["light_level"] == 3
    assert snapshot["out_level"] == 5
    assert radar.engineering_retrieved()


def test_blocking_read_and_original_getters():
    uart = FakeUART()
    radar = LD2410(uart)
    uart.inject(basic_frame())

    result = radar.read_frame(100)
    assert result["moving_distance_cm"] == 81
    assert radar.movingTargetDistance() == 81
    assert radar.stationaryTargetEnergy() == 59


def test_commands_decode_firmware_and_configuration():
    uart = FakeUART()
    radar = LD2410(uart, command_timeout_ms=100, command_delay_ms=0)

    assert radar.request_firmware_version()
    assert (radar.firmware_major_version, radar.firmware_minor_version,
            radar.firmware_bugfix_version) == (1, 7, 0x22091516)
    assert radar.request_current_configuration()
    assert radar.motion_sensitivity == [20] * 9
    assert radar.stationary_sensitivity == [25] * 9
    assert radar.sensor_idle_time == 5
    assert len(uart.writes) == 6


def test_command_error_is_available_at_low_level():
    class FailedUART(FakeUART):
        def _ack(self, command):
            body = bytes([command & 0xFF, 0x01, 1, 0])
            self.inject(COMMAND_HEAD + _le16(len(body)) + body + COMMAND_TAIL)

    radar = LD2410(FailedUART(), command_timeout_ms=20,
                   command_delay_ms=0)
    try:
        radar.send_command(0xFF, b"\x01\x00")
    except LD2410CommandError:
        return
    raise AssertionError("expected LD2410CommandError")


def run_all():
    tests = (test_poll_and_snapshot,
             test_blocking_read_and_original_getters,
             test_commands_decode_firmware_and_configuration,
             test_command_error_is_available_at_low_level)
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("All v2 LD2410 tests passed")


if __name__ == "__main__":
    run_all()
