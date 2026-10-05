"""Fake PIR/PWM checks; no hardware sound or timing validation."""
import ast
import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config


class StopCycles(BaseException):
    pass


def load_task(name, **namespace):
    tree = ast.parse((ROOT / 'tasks.py').read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
    namespace['config'] = config
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'tasks.py', 'exec'), namespace)
    return namespace[name]


class PirMusicTests(unittest.IsolatedAsyncioTestCase):
    async def test_edges_ignore_initial_high_and_continuous_high(self):
        values = iter([True, True, False, True, True, False, True])
        count = 0
        samples = 0
        class Event:
            def set(self):
                nonlocal count
                count += 1
        async def sleep(ms):
            nonlocal samples
            self.assertEqual(ms, 500)
            samples += 1
            if samples == 7:
                raise StopCycles()
        task = load_task('pir_monitor_task', uasyncio=types.SimpleNamespace(sleep_ms=sleep))
        with self.assertRaises(StopCycles):
            await task(types.SimpleNamespace(is_motion=lambda: next(values)), Event())
        self.assertEqual(count, 2)

    async def test_music_events_coalesce_and_cancel_silences(self):
        event = asyncio.Event()
        started = asyncio.Event()
        release = asyncio.Event()
        second = asyncio.Event()
        class Speaker:
            plays = 0
            silenced = False
            async def play_song(self, notes):
                self.plays += 1
                if self.plays == 1:
                    started.set()
                    await release.wait()
                else:
                    second.set()
            def silence(self):
                self.silenced = True
        speaker = Speaker()
        task = load_task('music_on_motion_task', uasyncio=asyncio)
        running = asyncio.create_task(task(speaker, event))
        event.set()
        await asyncio.wait_for(started.wait(), 1)
        # Several movements during the first song become exactly one pending song.
        for _ in range(5):
            event.set()
        release.set()
        await asyncio.wait_for(second.wait(), 1)
        await asyncio.sleep(0)
        self.assertEqual(speaker.plays, 2)
        running.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await running
        self.assertTrue(speaker.silenced)

    async def test_pwm_melody_yields_rest_and_finally(self):
        class PWM:
            def __init__(self, pin, freq, duty):
                self.level = duty
                self.frequencies = []
                self.closed = 0
            def duty(self, value):
                self.level = value
            def freq(self, value):
                self.frequencies.append(value)
            def deinit(self):
                self.closed += 1
        machine = types.ModuleType('machine')
        machine.Pin = lambda pin, mode: pin
        # Functions can carry the Pin.OUT constant used by the constructor.
        machine.Pin.OUT = 1
        machine.PWM = PWM
        tools = types.ModuleType('ns_tools')
        tools.NOTE_FREQS = {'C4': 262, 'E4': 330, 'D4': 294, 'G3': 196, 'REST': 0}
        levels, durations = [], []
        progress = 0
        async def sleep(duration):
            durations.append(duration)
            levels.append(speaker.pwm.level)
            await asyncio.sleep(0)
        with patch.dict(sys.modules, {'machine': machine, 'ns_tools': tools,
                                     'uasyncio': types.SimpleNamespace(sleep=sleep)}):
            spec = importlib.util.spec_from_file_location('speaker_test', ROOT / 'hardware/speaker.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            speaker = module.Speaker()
        async def other_task():
            nonlocal progress
            for _ in range(5):
                progress += 1
                await asyncio.sleep(0)
        await asyncio.gather(speaker.play_song(config.MOTION_MELODY), other_task())
        self.assertEqual(progress, 5)
        self.assertEqual(durations, [0.3, 0.3, 0.3, 0.3, 0.2])
        self.assertEqual(levels, [512, 512, 512, 512, 0])
        self.assertEqual(speaker.pwm.frequencies, [262, 330, 294, 196])
        self.assertEqual(speaker.pwm.level, 0)
        with self.assertRaises(KeyError):
            await speaker.play_song([('C4', 0.01), ('INVALID', 0.01)])
        self.assertEqual(speaker.pwm.level, 0)
        async def cancel(_):
            raise asyncio.CancelledError()
        module.uasyncio.sleep = cancel
        with self.assertRaises(asyncio.CancelledError):
            await speaker.play_song(config.MOTION_MELODY)
        self.assertEqual(speaker.pwm.level, 0)
        pwm = speaker.pwm
        speaker.deinit()
        speaker.deinit()
        self.assertEqual(pwm.closed, 1)
