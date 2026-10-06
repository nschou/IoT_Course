"""
hardware/led.py - RGB LED 控制模組
封裝三色 LED 的初始化與控制邏輯
"""

from machine import Pin
import config


class LedBusyError(Exception):
    """警示或關機期間，拒絕一般 LED 指令；不排隊。"""


class RgbLed:
    """
    RGB LED 控制類別
    使用 3 個 GPIO 腳位控制紅、綠、藍三色
    """
    
    def __init__(self):
        """初始化 RGB LED 的三個 Pin"""
        self.red = Pin(config.LED_RED_PIN, Pin.OUT)
        self.green = Pin(config.LED_GREEN_PIN, Pin.OUT)
        self.blue = Pin(config.LED_BLUE_PIN, Pin.OUT)
        self.current_color_index = 0
        self.is_on = False
        self._alert_token = None
        self._saved_state = None
        self._shutdown = False
        self.off()  # 預設關閉
    
    def set_color_by_index(self, index):
        """
        根據 3-bit 索引設定 LED 顏色
        index: 0~7，表示 (Red, Green, Blue) 的組合
        
        例：
            0 (0b000) -> 黑色（全滅）
            1 (0b001) -> 藍色
            2 (0b010) -> 綠色
            3 (0b011) -> 青色
            4 (0b100) -> 紅色
            5 (0b101) -> 紫色
            6 (0b110) -> 黃色
            7 (0b111) -> 白色
        """
        self._require_available()
        index = index % 8  # 確保在 0~7 範圍內
        self._write_output(index)
        self.current_color_index = index
        self.is_on = index != 0

    def _write_output(self, index):
        """僅改 GPIO；警示閃爍不改正常色碼／亮滅狀態。"""
        
        # 使用位元運算提取 R, G, B 狀態
        r = (index >> 2) & 1
        g = (index >> 1) & 1
        b = index & 1
        
        self.red.value(r)
        self.green.value(g)
        self.blue.value(b)
        
    @property
    def alert_active(self):
        return self._alert_token is not None

    @property
    def alert_token(self):
        return self._alert_token

    def _require_available(self):
        if self.alert_active or self._shutdown:
            raise LedBusyError('紅燈警示中，拒絕改色' if self.alert_active else 'LED 已關閉')

    def begin_alert(self):
        """同步取得控制權及快照；沒有 await，不會被其他協程插入。"""
        self._require_available()
        self._saved_state = (self.current_color_index, self.is_on)
        self._alert_token = object()
        return self._alert_token

    def alert_step(self, token, lit):
        if token is None or token is not self._alert_token or self._shutdown:
            return False
        self._write_output(4 if lit else 0)
        return True

    def end_alert(self, token):
        if token is None or token is not self._alert_token or self._shutdown:
            return
        index, is_on = self._saved_state
        try:
            self._write_output(index if is_on else 0)
            self.current_color_index = index
            self.is_on = is_on
        finally:
            self._saved_state = None
            self._alert_token = None

    def shutdown(self):
        """使警示 token 失效；晚到的 finally 不可恢復原色。"""
        self._shutdown = True
        self._alert_token = None
        self._saved_state = None
        self.is_on = False
        self._write_output(0)
    
    def get_color_name(self, index):
        """根據色彩索引取得顏色名稱"""
        return config.COLOR_MAP.get(index % 8, ('未知', 0b000))[0]
    
    def on(self, index=7):
        """打開 LED，設定為指定顏色（預設白色）"""
        self.set_color_by_index(index)
    
    def off(self):
        """熄滅輸出，保留選定色碼，供自動亮燈或下次換色使用。"""
        self._require_available()
        self._write_output(0)
        self.is_on = False
    
    def next_color(self):
        """循環到下一個顏色"""
        next_index = (self.current_color_index + 1) % 8
        self.set_color_by_index(next_index)
        return next_index
    
    def toggle(self):
        """切換開/關狀態"""
        if not self.is_on:
            self.on(self.current_color_index or 7)
        else:
            self.off()
