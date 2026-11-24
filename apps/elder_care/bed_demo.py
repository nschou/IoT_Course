"""Bed monitoring demo + calibration tool (ESP32 + MicroPython).

Run in the device REPL, not together with main.py:

    exec(open('apps/elder_care/bed_demo.py').read())
    run(60)      # 60 秒，期間依序：躺著 -> 坐起 -> 躺下 -> 下床 -> 回床

每 200 ms 印出距離、能量、狀態與基線，方便決定 config.py 的
RADAR_BED_MIN_CM / RADAR_BED_MAX_CM / RADAR_BED_SIT_UP_DELTA_CM。
"""
import time

import config

from hardware.ld2410 import LD2410
import sys

try:
    from apps.elder_care.bed_monitor import BedMonitor
except ImportError:  # flat deployment on the device
    sys.path.append('apps/elder_care')
    from bed_monitor import BedMonitor


def _setting(name, default):
    return getattr(config, name, default)


def build_radar():
    return LD2410(
        uart_id=_setting('LD2410B_UART_ID', 1),
        tx=_setting('LD2410B_TX_PIN', 15),
        rx=_setting('LD2410B_RX_PIN', 16),
        baudrate=_setting('LD2410B_BAUDRATE', 115200),
        out_pin=_setting('LD2410B_OUT_PIN', None),
        out_active_high=_setting('LD2410B_OUT_ACTIVE_HIGH', True),
    )


def build_monitor():
    return BedMonitor(settings={
        'bed_min_cm': _setting('RADAR_BED_MIN_CM', 60),
        'bed_max_cm': _setting('RADAR_BED_MAX_CM', 180),
        'turn_energy_min': _setting('RADAR_BED_TURN_ENERGY_MIN', 60),
        'turn_debounce_ms': _setting('RADAR_BED_TURN_DEBOUNCE_MS', 3000),
        'sit_up_delta_cm': _setting('RADAR_BED_SIT_UP_DELTA_CM', 25),
        'exit_confirm_ms': _setting('RADAR_BED_EXIT_CONFIRM_MS', 5000),
        'return_confirm_ms': _setting('RADAR_BED_RETURN_CONFIRM_MS', 3000),
    })


def describe(event):
    kind = event['type']
    if kind == 'turn':
        return '翻身（distance=%s cm）' % event.get('distance_cm')
    if kind == 'sit_up':
        return '坐起（distance=%s cm）' % event.get('distance_cm')
    if kind == 'leave_bed':
        return '離床（在床上 %.0f 秒）' % (event.get('in_bed_ms', 0) / 1000.0)
    if kind == 'return_bed':
        return '回床（離開 %.0f 秒）' % (event.get('out_ms', 0) / 1000.0)
    return kind


def run(seconds=60, report_ms=200):
    radar = build_radar()
    monitor = build_monitor()
    start = time.ticks_ms()
    end = time.ticks_add(start, int(seconds * 1000))
    next_report = 0

    print('t(s)   dist  mov_e  sta_e  state        baseline')
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        snap = radar.poll()
        if snap is None:
            time.sleep_ms(10)
            continue

        events = monitor.update(snap)
        for event in events:
            print('  >>> %s' % describe(event))

        now = time.ticks_ms()
        if time.ticks_diff(now, next_report) >= 0:
            next_report = now + report_ms
            status = monitor.state()
            print('%5.1f  %-5s %-6s %-6s %-12s %s'
                  % (time.ticks_diff(now, start) / 1000.0,
                     snap.get('moving_distance_cm'),
                     snap.get('moving_energy'),
                     snap.get('stationary_energy'),
                     status['state'], status['baseline_cm']))

        time.sleep_ms(20)

    print('--- 夜間統計 ---')
    print(monitor.state())


print('bed_demo 已載入；執行 run(60) 開始校準/測試')
