"""Desktop fake GPIO checks for exclusive LED alert ownership."""
import ast
import asyncio
import importlib.util
import json
import sys
import types
import unittest
from unittest.mock import patch
from test_led_control import ROOT, FakePin, StopCycle
import config


def task(name, **namespace):
    tree = ast.parse((ROOT / 'tasks.py').read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
    namespace['config'] = config
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'tasks.py', 'exec'), namespace)
    return namespace[name]


class LightAlertTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        with patch.dict(sys.modules, {'machine': types.SimpleNamespace(Pin=FakePin)}):
            spec = importlib.util.spec_from_file_location('alert_led_test', ROOT / 'hardware/led.py')
            self.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.module)
        self.led = self.module.RgbLed()

    def output(self):
        return (self.led.red.value() << 2) | (self.led.green.value() << 1) | self.led.blue.value()

    async def test_five_cycles_reject_all_normal_writes_and_restore(self):
        self.led.set_color_by_index(3)
        self.led.begin_alert()
        frames, waits = [], []
        class Event:
            calls = 0
            async def wait(self):
                self.calls += 1
                if self.calls == 2:
                    raise StopCycle()
            def clear(self):
                pass
        async def sleep(ms):
            frames.append(self.output())
            waits.append(ms)
            for operation in [self.led.next_color, lambda: self.led.set_color_by_index(2),
                              self.led.off, self.led.toggle]:
                with self.assertRaises(self.module.LedBusyError):
                    operation()
            self.assertEqual(self.led.current_color_index, 3)
            await asyncio.sleep(0)
        run = task('light_alert_task', uasyncio=types.SimpleNamespace(sleep_ms=sleep))
        with self.assertRaises(StopCycle):
            await run(self.led, Event())
        self.assertEqual(frames, [4, 0] * 5)
        self.assertEqual(waits, [300] * 10)
        self.assertFalse(self.led.alert_active)
        self.assertEqual(self.output(), 3)
        self.assertEqual(self.led.next_color(), 4)

    async def test_cancel_restores_but_shutdown_prevents_late_restore(self):
        for shutdown in [False, True]:
            led = self.module.RgbLed()
            led.set_color_by_index(6)
            led.begin_alert()
            reached = asyncio.Event()
            async def sleep(_):
                reached.set()
                await asyncio.Event().wait()
            event = asyncio.Event()
            event.set()
            run = task('light_alert_task', uasyncio=types.SimpleNamespace(sleep_ms=sleep))
            running = asyncio.create_task(run(led, event))
            await asyncio.wait_for(reached.wait(), 1)
            if shutdown:
                led.shutdown()
            running.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await running
            output = (led.red.value() << 2) | (led.green.value() << 1) | led.blue.value()
            self.assertEqual(output, 0 if shutdown else 6)
            self.assertFalse(led.alert_active)

    async def test_hysteresis_no_queue_and_startup_dark(self):
        readings = iter([999, 500, 1099, 1100, 1000, 999, 1100, 500, 500, 1100, 999])
        snapshots = []
        self.led.set_color_by_index(1)
        event = asyncio.Event()
        async def sleep(_):
            snapshots.append(event.is_set())
            event.clear()
            # Keep second alert active across a bright/dark excursion.
            if len(snapshots) in [1, 8, 11]:
                self.led.end_alert(self.led.alert_token)
            if len(snapshots) == 11:
                raise StopCycle()
        run = task('light_sensor_task', uasyncio=types.SimpleNamespace(sleep_ms=sleep))
        with self.assertRaises(StopCycle):
            await run(types.SimpleNamespace(read=lambda: next(readings)), self.led, event)
        self.assertEqual([i+1 for i, value in enumerate(snapshots) if value], [1, 6, 11])
        self.assertEqual(self.output(), 1)

    async def test_physical_button_rejected_press_consumed_before_next_press(self):
        self.led.set_color_by_index(1)
        seen = []
        led = self.led
        class Button:
            press_rejected = False
            count = 0
            async def wait_press(self, reject_if=None):
                self.count += 1
                if self.count == 1:
                    token = led.begin_alert()
                    self.press_rejected = reject_if()
                    led.end_alert(token)  # Alert finishes during debounce.
                else:
                    self.press_rejected = False
            async def wait_release(self):
                seen.append(led.current_color_index)
                if self.count == 2:
                    raise StopCycle()
        async def sleep(_):
            pass
        run = task('button1_task', LedBusyError=self.module.LedBusyError,
                   uasyncio=types.SimpleNamespace(sleep_ms=sleep, sleep=sleep))
        with self.assertRaises(StopCycle):
            await run(Button(), led, asyncio.Event())
        self.assertEqual(seen, [1, 2])

    async def test_api_409_is_authoritative_and_succeeds_after_restore(self):
        sys.path.insert(0, str(ROOT / 'lib'))
        try:
            with patch.dict(sys.modules, {'hardware.led': self.module,
                    'network': types.ModuleType('network'), 'uasyncio': asyncio}):
                spec = importlib.util.spec_from_file_location('alert_web_test', ROOT / 'web_server.py')
                web = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(web)
            web.rgb_led = self.led
            self.led.set_color_by_index(1)
            token = self.led.begin_alert()
            response = await web.api_led_toggle(None)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(self.led.current_color_index, 1)
            data = json.loads((await web.api_data(None)).body)
            self.assertTrue(data['led']['alert_active'])
            self.led.end_alert(token)
            self.assertEqual((await web.api_led_toggle(None)).status_code, 200)
            self.assertEqual(self.led.current_color_index, 2)
        finally:
            sys.path.remove(str(ROOT / 'lib'))

    async def test_actual_button_debounce_remembers_busy_even_after_warning_ends(self):
        class Pin(FakePin):
            IN, PULL_UP = 0, 1
            def __init__(self, *args):
                self.level = 0
        busy = True
        async def sleep(_):
            nonlocal busy
            busy = False  # Ends during debounce, not a new button press.
        with patch.dict(sys.modules, {'machine': types.SimpleNamespace(Pin=Pin),
                'uasyncio': types.SimpleNamespace(sleep_ms=sleep)}):
            spec = importlib.util.spec_from_file_location('alert_button_test', ROOT / 'hardware/button.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        button = module.Button(17)
        await button.wait_press(reject_if=lambda: busy)
        self.assertTrue(button.press_rejected)
        button.pin.value(1)
        await button.wait_release()
        button.pin.value(0)
        await button.wait_press(reject_if=lambda: busy)
        self.assertFalse(button.press_rejected)
