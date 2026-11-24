"""asyncio layer for the LD2410C driver.

`ld2410c.py` owns the protocol: framing, parsing, command encoding and the
blocking wait loops.  This module keeps that logic but replaces every wait
with an `await`, so UART latency never blocks the rest of an asyncio program.

Only the waiting parts are re-implemented; parsing and encoding are imported
from the core module so there is exactly one copy of the protocol.

    from hardware.ld2410c_aio import LD2410CAsync
    radar = LD2410CAsync(uart_id=1, tx=36, rx=38, out_pin=40)
    snap = await radar.read_async(1000)      # yields while waiting
    params = await radar.read_params_async()

Design: every wait polls the UART and then awaits `sleep_ms(2)`.  On
MicroPython that maps to `uasyncio.sleep_ms`; on CPython (tests) it falls
back to `asyncio.sleep`.
"""

try:
    import uasyncio as asyncio
except ImportError:  # CPython, used by the desktop tests
    import asyncio

try:
    from hardware.ld2410c import (
        CMD_ENGINEERING_OFF, CMD_ENGINEERING_ON, CMD_ENTER_CONFIG,
        CMD_EXIT_CONFIG, CMD_FIRMWARE, CMD_READ_PARAMS, CMD_READ_RESOLUTION,
        CMD_RESTART, CMD_SET_MAX_GATES, CMD_SET_SENSITIVITY,
        LD2410C, LD2410CCommandError, LD2410CError, LD2410CTimeout,
        _le16, _le32, _u16, _u32, compare_params, hexdump, ticks_add, ticks_diff, ticks_ms,
    )
except ImportError:  # flat deployment on the device
    from ld2410c import (
        CMD_ENGINEERING_OFF, CMD_ENGINEERING_ON, CMD_ENTER_CONFIG,
        CMD_EXIT_CONFIG, CMD_FIRMWARE, CMD_READ_PARAMS, CMD_READ_RESOLUTION,
        CMD_RESTART, CMD_SET_MAX_GATES, CMD_SET_SENSITIVITY,
        LD2410C, LD2410CCommandError, LD2410CError, LD2410CTimeout,
        _le16, _le32, _u16, _u32, compare_params, hexdump, ticks_add, ticks_diff, ticks_ms,
    )


async def sleep_ms_async(delay):
    """Sleep in milliseconds on MicroPython, seconds on CPython."""
    sleep_ms = getattr(asyncio, "sleep_ms", None)
    if sleep_ms is not None:
        await sleep_ms(delay)
    else:
        await asyncio.sleep(delay / 1000.0)


class LD2410CAsync(LD2410C):
    """Same protocol as LD2410C, with awaitable waits."""

    # --------------------------------------------------------------- data

    async def poll_async(self):
        """Non-blocking poll; returns a frame dict or None. Never awaits."""
        return self.poll()

    async def read_async(self, timeout_ms=None):
        """Wait for one data frame without blocking other tasks."""
        if timeout_ms is None:
            return self.poll()
        deadline = ticks_add(ticks_ms(), timeout_ms)
        while ticks_diff(deadline, ticks_ms()) > 0:
            frame = self.poll()
            if frame is not None:
                return frame
            await sleep_ms_async(2)
        raise LD2410CTimeout("no data frame within %d ms" % timeout_ms)

    # ------------------------------------------------------------ commands

    async def _wait_ack_async(self, command, timeout_ms):
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
            await sleep_ms_async(2)
        return None

    async def send_async(self, command, value=b"", timeout_ms=None, retries=1,
                         flush=True):
        """Awaitable version of send(). Same exceptions, same retries."""
        if self.uart is None:
            raise LD2410CError("UART is not configured")
        if timeout_ms is None:
            timeout_ms = self.timeout_ms
        for _attempt in range(retries):
            if flush:
                self.flush()
            self._send_frame(command, value)
            payload = await self._wait_ack_async(command, timeout_ms)
            if payload is not None:
                return payload
        raise LD2410CTimeout("command 0x%04X: no ACK" % command)

    async def enter_config_async(self, retries=6, delay_ms=40):
        last = None
        for _attempt in range(retries):
            try:
                await self.send_async(CMD_ENTER_CONFIG, b"\x01\x00", retries=1)
                await sleep_ms_async(20)
                return True
            except LD2410CError as error:
                last = error
                await sleep_ms_async(delay_ms)
        raise LD2410CTimeout("enter config mode failed (%s)" % (last,))

    async def exit_config_async(self, quiet=True):
        try:
            await self.send_async(CMD_EXIT_CONFIG, b"", timeout_ms=400, retries=1)
            return True
        except LD2410CError:
            if not quiet:
                raise
            return False

    async def _configured_async(self, operation):
        """Run an awaitable operation inside one enable/end config session."""
        await self.enter_config_async()
        try:
            return await operation()
        finally:
            await self.exit_config_async()

    # ---------------------------------------------------------- parameters

    async def read_params_async(self):
        payload = await self._configured_async(
            lambda: self.send_async(CMD_READ_PARAMS, b"", timeout_ms=1000))
        if len(payload) < 24 or payload[0] != 0xAA:
            raise LD2410CCommandError(
                "unexpected parameter answer: %s" % hexdump(payload))
        gates = payload[1]
        if gates > 8:
            raise LD2410CCommandError("gate count %d out of range" % gates)
        motion = list(payload[4:4 + gates + 1])
        static = list(payload[4 + gates + 1:4 + 2 * (gates + 1)])
        idle_at = 4 + 2 * (gates + 1)
        if len(payload) < idle_at + 2 or len(motion) != gates + 1:
            raise LD2410CCommandError("short parameter answer")
        params = {
            "max_gate": gates,
            "max_moving_gate": payload[2],
            "max_stationary_gate": payload[3],
            "motion_sens": motion,
            "static_sens": static,
            "no_one_seconds": _u16(payload, idle_at),
        }
        self.last_params = params
        return params

    async def write_params_async(self, params, verify=True):
        """Awaitable version of write_params(); still verifies by read-back."""
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

        async def write():
            await self.send_async(
                CMD_SET_MAX_GATES,
                _le16(0) + _le32(max_moving) +
                _le16(1) + _le32(max_static) +
                _le16(2) + _le32(idle), timeout_ms=1000)
            await sleep_ms_async(20)
            for gate in range(9):
                await self.send_async(
                    CMD_SET_SENSITIVITY,
                    _le16(0) + _le32(gate) +
                    _le16(1) + _le32(motion[gate]) +
                    _le16(2) + _le32(static[gate]), timeout_ms=1000)
                await sleep_ms_async(20)

        await self._configured_async(write)

        result = {"verified": None, "readback": None, "diff": []}
        if verify:
            back = await self.read_params_async()
            diff = compare_params(params, back)
            result["verified"] = not diff
            result["readback"] = back
            result["diff"] = diff
        return result

    async def firmware_version_async(self):
        payload = await self._configured_async(
            lambda: self.send_async(CMD_FIRMWARE, b"", timeout_ms=800))
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

    async def read_resolution_async(self):
        """Distance per gate: 0.75 m (factory) or 0.2 m."""
        payload = await self._configured_async(
            lambda: self.send_async(CMD_READ_RESOLUTION, b"", timeout_ms=800))
        if len(payload) < 2:
            raise LD2410CCommandError("short resolution answer")
        index = _u16(payload, 0)
        return {"index": index, "meters": 0.2 if index else 0.75}

    async def engineering_async(self, enabled=True):
        command = CMD_ENGINEERING_ON if enabled else CMD_ENGINEERING_OFF
        await self._configured_async(
            lambda: self.send_async(command, b"", timeout_ms=800))
        return bool(enabled)

    async def restart_async(self):
        ok = True
        try:
            await self._configured_async(
                lambda: self.send_async(CMD_RESTART, b"", timeout_ms=600))
        except LD2410CError:
            ok = False
        self.frame_ms = None
        self.frames = 0
        await sleep_ms_async(200)
        self.flush()
        return ok

