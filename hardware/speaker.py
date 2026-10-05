"""無源喇叭 PWM 播放；音符等待使用協作式排程。"""
from machine import Pin, PWM
import uasyncio
import config


class Speaker:
    def __init__(self):
        # 只需 machine/uasyncio；避免為音符表載入整套網路與 NTP 工具。
        self.note_freqs = {'C4': 262, 'E4': 330, 'D4': 294, 'G3': 196, 'REST': 0}
        pin = getattr(config, 'SPEAKER_PIN', 6)
        self.pwm = PWM(Pin(pin, Pin.OUT))
        try:
            self.pwm.duty(0)
            self.pwm.freq(1000)
        except BaseException:
            self.pwm.deinit()
            self.pwm = None
            raise
        print(f'[Speaker] PWM 初始化成功，GPIO={pin}')

    async def play_song(self, notes):
        try:
            for note, duration in notes:
                freq = self.note_freqs[note]
                self.silence()
                if freq:
                    self.pwm.freq(freq)
                    self.pwm.duty(getattr(config, 'SPEAKER_DUTY', 512))
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
