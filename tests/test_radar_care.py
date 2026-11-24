"""Unit tests for apps.elder_care.radar_care (pure logic, fake clock)."""
import os
import sys
import unittest

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from apps.elder_care.radar_care import RadarCare


class FakeClock:
    def __init__(self):
        self.now = 0

    def ticks_ms(self):
        return self.now

    def ticks_diff(self, end, start):
        return end - start

    def advance(self, ms):
        self.now += ms


def snapshot(target="moving_and_stationary", moving=80, moving_energy=100,
             stationary=80, stationary_energy=100, out=True, state="ok"):
    return {
        "state": state,
        "frame_type": 0x02,
        "target_state": target,
        "moving_distance_cm": moving,
        "moving_energy": moving_energy,
        "stationary_distance_cm": stationary,
        "stationary_energy": stationary_energy,
        "out": out,
    }


def absent(**kwargs):
    return snapshot(target="none", moving=0, moving_energy=0,
                    stationary=0, stationary_energy=0, out=False, **kwargs)


class RadarCareTests(unittest.TestCase):
    def make(self, **settings):
        clock = FakeClock()
        care = RadarCare(settings=settings, clock=clock)
        return clock, care

    def types(self, events):
        return [event["type"] for event in events]

    def test_movement_session_is_debounced(self):
        clock, care = self.make()
        self.assertEqual(self.types(care.update(snapshot(), hour=14)),
                         ["movement"])
        clock.advance(10 * 1000)
        self.assertEqual(care.update(snapshot(), hour=14), [])
        clock.advance(61 * 1000)
        self.assertEqual(self.types(care.update(snapshot(), hour=14)),
                         ["movement"])
        self.assertEqual(care.state()["movement_sessions"], 2)

    def test_night_move_counts_as_wake_up(self):
        clock, care = self.make()
        events = care.update(snapshot(), hour=23)
        self.assertEqual(self.types(events), ["movement", "wake_up"])
        self.assertEqual(care.state()["wake_ups"], 1)

    def test_night_light_needs_night_low_light_and_cooldown(self):
        clock, care = self.make(night_light_cooldown_ms=60000)
        clock.advance(61 * 1000)
        events = care.update(snapshot(), hour=23, light=500)
        self.assertIn("night_light", self.types(events))

        clock.advance(1000)
        events = care.update(snapshot(), hour=23, light=500)
        self.assertNotIn("night_light", self.types(events))

        clock.advance(61 * 1000)
        events = care.update(snapshot(), hour=23, light=3000)
        self.assertNotIn("night_light", self.types(events))

        events = care.update(snapshot(), hour=12, light=300)
        self.assertNotIn("night_light", self.types(events))

    def test_inactivity_fires_once_and_clears_on_movement(self):
        clock, care = self.make(inactivity_seconds=60)
        care.update(absent(), hour=14)
        clock.advance(61 * 1000)
        events = care.update(absent(), hour=14)
        self.assertEqual(self.types(events), ["inactivity"])

        clock.advance(61 * 1000)
        # 已告警過就不再重複觸發
        self.assertEqual(care.update(absent(), hour=14), [])

        care.update(snapshot(), hour=14)
        self.assertFalse(care.state()["inactivity_alarm"])

    def test_bed_exit_overdue_then_clear_on_return(self):
        clock, care = self.make(bed_min_cm=25, bed_max_cm=120,
                                bed_exit_seconds=60)
        care.update(snapshot(stationary=80), hour=2)
        self.assertTrue(care.state()["in_bed"])

        care.update(snapshot(moving=220, moving_energy=100, stationary=220), hour=2)
        clock.advance(61 * 1000)
        events = care.update(snapshot(moving=220, stationary=220), hour=2)
        self.assertIn("bed_exit_overdue", self.types(events))

        care.update(snapshot(stationary=80), hour=2)
        self.assertTrue(care.state()["in_bed"])
        self.assertFalse(care.state()["bed_exit_alarm"])

    def test_away_too_long_fires_and_resets_on_return(self):
        clock, care = self.make(away_seconds=120)
        care.update(absent(), hour=14)
        clock.advance(121 * 1000)
        events = care.update(absent(), hour=14)
        self.assertIn("away_too_long", self.types(events))

        care.update(snapshot(), hour=14)
        self.assertFalse(care.state()["away_alarm"])

    def test_unknown_snapshot_is_not_absence(self):
        clock, care = self.make(away_seconds=60)
        care.update(absent(), hour=14)
        clock.advance(30 * 1000)
        self.assertEqual(care.update(snapshot(state="unknown"), hour=14), [])
        self.assertFalse(care.state()["link_ok"])

        clock.advance(40 * 1000)
        events = care.update(absent(), hour=14)
        self.assertIn("away_too_long", self.types(events))
        self.assertTrue(care.state()["link_ok"])

    def test_reset_daily_clears_counters(self):
        clock, care = self.make()
        care.update(snapshot(), hour=23)
        self.assertEqual(care.state()["movement_sessions"], 1)
        care.reset_daily()
        self.assertEqual(care.state()["movement_sessions"], 0)
        self.assertEqual(care.state()["wake_ups"], 0)


if __name__ == "__main__":
    unittest.main()
