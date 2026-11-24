"""Tests for the asyncio layer (hardware/ld2410c_aio.py).

PC ONLY: this file needs `unittest` and CPython asyncio, neither of which
exists on MicroPython.  The on-device async check is
`tests/esp32_ld2410_aio_smoke.py`.

Runs on CPython with plain asyncio; on the device the same class uses
uasyncio.  A fake UART supplies ACKs and data frames, so no hardware is used.
"""
import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hardware.ld2410c import (
    CMD_ENTER_CONFIG, CMD_EXIT_CONFIG, CMD_FIRMWARE, CMD_HEAD, CMD_READ_PARAMS,
    CMD_SET_MAX_GATES, CMD_SET_SENSITIVITY, CMD_TAIL, LD2410CCommandError,
    LD2410CTimeout,
)
from hardware.ld2410c_aio import LD2410CAsync


def _le16(value):
    return bytes((value & 0xFF, (value >> 8) & 0xFF))


def _u16(data, offset):
    return data[offset] | (data[offset + 1] << 8)


PARAMS = bytes([0xAA, 8, 8, 8] + [20] * 9 + [25] * 9 + [5, 0])
FIRMWARE = bytes([0x01, 0x00, 0x07, 0x01, 0x16, 0x15, 0x09, 0x22])


def data_frame(moving=95, stationary=83, state=0x03):
    payload = (bytes((0x02, 0xAA, state)) + _le16(moving) + bytes((100,)) +
               _le16(stationary) + bytes((100,)) + _le16(moving) +
               b"\x55\x00")
    return (b"\xf4\xf3\xf2\xf1" + _le16(len(payload)) + payload +
            b"\xf8\xf7\xf6\xf5")


class FakeUART:
    """answers commands with ACKs; data frames are injected by the test"""

    def __init__(self, params=PARAMS, firmware=FIRMWARE, ignore_first=0,
                 fail_status=False):
        self.rx = bytearray()
        self.writes = []
        self.commands = []
        self.params = params
        self.firmware = firmware
        self.ignore_first = ignore_first
        self.fail_status = fail_status

    def any(self):
        return len(self.rx)

    def read(self, count=None):
        if count is None:
            count = len(self.rx)
        count = min(count, len(self.rx))
        out = bytes(self.rx[:count])
        del self.rx[:count]
        return out

    def write(self, data):
        data = bytes(data)
        self.writes.append(data)
        command = _u16(data, 6)
        self.commands.append(command)
        if self.ignore_first > 0:
            self.ignore_first -= 1
            return len(data)
        if self.fail_status:
            self._ack(command, b"\x01\x00")
        elif command == CMD_READ_PARAMS:
            self._ack(command, b"\x00\x00" + self.params)
        elif command == CMD_FIRMWARE:
            self._ack(command, b"\x00\x00" + self.firmware)
        else:
            self._ack(command, b"\x00\x00")
        return len(data)

    def _ack(self, command, status_and_data):
        body = bytes((command & 0xFF, ((command >> 8) + 1) & 0xFF))
        body += status_and_data
        self.rx.extend(CMD_HEAD + _le16(len(body)) + body + CMD_TAIL)

    def inject(self, raw):
        self.rx.extend(raw)


class AsyncDriverTests(unittest.IsolatedAsyncioTestCase):
    def make(self, **kwargs):
        uart = FakeUART(**kwargs)
        return uart, LD2410CAsync(uart=uart, timeout_ms=40)

    async def test_read_async_returns_frame(self):
        uart, radar = self.make()
        uart.inject(data_frame())
        frame = await radar.read_async(100)
        self.assertEqual(frame["moving_cm"], 95)
        self.assertEqual(frame["state"], 0x03)

    async def test_read_async_timeout(self):
        _uart, radar = self.make()
        with self.assertRaises(LD2410CTimeout):
            await radar.read_async(30)

    async def test_read_async_does_not_block_other_tasks(self):
        uart, radar = self.make()
        ticks = [0]

        async def ticker():
            while True:
                ticks[0] += 1
                await asyncio.sleep(0)

        task = asyncio.ensure_future(ticker())
        try:
            await radar.read_async(60)
        except LD2410CTimeout:
            pass
        finally:
            task.cancel()
        self.assertGreater(ticks[0], 0, "await 期間其他任務必須能執行")

    async def test_send_async_returns_payload(self):
        uart, radar = self.make()
        payload = await radar.send_async(CMD_READ_PARAMS, timeout_ms=100)
        self.assertEqual(payload, PARAMS)
        self.assertEqual(uart.commands, [CMD_READ_PARAMS])

    async def test_send_async_status_error(self):
        uart, radar = self.make(fail_status=True)
        with self.assertRaises(LD2410CCommandError):
            await radar.send_async(CMD_ENTER_CONFIG, b"\x01\x00", timeout_ms=100)

    async def test_send_async_retries(self):
        uart, radar = self.make(ignore_first=1)
        payload = await radar.send_async(CMD_READ_PARAMS, timeout_ms=40, retries=2)
        self.assertEqual(payload, PARAMS)
        self.assertEqual(len(uart.commands), 2)

    async def test_enter_config_retries_until_ack(self):
        uart, radar = self.make(ignore_first=1)
        self.assertTrue(await radar.enter_config_async(retries=3, delay_ms=1))

    async def test_read_params_async_parses_gates(self):
        _uart, radar = self.make()
        params = await radar.read_params_async()
        self.assertEqual(params["max_gate"], 8)
        self.assertEqual(params["max_moving_gate"], 8)
        self.assertEqual(params["max_stationary_gate"], 8)
        self.assertEqual(params["motion_sens"], [20] * 9)
        self.assertEqual(params["static_sens"], [25] * 9)
        self.assertEqual(params["no_one_seconds"], 5)

    async def test_write_params_async_verifies(self):
        uart, radar = self.make()
        params = {"max_moving_gate": 6, "max_stationary_gate": 6,
                  "no_one_seconds": 10,
                  "motion_sens": [40] * 9, "static_sens": [30] * 9}
        # 讓回讀拿到我們剛寫的值
        uart.params = bytes([0xAA, 8, 6, 6] + [40] * 9 + [30] * 9 + [10, 0])
        result = await radar.write_params_async(params, verify=True)
        self.assertTrue(result["verified"])
        self.assertEqual(uart.commands.count(CMD_SET_SENSITIVITY), 9)
        self.assertIn(CMD_SET_MAX_GATES, uart.commands)

    async def test_firmware_version_async(self):
        _uart, radar = self.make()
        info = await radar.firmware_version_async()
        self.assertEqual(info["string"], "V1.07.22091516")

    async def test_command_sends_exit_config_after_error(self):
        uart, radar = self.make()
        await radar.read_params_async()
        self.assertEqual(uart.commands[0], CMD_ENTER_CONFIG)
        self.assertEqual(uart.commands[-1], CMD_EXIT_CONFIG)


if __name__ == "__main__":
    unittest.main()
