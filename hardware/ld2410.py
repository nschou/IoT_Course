"""Compatibility layer: the project LD2410 API on top of the canonical driver.

The real driver is the MicroPython package version:

    LD2410_repo/micropython/hardware/ld2410c.py

hardware/ld2410c.py in this folder is a copy of it; keep the two in sync.
This module only keeps the older snapshot contract used by apps/elder_care
and the demos (target_state / moving_distance_cm / out / state), so the
protocol work lives in exactly one place.
"""
from hardware.ld2410c import LD2410C

TARGET_STATES = {
    0: "none",
    1: "moving",
    2: "stationary",
    3: "moving_and_stationary",
}


class LD2410(LD2410C):
    """Old snapshot API on top of the canonical LD2410C driver."""

    def __init__(self, *args, **kwargs):
        self.stale_after_ms = kwargs.pop("stale_after_ms", 2000)
        LD2410C.__init__(self, *args, **kwargs)

    def snapshot(self):
        """Latest reading with the old key names plus freshness and OUT."""
        frame = self.frame
        age = self.age_ms()
        if age is None or age > self.stale_after_ms:
            state = "unknown"
        else:
            state = "ok"
        return {
            "state": state,
            "target_state": TARGET_STATES.get(frame.get("state"), "none"),
            "target_state_code": frame.get("state"),
            "moving_distance_cm": frame.get("moving_cm", 0),
            "moving_energy": frame.get("moving_energy", 0),
            "stationary_distance_cm": frame.get("stationary_cm", 0),
            "stationary_energy": frame.get("stationary_energy", 0),
            "detection_distance_cm": frame.get("detection_cm", 0),
            "age_ms": age,
            "out": self.out_level(),
        }

    def poll(self):
        """Return a snapshot when a new frame arrived, otherwise None."""
        if LD2410C.poll(self) is None:
            return None
        return self.snapshot()

    def current_config(self):
        cfg = self.read_params()
        return {
            "max_gate": cfg["max_gate"],
            "max_moving_gate": cfg["max_moving_gate"],
            "max_stationary_gate": cfg["max_stationary_gate"],
            "moving_sensitivity": cfg["motion_sens"],
            "stationary_sensitivity": cfg["static_sens"],
            "no_target_seconds": cfg["no_one_seconds"],
        }

    def firmware_version(self):
        info = LD2410C.firmware_version(self)
        info["version"] = info["string"]
        return info

    def presence(self):
        out = self.out_level()
        if out is not None:
            return out
        return bool(self.frame.get("presence"))
