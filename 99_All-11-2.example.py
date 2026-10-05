from machine import Pin, ADC, I2C, PWM
from ssd1306 import SSD1306_I2C
from aiot_tools import *
from ns_tools import *
from mfrc522_async import MFRC522Async
import time, dht
import uasyncio as asyncio
from bitmap_font_tool import set_font_path, draw_text
from mqtt_as import MQTTClient, config

# =================== 常數 ===================
LED_PINS = {'rpin': 37, 'gpin': 35, 'bpin': 33}
BTN_PINS = [17, 21]
PIR_PIN = 4
SPEAKER_PIN = 6
DHT_PIN = 18
TEMT_PIN = 8
OLED_I2C_PINS = {'scl': 7, 'sda': 5}
I2C_ID = 0

LIGHT_ON = 800
LIGHT_OFF = 1200

WIFI_PROFILES = {
    'YOUR_WIFI_SSID': 'YOUR_WIFI_PASSWORD',
}

MQTT_TOPICS = {
    'cmd': b"nuu/csie/iot1133/cmd01",
    'temp_humi': b"nuu/csie/iot1133/TempHumi",
    'all': b"nuu/csie/iot1133/#",
}

# =================== 硬體封裝 ===================
class RGBLED:
    def __init__(self, rpin, gpin, bpin):
        self.leds = [Pin(rpin, Pin.OUT), Pin(gpin, Pin.OUT), Pin(bpin, Pin.OUT)]
    def set(self, code):
        for i in range(3):
            self.leds[2 - i].value((code >> i) & 1)
    def off(self):
        for led in self.leds:
            led.value(0)

class Speaker:
    def __init__(self, pin):
        self.pwm = PWM(Pin(pin, Pin.OUT))
        self.duty_val = 512
        self.pwm.duty(0)
        self.pwm.freq(1000)
    def play_note(self, freq, duration=0.5):
        if freq == 0:
            self.pwm.duty(0)
        else:
            self.pwm.duty(self.duty_val)
            self.pwm.freq(freq)
        if duration<=5:
            time.sleep(duration)
        else:
            time.sleep_ms(duration)
        self.pwm.duty(0)
    def play_song(self, notes):
        play_song(self.pwm, notes)
    def deinit(self):
        self.pwm.deinit()

class SensorManager:
    def __init__(self, temt_pin, pir_pin, dht_pin):
        self.temt = ADC(Pin(temt_pin))
        self.pir = Pin(pir_pin, Pin.IN)
        self.dht11 = dht.DHT11(Pin(dht_pin))
    def read_light(self):
        return self.temt.read()
    def is_motion(self):
        return self.pir.value()
    def read_dht(self):
        self.dht11.measure()
        return self.dht11.temperature(), self.dht11.humidity()

class OLEDUnit:
    def __init__(self, i2c_id, scl, sda):
        set_font_path('./lib/fonts/fusion_bdf.12')
        i2c = I2C(i2c_id, scl=Pin(scl), sda=Pin(sda))
        self.oled = SSD1306_I2C(128, 64, i2c)
    def show(self, text_lines):
        self.oled.fill(0)
        for i, txt in enumerate(text_lines):
            draw_text(self.oled, txt, 0, 16 * i)
        self.oled.show()

# =================== 主控制 ===================
class IoTSystem:
    def __init__(self):
        set_font_path('./lib/fonts/fusion_bdf.12')
        self.led = RGBLED(**LED_PINS)
        self.speaker = Speaker(SPEAKER_PIN)
        self.sensors = SensorManager(TEMT_PIN, PIR_PIN, DHT_PIN)
        self.oled = OLEDUnit(I2C_ID, **OLED_I2C_PINS)
        self.rfid = MFRC522Async(sck=12, mosi=11, miso=10, rst=9, cs=13)
        self.temp, self.humi = 0, 0
        self.temp_humi_str = ''
        #self.pub_flag = asyncio.Event()
        self.mov_flag = asyncio.Event()
        self.client = self.mqtt_client_init()
        self.cnt = 0            # LED模式代碼（0～7）
        self.prev_led_state = None

    def mqtt_client_init(self):
        [ssid, pwd] = connect_to_known_wifi(WIFI_PROFILES)
        mySetTime()  # 執行時間同步
        config['ssid'] = ssid
        config['wifi_pw'] = pwd
        config['server'] = 'broker.emqx.io'
        config['subs_cb'] = self.on_msg
        config['connect_coro'] = self.on_connected
        MQTTClient.DEBUG = True
        return MQTTClient(config)
    
    # --- 事件/回調 ---
    def button1_cb(self, id, pinNo):
        self.cnt = (self.cnt + 1) % 8
        print(f"按鈕1 +1: {self.cnt}")

    def button2_cb(self, id, pinNo):
        self.temp_humi_str = f'周念湘：溫度：{self.temp}℃, 濕度：{self.humi}%'
        print(self.temp_humi_str)
        #self.pub_flag.set()
        # 直接發佈(在同步函數中使用非同步的範例)，不用 pub_flag
        asyncio.create_task(self.client.publish(
            MQTT_TOPICS['temp_humi'],
            self.temp_humi_str.encode(),
            qos=1
        ))

    def on_msg(self, topic, msg, retained, properties=None):
        msgStr = msg.decode()
        if topic == MQTT_TOPICS['cmd']:
            print(f'MQTT： Cmd to ESP32: {topic} -- {msgStr}')
        elif topic == MQTT_TOPICS['temp_humi']:
            print(f'MQTT： DHT11 from ESP32: {msgStr}')

    async def on_connected(self, client):
        print(f"MQTT broker連線成功")
        await client.subscribe(MQTT_TOPICS['all'], 1)

    async def monitor_light(self):
        while True:
            light_adc = self.sensors.read_light()
            # 太暗時根據cnt點燈，否則全滅
            if light_adc < LIGHT_ON:
                self.led.set(self.cnt)
            elif light_adc > LIGHT_OFF:
                self.led.off()
            await asyncio.sleep_ms(100)

    async def monitor_rfid(self):
        while True:
            stat, tag_type = await self.rfid.request(self.rfid.REQIDL)
            if stat == self.rfid.OK:
                stat, raw_uid = await self.rfid.anticoll()
                if stat == self.rfid.OK:
                    id_str = to_hex_string(raw_uid)
                    print('RFID：', id_str)
            await asyncio.sleep_ms(500)
    
    async def monitor_dht(self):
        while True:
            self.temp, self.humi = self.sensors.read_dht()
            await asyncio.sleep(2)

    async def show_status(self):
        while True:
            date_str, weekday_str, time_str = get_time()
            self.oled.show([
                f'{date_str} {weekday_str}  {time_str[:5]}',
                f'溫度：{self.temp}℃ 濕度：{self.humi}%'
            ])
            await asyncio.sleep(1)

    async def monitor_move(self):
        while True:
            if self.sensors.is_motion():
                self.mov_flag.set()
            await asyncio.sleep_ms(500)

    async def music_on_motion(self):
        NOTES_0 = [('C4', 0.3), ('E4', 0.3), ('D4', 0.3), ('G3', 0.3), ('REST', 0.2)]
        while True:
            if self.mov_flag.is_set():
                self.mov_flag.clear()
                #self.speaker.play_note(523, 0.3)  # C5
                #self.speaker.play_song(NOTES_0)
                play_song(self.speaker.pwm, NOTES_0)
            await asyncio.sleep_ms(500)

    async def main(self):
        dbbtn1 = DebouncedButton(BTN_PINS[0], id=1, on_click=self.button1_cb)
        dbbtn2 = DebouncedButton(BTN_PINS[1], id=2, on_click=self.button2_cb)
        try:
            await self.client.connect()
            await asyncio.gather(
                self.monitor_dht(),
                self.monitor_light(),
                self.show_status(),
                self.monitor_rfid(),
                self.monitor_move(),
                self.music_on_motion()
            )
        except Exception as e:
            print("主協程錯誤:", e)
            self.led.off()
            raise

# ================ 主程式區 ====================
if __name__ == "__main__":
    system = IoTSystem()    
    try:
        asyncio.run(system.main())
    except KeyboardInterrupt:
        system.led.off()
        system.speaker.deinit()
        print("程式被強行中斷...")
