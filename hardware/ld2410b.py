"""Backward-compatible alias for :mod:`hardware.ld2410`.

LD2410, LD2410B and LD2410C share the same UART protocol, so the driver is
no longer named after the B variant. This module stays so older teaching
scripts (for example `ld2410b_bed_monitor_test.py`) keep importing
`LD2410B` without change.
"""

try:
    from hardware.ld2410 import LD2410 as LD2410B
except ImportError:  # flat deployment: hardware/*.py copied next to main.py
    from ld2410 import LD2410 as LD2410B

__all__ = ["LD2410B"]
