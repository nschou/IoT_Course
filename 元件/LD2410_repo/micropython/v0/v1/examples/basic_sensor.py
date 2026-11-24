"""Minimal LD2410 MicroPython example.

Adjust UART number and pins for the target board before copying to it.
"""

from machine import UART, Pin
from hardware import LD2410


RADAR_UART = UART(1, baudrate=256000, bits=8, parity=None, stop=1,
                  tx=Pin(15), rx=Pin(16))
radar = LD2410(RADAR_UART, wait_for_radar=False)

while True:
    radar.read()
    if not radar.is_connected():
        continue

    if radar.presence_detected():
        print("moving: {} cm, energy {}".format(
            radar.moving_target_distance(), radar.moving_target_energy()))
        print("stationary: {} cm, energy {}".format(
            radar.stationary_target_distance(),
            radar.stationary_target_energy()))
    else:
        print("no target")
