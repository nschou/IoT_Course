"""Bed-occupancy state machine for the LD2410 (sleep monitoring).

What the radar can and cannot tell us:

  * it reports distance, moving/stationary energy and a target state;
  * it cannot see posture, so "turning over" vs "sitting up" is inferred from
    a movement burst and how much the distance moved relative to a baseline;
  * "leaving the bed" is inferred from the bed distance band staying empty.

States: unknown -> in_bed <-> turning / sitting -> out_of_bed -> in_bed

Events:

    {"type": "turn",       "at_ms": ..., "distance_cm": ...}
    {"type": "sit_up",     "at_ms": ..., "distance_cm": ...}
    {"type": "leave_bed",  "at_ms": ..., "in_bed_ms": ...}
    {"type": "return_bed", "at_ms": ..., "out_ms": ...}
"""
import time


DEFAULTS = {
    # 床鋪在雷達座標中的距離帶（cm）：校準時量「躺著」與「站在床邊」兩個值
    "bed_min_cm": 60,
    "bed_max_cm": 180,
    # 翻身的判定：移動能量門檻與去抖
    "turn_energy_min": 60,
    "turn_debounce_ms": 3000,
    # 起床的判定：距離相對基線縮短多少 cm 以上（坐起來會變近或變遠，校準時取正負）
    "sit_up_delta_cm": 25,
    # 離床：距離帶連續空多久才算離開
    "exit_confirm_ms": 5000,
    # 回床：重新落在距離帶內多久才算回來
    "return_confirm_ms": 3000,
    # 基線平滑係數（越小越慢，0.1 約等於十幾個 frame 的平均）
    "baseline_alpha": 0.1,
    # 地板距離帶：一般床高 45-60 cm，躺床與躺地板的距離差約 55-75 cm，
    # 所以天花板安裝時可用距離把兩者分開。
    "floor_min_cm": 225,
    "floor_max_cm": 255,
    # 分級告警：寧可多報不可漏報，但要讓照護者能確認
    "floor_notice_ms": 30000,
    "floor_alert_ms": 120000,
    "floor_critical_ms": 600000,
}


class BedMonitor:
    """Infer turning / sitting up / leaving / returning from radar snapshots."""

    def __init__(self, settings=None, clock=None):
        merged = dict(DEFAULTS)
        if settings:
            merged.update(settings)
        self.settings = merged
        self._clock = clock or time

        self._state = "unknown"
        self._baseline_cm = None
        self._last_turn_ms = None
        self._exit_ms = None
        self._return_ms = None
        self._in_bed_since = None
        self._out_since = None
        self._floor_since = None
        self._floor_notice_sent = False
        self._floor_alert_sent = False
        self._floor_critical_sent = False
        self._floor_acknowledged = False

        self.turns = 0
        self.sit_ups = 0
        self.leaves = 0
        self._floor_events = 0

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

    @staticmethod
    def _distance(snap):
        """Prefer the moving distance while the target moves, else stationary."""
        if (snap.get("moving_energy") or 0) >= 20:
            return snap.get("moving_distance_cm") or 0
        return snap.get("stationary_distance_cm") or 0

    def _update_baseline(self, distance):
        alpha = self.settings["baseline_alpha"]
        if self._baseline_cm is None:
            self._baseline_cm = distance
        else:
            self._baseline_cm = (self._baseline_cm * (1 - alpha)) + (distance * alpha)

    # -------------------------------------------------------------- update

    def update(self, snap, hour=None):
        """Feed one snapshot and return the events it produced (usually none)."""
        if snap is None or snap.get("state") == "unknown":
            return []

        now = self._now()
        events = []
        target = snap.get("target_state") or "none"
        present = target != "none"
        distance = self._distance(snap)
        moving_energy = snap.get("moving_energy") or 0
        stationary_energy = snap.get("stationary_energy") or 0

        low = self.settings["bed_min_cm"]
        high = self.settings["bed_max_cm"]
        in_band = present and low <= distance <= high

        # 基線只在「躺著、沒有大動作」時更新，避免坐起來把基線帶走。
        if in_band and stationary_energy > 0 and moving_energy < 20:
            self._update_baseline(distance)

        # --- 離床 / 回床 -------------------------------------------------
        if in_band:
            self._exit_ms = None
            if self._state == "out_of_bed":
                if self._return_ms is None:
                    self._return_ms = now
                if self._diff(now, self._return_ms) >= self.settings["return_confirm_ms"]:
                    out_ms = self._diff(now, self._out_since)
                    events.append({"type": "return_bed", "at_ms": now,
                                   "out_ms": out_ms})
                    self._state = "in_bed"
                    self._return_ms = None
                    self._out_since = None
                    self._in_bed_since = now
            elif self._state == "unknown":
                self._state = "in_bed"
                self._in_bed_since = now
        else:
            self._return_ms = None
            if self._state in ("in_bed", "turning", "sitting"):
                if self._exit_ms is None:
                    self._exit_ms = now
                if self._diff(now, self._exit_ms) >= self.settings["exit_confirm_ms"]:
                    events.append({"type": "leave_bed", "at_ms": now,
                                   "in_bed_ms": self._diff(now, self._in_bed_since)})
                    self._state = "out_of_bed"
                    self.leaves += 1
                    self._out_since = now
                    self._exit_ms = None

        # --- 地板高度停留（疑似倒地，需人工確認）-------------------------
        floor_low = self.settings["floor_min_cm"]
        floor_high = self.settings["floor_max_cm"]
        on_floor = present and floor_low <= distance <= floor_high
        if on_floor:
            if self._floor_since is None:
                self._floor_since = now
            dwell = self._diff(now, self._floor_since)
            if not self._floor_acknowledged:
                if (dwell >= self.settings["floor_notice_ms"]
                        and not self._floor_notice_sent):
                    self._floor_notice_sent = True
                    events.append({"type": "floor_notice", "at_ms": now,
                                   "distance_cm": distance})
                if (dwell >= self.settings["floor_alert_ms"]
                        and not self._floor_alert_sent):
                    self._floor_alert_sent = True
                    self._floor_events += 1
                    events.append({"type": "floor_alert", "at_ms": now,
                                   "distance_cm": distance,
                                   "seconds": int(dwell / 1000.0)})
                if (dwell >= self.settings["floor_critical_ms"]
                        and not self._floor_critical_sent):
                    self._floor_critical_sent = True
                    self._floor_events += 1
                    events.append({"type": "floor_critical", "at_ms": now,
                                   "distance_cm": distance,
                                   "seconds": int(dwell / 1000.0)})
        else:
            self._floor_since = None
            self._floor_notice_sent = False
            self._floor_alert_sent = False
            self._floor_critical_sent = False
            self._floor_acknowledged = False

        # --- 翻身 / 起身 -------------------------------------------------
        if in_band and moving_energy >= self.settings["turn_energy_min"]:
            debounced = (self._last_turn_ms is not None and
                         self._diff(now, self._last_turn_ms) < self.settings["turn_debounce_ms"])
            if not debounced:
                self._last_turn_ms = now
                baseline = self._baseline_cm
                drop = 0
                if baseline is not None:
                    drop = baseline - distance
                if abs(drop) >= self.settings["sit_up_delta_cm"]:
                    self._state = "sitting"
                    self.sit_ups += 1
                    events.append({"type": "sit_up", "at_ms": now,
                                   "distance_cm": distance})
                else:
                    self._state = "turning"
                    self.turns += 1
                    events.append({"type": "turn", "at_ms": now,
                                   "distance_cm": distance})

        # 靜止下來後回到 in_bed 狀態
        if self._state in ("turning", "sitting") and moving_energy < 20 and in_band:
            self._state = "in_bed"

        return events

    # --------------------------------------------------------------- state

    def state(self):
        now = self._now()
        return {
            "state": self._state,
            "in_bed": self._state in ("in_bed", "turning", "sitting"),
            "baseline_cm": int(self._baseline_cm) if self._baseline_cm is not None else None,
            "in_bed_ms": self._diff(now, self._in_bed_since) if self._in_bed_since else 0,
            "out_ms": self._diff(now, self._out_since) if self._out_since else 0,
            "turns": self.turns,
            "sit_ups": self.sit_ups,
            "leaves": self.leaves,
            "on_floor": self._floor_since is not None,
            "floor_seconds": int(self._diff(now, self._floor_since) / 1000.0) if self._floor_since else 0,
            "floor_alerts": self._floor_events,
            "floor_acknowledged": self._floor_acknowledged,
        }

    def acknowledge(self):
        """A caregiver confirmed the floor event; stop escalating this episode."""
        if self._floor_since is not None:
            self._floor_acknowledged = True

    def reset_night(self):
        """Clear per-night counters; call when the night window ends."""
        self.turns = 0
        self.sit_ups = 0
        self.leaves = 0

