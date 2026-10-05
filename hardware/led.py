"""
hardware/led.py - RGB LED 控制模組
封裝三色 LED 的初始化與控制邏輯
"""

from machine import Pin
import config


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
        index = index % 8  # 確保在 0~7 範圍內
        
        # 使用位元運算提取 R, G, B 狀態
        r = (index >> 2) & 1
        g = (index >> 1) & 1
        b = index & 1
        
        self.red.value(r)
        self.green.value(g)
        self.blue.value(b)
        
        self.current_color_index = index
        self.is_on = index != 0
    
    def get_color_name(self, index):
        """根據色彩索引取得顏色名稱"""
        return config.COLOR_MAP.get(index % 8, ('未知', 0b000))[0]
    
    def on(self, index=7):
        """打開 LED，設定為指定顏色（預設白色）"""
        self.set_color_by_index(index)
    
    def off(self):
        """熄滅輸出，保留選定色碼，供自動亮燈或下次換色使用。"""
        self.red.value(0)
        self.green.value(0)
        self.blue.value(0)
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
