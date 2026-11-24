# -*- coding: utf-8 -*-
"""測試 1：讀取距離與目標狀態（ESP32 + HLK-LD2410C）

接線（本專案實測配置）：
    模組 Pin1 VCC      -> ESP32 5V/VIN   (模組要 5V，電流 >200mA)
    模組 Pin2 GND      -> ESP32 GND
    模組 Pin3 OUT      -> ESP32 GPIO14
    模組 Pin4 UART_RX  <- ESP32 GPIO15 (UART1 TX)
    模組 Pin5 UART_TX  -> ESP32 GPIO16 (UART1 RX)

模組出廠 baud 是 256000，但很多 USB-轉-COM 驅動找不到這個速率，
本模組已用手機 App（HLKRadarTool）改成 115200。
若你的模組還是出廠值，把下面 baudrate 改成 256000，或先跑 04_diagnose.py。
"""

import time
from hardware.ld2410c import LD2410C

# ==== 接線設定（改腳位只要改這裡）====
UART_ID = 1
TX_PIN = 15      # ESP32 GPIO15 (UART TX)  -> 模組 Pin4 UART_RX
RX_PIN = 16      # ESP32 GPIO16 (UART RX)  <- 模組 Pin5 UART_TX
OUT_PIN = 14     # 模組 Pin3 OUT -> ESP32 GPIO14（選用）
BAUD = 115200

radar = LD2410C(uart_id=UART_ID, tx=TX_PIN, rx=RX_PIN,
                baudrate=BAUD, out_pin=OUT_PIN)

print("=== LD2410C 距離測試 ===")
print("等待資料流（沒有畫面就是接線或 baud 不對，請跑 04_diagnose.py）")

# 工程模式會多送出每個距離門的能量值，斷電後失效，所以每次開機都要重開。
try:
    radar.engineering(True)
    print("工程模式：已開啟（可看到 9 個距離門的能量）")
except Exception as error:
    print("工程模式開啟失敗：", error)

last_print = time.ticks_ms()
last_gate_print = time.ticks_ms()

while True:
    frame = radar.poll()
    if frame is None:
        continue

    now = time.ticks_ms()
    if time.ticks_diff(now, last_print) < 200:   # 每秒最多印 5 次
        continue
    last_print = now

    if frame["presence"]:
        state = frame["state_name"]
        print("--------------------------------------------------")
        print("狀態: %-18s 距離: %3d cm" % (state, frame["distance_cm"]))
        print("移動目標: %3d cm 能量 %3d    靜止目標: %3d cm 能量 %3d"
              % (frame["moving_cm"], frame["moving_energy"],
                 frame["stationary_cm"], frame["stationary_energy"]))
        out = radar.out_level()
        print("偵測距離(原始): %3d cm   OUT: %s   光敏: %s"
              % (frame["detection_cm"], "HIGH" if out else "LOW",
                 frame["light"]))
        bar = frame["distance_cm"] * 40 // 600
        if bar > 40:
            bar = 40
        print("距離 |" + "#" * bar + "." * (40 - bar) + "| 0~6 m")
    else:
        print("無人 (最近封包 %d ms 前)" % radar.age_ms())

    # 能量分佈不需要每次都印，一秒一次就好
    if (frame["engineering"]
            and time.ticks_diff(now, last_gate_print) > 1000):
        last_gate_print = now
        print("門能量 移動:", list(frame["moving_gates"]))
        print("門能量 靜止:", list(frame["stationary_gates"]))
