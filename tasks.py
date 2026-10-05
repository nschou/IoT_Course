"""
tasks.py - 非同步任務協程（修正版 v1.1.3）
已整合 aiot_tools 和 ns_tools 的時間函數
修正：OLED 顯示搬到 hardware.display，並修正 NoneType 錯誤
"""

import uasyncio
import config
from hardware.led import RgbLed
from hardware.button import Button
from hardware.sensors import Dht11Sensor, LightSensor
from hardware.display import OledDisplay
from communication.wifi import get_current_time


# ==================== 任務：按鈕監聽 ====================

async def button1_task(button1, rgb_led, publish_event):
    """
    按鈕 1 監聽任務
    功能：按下按鈕1時，循環切換 LED 顏色
    """
    button_id = 1
    print(f"[Task] 按鈕 {button_id} 監聽已啟動")

    while True:
        try:
            await button1.wait_press()
            print(f"[Button] 按鈕 {button_id} 被按下")

            next_color = rgb_led.next_color()
            color_name = rgb_led.get_color_name(next_color)
            print(f"[LED] 顏色改變為: {color_name} (索引: {next_color})")

            await button1.wait_release()
            print(f"[Button] 按鈕 {button_id} 被釋放")

            await uasyncio.sleep_ms(100)
        except Exception as e:
            print(f"[Error] 按鈕 {button_id} 任務異常: {e}")
            await uasyncio.sleep(1)


async def button2_task(button2, dht_sensor, mqtt_manager, publish_event):
    """
    按鈕 2 監聽任務
    功能：按下按鈕2時，讀取溫濕度並透過 MQTT 發佈
    """
    button_id = 2
    print(f"[Task] 按鈕 {button_id} 監聽已啟動")

    while True:
        try:
            await button2.wait_press()
            print(f"[Button] 按鈕 {button_id} 被按下")

            publish_event.set()
            print("[Task] 觸發溫濕度發佈事件")

            await button2.wait_release()
            print(f"[Button] 按鈕 {button_id} 被釋放")

            await uasyncio.sleep_ms(100)
        except Exception as e:
            print(f"[Error] 按鈕 {button_id} 任務異常: {e}")
            await uasyncio.sleep(1)


# ==================== 任務：感測器讀取 ====================

async def dht11_read_task(dht_sensor):
    """
    DHT11 溫濕度讀取任務
    定期讀取溫濕度，並儲存最新資料供其他任務使用
    """
    print("[Task] DHT11 讀取任務已啟動")

    while True:
        try:
            result = dht_sensor.measure()
            if result:
                temp, humi = result
                #print(f"[DHT11] 溫度: {temp}℃, 濕度: {humi}%")
            else:
                print("[DHT11] 量測失敗，使用上次資料")

            await uasyncio.sleep(config.DHT11_POLL_INTERVAL_SEC)
        except Exception as e:
            print(f"[Error] DHT11 任務異常: {e}")
            await uasyncio.sleep(config.DHT11_POLL_INTERVAL_SEC)


async def light_sensor_task(light_sensor, rgb_led):
    """
    光感測器讀取任務
    持續讀取亮度；只有啟用 LIGHT_AUTO_CONTROL_ENABLED 時才自動控制 LED。
    預設不覆寫按鈕／網頁選定的顏色。
    """
    print("[Task] 光感測器任務已啟動")

    while True:
        try:
            brightness = light_sensor.read()

            if config.LIGHT_AUTO_CONTROL_ENABLED:
                if brightness < config.LIGHT_THRESHOLD_ON:
                    rgb_led.on(rgb_led.current_color_index)
                elif brightness > config.LIGHT_THRESHOLD_OFF:
                    rgb_led.off()

            await uasyncio.sleep_ms(config.LIGHT_POLL_INTERVAL_MS)
        except Exception as e:
            print(f"[Error] 光感測器任務異常: {e}")
            await uasyncio.sleep_ms(config.LIGHT_POLL_INTERVAL_MS)


# ==================== 任務：顯示更新 ====================

async def rfid_read_task(rfid_reader, rfid_state):
    """唯一讀卡者：500 ms 輪詢，將最後成功結果提供給 Web API。"""
    if rfid_reader is None:
        print("[Task] RFID 未初始化，跳過讀卡任務")
        return
    print("[Task] RFID 讀卡任務已啟動")
    while True:
        try:
            uid = await rfid_reader.read_uid()
            if uid is not None:
                date_str, weekday_str, time_str = get_current_time()
                # 更新期間沒有 await；協作式排程下 API 不會讀到半份紀錄。
                rfid_state['last_uid'] = uid
                rfid_state['last_read_at'] = '{} {}'.format(date_str, time_str)
                rfid_state['status'] = 'ready'
                rfid_state['error'] = None
                print('RFID：', uid)
            # 無卡不清除最後紀錄；錯誤只在下一次成功讀卡後解除。
        except Exception as e:
            rfid_state['status'] = 'read_error'
            rfid_state['error'] = str(e)
            print(f"[Error] RFID 讀卡異常: {e}")
        await uasyncio.sleep_ms(config.RFID_POLL_INTERVAL_MS)


async def oled_display_task(dht_sensor):
    """
    OLED 顯示更新任務（修正版）
    每秒更新 OLED 螢幕，顯示時間、溫濕度等資訊

    功能：
    • 第一行：日期、星期、時間
    • 第二行：溫度、濕度
    使用 hardware.display.OledDisplay 負責硬體初始化
    """
    print("[Task] OLED 顯示任務已啟動")

    oled = None
    try:
        oled = OledDisplay()
        print("[OLED] 初始化成功（由 hardware.display 管理）")
    except Exception as e:
        print(f"[OLED] 初始化失敗: {e}")
        print("[OLED] 使用簡化模式（只輸出日誌）")
        oled = None

    while True:
        try:
            # 取得時間與溫溼度
            date_str, weekday_str, time_str = get_current_time()
            temp, humi = dht_sensor.get_data()

            # 防呆：避免 NoneType 傳到字型庫
            date_str = "" if date_str is None else str(date_str)
            weekday_str = "" if weekday_str is None else str(weekday_str)
            time_str = "" if time_str is None else str(time_str)

            temp = 0 if temp is None else temp
            humi = 0 if humi is None else humi

            line1 = f"{date_str} 週{weekday_str} {time_str[:5]}"
            line2 = f"溫度：{temp}℃ 濕度：{humi}%"

            if oled is not None:
                try:
                    oled.show_two_lines(line1, line2)
                except Exception as e:
                    print(f"[OLED] 顯示更新異常: {e}")

            #print(f"[Display] {line1} | 溫: {temp}℃ 濕: {humi}%")

            await uasyncio.sleep(1)
        except Exception as e:
            print(f"[Error] OLED 顯示任務異常: {e}")
            await uasyncio.sleep(1)


# ==================== 任務：MQTT 發佈 ====================

async def mqtt_publish_task(dht_sensor, mqtt_manager, publish_event):
    """
    MQTT 發佈任務
    監聽 publish_event，在事件觸發時發佈溫濕度訊息
    """
    print("[Task] MQTT 發佈任務已啟動")

    await mqtt_manager.wait_connected()
    print("[MQTT Pub] 已連線，開始監聽發佈事件")

    while True:
        try:
            await publish_event.wait()

            temp, humi = dht_sensor.get_data()
            temp = 0 if temp is None else temp
            humi = 0 if humi is None else humi

            message = f'{config.DEVICE_NAME}：溫度：{temp}℃, 濕度：{humi}%'

            success = await mqtt_manager.publish(
                config.MQTT_TOPICS['temp_humi'],
                message,
                qos=0
            )

            if success:
                print(f"[MQTT Pub] 溫濕度已發佈: {message}")
            else:
                print("[MQTT Pub] 發佈失敗")

            publish_event.clear()
            await uasyncio.sleep_ms(100)
        except Exception as e:
            print(f"[Error] MQTT 發佈任務異常: {e}")
            await uasyncio.sleep(1)


# ==================== 任務：MQTT 訂閱與指令處理 ====================

async def mqtt_subscribe_task(mqtt_manager, rgb_led):
    """
    MQTT 訂閱與指令處理任務
    監聽 MQTT 訂閱的訊息，並根據指令控制裝置
    """
    print("[Task] MQTT 訂閱任務已啟動")

    await mqtt_manager.wait_connected()
    print("[MQTT Sub] 已連線，開始監聽指令")

    async def handle_cmd(msg):
        try:
            msg_str = msg.decode() if isinstance(msg, bytes) else msg
            print(f"[MQTT Sub] 收到指令: {msg_str}")

            if 'led' in msg_str.lower():
                try:
                    led_value = int(msg_str.split(':')[-1].split('=')[-1].strip())
                    rgb_led.set_color_by_index(led_value)
                    color = rgb_led.get_color_name(led_value)
                    print(f"[LED] 已設定為: {color}")
                except ValueError:
                    print("[MQTT Sub] 指令解析失敗（無效索引）")
                except Exception as e:
                    print(f"[MQTT Sub] 指令解析異常: {e}")
        except Exception as e:
            print(f"[Error] 指令處理異常: {e}")

    await mqtt_manager.subscribe(
        config.MQTT_TOPICS['cmd'],
        qos=0,
        callback=handle_cmd
    )

    while True:
        await uasyncio.sleep(10)
