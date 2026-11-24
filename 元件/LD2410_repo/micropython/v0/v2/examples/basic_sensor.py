"""LD2410 v2 ESP32 example with startup and UART diagnostics."""

import time

from machine import Pin, UART
from hardware import LD2410


UART_TX = 15
UART_RX = 16

print("LD2410 v2 starting")
print("UART1 TX={}, RX={}, baudrate=256000".format(UART_TX, UART_RX))

uart = UART(1, baudrate=256000, bits=8, parity=None, stop=1,
            tx=Pin(UART_TX), rx=Pin(UART_RX))
radar = LD2410(uart=uart, out_pin=4, wait_for_radar=False)

last_waiting_message = time.ticks_ms()

while True:
    snapshot = radar.poll()
    if snapshot is not None:
        print("state:", snapshot["state"])
        print("target:", snapshot["target_state"])
        print("moving:", snapshot["moving_distance_cm"],
              snapshot["moving_energy"])
        print("stationary:", snapshot["stationary_distance_cm"],
              snapshot["stationary_energy"])
        continue

    if time.ticks_diff(time.ticks_ms(), last_waiting_message) >= 2000:
        print("waiting for LD2410 data; check TX/RX wiring and power")
        last_waiting_message = time.ticks_ms()
