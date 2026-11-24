"""
config.py - 全域配置文件
集中管理所有硬體腳位、MQTT 設定、WiFi 設定等
"""

# ==================== 硬體腳位配置 ====================

# LED 腳位配置（GPIO）
LED_RED_PIN = 37
LED_GREEN_PIN = 35
LED_BLUE_PIN = 33

# 按鈕腳位配置（GPIO）
BUTTON1_PIN = 17
BUTTON2_PIN = 21

# 感測器腳位配置
DHT11_PIN = 18
TEMT_ADC_PIN = 8
PIR_PIN = 4
SPEAKER_PIN = 6

# I2C 配置（OLED）
I2C_ID = 0
I2C_SCL_PIN = 7
I2C_SDA_PIN = 5
OLED_WIDTH = 128
OLED_HEIGHT = 64

# SPI 配置（RFID）
RFID_SCK_PIN = 12
RFID_MOSI_PIN = 11
RFID_MISO_PIN = 10
RFID_RST_PIN = 9
RFID_CS_PIN = 13

# LD2410B 毫米波雷達（UART 115200 8N1；TX/RX 需與模組交叉；出廠預設 256000）
# 板子：ESP32-S2 Mini（GPIO 33-40 引出；26-32 為 flash/PSRAM，不可用）
#   GPIO36 = ESP32 TX  -> 模組 RX
#   GPIO38 = ESP32 RX  <- 模組 TX
#   GPIO40 = OUT（模組推挽輸出）
# 注意：S2 的 GPIO39-42 預設為 JTAG 腳；GPIO40(MTDO) 當輸入可用，但不要同時接 JTAG 除錯器。
#      若 OUT 讀值不穩，可改接 GPIO34（目前未被其他裝置使用）。
LD2410B_UART_ID = 1
LD2410B_TX_PIN = 36
LD2410B_RX_PIN = 38
LD2410B_OUT_PIN = 40
LD2410B_OUT_ACTIVE_HIGH = True    # OUT 電位極性；模組為推挽輸出，有人時為高電位
LD2410B_BAUDRATE = 115200

# 獨居長者照護規則（apps/elder_care/radar_care.py）
RADAR_CARE_MOVE_ENERGY_MIN = 25        # 判定「有活動」的移動能量門檻 0-100
RADAR_CARE_MOVE_SESSION_GAP_MS = 60000  # 相隔多久才算新的一次活動（去抖）
RADAR_CARE_INACTIVITY_SECONDS = 1800   # 連續無活動多久告警（30 分鐘）
RADAR_CARE_AWAY_SECONDS = 10800        # 連續無人在房多久告警（3 小時）
RADAR_CARE_BED_MIN_CM = 25             # 床鋪距離範圍（cm）
RADAR_CARE_BED_MAX_CM = 120
RADAR_CARE_BED_EXIT_SECONDS = 600      # 離床後多久未回床告警（10 分鐘）
RADAR_CARE_NIGHT_START_HOUR = 22       # 夜間時段
RADAR_CARE_NIGHT_END_HOUR = 6
RADAR_CARE_NIGHT_LIGHT_MAX_ADC = 1100  # 低於此光感值視為昏暗
RADAR_CARE_NIGHT_LIGHT_SECONDS = 60    # 夜燈持續時間

# 床鋪監測（apps/elder_care/bed_monitor.py）
RADAR_BED_MIN_CM = 60             # 躺著時的距離帶下限（校準後填入）
RADAR_BED_MAX_CM = 180            # 距離帶上限
RADAR_BED_TURN_ENERGY_MIN = 60    # 翻身判定的移動能量門檻
RADAR_BED_TURN_DEBOUNCE_MS = 3000 # 翻身去抖，避免一次翻身算多次
RADAR_BED_SIT_UP_DELTA_CM = 25    # 距離相對基線改變多少視為坐起
RADAR_BED_EXIT_CONFIRM_MS = 5000  # 距離帶要空多久才算離床
RADAR_BED_RETURN_CONFIRM_MS = 3000 # 回到距離帶要待多久才算回床
RADAR_BED_FLOOR_MIN_CM = 225     # 地板距離帶下限（天花板安裝時，躺地板約 230-250 cm）
RADAR_BED_FLOOR_MAX_CM = 255
RADAR_BED_FLOOR_NOTICE_MS = 30000    # 停在地板 30 秒：輕提示
RADAR_BED_FLOOR_ALERT_MS = 120000    # 2 分鐘：告警
RADAR_BED_FLOOR_CRITICAL_MS = 600000 # 10 分鐘：升級告警



# ==================== 感測器參數 ====================

# 光感測器閾值
# LED 控制模式：AUTO 允許光感低光警示；MANUAL 不由光感覆蓋使用者命令
LED_CONTROL_MODE = 'AUTO'
LIGHT_ALERT_ENABLED = True
LIGHT_ALERT_TRIGGER_ADC = 1000  # 嚴格低於此值觸發一次
LIGHT_ALERT_RESET_ADC = 1100    # 回升至此值以上才允許下一次
LIGHT_ALERT_BLINK_COUNT = 5
LIGHT_ALERT_ON_MS = 300
LIGHT_ALERT_OFF_MS = 300
LIGHT_POLL_INTERVAL_MS = 50    # 光感測輪詢間隔

# DHT11 量測間隔
DHT11_POLL_INTERVAL_SEC = 2

# OLED 更新間隔
OLED_UPDATE_INTERVAL_SEC = 1

# RFID 讀卡間隔（避免反應過快）
RFID_POLL_INTERVAL_MS = 500

# PIR 移動提示：每次低→高觸發，音符時間單位為秒
PIR_POLL_INTERVAL_MS = 100
PIR_HIGH_DEBOUNCE_MS = 200
PIR_LOW_REARM_MS = 1500
MOTION_DETECTED_HOLD_MS = 5000  # 網頁狀態顯示保持時間，不是PIR去重時間
SPEAKER_DUTY = 512
MOTION_MELODY = (('C4', 0.3), ('E4', 0.3), ('D4', 0.3),
                 ('G3', 0.3), ('REST', 0.2))

# 按鈕去彈跳時間
BUTTON_DEBOUNCE_MS = 20         # 按鈕穩定判定時間
BUTTON_POLL_INTERVAL_MS = 30    # 按鈕輪詢間隔

# ==================== WiFi 配置 ====================

# 已知 WiFi 網路清單（SSID: 密碼）
WIFI_PROFILES = {
    'YOUR_WIFI_SSID': 'YOUR_WIFI_PASSWORD',
}

# 時區設定（UTC+8 for Taiwan）
TIMEZONE_OFFSET_SEC = 8 * 3600

# ==================== MQTT 配置 ====================

# MQTT Broker 設定
MQTT_BROKER = 'broker.emqx.io'
MQTT_PORT = 1883

# MQTT Topic 配置
MQTT_TOPICS = {
    'cmd': b'nuu/csie/iot1133/cmd01',           # 接收指令
    'temp_humi': b'nuu/csie/iot1133/TempHumi',  # 發佈溫濕度
    'subscribe': b'nuu/csie/iot1133/#',         # 訂閱所有
}

# MQTT 重連設定
MQTT_RECONNECT_INITIAL_DELAY_SEC = 2     # 初始重連延遲
MQTT_RECONNECT_MAX_DELAY_SEC = 60        # 最大重連延遲
MQTT_RECONNECT_BACKOFF_FACTOR = 1.5      # 指數退避因子

# ==================== 字體配置 ====================

FONT_PATH = './lib/fonts/fusion_bdf.12'

# ==================== 顏色對應 ====================

# RGB LED 8 色對應 (3-bit: RGB)
COLOR_MAP = {
    0: ('黑', 0b000),
    1: ('藍', 0b001),
    2: ('綠', 0b010),
    3: ('青', 0b011),
    4: ('紅', 0b100),
    5: ('紫', 0b101),
    6: ('黃', 0b110),
    7: ('白', 0b111),
}

# ==================== 裝置識別 ====================

DEVICE_NAME = '周念湘的 IoT 裝置'
DEVICE_ID = 'iot1133'
