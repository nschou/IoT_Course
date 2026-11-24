"""Unit tests for apps.elder_care.bed_monitor (fake clock, synthetic snapshots)."""
import os
import sys
import unittest

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from apps.elder_care.bed_monitor import BedMonitor


class FakeClock:
    def __init__(self):
        self.now = 0

    def ticks_ms(self):
        return self.now

    def ticks_diff(self, end, start):
        return end - start

    def advance(self, ms):
        self.now += ms


def lying(distance=100):
    return {"state": "ok", "target_state": "stationary",
            "moving_distance_cm": 0, "moving_energy": 0,
            "stationary_distance_cm": distance, "stationary_energy": 100}


def moving(distance, energy=80):
    return {"state": "ok", "target_state": "moving_and_stationary",
            "moving_distance_cm": distance, "moving_energy": energy,
            "stationary_distance_cm": distance, "stationary_energy": 100}


def absent():
    return {"state": "ok", "target_state": "none",
            "moving_distance_cm": 0, "moving_energy": 0,
            "stationary_distance_cm": 0, "stationary_energy": 0}


def unknown():
    return {"state": "unknown", "target_state": "none",
            "moving_distance_cm": 0, "moving_energy": 0,
            "stationary_distance_cm": 0, "stationary_energy": 0}


class BedMonitorTests(unittest.TestCase):
    def make(self, **settings):
        clock = FakeClock()
        monitor = BedMonitor(settings=settings, clock=clock)
        return clock, monitor

    def types(self, events):
        return [event["type"] for event in events]

    def settle(self, clock, monitor, snapshot, seconds=2):
        """Feed a few frames so the baseline and state are established."""
        for _ in range(seconds * 10):
            monitor.update(snapshot)
            clock.advance(100)

    def test_lying_establishes_in_bed(self):
        clock, monitor = self.make()
        self.settle(clock, monitor, lying())
        self.assertEqual(monitor.state()["state"], "in_bed")
        self.assertAlmostEqual(monitor.state()["baseline_cm"], 100, delta=1)

    def test_turn_without_distance_change(self):
        clock, monitor = self.make()
        self.settle(clock, monitor, lying())
        events = monitor.update(moving(100))
        self.assertEqual(self.types(events), ["turn"])
        self.assertEqual(monitor.state()["turns"], 1)

    def test_turn_is_debounced(self):
        clock, monitor = self.make()
        self.settle(clock, monitor, lying())
        monitor.update(moving(100))
        clock.advance(1000)
        self.assertEqual(monitor.update(moving(100)), [])

    def test_sitting_up_shows_as_distance_drop(self):
        clock, monitor = self.make()
        self.settle(clock, monitor, lying(100))
        events = monitor.update(moving(70))
        self.assertEqual(self.types(events), ["sit_up"])
        self.assertEqual(monitor.state()["sit_ups"], 1)

    def test_leave_and_return(self):
        clock, monitor = self.make(exit_confirm_ms=5000, return_confirm_ms=3000)
        self.settle(clock, monitor, lying())
        self.assertTrue(monitor.state()["in_bed"])

        # 先收到一筆空畫面才開始計時，之後再過 6 秒才算離開
        monitor.update(absent())
        clock.advance(6000)
        events = monitor.update(absent())
        self.assertEqual(self.types(events), ["leave_bed"])
        self.assertEqual(monitor.state()["state"], "out_of_bed")
        self.assertEqual(monitor.state()["leaves"], 1)

        monitor.update(lying())
        clock.advance(4000)
        events = monitor.update(lying())
        self.assertEqual(self.types(events), ["return_bed"])
        self.assertEqual(monitor.state()["state"], "in_bed")

    def test_unknown_snapshot_does_not_end_the_night(self):
        clock, monitor = self.make(exit_confirm_ms=5000)
        self.settle(clock, monitor, lying())
        for _ in range(50):
            self.assertEqual(monitor.update(unknown()), [])
            clock.advance(1000)
        self.assertEqual(monitor.state()["state"], "in_bed")
        self.assertEqual(monitor.state()["leaves"], 0)

    def test_short_absence_does_not_count_as_leaving(self):
        clock, monitor = self.make(exit_confirm_ms=5000)
        self.settle(clock, monitor, lying())
        monitor.update(absent())
        clock.advance(1000)
        monitor.update(lying())
        self.assertEqual(monitor.state()["leaves"], 0)


    def test_floor_escalates_through_three_levels(self):
        clock, monitor = self.make(floor_min_cm=225, floor_max_cm=255,
                                   floor_notice_ms=1000, floor_alert_ms=2000,
                                   floor_critical_ms=3000)
        monitor.update(lying(240))
        clock.advance(1000)
        self.assertEqual(self.types(monitor.update(lying(240))), ["floor_notice"])
        clock.advance(1000)
        self.assertEqual(self.types(monitor.update(lying(240))), ["floor_alert"])
        clock.advance(1000)
        self.assertEqual(self.types(monitor.update(lying(240))), ["floor_critical"])
        clock.advance(5000)
        self.assertEqual(monitor.update(lying(240)), [])
        self.assertEqual(monitor.state()["floor_alerts"], 2)

    def test_standing_distance_is_not_floor(self):
        clock, monitor = self.make(floor_min_cm=225, floor_max_cm=255,
                                   floor_notice_ms=1000)
        monitor.update(lying(110))
        clock.advance(61000)
        self.assertEqual(monitor.update(lying(110)), [])
        self.assertFalse(monitor.state()["on_floor"])

    def test_floor_alert_rearms_after_leaving_the_band(self):
        clock, monitor = self.make(floor_min_cm=225, floor_max_cm=255,
                                   floor_notice_ms=1000)
        monitor.update(lying(240))
        clock.advance(2000)
        self.assertEqual(self.types(monitor.update(lying(240))), ["floor_notice"])

        monitor.update(lying(100))
        self.assertFalse(monitor.state()["on_floor"])

        monitor.update(lying(240))
        clock.advance(2000)
        self.assertEqual(self.types(monitor.update(lying(240))), ["floor_notice"])

    def test_acknowledge_stops_escalation_for_this_episode(self):
        clock, monitor = self.make(floor_min_cm=225, floor_max_cm=255,
                                   floor_notice_ms=1000, floor_alert_ms=2000,
                                   floor_critical_ms=3000)
        monitor.update(lying(240))
        clock.advance(1000)
        self.assertEqual(self.types(monitor.update(lying(240))), ["floor_notice"])
        monitor.acknowledge()
        clock.advance(5000)
        self.assertEqual(monitor.update(lying(240)), [])
        self.assertTrue(monitor.state()["floor_acknowledged"])


if __name__ == "__main__":
    unittest.main()
