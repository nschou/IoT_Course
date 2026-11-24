# -*- coding: utf-8 -*-
"""測試 3：修改參數並儲存（會寫入模組內部 flash，斷電不消失）

流程：
    1. 先讀出目前的參數，備份到 ld2410_params_backup.json
    2. 寫入新的參數（最遠門、無人延遲、每一門的靈敏度）
    3. 立刻回讀，逐一比對
    4. 比對失敗就自動還原備份

用法：
    直接執行           -> 套用下方的 NEW_* 設定
    執行時加 restore   -> 從 ld2410_params_backup.json 還原
"""

import sys

try:
    import json
except ImportError:      # 罕見的精簡版固件
    json = None

from hardware.ld2410c import LD2410C, LD2410CError

BACKUP_FILE = "ld2410_params_backup.json"

# ------------------------------------------------------------------ 新的設定
# 最遠偵測距離門：0.75 m/門時，門 4 約等於 3.0 m
NEW_MAX_MOVING_GATE = 4
NEW_MAX_STATIONARY_GATE = 4
NEW_NO_ONE_SECONDS = 10
# 9 個距離門（0~8）的靈敏度，0~100。數字越小越靈敏。
NEW_MOTION_SENS = [60, 60, 55, 50, 45, 40, 35, 30, 25]
NEW_STATIC_SENS = [55, 55, 50, 45, 40, 35, 30, 25, 20]


def save_backup(params):
    if json is None:
        return False
    with open(BACKUP_FILE, "w") as handle:
        json.dump(params, handle)
    return True


def load_backup():
    if json is None:
        return None
    try:
        with open(BACKUP_FILE) as handle:
            return json.load(handle)
    except OSError:
        return None


def show(params):
    print("  最遠運動門 %d / 最遠靜止門 %d / 無人延遲 %d s"
          % (params["max_moving_gate"], params["max_stationary_gate"],
             params["no_one_seconds"]))
    print("  運動靈敏度 %s" % (params["motion_sens"],))
    print("  靜止靈敏度 %s" % (params["static_sens"],))


def main():
    # ==== 接線設定（改腳位只要改這裡）====
    UART_ID = 1
    TX_PIN = 15      # ESP32 GPIO15 (UART TX)  -> 模組 Pin4 UART_RX
    RX_PIN = 16      # ESP32 GPIO16 (UART RX)  <- 模組 Pin5 UART_TX
    OUT_PIN = 14     # 模組 Pin3 OUT -> ESP32 GPIO14（選用）
    BAUD = 115200

    radar = LD2410C(uart_id=UART_ID, tx=TX_PIN, rx=RX_PIN,
                    baudrate=BAUD, out_pin=OUT_PIN)
    mode = "apply"
    try:
        if len(sys.argv) > 1:
            mode = sys.argv[1]
    except (NameError, AttributeError):
        pass

    print("=== LD2410C 參數修改與儲存 ===")
    print("固件版本:", radar.firmware_version()["string"])

    if mode == "restore":
        backup = load_backup()
        if backup is None:
            print("找不到 %s，無法還原" % BACKUP_FILE)
            return
        print("從備份還原：")
        show(backup)
        result = radar.write_params(backup)
    else:
        current = radar.read_params()
        print("原始設定（已備份到 %s）：" % BACKUP_FILE)
        show(current)
        if not save_backup(current):
            print("（這個固件沒有 json 模組，跳過備份）")

        wanted = {
            "max_gate": current["max_gate"],
            "max_moving_gate": NEW_MAX_MOVING_GATE,
            "max_stationary_gate": NEW_MAX_STATIONARY_GATE,
            "no_one_seconds": NEW_NO_ONE_SECONDS,
            "motion_sens": list(NEW_MOTION_SENS),
            "static_sens": list(NEW_STATIC_SENS),
        }
        print("")
        print("寫入新設定：")
        show(wanted)
        try:
            result = radar.write_params(wanted)
        except LD2410CError as error:
            print("寫入失敗：%s" % error)
            print("嘗試還原備份 ...")
            radar.write_params(current)
            return

        if not result["verified"]:
            print("")
            print("回讀不一致，自動還原備份：")
            for line in result["diff"]:
                print("  ! " + line)
            radar.write_params(current)
            return

    print("")
    print("回讀結果（已寫入 flash，斷電後仍保留）：")
    show(result["readback"])

    if result["verified"]:
        print("")
        print("驗證成功：模組回報的值與寫入值完全相同")
    else:
        print("")
        print("驗證失敗：請看上面的差異，並重新執行一次")

    print("")
    print("（若要還原成原本設定，執行：03_set_and_save.py restore）")


main()
