"""Standalone MicroPython bed-exit experiment for HLK-LD2410B.

This program is an engineering test, not a medical or fall-detection alarm.
It treats stationary radar energy as a breathing candidate and turns the RGB
LED yellow after a confirmed moving transition outside the configured bed
range.
"""
import time

import config
from hardware.ld2410b import LD2410B


YELLOW = 6  # hardware.led.RgbLed: red + green
OFF = 0


def _setting(name, default):
    return getattr(config, name, default)


class BedExitMonitor:
    """Classify radar frames and own the bed-exit alert state."""

    def __init__(self, led, bed_min_cm=25, bed_max_cm=100,
                 breathing_energy_min=1, motion_confirm_frames=2,
                 rearm_confirm_frames=3):
        self.led = led
        self.bed_min_cm = bed_min_cm
        self.bed_max_cm = bed_max_cm
        self.breathing_energy_min = breathing_energy_min
        self.motion_confirm_frames = motion_confirm_frames
        self.rearm_confirm_frames = rearm_confirm_frames
        self.previous_inside = None
        self.previous_target_state = None
        self.exit_candidate = False
        self.exit_frames = 0
        self.rearm_frames = 0
        self.alert_active = False
        self.last_report = None
        self.led.write(OFF)

    @staticmethod
    def _motion_state(target_state):
        if target_state in ('moving', 'moving_and_stationary'):
            return 'moving'
        if target_state == 'stationary':
            return 'stationary'
        return 'unknown'

    def _distance_cm(self, frame, motion_state):
        if motion_state == 'moving':
            distance = frame.get('moving_distance_cm', 0)
            if distance > 0:
                return distance
        distance = frame.get('stationary_distance_cm', 0)
        if distance > 0:
            return distance
        return frame.get('detection_distance_cm', 0)

    def observe(self, frame):
        target_state = frame.get('target_state', 'unknown')
        motion_state = self._motion_state(target_state)
        distance_cm = self._distance_cm(frame, motion_state)
        inside_bed = self.bed_min_cm <= distance_cm <= self.bed_max_cm
        breathing_candidate = (
            target_state in ('stationary', 'moving_and_stationary') and
            inside_bed and
            frame.get('stationary_energy', 0) >= self.breathing_energy_min
        )
        outside_bed = distance_cm > 0 and not inside_bed
        state_changed = target_state != self.previous_target_state

        if inside_bed:
            self.exit_candidate = False
            self.exit_frames = 0
        elif (outside_bed and motion_state == 'moving' and
              (state_changed and self.previous_inside is True or
               self.exit_candidate)):
            self.exit_candidate = True
            self.exit_frames += 1
        else:
            self.exit_candidate = False
            self.exit_frames = 0

        exit_confirmed = (
            self.exit_candidate and
            self.exit_frames >= self.motion_confirm_frames
        )
        if exit_confirmed and not self.alert_active:
            self.alert_active = True
            self.rearm_frames = 0
            self.led.write(YELLOW)
            print('[ALERT] moving + outside bed range -> YELLOW')

        if self.alert_active:
            if inside_bed and motion_state == 'stationary':
                self.rearm_frames += 1
                if self.rearm_frames >= self.rearm_confirm_frames:
                    self.alert_active = False
                    self.exit_candidate = False
                    self.exit_frames = 0
                    self.led.write(OFF)
                    print('[INFO] stationary inside bed range -> rearmed')
            else:
                self.rearm_frames = 0

        self.previous_inside = inside_bed
        self.previous_target_state = target_state
        self.last_report = {
            'target_state': target_state,
            'motion_state': motion_state,
            'distance_cm': distance_cm,
            'inside_bed': inside_bed,
            'breathing_candidate': breathing_candidate,
            'alert_active': self.alert_active,
            'state_changed': state_changed,
        }
        return dict(self.last_report)


def _print_report(report, frame):
    breathing = 'candidate' if report['breathing_candidate'] else 'not-confirmed'
    print(
        '[RADAR] state={} motion={} distance={}cm stationary_energy={} '
        'breathing={} inside={} alert={}'.format(
            report['target_state'], report['motion_state'],
            report['distance_cm'], frame.get('stationary_energy', 0),
            breathing, report['inside_bed'], report['alert_active']))


def main():
    # Optional overrides may be added to config.py without changing this file.
    bed_min_cm = _setting('LD2410B_BED_MIN_DISTANCE_CM', 25)
    bed_max_cm = _setting('LD2410B_BED_MAX_DISTANCE_CM', 100)
    breathing_energy_min = _setting('LD2410B_BREATHING_ENERGY_MIN', 1)
    motion_confirm_frames = _setting('LD2410B_MOTION_CONFIRM_FRAMES', 2)
    rearm_confirm_frames = _setting('LD2410B_REARM_CONFIRM_FRAMES', 3)
    read_timeout_ms = _setting('LD2410B_TEST_READ_TIMEOUT_MS', 1500)
    poll_delay_ms = _setting('LD2410B_TEST_POLL_DELAY_MS', 50)

    from hardware.led import RgbLed

    led = RgbLed()
    radar = LD2410B(
        uart_id=config.LD2410B_UART_ID,
        tx=config.LD2410B_TX_PIN,
        rx=config.LD2410B_RX_PIN,
        baudrate=config.LD2410B_BAUDRATE,
    )
    monitor = BedExitMonitor(
        led,
        bed_min_cm=bed_min_cm,
        bed_max_cm=bed_max_cm,
        breathing_energy_min=breathing_energy_min,
        motion_confirm_frames=motion_confirm_frames,
        rearm_confirm_frames=rearm_confirm_frames,
    )

    print('LD2410B bed monitor test started')
    print('bed range: {}..{} cm; breathing energy >= {}'.format(
        bed_min_cm, bed_max_cm, breathing_energy_min))
    print('yellow LED index: {}'.format(YELLOW))
    try:
        while True:
            try:
                frame = radar.read(timeout_ms=read_timeout_ms)
                report = monitor.observe(frame)
                _print_report(report, frame)
            except OSError as error:
                print('[RADAR] read error: {}'.format(error))
            time.sleep_ms(poll_delay_ms)
    except KeyboardInterrupt:
        print('LD2410B bed monitor test stopped')
    finally:
        led.write(OFF)


if __name__ == '__main__':
    main()
