# 專案協作規則

## 變更追溯

- 本專案每次修改程式、設定、測試、部署、文件或版控規則，都必須同步更新根目錄 `ChangeLog.md`，並納入同一次提交。
- 依 `ChangeLog.md` 範本記錄日期、時間、原因類別（`BUG` 或 `需求變更`）、詳細原因、修改作法、影響、驗證與部署／回復方法。
- 使用 `Asia/Taipei / UTC+08:00`；以工具取得目前時間。歷史精確時間未知時明確註記，不得捏造。
- 不覆蓋舊紀錄；新紀錄置頂。說明哪些項目只是提案、哪些已實作、哪些未驗證。
- commit hash 由 Git 歷史查詢，無須將目前 commit 的 hash 寫回自身。

## Git 與設定

- 先閱讀 `GIT_VERSION_CONTROL.md`，遵循小範圍提交、檢查差異與測試的流程。
- 不提交密碼、token、金鑰或裝置私密設定；不要以 `git add -f` 加入 `config.py`。
- 本機 `config.py` 含私人 WiFi profiles，被 Git 排除。非機密配置變更必须同步到 `config.example.py`，秘密不得同步過去。
- 不擅自覆蓋其他人的修改，不因清理版控而刪除本機設定。
- 遠端建立、公開與 push 需有使用者指定的目的地及授權。

## 驗證

- LED 邏輯修改後執行 `python -B -m unittest discover -s tests -v`，或使用可用的 Python 執行檔。
- 明確區分桌面 fake GPIO 測試與 ESP32 實機驗證；不可宣稱未執行的驗證已通過。
