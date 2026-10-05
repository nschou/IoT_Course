"""Desktop regression tests with fake GPIO; no ESP32 required."""
import ast
import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config


class FakePin:
    OUT = 1

    def __init__(self, number, mode):
        self.level = 0

    def value(self, level=None):
        if level is not None:
            self.level = level
        return self.level


class StopCycle(BaseException):
    pass


async def stop_after_cycle(_):
    raise StopCycle()


class LedControlTests(unittest.TestCase):
    def setUp(self):
        machine = types.ModuleType('machine')
        machine.Pin = FakePin
        original = sys.modules.get('machine')
        sys.modules['machine'] = machine
        try:
            spec = importlib.util.spec_from_file_location('led_test', ROOT / 'hardware/led.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.led = module.RgbLed()
        finally:
            if original is None:
                del sys.modules['machine']
            else:
                sys.modules['machine'] = original
        self.original_auto = config.LIGHT_AUTO_CONTROL_ENABLED

    def tearDown(self):
        config.LIGHT_AUTO_CONTROL_ENABLED = self.original_auto

    def output(self):
        return (self.led.red.value() << 2) | (self.led.green.value() << 1) | self.led.blue.value()

    def poll_light(self, brightness):
        tree = ast.parse((ROOT / 'tasks.py').read_text(encoding='utf-8'))
        task = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                    and node.name == 'light_sensor_task')
        namespace = {'config': config, 'uasyncio': types.SimpleNamespace(sleep_ms=stop_after_cycle)}
        exec(compile(ast.Module(body=[task], type_ignores=[]), 'tasks.py', 'exec'), namespace)
        sensor = types.SimpleNamespace(read=lambda: brightness)
        with self.assertRaises(StopCycle):
            asyncio.run(namespace['light_sensor_task'](sensor, self.led))

    def test_button_colors_survive_light_polling_and_wrap(self):
        self.assertFalse(config.LIGHT_AUTO_CONTROL_ENABLED)
        for expected in [1, 2, 3, 4, 5, 6, 7, 0, 1]:
            self.assertEqual(self.led.next_color(), expected)
            for brightness in [2000, 500, 1050]:
                self.poll_light(brightness)
                self.assertEqual(self.led.current_color_index, expected)
                self.assertEqual(self.output(), expected)

    def test_auto_off_preserves_color_and_dark_restores_it(self):
        config.LIGHT_AUTO_CONTROL_ENABLED = True
        self.led.set_color_by_index(4)
        self.poll_light(2000)
        self.assertEqual(self.output(), 0)
        self.assertEqual(self.led.current_color_index, 4)
        self.assertFalse(self.led.is_on)
        self.poll_light(500)
        self.assertEqual(self.output(), 4)
        self.assertTrue(self.led.is_on)

    def test_toggle_restores_selected_color(self):
        self.led.set_color_by_index(6)
        self.led.toggle()
        self.assertEqual(self.output(), 0)
        self.led.toggle()
        self.assertEqual(self.output(), 6)


if __name__ == '__main__':
    unittest.main()
