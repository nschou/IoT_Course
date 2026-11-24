"""Elderly-care rules built on top of the LD2410 radar snapshot.

Pure logic: the caller feeds snapshots, the class returns events. No hardware,
no asyncio, and the same code runs on CPython (tests) and MicroPython.

Snapshot contract (see hardware/ld2410.py):

    state                  "ok" | "unknown"
    target_state           "none" | "moving" | "stationary" | "moving_and_stationary"
    moving_distance_cm, moving_energy, stationary_distance_cm, stationary_energy, out

Events returned by update():

    {"type": "movement",          "at_ms": ...}
    {"type": "wake_up",           "at_ms": ...}   夜間活動（疑似起身）
    {"type": "night_light",       "at_ms": ...}   夜間低光且有活動
    {"type": "inactivity",        "value": 秒}    連續無活動
    {"type": "bed_exit_overdue",  "value": 秒}    離床後未回床
    {"type": "away_too_long",     "value": 秒}    連續無人在房
"""
import time


DEFAULTS = {
    "move_energy_min": 25,
    "move_session_gap_ms": 60000,
    "inactivity_seconds": 1800,
    "away_seconds": 3 * 3600,
    "bed_min_cm": 25,
    "bed_max_cm": 120,
    "bed_exit_seconds": 600,
    "night_start_hour": 22,
    "night_end_hour": 6,
    "night_light_cooldown_ms": 60000,
    "night_light_max_adc": 1100,
}


class RadarCare:
    """Turn radar snapshots into care events and a compact status dict."""

    def __init__(self, settings=None, clock=None):
        merged = dict(DEFAULTS)
        if settings:
            merged.update(settings)
        self.settings = merged
        self._clock = clock or time

        self._present = False
        self._link_ok = False
        self._in_bed = False
        self._last_move_ms = None
        self._bed_exit_ms = None
        self._away_since_ms = None
        self._night_light_until = 0

        self._inactivity_reported = False
        self._bed_exit_reported = False
        self._away_reported = False

        self._movement_sessions = 0
        self._wake_ups = 0
        self._night_lights = 0

    # ------------------------------------------------------------- helpers

    def _now(self):
        return self._clock.ticks_ms()

    def _diff(self, now, then):
        if then is None:
            return 0
        ticks_diff = getattr(self._clock, "ticks_diff", None)
        if callable(ticks_diff):
            return ticks_diff(now, then)
        return now - then

    def _is_night(self, hour):
        if hour is None:
            return False
        start = self.settings["night_start_hour"]
        end = self.settings["night_end_hour"]
        if start == end:
            return False
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end

    def _in_bed_range(self, snap):
        """Bed occupancy: check both distance fields on purpose.

        A person lying still is reported in stationary_distance_cm (moving
        energy falls to 0), while turning over or getting up shows up in
        moving_distance_cm first. Checking only one field would miss half of
        the situations. The one-frame lag (~100 ms) is irrelevant here: this
        rule is evaluated over minutes, not milliseconds.
        """
        low = self.settings["bed_min_cm"]
        high = self.settings["bed_max_cm"]
        for key in ("stationary_distance_cm", "moving_distance_cm"):
            distance = snap.get(key) or 0
            if low <= distance <= high:
                return True
        return False

    # -------------------------------------------------------------- update

    def update(self, snap, hour=None, light=None):
        """Feed one snapshot; return a list of new events (usually empty).

        An unknown snapshot (UART timeout) never means "nobody home": it is
        ignored for presence, and running timers keep counting. Callers should
        surface link_ok separately instead of treating it as absence.
        """
        if snap is None or snap.get("state") == "unknown":
            self._link_ok = False
            return []

        self._link_ok = True
        now = self._now()
        events = []

        target = snap.get("target_state") or "none"
        present = target != "none"
        moving_energy = snap.get("moving_energy") or 0
        moving_distance = snap.get("moving_distance_cm") or 0
        moving = (moving_energy >= self.settings["move_energy_min"]
                  and moving_distance > 0)

        if present:
            self._present = True

        # --- movement session (debounced to one event per gap) ----------
        if moving:
            if (self._last_move_ms is None or
                    self._diff(now, self._last_move_ms) >= self.settings["move_session_gap_ms"]):
                self._movement_sessions += 1
                events.append({"type": "movement", "at_ms": now})
                if self._is_night(hour):
                    self._wake_ups += 1
                    events.append({"type": "wake_up", "at_ms": now})
            self._last_move_ms = now
            self._inactivity_reported = False

            if (self._is_night(hour) and light is not None
                    and light < self.settings["night_light_max_adc"]
                    and now >= self._night_light_until):
                self._night_lights += 1
                events.append({"type": "night_light", "at_ms": now})
                self._night_light_until = now + self.settings["night_light_cooldown_ms"]

        # --- inactivity --------------------------------------------------
        if self._last_move_ms is None:
            self._last_move_ms = now
        else:
            idle_seconds = self._diff(now, self._last_move_ms) / 1000.0
            if (idle_seconds >= self.settings["inactivity_seconds"]
                    and not self._inactivity_reported):
                self._inactivity_reported = True
                events.append({"type": "inactivity", "value": int(idle_seconds)})

        # --- bed occupancy ----------------------------------------------
        if present and self._in_bed_range(snap):
            self._in_bed = True
            self._bed_exit_ms = None
            self._bed_exit_reported = False
        elif self._in_bed and present and self._bed_exit_ms is None:
            self._bed_exit_ms = now

        if self._bed_exit_ms is not None:
            away_seconds = self._diff(now, self._bed_exit_ms) / 1000.0
            if (away_seconds >= self.settings["bed_exit_seconds"]
                    and not self._bed_exit_reported):
                self._bed_exit_reported = True
                events.append({"type": "bed_exit_overdue", "value": int(away_seconds)})

        # --- away from the room -----------------------------------------
        if not present:
            if self._away_since_ms is None:
                self._away_since_ms = now
            away_seconds = self._diff(now, self._away_since_ms) / 1000.0
            if (away_seconds >= self.settings["away_seconds"]
                    and not self._away_reported):
                self._away_reported = True
                events.append({"type": "away_too_long", "value": int(away_seconds)})
        else:
            self._away_since_ms = None
            self._away_reported = False

        return events

    # --------------------------------------------------------------- state

    def state(self):
        now = self._now()
        idle = None
        if self._last_move_ms is not None:
            idle = int(self._diff(now, self._last_move_ms) / 1000.0)
        return {
            "present": self._present,
            "link_ok": self._link_ok,
            "idle_seconds": idle,
            "movement_sessions": self._movement_sessions,
            "wake_ups": self._wake_ups,
            "night_lights": self._night_lights,
            "in_bed": self._in_bed and self._bed_exit_ms is None,
            "inactivity_alarm": self._inactivity_reported,
            "bed_exit_alarm": self._bed_exit_reported,
            "away_alarm": self._away_reported,
        }

    def reset_daily(self):
        """Clear per-day counters; call at local midnight."""
        self._movement_sessions = 0
        self._wake_ups = 0
        self._night_lights = 0

