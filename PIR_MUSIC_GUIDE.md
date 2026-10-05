# PIR 移動提示音樂：流程與部署

本功能接入 `main.py`，由 PIR 偵測任務與無源喇叭播放任務協作；目前完成桌面測試，尚未做 ESP32 實機驗證。開發分支為 `feature/pir-music`，待使用者實機確認後再合併／推送。

## 初始化與呼叫

`main.initialize_system()` 在通訊初始化後建立 `PirSensor()` 與 `Speaker()`；任一初始化失敗就略過移動音樂功能，其他功能繼續運作。`main()` 建立獨立的 `motion_event = uasyncio.Event()`，將兩個任務加入既有 `gather()`。

`PirSensor` 使用 `machine.Pin(config.PIR_PIN, Pin.IN)`，GPIO 為 4；`is_motion()` 將 `Pin.value()` 轉為布林值。`pir_monitor_task()` 每 500 ms 取樣，第一次只建立基準；後續低→高時呼叫 `motion_event.set()`。持續高電位不會重複觸發，需先回到低電位再升高。500 ms 輪詢可能漏掉比取樣間隔短的脈衝；PIR 開機暖機期間的低→高仍可能觸發，本版未加暖機遮蔽時間。

`music_on_motion_task()` 以 `await motion_event.wait()` 等待，收到後先 `clear()`，再 `await speaker.play_song(config.MOTION_MELODY)`。Event 是布林旗標而不是事件佇列；播放期間多次 set 只保留一次待播。因此旋律不重疊，播放完最多接續一次待播，不保留每次移動的數量。

`Speaker` 使用 GPIO 6 的 `machine.PWM`，初始占空比 0；沿用 `ns_tools.NOTE_FREQS` 頻率表。旋律由配置提供：C4（262 Hz）、E4（330 Hz）、D4（294 Hz）、G3（196 Hz）各 0.3 秒，再休止 0.2 秒。發聲占空比 512，休止時為 0；PWM 頻率形成音高，無源喇叭需要這種交變訊號。

原範例 `ns_tools.play_song()` 使用 `utime.sleep()`，會阻塞事件迴圈。本版不修改該既有函式，而由新封裝用 `await uasyncio.sleep(duration)` 等待，讓 RFID、按鈕、MQTT、Web 等協程繼續執行。音符時間是排程等待時間，並非硬體精準計時。

播放函式的 `finally` 在成功、錯誤或取消後靜音；播放任務結束也會靜音。`main()` 的 `finally` 呼叫 `speaker.deinit()`，停止並釋放 PWM。播放例外記錄後等 1 秒，再等待／處理事件；PIR 讀取例外重設取樣基準，避免把錯誤當移動。這些清理適用於 Python 控制流程正常進入 finally，不能保證突然断電或強制重置時執行。

## 配置與部署

本機 `config.py` 與公開 `config.example.py` 已同步新增 `PIR_PIN = 4`、`SPEAKER_PIN = 6`、`PIR_POLL_INTERVAL_MS = 500`、`SPEAKER_DUTY = 512` 與 `MOTION_MELODY`。私人 WiFi profiles 未修改、未納入 Git。

部署 `main.py`、`tasks.py`、`hardware/sensors.py` 與新增 `hardware/speaker.py`；另更新裝置私人 `config.py` 的上述非機密參數，保留其 WiFi 設定。確認 `/lib/ns_tools.py` 與既有依賴存在，再重啟。此版未新增 Web 顯示、按鈕或 MQTT 移動發布。

實機驗收建議：PIR 輸出先為低，再偵測移動，確認播放一次；持續高電位不連續重播；回低後再次移動會再播放；播放中刷 RFID、操作 LED 與網頁確認可回應；中斷程式確認喇叭停止。依實際 PIR 模組的保持時間與暖機特性判讀。

## 驗證與版本恢復

9 個 Python 測試通過，涵蓋原有 LED／RFID 回歸與新增的邊緣觸發、待播合併、音符／休止、協程讓出、播放錯誤／取消後靜音和 PWM 重複釋放；既有 RFID 網頁 JavaScript 測試也通過。測試使用 fake GPIO／PWM，未驗證聲音、接線或實際排程延遲。

```powershell
python -B -m unittest discover -s tests -v
node tests/test_rfid_ui.cjs
```

目前已確認的 RFID 基線標籤仍為 `rfid-validated-20261006`。需要回到該版時，在乾淨工作目錄建立回復分支：

```powershell
git switch -c restore-rfid rfid-validated-20261006
```

再將基線應用檔案部署到 ESP32。Git 不會回復未追蹤的私人 `config.py`；本次只新增非機密配置，舊程式可忽略它們，若要完全一致請自行比對私人備份。單檔 `99_All-11-2.py` 及其公開範例本次未改動。
