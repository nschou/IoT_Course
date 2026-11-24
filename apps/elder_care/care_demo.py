"""Standalone elderly-care demo on the LD2410 radar (ESP32 + MicroPython).

Run in the device REPL, NOT together with main.py (this program drives the
RGB LED directly, the same way ld2410b_bed_monitor_test.py does):

    exec(open('apps/elder_care/care_demo.py').read())
    run(300)          # 5 分鐘

It prints care events and maps them to the LED:

    night_light   -> 藍燈（夜間起身照明）
    inactivity    -> 紅燈閃爍（久無活動）
    bed_exit      -> 紅燈閃爍（離床未回）
    away_too_long -> 紅燈閃爍（長時間無人）
"""
import time

import config

from hardware.ld2410 import LD2410
from hardware.led import RgbLed
import sys

try:
    from apps.elder_care.radar_care import RadarCare
except ImportError:  # flat deployment on the device
    sys.path.append('apps/elder_care')
    from radar_care import RadarCare


OFF, BLUE, GREEN, RED, YELLOW, WHITE = 0, 1, 2, 4, 6, 7


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


def build_care():
    return RadarCare(settings={
        'move_energy_min': _setting('RADAR_CARE_MOVE_ENERGY_MIN', 25),
        'move_session_gap_ms': _setting('RADAR_CARE_MOVE_SESSION_GAP_MS', 60000),
        'inactivity_seconds': _setting('RADAR_CARE_INACTIVITY_SECONDS', 1800),
        'away_seconds': _setting('RADAR_CARE_AWAY_SECONDS', 10800),
        'bed_min_cm': _setting('RADAR_CARE_BED_MIN_CM', 25),
        'bed_max_cm': _setting('RADAR_CARE_BED_MAX_CM', 120),
        'bed_exit_seconds': _setting('RADAR_CARE_BED_EXIT_SECONDS', 600),
        'night_start_hour': _setting('RADAR_CARE_NIGHT_START_HOUR', 22),
        'night_end_hour': _setting('RADAR_CARE_NIGHT_END_HOUR', 6),
        'night_light_max_adc': _setting('RADAR_CARE_NIGHT_LIGHT_MAX_ADC', 1100),
    })


def local_hour():
    try:
        return time.localtime()[3]
    except Exception:
        return None


def describe(event):
    kind = event['type']
    if kind == 'movement':
        return '活動'
    if kind == 'wake_up':
        return '夜間起身'
    if kind == 'night_light':
        return '夜間照明'
    if kind == 'inactivity':
        return '久無活動 %d 秒' % event.get('value', 0)
    if kind == 'bed_exit_overdue':
        return '離床未回 %d 秒' % event.get('value', 0)
    if kind == 'away_too_long':
        return '長時間無人 %d 秒' % event.get('value', 0)
    return kind


def run(seconds=120, tick_ms=50, report_ms=2000):
    radar = build_radar()
    care = build_care()
    led = RgbLed()

    led_until = 0
    led_pattern = OFF
    next_report = 0
    start = time.ticks_ms()
    end = time.ticks_add(start, int(seconds * 1000))

    print('照護示範開始，%d 秒；Ctrl-C 停止' % seconds)
    try:
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            snap = radar.poll()
            if snap is None:
                time.sleep_ms(10)
                continue

            now = time.ticks_ms()
            events = care.update(snap, hour=local_hour(), light=None)
            for event in events:
                print('[%6.1f s] %s' %
                      (time.ticks_diff(now, start) / 1000.0, describe(event)))
                if event['type'] == 'night_light':
                    led_pattern = BLUE
                    led_until = now + _setting('RADAR_CARE_NIGHT_LIGHT_SECONDS', 60) * 1000
                elif event['type'] in ('inactivity', 'bed_exit_overdue',
                                       'away_too_long'):
                    led_pattern = RED
                    led_until = now + 5000

            if led_pattern != OFF and time.ticks_diff(led_until, now) <= 0:
                led_pattern = OFF
                led.write(OFF)
            elif led_pattern != OFF:
                led.write(led_pattern)

            if time.ticks_diff(now, next_report) >= 0:
                next_report = now + report_ms
                status = care.state()
                print('  present=%s in_bed=%s idle=%s s  dist=%s cm  out=%s'
                      % (status['present'], status['in_bed'],
                         status['idle_seconds'], snap.get('moving_distance_cm'),
                         snap.get('out')))

            time.sleep_ms(tick_ms)
    finally:
        led.write(OFF)
        print('結束；統計:', care.state())


print('care_demo 已載入；執行 run(120) 開始，Ctrl-C 停止')
