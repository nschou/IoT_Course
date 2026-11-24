"""Async example: configuration as its own job, streaming as another.

The rule this demonstrates: judgments must not start before the module
configuration is known, and a configuration job must never interleave with
the streaming loop.  One asyncio.Lock guards the UART.

Run on the device:

    exec(open("examples/05_async.py").read())
    import uasyncio; uasyncio.run(main())
"""
try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

try:
    import config as _cfg
except ImportError:
    _cfg = None

try:
    from hardware.ld2410c_aio import LD2410CAsync
except ImportError:
    from ld2410c_aio import LD2410CAsync


def _setting(name, default):
    return getattr(_cfg, name, default) if _cfg is not None else default


class RadarSession:
    """Shared state between the setup job and the streaming job."""

    def __init__(self, radar):
        self.radar = radar
        self.lock = asyncio.Lock()
        self.ready = False
        self.firmware = None
        self.params = None
        self.frames = 0

    async def configure(self):
        """Independent job: read firmware and parameters before judging."""
        async with self.lock:
            self.firmware = await self.radar.firmware_version_async()
            self.params = await self.radar.read_params_async()
        self.ready = True
        print("firmware:", self.firmware["string"])
        print("max gates: moving %d stationary %d no-one %d s"
              % (self.params["max_moving_gate"],
                 self.params["max_stationary_gate"],
                 self.params["no_one_seconds"]))

    async def stream(self, seconds=None):
        """Streaming job: never runs a command, only reads frames."""
        if not self.ready:
            print("config not loaded yet; refusing to judge")
            return
        deadline = None
        if seconds is not None:
            deadline = asyncio.ticks_add(asyncio.ticks_ms(), seconds * 1000)
        while deadline is None or asyncio.ticks_diff(deadline, asyncio.ticks_ms()) > 0:
            frame = await self.radar.read_async(500)
            self.frames += 1
            print("state=%-22s mov=%3d cm stat=%3d cm out=%s"
                  % (frame["state_name"], frame["moving_cm"],
                     frame["stationary_cm"], self.radar.out_level()))


async def main():
    radar = LD2410CAsync(
        uart_id=_setting("LD2410B_UART_ID", 1),
        tx=_setting("LD2410B_TX_PIN", 15),
        rx=_setting("LD2410B_RX_PIN", 16),
        baudrate=_setting("LD2410B_BAUDRATE", 115200),
        out_pin=_setting("LD2410B_OUT_PIN", None),
    )
    session = RadarSession(radar)
    await session.configure()          # 先完成設定，再開始判斷
    await session.stream(seconds=20)
