"""無源喇叭 PWM 播放；音符等待使用協作式排程。"""
from machine import Pin, PWM
import uasyncio
import config


class Speaker:
    def __init__(self):
        from ns_tools import NOTE_FREQS
        self.note_freqs = NOTE_FREQS
        self.pwm = PWM(Pin(config.SPEAKER_PIN, Pin.OUT), freq=1000, duty=0)

    async def play_song(self, notes):
        try:
            for note, duration in notes:
                freq = self.note_freqs[note]
                self.silence()
                if freq:
                    self.pwm.freq(freq)
                    self.pwm.duty(config.SPEAKER_DUTY)
                await uasyncio.sleep(duration)
        finally:
            # 正常结束、音符錯誤或協程取消都要停止發聲。
            self.silence()

    def silence(self):
        if self.pwm is not None:
            self.pwm.duty(0)

    def deinit(self):
        if self.pwm is not None:
            try:
                self.silence()
            finally:
                self.pwm.deinit()
                self.pwm = None
