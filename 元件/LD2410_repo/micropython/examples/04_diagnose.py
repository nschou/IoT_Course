# -*- coding: utf-8 -*-
"""測試 0：接線與 baud rate 診斷（「指令送出去沒有回應」先跑這支）

它會依序檢查：
    1. 目前 baud 下，模組有沒有在送資料（代表 TX/RX 至少一個方向通）
    2. 目前 baud 下，送「進入設定模式」指令有沒有 ACK
    3. 若失敗，自動換 9600 / 19200 / 38400 / 57600 / 115200 / 230400 /
       256000 / 460800 再試，並印出收到的前 12 個位元組

不會修改模組任何設定。
"""

from hardware.ld2410c import LD2410C

# ==== 接線設定（改腳位只要改這裡）====
UART_ID = 1
TX_PIN = 15      # ESP32 GPIO15 (UART TX)  -> 模組 Pin4 UART_RX
RX_PIN = 16      # ESP32 GPIO16 (UART RX)  <- 模組 Pin5 UART_TX
OUT_PIN = 14     # 模組 Pin3 OUT -> ESP32 GPIO14（選用）
BAUD = 115200

radar = LD2410C(uart_id=UART_ID, tx=TX_PIN, rx=RX_PIN,
                baudrate=BAUD, out_pin=OUT_PIN)

print("=== LD2410C 接線 / baud rate 診斷 ===")
print("本程式使用的腳位（要改請改檔案上方的常數）：")
print("  模組 Pin1 VCC      -> ESP32 5V/VIN（要 5V，電流 >200mA）")
print("  模組 Pin2 GND      -> ESP32 GND（一定要共地）")
print("  模組 Pin3 OUT      -> ESP32 GPIO%d（選用）" % OUT_PIN)
print("  模組 Pin4 UART_RX  <- ESP32 GPIO%d（UART1 TX）" % TX_PIN)
print("  模組 Pin5 UART_TX  -> ESP32 GPIO%d（UART1 RX）" % RX_PIN)
print("")

result = radar.diagnose(verbose=True)

print("")
print("----------- 診斷結果 -----------")
if result["ok"] and result["data_ok"]:
    print("正常：baud = %d，資料流與指令通道都在工作" % result["found_baud"])
    print("請把程式裡的 baudrate 設成 %d" % result["found_baud"])
elif result["ok"]:
    print("指令通道正常（baud = %d），但這 0.5 秒內沒收到資料流："
          % result["found_baud"])
    print("  * 模組可能還停在設定模式（0x00FF 之後沒收到 0x00FE）")
    print("  * 或資料輸出被關掉；請先跑 02_read_params.py 看能不能讀參數")
elif result["data_ok"]:
    print("看得到資料流，但指令沒有 ACK：")
    print("  * 大多是 GND 沒接好、或模組正在連續輸出時漏掉指令")
    print("  * 本驅動已自動重送 6 次；若仍失敗，請檢查模組 RX 那條線")
    print("  * 也確認 baud 與模組現在的設定一致（目前 %d）" % radar.baudrate)
else:
    print("完全收不到任何東西：")
    print("  * 模組是否供電 5V、有沒有發熱/指示")
    print("  * TX/RX 是否交叉、杜邦線是否鬆脫")
    print("  * 上面的 raw 若是 00 或亂碼，代表 baud 不對（模組可能還是 256000）")
    print("  * 用手機 App（HLKRadarTool）看得到模組，代表模組本身正常")

if result["scan"]:
    print("")
    print("其他 baud 的嘗試結果：")
    for entry in result["scan"]:
        print("  %6d: %d 個資料封包, 指令 %s, 前 12 bytes: %s"
              % (entry["baud"], entry["frames"],
                 "OK" if entry["cmd_ok"] else "無",
                 entry["raw"] or "-"))
