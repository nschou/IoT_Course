"""Desktop fake-UART tests for the HLK-LD2410B basic functions.

These tests cover protocol framing and configuration values only. They do not
validate GPIO electrical levels, UART wiring, radar detection, or ESP32 timing.
"""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
from hardware import ld2410b as radar_module


class FakeTime:
    now_ms = 0

    @classmethod
    def ticks_ms(cls):
        return cls.now_ms

    @staticmethod
    def ticks_add(start, delta):
        return start + delta

    @classmethod
    def ticks_diff(cls, end, start):
        return end - start

    @classmethod
    def sleep_ms(cls, delay):
        cls.now_ms += delay


def data_frame(payload):
    return (radar_module.LD2410B.DATA_HEAD + len(payload).to_bytes(2, 'little') +
            payload + radar_module.LD2410B.DATA_TAIL)


def command_frame(payload):
    return (radar_module.LD2410B.CMD_HEAD + len(payload).to_bytes(2, 'little') +
            payload + radar_module.LD2410B.CMD_TAIL)


def normal_payload(target_state, moving_distance, moving_energy,
                   stationary_distance, stationary_energy,
                   detection_distance):
    return (
        bytes((0x02, 0xaa, target_state)) +
        moving_distance.to_bytes(2, 'little') + bytes((moving_energy,)) +
        stationary_distance.to_bytes(2, 'little') + bytes((stationary_energy,)) +
        detection_distance.to_bytes(2, 'little') + b'\x55\x00'
    )


class FakeUART:
    def __init__(self, chunks=(), config_payload=b'\x08\x00\x08\x00\x05\x00'):
        self.chunks = list(chunks)
        self.config_payload = config_payload
        self.writes = []

    def read(self):
        if self.chunks:
            return self.chunks.pop(0)
        return b''

    def write(self, frame):
        self.writes.append(frame)
        command = int.from_bytes(frame[6:8], 'little')
        response = bytes((command & 0xff, ((command >> 8) + 1) & 0xff))
        response += b'\x00\x00'
        if command == 0x0061:
            response += self.config_payload
        self.chunks.append(command_frame(response))
        return len(frame)


class UartFactory:
    def __init__(self):
        self.calls = []
        self.uart = FakeUART()

    def __call__(self, uart_id, **kwargs):
        self.calls.append((uart_id, kwargs))
        return self.uart


class LD2410BTests(unittest.TestCase):
    def test_config_declares_unused_uart_and_out_pins(self):
        names = (
            'LD2410B_TX_PIN', 'LD2410B_RX_PIN', 'LD2410B_OUT_PIN',
        )
        pins = [getattr(config, name) for name in names]
        existing = {
            config.LED_RED_PIN, config.LED_GREEN_PIN, config.LED_BLUE_PIN,
            config.BUTTON1_PIN, config.BUTTON2_PIN, config.DHT11_PIN,
            config.TEMT_ADC_PIN, config.PIR_PIN, config.SPEAKER_PIN,
            config.I2C_SCL_PIN, config.I2C_SDA_PIN,
            config.RFID_SCK_PIN, config.RFID_MOSI_PIN, config.RFID_MISO_PIN,
            config.RFID_RST_PIN, config.RFID_CS_PIN,
        }
        self.assertEqual(len(pins), len(set(pins)))
        self.assertTrue(set(pins).isdisjoint(existing))
        self.assertEqual(config.LD2410B_UART_ID, 1)
        self.assertEqual(config.LD2410B_BAUDRATE, 115200)

    def test_constructor_uses_configured_uart_parameters(self):
        factory = UartFactory()
        with patch.object(radar_module, 'UART', factory):
            radar_module.LD2410B(
                uart_id=config.LD2410B_UART_ID,
                tx=config.LD2410B_TX_PIN,
                rx=config.LD2410B_RX_PIN,
                baudrate=config.LD2410B_BAUDRATE,
            )
        self.assertEqual(factory.calls, [
            (1, {
                'baudrate': 115200,
                'bits': 8,
                'parity': None,
                'stop': 1,
                'tx': 15,
                'rx': 16,
            }),
        ])

    def test_read_normal_frame_handles_noise_and_fragmentation(self):
        frame = data_frame(normal_payload(0x03, 320, 77, 180, 42, 320))
        uart = FakeUART((b'\x00' + frame[:5], frame[5:13], frame[13:]))
        radar = radar_module.LD2410B(uart=uart)
        with patch.object(radar_module, 'time', FakeTime):
            result = radar.read(timeout_ms=20)
        self.assertEqual(result, {
            'frame_type': 0x02,
            'target_state_code': 0x03,
            'target_state': 'moving_and_stationary',
            'moving_distance_cm': 320,
            'moving_energy': 77,
            'stationary_distance_cm': 180,
            'stationary_energy': 42,
            'detection_distance_cm': 320,
        })

    def test_read_engineering_frame_exposes_gate_light_and_out_fields(self):
        payload = (
            bytes((0x01, 0xaa, 0x02)) +
            (250).to_bytes(2, 'little') + bytes((61,)) +
            (180).to_bytes(2, 'little') + bytes((49,)) +
            (250).to_bytes(2, 'little') + bytes((7, 8)) +
            bytes(range(1, 10)) + bytes(range(11, 20)) +
            bytes((23, 1)) + b'\x55\x00'
        )
        radar = radar_module.LD2410B(uart=FakeUART((data_frame(payload),)))
        with patch.object(radar_module, 'time', FakeTime):
            result = radar.read()
        self.assertEqual(result['target_state'], 'stationary')
        self.assertEqual(result['max_moving_gate'], 7)
        self.assertEqual(result['max_stationary_gate'], 8)
        self.assertEqual(result['moving_gate_energy'], list(range(1, 10)))
        self.assertEqual(result['stationary_gate_energy'], list(range(11, 20)))
        self.assertEqual(result['light_level'], 23)
        self.assertEqual(result['out_level'], 1)

    def test_read_config_runs_enter_read_exit_ack_sequence(self):
        uart = FakeUART()
        radar = radar_module.LD2410B(uart=uart)
        with patch.object(radar_module, 'time', FakeTime):
            result = radar.read_config()
        commands = [int.from_bytes(frame[6:8], 'little') for frame in uart.writes]
        self.assertEqual(commands, [0x00ff, 0x0061, 0x00fe])
        self.assertEqual(result, b'\x08\x00\x08\x00\x05\x00')
        self.assertEqual(uart.writes[0][8:-4], b'\x01\x00')
        self.assertEqual(uart.writes[1][8:-4], b'')
        self.assertEqual(uart.writes[2][8:-4], b'')

    def test_set_max_distance_and_timeout_encodes_official_parameters(self):
        uart = FakeUART()
        radar = radar_module.LD2410B(uart=uart)
        with patch.object(radar_module, 'time', FakeTime):
            radar.set_max_distance_and_timeout(
                moving_gate=8, stationary_gate=8, no_target_seconds=5)
        commands = [int.from_bytes(frame[6:8], 'little') for frame in uart.writes]
        self.assertEqual(commands, [0x00ff, 0x0060, 0x00fe])
        self.assertEqual(
            uart.writes[1][8:-4],
            b'\x00\x00\x08\x00\x00\x00'
            b'\x01\x00\x08\x00\x00\x00'
            b'\x02\x00\x05\x00\x00\x00',
        )


if __name__ == '__main__':
    unittest.main()
