"""Read, modify, verify, and restore one LD2410 configuration value.

The example changes only the no-target duration. The protocol document defines
its factory default as 5 seconds. Maximum moving/stationary gates are read from
the module and sent back unchanged while the test value is written.
"""

import time

from machine import Pin, UART
from hardware import LD2410


TEST_IDLE_SECONDS = 10
FACTORY_IDLE_SECONDS = 5


uart = UART(1, baudrate=256000, bits=8, parity=None, stop=1,
            tx=Pin(15), rx=Pin(16))
radar = LD2410(uart=uart, wait_for_radar=False)
time.sleep_ms(500)


def print_configuration(title):
    print("\n--- {} ---".format(title))
    print("max gate:", radar.max_gate)
    print("max moving gate:", radar.max_moving_gate)
    print("max stationary gate:", radar.max_stationary_gate)
    print("idle duration (s):", radar.sensor_idle_time)
    print("motion sensitivity:", radar.motion_sensitivity)
    print("stationary sensitivity:", radar.stationary_sensitivity)


def require(ok, operation):
    if not ok:
        error = getattr(radar, "last_error", "driver did not provide an error")
        raise RuntimeError("{} failed: {}".format(operation, error))


# 1. Read the current configuration and preserve the two gate limits.
require(radar.request_current_configuration(), "initial configuration read")
print_configuration("initial configuration")
current_moving_gate = radar.max_moving_gate
current_stationary_gate = radar.max_stationary_gate

# 2. Change only the no-target duration to 10 seconds.
require(radar.set_max_values(current_moving_gate, current_stationary_gate,
                             TEST_IDLE_SECONDS), "test value write")
require(radar.request_current_configuration(), "configuration reread")
print_configuration("after modification")
if radar.sensor_idle_time != TEST_IDLE_SECONDS:
    raise RuntimeError("modification verification failed")
print("modification verified")

# 3. Restore the documented factory default of 5 seconds.
require(radar.set_max_values(current_moving_gate, current_stationary_gate,
                             FACTORY_IDLE_SECONDS), "factory value restore")
require(radar.request_current_configuration(), "final configuration reread")
print_configuration("after restore")
if radar.sensor_idle_time != FACTORY_IDLE_SECONDS:
    raise RuntimeError("factory value verification failed")
print("factory default restored")
