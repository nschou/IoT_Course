# -*- coding: utf-8 -*-
"""測試 2：讀取模組參數（固件版本、距離門、靈敏度、無人延遲、解析度）

這個程式只讀不寫，可以安心執行。
"""

from hardware.ld2410c import LD2410C, check_params

# ==== 接線設定（改腳位只要改這裡）====
UART_ID = 1
TX_PIN = 15      # ESP32 GPIO15 (UART TX)  -> 模組 Pin4 UART_RX
RX_PIN = 16      # ESP32 GPIO16 (UART RX)  <- 模組 Pin5 UART_TX
OUT_PIN = 14     # 模組 Pin3 OUT -> ESP32 GPIO14（選用）
BAUD = 115200

radar = LD2410C(uart_id=UART_ID, tx=TX_PIN, rx=RX_PIN,
                baudrate=BAUD, out_pin=OUT_PIN)


def gate_range(gate, resolution):
    """距離門 gate 覆蓋的範圍（公尺）。"""
    return gate * resolution, (gate + 1) * resolution


def main():
    print("=== LD2410C 參數測試 ===")

    firmware = radar.firmware_version()
    print("固件版本 : %s" % firmware["string"])

    resolution = radar.read_resolution()
    print("偵測精度 : %.2f m / 門" % resolution["meters"])

    params = radar.read_params()
    print("")
    low, high = gate_range(params["max_moving_gate"], resolution["meters"])
    print("最遠運動距離門 : %d  (約 %.2f ~ %.2f m)"
          % (params["max_moving_gate"], low, high))
    low, high = gate_range(params["max_stationary_gate"], resolution["meters"])
    print("最遠靜止距離門 : %d  (約 %.2f ~ %.2f m)"
          % (params["max_stationary_gate"], low, high))
    print("無人持續時間   : %d 秒" % params["no_one_seconds"])
    print("")

    print("門  距離範圍(m)   運動  靜止")
    for gate in range(len(params["motion_sens"])):
        low, high = gate_range(gate, resolution["meters"])
        print("%2d   %5.2f~%5.2f   %4d  %4d"
              % (gate, low, high,
                 params["motion_sens"][gate],
                 params["static_sens"][gate]))

    print("")
    warnings = check_params(params)
    if warnings:
        print("檢查結果：")
        for warning in warnings:
            print("  ! " + warning)
    else:
        print("檢查結果：參數都在合法範圍內")

    print("")
    print("（提示：靈敏度 100 表示該門幾乎不會辨識目標，"
          "可以用來遮掉干擾區）")


main()
