"""
main.py - 主程式進入點（修正版 v1.2 - 含 Web Server）
已整合 aiot_tools.py、ns_tools.py、mqtt_as 和 Microdot Web Server
"""

import uasyncio
import sys

# 導入配置與模組
import config
from hardware.led import RgbLed
from hardware.button import Button
from hardware.sensors import Dht11Sensor, LightSensor
from hardware.display import OledDisplay
from hardware.rfid import RfidReader, new_rfid_state
from communication.mqtt_client import MqttManager

# 導入修正後的 WiFi 模組
from communication.wifi import connect_wifi, sync_time, get_current_time

# 導入任務
import tasks

# 導入 Web Server
import web_server


# ==================== 系統初始化 ====================

async def initialize_system():
    """
    初始化系統的所有硬體與通訊模組
    返回: LED、按鈕、感測器、MQTT、RFID 物件與 RFID 共享狀態元組
    """
    print("\n" + "="*60)
    print("系統初始化")
    print("="*60 + "\n")
    
    # 1. 初始化硬體
    print("[Init] 初始化 RGB LED...")
    rgb_led = RgbLed()
    rgb_led.on(7)  # 白色指示燈
    
    print("[Init] 初始化按鈕...")
    button1 = Button(config.BUTTON1_PIN)
    button2 = Button(config.BUTTON2_PIN)
    
    print("[Init] 初始化感測器...")
    dht_sensor = Dht11Sensor()
    light_sensor = LightSensor()
    
    # 初次測量
    dht_sensor.measure()

    print("[Init] 初始化 RFID...")
    rfid_state = new_rfid_state()
    rfid_reader = None
    try:
        rfid_reader = RfidReader()
        rfid_state['status'] = 'ready'
    except Exception as e:
        rfid_state['status'] = 'init_error'
        rfid_state['error'] = str(e)
        print(f"[RFID] 初始化失敗: {e}，其他功能繼續運行")
    
    print("[Init] 硬體初始化完成\n")
    
    # 2. WiFi 連線
    ssid, password = await connect_wifi()
    
    # 3. 時間同步
    await sync_time()
    
    # 4. 初始化 MQTT
    print("[Init] 初始化 MQTT 客戶端...")
    mqtt_manager = MqttManager(ssid, password, broker='broker.emqx.io')
    
    mqtt_connected = False
    for attempt in range(1, 4):
        print(f"[Init] MQTT 連線嘗試 {attempt}/3...")
        try:
            if await mqtt_manager.connect():
                mqtt_connected = True
                print("[Init] MQTT 連線成功")
                break
        except Exception as e:
            print(f"[Init] MQTT 連線異常: {e}")
        
        if attempt < 3:
            await uasyncio.sleep(2)
    
    if not mqtt_connected:
        print("[Init] ⚠️ MQTT 連線失敗，但繼續運行（其他功能仍可用）")
    
    print("[Init] 系統初始化完成\n")
    
    return (rgb_led, button1, button2, dht_sensor, light_sensor,
            mqtt_manager, rfid_reader, rfid_state)


# ==================== 主非同步函式 ====================

async def main():
    """
    主程式：初始化系統並啟動所有協程
    """
    # 初始化系統
    (rgb_led, button1, button2, dht_sensor, light_sensor,
     mqtt_manager, rfid_reader, rfid_state) = await initialize_system()
    
    # 建立任務間通訊事件
    publish_event = uasyncio.Event()
    
    # 初始化 Web Server 的全局變數
    web_server.mqtt_manager = mqtt_manager
    web_server.publish_event = publish_event
    web_server.dht_sensor = dht_sensor
    web_server.rgb_led = rgb_led
    web_server.light_sensor = light_sensor
    web_server.rfid_state = rfid_state
    
    try:
        print("[Main] 啟動所有協程...\n")
        
        # 使用 asyncio.gather() 同時啟動所有任務
        await uasyncio.gather(
            # 按鈕監聽任務
            tasks.button1_task(button1, rgb_led, publish_event),
            tasks.button2_task(button2, dht_sensor, mqtt_manager, publish_event),
            
            # 感測器讀取任務
            tasks.dht11_read_task(dht_sensor),
            tasks.light_sensor_task(light_sensor, rgb_led),
            tasks.rfid_read_task(rfid_reader, rfid_state),
            
            # 顯示與通訊任務
            tasks.oled_display_task(dht_sensor),
            tasks.mqtt_publish_task(dht_sensor, mqtt_manager, publish_event),
            tasks.mqtt_subscribe_task(mqtt_manager, rgb_led),
            
            # Web Server 任務
            web_server.web_server_task(),
            web_server.sensor_monitor_task(),
        )
    
    except KeyboardInterrupt:
        print("\n[Main] 程式被使用者中斷")
        rgb_led.off()
    
    except Exception as e:
        print(f"\n[Error] 主程式異常: {e}")
        print("[Error] 進行緊急清理...")
        rgb_led.off()
        try:
            await mqtt_manager.disconnect()
        except:
            pass
        raise


# ==================== 程式進入點 ====================

if __name__ == '__main__':
    print("\n")
    print("╔" + "═"*58 + "╗")
    print("║" + " "*12 + "IoT 教學專案 - ESP32 多感測器系統" + " "*12 + "║")
    print("║" + " "*15 + "含 Web Server (Microdot)" + " "*19 + "║")
    print("╚" + "═"*58 + "╝")
    print("\n")
    
    try:
        # 執行主程式
        uasyncio.run(main())
    
    except Exception as e:
        print(f"\n[Fatal Error] 致命錯誤: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n[Shutdown] 程式結束\n")
