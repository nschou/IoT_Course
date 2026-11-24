import unittest

from hardware.ld2410 import (COMMAND_FOOTER, COMMAND_HEADER, DATA_FOOTER,
                              DATA_HEADER, LD2410)


class FakeUART:
    def __init__(self):
        self.rx = bytearray()
        self.writes = []

    def any(self):
        return len(self.rx)

    def read(self, count=None):
        if count is None:
            count = len(self.rx)
        count = min(count, len(self.rx))
        result = bytes(self.rx[:count])
        del self.rx[:count]
        return result

    def write(self, data):
        data = bytes(data)
        self.writes.append(data)
        opcode = data[6]
        if opcode == 0xFF:
            self.inject_ack(opcode, b"\x00\x00\x01\x00\x40\x00")
        elif opcode == 0xA0:
            self.inject_ack(opcode, b"\x00\x00\x01\x00\x07\x01\x16\x15\x09\x22")
        elif opcode == 0x61:
            self.inject_ack(opcode, bytes(
                [0x00, 0x00, 0xAA, 8, 8, 8] +
                [20] * 9 + [25] * 9 + [5, 0]))
        else:
            self.inject_ack(opcode)
        return len(data)

    def inject(self, data):
        self.rx.extend(data)

    def inject_ack(self, opcode, payload=b"\x00\x00"):
        body = bytes((opcode, 0x01)) + payload
        self.inject(COMMAND_HEADER + len(body).to_bytes(2, "little") +
                    body + COMMAND_FOOTER)


def basic_frame():
    return (DATA_HEADER + b"\x0d\x00" +
            bytes([0x02, 0xAA, 0x02, 0x51, 0x00, 0x00, 0x00, 0x00, 0x3B,
                   0x00, 0x00, 0x55, 0x00]) + DATA_FOOTER)


def engineering_frame():
    return (DATA_HEADER + b"\x23\x00" +
            bytes([0x01, 0xAA, 0x03, 0x1E, 0x00, 0x3C, 0x00, 0x00, 0x39,
                   0x00, 0x00, 0x08, 0x08,
                   0x3C, 0x22, 0x05, 0x03, 0x03, 0x04, 0x03, 0x06, 0x05,
                   0x00, 0x00, 0x39, 0x10, 0x13, 0x06, 0x06, 0x08, 0x04,
                   0x03, 0x05, 0x55, 0x00]) + DATA_FOOTER)


class LD2410Tests(unittest.TestCase):
    def test_constructor_is_nonblocking(self):
        uart = FakeUART()
        LD2410(uart)
        self.assertEqual(uart.writes, [])

    def test_basic_and_engineering_frames(self):
        uart = FakeUART()
        radar = LD2410(uart, wait_for_radar=False)
        uart.inject(b"\x00\x7f" + basic_frame() + engineering_frame())

        self.assertTrue(radar.read())
        self.assertEqual(radar.moving_target_distance(), 30)
        self.assertEqual(radar.moving_target_energy(), 60)
        self.assertEqual(radar.stationary_target_energy(), 57)
        self.assertEqual(radar.detection_distance(), 0)
        self.assertEqual([radar.moving_energy_at_gate(i) for i in range(9)],
                         [60, 34, 5, 3, 3, 4, 3, 6, 5])
        self.assertEqual([radar.stationary_energy_at_gate(i) for i in range(9)],
                         [0, 0, 57, 16, 19, 6, 6, 8, 4])
        self.assertTrue(radar.engineering_retrieved())
        self.assertEqual(radar.get_frame_data(), engineering_frame())

    def test_bad_frame_does_not_update_state(self):
        uart = FakeUART()
        radar = LD2410(uart, wait_for_radar=False)
        bad = bytearray(basic_frame())
        bad[-1] = 0
        uart.inject(bad + basic_frame())

        radar.read()
        self.assertEqual(radar.moving_target_distance(), 81)

    def test_firmware_and_configuration_commands(self):
        uart = FakeUART()
        radar = LD2410(uart, wait_for_radar=False, command_delay_ms=0)

        self.assertTrue(radar.request_firmware_version())
        self.assertEqual((radar.firmware_major_version,
                          radar.firmware_minor_version,
                          radar.firmware_bugfix_version),
                         (1, 7, 0x22091516))

        self.assertTrue(radar.request_current_configuration())
        self.assertEqual(radar.max_gate, 8)
        self.assertEqual(radar.motion_sensitivity, [20] * 9)
        self.assertEqual(radar.stationary_sensitivity, [25] * 9)
        self.assertEqual(radar.sensor_idle_time, 5)
        self.assertEqual(len(uart.writes), 6)  # enter, command, leave twice


if __name__ == "__main__":
    unittest.main()
