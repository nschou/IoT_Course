# 專案變更紀錄

本檔案記錄「物聯網軟體架構」教學專案的演變、修改原因、作法與驗證。時間一律使用台灣時間 `Asia/Taipei / UTC+08:00`，日期格式為 `YYYY-MM-DD`，時間格式為 `HH:mm:ss`。新紀錄放在最上方，保留既有歷史，不以最新結論覆蓋舊紀錄。

## 紀錄規則

每次修改程式、設定、測試、部署、文件或版控規則，都必須在同一個 Git commit 更新本檔案。紀錄至少包含：

- 變更 ID、版本或狀態。
- 修正／完成日期與時間，以及紀錄時間；不確定的時間明確註記，不得推估成精確時間。
- 原因類別：`BUG` 或 `需求變更`。
- 現象、原因分析、詳細作法、影響範圍、驗證與限制。
- 關聯檔案、測試方式、部署或回復方法。

`BUG` 表示行為不符合既有預期；`需求變更` 包含新功能、政策調整、文件與流程要求。一件工作若同時包含兩類，拆分紀錄或明確標示各項原因。

Git commit hash 由歷史查詢取得；不要求把包含本紀錄的 commit hash 寫回本紀錄，避免自我引用。既有程式中的 v1.1.x／v1.2 註解不是統一的專案版本，本次開始以 Git commit 與後續 tag 作為版本依據。

## CHG-20261006-004｜整合 PIR 移動與非同步音樂播放

- **類別：**需求變更。
- **日期／作業開始時間：**2026-10-06 02:22:36 +08:00。
- **測試完成／紀錄時間：**2026-10-06 02:24:45 +08:00。
- **原因：**使用者同意參考單檔範例將 PIR 與無源喇叭接入 main；原範例同步 sleep 會阻塞其他協程，持續高電位也會反覆觸發，採用已確認的非同步播放與低→高觸發策略。
- **作法：**hardware/sensors.py 新增 PirSensor（GPIO 4）；新增 hardware/speaker.py（GPIO 6 PWM），沿用 ns_tools.NOTE_FREQS，以 await uasyncio.sleep 播放 C4/E4/D4/G3 各 0.3 秒加 0.2 秒休止。config.py 與 config.example.py 同步非機密腳位、500 ms 輪詢、512 占空比與旋律，私人 WiFi 值保留。
- **呼叫／生命週期：**main 初始化兩個硬體與獨立 Event，加入 PIR 偵測及播放任務。首次取樣建立基準，後續低→高才 set；播放任務 wait 後先 clear，再播放。Event 合併播放中多次觸發為最多一次待播，不累積計數或歷史；重啟清空事件與基準。播放 finally 靜音，main finally 釋放 PWM；初始化失败略過該功能，讀取／播放例外記錄並延遲重試。
- **影響：**不變更 RFID／LED／Web／MQTT 行為，未新增網頁或移動 MQTT 發布；ns_tools 原同步播放函式及单檔範例不改。500 ms 取樣可能漏掉短脈衝，未新增 PIR 暖機遮蔽；PWM 與音量需實機確認。
- **驗證：**9 個 Python 測試通過（3 個新增 PIR／音樂測試與 6 個 LED／RFID 回歸），涵蓋邊緣觸發、初始高電位、持續高電位、事件合併、協程讓出、音符與休止、錯誤／取消後靜音及重複釋放。既有 RFID 網頁 JavaScript 測試通過。均為桌面 fake 測試，未執行 ESP32 聲音、接線或時序實機驗證。
- **部署／回復：**詳見 PIR_MUSIC_GUIDE.md；部署 main/tasks/sensors/speaker 並新增裝置私人配置。回復使用 rfid-validated-20261006 標籤，重新部署舊應用；私人 config.py 不由 Git 回復。
- **版控：**在 feature/pir-music 本地提交；依已確認方案，等待使用者實機確認再合併與推送。main 與 GitHub RFID 標籤保持既有版本。

## CHG-20261006-003｜保存使用者確認正常的 RFID 版本

- **類別：**需求變更（版本發布與驗證紀錄）。
- **日期／紀錄時間：**2026-10-06 01:29:37 +08:00；實際實機測試時間未提供。
- **原因：**使用者回報目前 RFID 功能正常，明確要求進版本並推送 GitHub。
- **驗證來源：**ESP32 實機正常由使用者確認；未提供逐項驗收紀錄，不推論所有錯誤情境、卡片種類或瀏覽器皆已驗證。先前桌面 6 個 Python 測試及 JavaScript 測試結果仍見 CHG-20261006-002。本次沒有程式邏輯變更，不重複執行相同測試。
- **作法：**fetch 核對遠端；更新 RFID_INTEGRATION.md 的驗證／版本狀態；提交紀錄後，將 feature/rfid-integration 快轉合併至 main，建立帶註解標籤 rfid-validated-20261006，推送 main、功能分支與標籤至既有 origin。保留原基線標籤，完成後核對遠端 SHA 與工作目錄。
- **影響：**RFID 實作維持 6e341b6 的內容，只更新文件與版本指標；私人設定與備份仍排除於 GitHub。版本及 push 成功以 Git refs 為準。
- **回復：**乾淨工作目錄執行 git switch -c restore-before-rfid baseline-before-rfid-20261006 可取得整合前基線；執行 git switch -c restore-rfid rfid-validated-20261006 可取得此次確認版本。Git 切換後仍需自行部署到 ESP32，私人 config.py 另行保留／回復，不採 reset --hard 或 force push。

## CHG-20261006-002｜將 RFID 接入模組化程式與 Web 顯示

- **類別：**需求變更；連帶修正 API JSON 與網頁零值顯示 BUG。
- **日期／紀錄時間：**2026-10-06 00:31:46 +08:00。
- **需求原因：**使用者同意參考單檔範例整合 RFID，並保存可恢復的修改前版本。
- **作法：**新增 hardware/rfid.py，延後明確匯入 MFRC522Async、to_hex_string，沿用配置腳位與 request(REQIDL) → anticoll() → 完整 raw_uid 轉換。main 初始化 RFID 與共享字典，注入 Web Server 並加入 gather；tasks 每輪讀取後等待 500 ms，成功更新最後識別碼與装置時間，例外保留最後紀錄並持續重試。
- **Web 資料：**/api/data 回傳 rfid.status、last_uid、last_read_at、error；API 只複製快取、不直接讀 SPI。以 ujson/json.dumps 取代手組 JSON，避免 None 產生非法 JSON，並跳脫字串。index.html 新增最後讀取卡片區，沿用每秒刷新，以 textContent 顯示；零值使用 ?? 保留，檢查 HTTP 狀態，成功恢復連線顯示。
- **生命週期／影響：**最後紀錄只在 RAM，成功覆寫、無回應保留、重啟清空；讀取例外後下一次成功才清除錯誤。初始化失敗跳過讀卡、保留其他功能。沿用驅動 5-byte 結果（含 BCC），未新增長 UID、刷卡歷史、寫卡、RFID MQTT 或門禁。request 無法區分無卡與部分通訊失敗，ready 只代表已初始化。
- **驗證：**6 個 Python 測試通過（3 個原有 LED 測試及 3 個 RFID／API 測試）；實際網頁 JavaScript 在模擬 DOM/fetch 下驗證初始值、讀卡顯示、零值、錯誤字串、連線失敗與恢复通過。未做 ESP32 實機、SPI 接線或瀏覽器視覺驗證。
- **部署／回復：**詳見 RFID_INTEGRATION.md；部署新硬體模組及四個應用檔案，確認 /lib 驅動與 aiot_tools 依賴後重啟。修改前標籤 baseline-before-rfid-20261006 已推送，基線 commit 為 38a65fd；使用乾淨工作目錄建立回復分支並重新部署。私人配置由本機備份另行處理。
- **版控：**在 feature/rfid-integration 提交並推送；待 ESP32 實機驗證後再合併 main。Git refs 為推送結果依據。

## CHG-20261006-001｜保存 RFID 整合前基線

- **類別：**需求變更。
- **日期／紀錄時間：**2026-10-06 00:26:05 +08:00。
- **原因：**使用者同意 RFID 整合與 GitHub 版本保存；原提交未包含新加入的 Microdot 與個人 VS Code 設定。
- **作法：**納入本機既有 Microdot 2.4.0 套件；同步去除私人 WiFi profiles 的單檔範例；保留個人 settings.json，新增可攜的 settings.example.json；排除 typings 與 .local-backups。私人 config.py、單檔原稿及 settings.json 複製至 .local-backups/baseline-before-rfid-20261006（只留本機）。
- **版本保存：**提交後建立 baseline-before-rfid-20261006 標籤並推送 main 與標籤；以 Git refs 核對實際結果。
- **影響／限制：**此基線不變更應用邏輯；Microdot 是使用者已有的檔案，尚未驗證 ESP32 實機。GitHub 不含私人配置；本機備份不是異地備份。
- **回復：**在乾淨工作目錄使用 git switch -c restore-before-rfid baseline-before-rfid-20261006；需部署時以此版本覆蓋裝置檔案，私人配置另從本機備份取回。個人 VS Code 設定不由 Git 恢復。

## CHG-20261005-003｜納入教學文件與公開範例，推送 GitHub

- **類別：**需求變更。
- **日期／作業開始時間：**2026-10-05 21:49:32 +08:00。
- **紀錄時間：**2026-10-05 21:49:32 +08:00。
- **目的地：**`https://github.com/nschou/IoT_Course.git`。
- **需求來源：**使用者已建立 repository，明確要求將此專案推送至該目的地。

### 原因與作法

1. 檢查遠端既有 refs，確認目前無分支，使用本地 `main` 建立遠端基線，不採 force push。
2. 將獨立 `WEB_UI_EXECUTION_GUIDE.md` 講義與 `AGENTS.md` 中的 Mermaid 11.13.0 規則納入版本快照。講義前次建立及修正時依使用者指示未更新 ChangeLog；本項只記錄此次納入版控／交付，保留先前紀錄方式。
3. 講義的 `Loop` 參與者名稱已改成 `Scheduler`；時序訊息中的分號已改為 `#59;`。講義 12 個圖已用 Mermaid 11.13.0 實際解析通過；這不等於已在所有編輯器驗證視覺布局。
4. 納入現有的 `ESP32上無源按鈕的asyncio版本.md` 教學文件，保留原內容。此項不代表已實作或驗證文件內的按鈕範例。
5. 檢查新單檔範例 `99_All-11-2.py`，發現其 WiFi profiles 含私人值；保留原檔不修改，新增 ignore 規則並建立 `99_All-11-2.example.py`，僅以示範 SSID／密碼取代 profiles，保留其餘程式內容。
6. 在版控指南補充此次 GitHub 目的地及單檔範例部署方式。推送前檢查暫存內容與全部 commit 中的已知私人 WiFi 值及常見 token／私鑰特徵。
7. 設定 `origin` 為使用者指定的網址，提交交付檔案並推送 `main`，完成後核對本地 HEAD 與遠端 main 是否一致；提交／推送結果以 Git refs 為準。

### 影響與驗證範圍

不變更目前裝置應用邏輯或本機連線配置。本機 `config.py` 與 `99_All-11-2.py` 不在 Git 內，新環境需使用相應範本建立設定／範例並自行填入 profiles。單檔範例只是去除私人設定，尚未做 ESP32 實機驗證。秘密掃描只涵蓋已知值與指定模式，不宣稱可辨識所有機密。

## CHG-20261005-002｜建立變更追蹤與本地 Git 版控流程

- **類別：**需求變更。
- **日期：**2026-10-05。
- **作業開始／首次紀錄時間：**12:52:56 +08:00。
- **狀態：**本地 `main` 已初始化；本紀錄隨初始基線提交保存，實際 commit 以 `git log` 查詢。
- **文件與驗證完成時間：**2026-10-05 12:58:12 +08:00；初始提交時間由 Git 記錄。
- **需求來源：**使用者要求所有修正持續記錄日期、時間、原因與作法，並提供每個版控目的所需的指令。

### 原因與目的

先前修改只存在於對話與檔案內容，缺少集中、持續、可追溯的變更歷史。工作目錄檢查時尚未建立 Git repository。另發現 `config.py` 包含實際 WiFi 密碼，不適合直接納入可能分享的版本庫。

### 作法

1. 新增本檔案，追記本次 LED BUG，並定義後續紀錄欄位與時間規則。
2. 新增 `GIT_VERSION_CONTROL.md`，說明初始化、檢查差異、暫存、提交、分支、合併、撤回、標籤、遠端協作與備份的目的及 PowerShell 指令。
3. 新增根目錄 `AGENTS.md`，要求後續協作者／代理在修改時同步更新 ChangeLog，並記錄測試結果，不得捏造時間或驗證。
4. 新增 `.gitignore`，排除本機 `config.py`、秘密、Python 快取與暫存輸出；新增 `.gitattributes` 統一文字檔案儲存為 LF，並將 `.12` 點陣字型標示為 binary，避免改寫二進位內容。
5. 從目前 `config.py` 製作 `config.example.py`，保留非機密設定，只以示範 SSID／密碼替代 WiFi profiles，作為可追蹤的設定範本。
6. 準備本地 `main` 分支與初始快照；不建立未經指定的遠端，也不自動 push。本機仍使用原有 `config.py`，不變更裝置連線設定。

### 影響與限制

- 此項主要改善變更追溯與交付流程，不修改 LED 或感測器的執行邏輯。
- 因排除整份本機 `config.py`，任何非機密設定修正必須同步到 `config.example.py` 才會進入 Git 歷史。
- 新 clone 的環境需由範本建立 `config.py`，填入本機 WiFi 設定；其內容不由 Git 備份。
- 原始修正前的版本未在 Git 中保存，初始提交只能記錄目前修正後基線，不能當作具有完整歷史的前後差異。
- 本地 Git 歷史不等於異地備份；遠端網址未提供，遠端建立與上傳留待設定。

### 驗證方式

三項 LED 桌面回歸測試再次通過。`config.example.py` 的 WiFi profiles 已驗證只有示範值；`git check-ignore` 確認本機 `config.py` 被排除。暫存內容掃描未找到原 WiFi 密碼或常見 GitHub token／私鑰特徵；新文件與測試的空白檢查通過。此掃描只涵蓋上述模式，不代表能辨識所有機密。字型指定為 binary，提交前比對暫存與工作檔 bytes；實機驗證仍未執行。

在不提供檔案擁有權的 G 槽上，部分 Git 執行環境回報 dubious ownership；版控操作僅用 `git -c safe.directory='<本專案確切路徑>' ...` 指定本次指令信任，未設全域萬用信任。

## CHG-20261005-001｜按鈕 1 換色索引反覆為 1，LED 閃爍後熄滅

- **類別：**BUG。
- **修正日期：**2026-10-05。
- **修正時間：**前一輪修正未記錄精確時間，無法可靠追溯；不補造時間。
- **追記時間：**2026-10-05 12:52:56 +08:00。
- **版本／狀態：**目前工作目錄已套用修正；此修正在建立 Git 前完成。

### 預期行為

按鈕 1 每次按下，LED 色碼應以 0～7 循環，並保持該顏色直到下一次操作；色碼 0 為黑色／全滅。開機初始化顯示白色 7，因此第一次按下會切換到 0，之後依序 1、2、3、4、5、6、7、0。

### 實際現象

使用者回報每次都印出藍色／索引 1，LED 短暫閃亮後熄滅：

```text
[Button] 按鈕 1 被按下
[LED] 顏色改變為: 藍 (索引: 1)
[Button] 按鈕 1 被釋放
```

### 原因分析

1. `button1_task()` 呼叫 `rgb_led.next_color()`，依目前色碼計算 `(current_color_index + 1) % 8`。
2. `light_sensor_task()` 同時每 50ms 讀取 ADC；亮度大於 1100 時呼叫 `rgb_led.off()`。
3. 修正前 `off()` 呼叫 `set_color_by_index(0)`，同時熄滅 GPIO 並把目前色碼改成 0。
4. 結果是按鈕短暫設定色碼 1，隨後被光感任務清除；下一次又從 0 切換到 1。

根因為兩個任務共同寫入同一 LED，且「暫時熄燈」與「選擇黑色」共用同一狀態。問題不是 `% 8` 的循環公式。

### 詳細作法

| 檔案 | 修改 | 目的 |
|---|---|---|
| `config.py` | 新增 `LIGHT_AUTO_CONTROL_ENABLED = False` | 預設保留手動選色，不讓光感覆寫 |
| `tasks.py` | 持續讀取 ADC，但只在上述開關為 True 時執行光感控制 | 保留亮度功能，分離感測與控制 |
| `hardware/led.py` | 新增 `is_on`，色碼設定時同步更新 | 分開所選顏色與輸出開關狀態 |
| `hardware/led.py` | `off()` 只將三個 GPIO 設為 0，保留 `current_color_index` | 熄燈不重設循環起點，允許自動亮燈恢復原色 |
| `hardware/led.py` | `toggle()` 依 `is_on` 判斷開關；重新開啟使用所選色碼，色碼為 0 時用白色 7 | 配合新的狀態語意 |
| `tests/test_led_control.py` | 新增 fake GPIO 與光感任務回歸測試 | 驗證循環、保持、恢復與 toggle |
| `SYSTEM_ARCHITECTURE.md`、`IOT_ARCHITECTURE_TECH_TREE.md` | 加入 2026-10-05 修正說明 | 保留修正前架構分析並註明現況差異 |

此處採最小修正，尚未建立完整 LedController、命令佇列或 AUTO／MANUAL 仲裁。若再次啟用光感自動控制，亮時仍會熄燈，這是設定所允許的自動行為；只有色碼不再被清除。

### 訊息位置

修改當時，`tasks.py` 第 33 行印出該訊息：

```python
print(f"[LED] 顏色改變為: {color_name} (索引: {next_color})")
```

後續行號可能變動，可用 `rg -n '顏色改變為' tasks.py` 重新查詢。

### 驗證與結果

已在桌面 Python 使用 fake GPIO 執行三項回歸測試，全部通過：

1. `test_button_colors_survive_light_polling_and_wrap`：1～7→0→1 循環，在亮／暗／遲滯區間讀取後仍維持索引與輸出。
2. `test_auto_off_preserves_color_and_dark_restores_it`：啟用自動控制時，亮處熄燈但保留紅色索引 4，暗處恢復紅色。
3. `test_toggle_restores_selected_color`：關閉再開啟，恢復選定黄色索引 6。

```powershell
python -B -m unittest discover -s tests -v
```

測試使用實際 LED 類別與從 `tasks.py` 擷取的光感任務，在桌面模擬執行；沒有驗證按鈕電氣訊號、實機排程或 LED 接線。使用者尚未回報上傳後的實機結果。

### 部署與回復

- 將更新的 `config.py`、`tasks.py`、`hardware/led.py` 上傳 ESP32 後重新啟動；第一次按下由白色 7 切至黑色 0，屬預期行為。
- 若要測試自動照明，在本機設定與範本將 `LIGHT_AUTO_CONTROL_ENABLED` 改為 True，另開變更紀錄；這不是完整撤回此次 BUG 修正。
- 此修正前沒有 Git commit；不能使用 `git revert` 取得原始修正前版本。日後已提交的修正可依 Git 指南使用 revert，並記錄原因。

## 後續紀錄範本

```text
## CHG-YYYYMMDD-NNN｜變更摘要
- 類別：BUG | 需求變更（實際選一項）
- 修正／完成日期：YYYY-MM-DD
- 修正／完成時間：HH:mm:ss +08:00
- 紀錄時間：YYYY-MM-DD HH:mm:ss +08:00
- 版本／狀態：分支、版本標籤或待提交

### 原因
預期、現象、根因，或需求來源與目的。
### 作法
修改檔案、行為差異、選擇理由與取捨。
### 驗證
指令、結果、實機／模擬範圍、未驗證項目。
### 影響與部署／回復
相容性、需要上傳的檔案、設定與回復方式。
```
