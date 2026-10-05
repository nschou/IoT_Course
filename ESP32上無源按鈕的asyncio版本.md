# micropython類別，ESP32上無源按鈕的asyncio版本：可偵測按鈕是否單擊、雙擊、長按。

---

```python
from machine import Pin
import uasyncio as asyncio

class DebouncedButton:
    def __init__(self, pinNo, id=None ,
                 on_click=None, on_long=None, on_double=None, 
                 debounce_ms=30, long_ms=800, double_ms=400):
        self.pinNo = pinNo
        self.pin = Pin(pinNo, Pin.IN, Pin.PULL_UP)
        self.id = id
        self.on_click = on_click          # 單擊處理函數
        self.on_long = on_long            # 長按處理函數
        self.on_double = on_double        # 雙擊處理函數
        self.debounce_ms = debounce_ms
        self.long_ms = long_ms
        self.double_ms = double_ms
        # 狀態追蹤
        self.last_release_time = 0
        self.click_pending = False
        # 啟動監控
        self.task = asyncio.create_task(self.watch())

    async def watch(self):
        while True:
            if self.pin.value() == 0:  # 按下
                t0 = time.ticks_ms()
                await asyncio.sleep_ms(self.debounce_ms)
                # 按鈕仍在按下
                if self.pin.value() == 0:
                    long_fired = False
                    while self.pin.value() == 0:
                        if not long_fired and time.ticks_diff(time.ticks_ms(), t0) > self.long_ms:
                            if self.on_long:
                                self.on_long(self.id, self.pinNo)
                            long_fired = True
                        await asyncio.sleep_ms(10)
                    t1 = time.ticks_ms()
                    duration = time.ticks_diff(t1, t0)
                    # 處理短按 (排除長按已執行過)
                    if not long_fired:
                        now = t1
                        if self.click_pending and time.ticks_diff(now, self.last_release_time) < self.double_ms:
                            if self.on_double:
                                self.on_double(self.id, self.pinNo)
                            self.click_pending = False
                        else:
                            # 先不立即觸發單擊，等一段時間內沒再按才視為單擊
                            self.click_pending = True
                            self.last_release_time = now
                            asyncio.create_task(self._single_click_timeout())
            else:
                await asyncio.sleep_ms(10)

    async def _single_click_timeout(self):
        await asyncio.sleep_ms(self.double_ms)
        if self.click_pending:
            if self.on_click:
                self.on_click(self.id, self.pinNo)
            self.click_pending = False
```

---

### 演算法詳細解說

#### 初始化與狀態追蹤

- 使用 `Pin(pinNo, Pin.IN, Pin.PULL_UP)` 建立上拉輸入端口。
- 設定消抖時間、長按判定時間、雙擊時間間隔。
- 用 `click_pending` 標記是否有尚未確定的單擊。
- 透過 asyncio 啟動非阻塞 watch 監控按鍵狀態。

#### 主監控流程 `watch()`

1. **按下偵測與消抖**
   - 發現 pin = 0（按下），開始記錄觸發時間 t0。
   - 等待 debounce_ms 毫秒進行消抖。
   - 將消抖後仍為按下視為真實按下。
2. **長按偵測**
   - 進入 while 持續檢查 pin 狀態，直到放開。
   - 如果持續按下且時間超過 long_ms，執行長按事件（on_long），設置 long_fired 防止重複觸發。
3. **釋放偵測**
   - 釋放按鍵，取得 t1，計算持續時間 duration。
   - 若未長按（long_fired == False），判斷是否雙擊：
     - 如果 click_pending 為 True 且上次釋放到現在 < double_ms，觸發雙擊（on_double）。
     - 否則記錄這次釋放時間並設 click_pending，等候 double_ms 毫秒後若依然沒有再按，就觸發單擊。
   - 單擊的延遲判斷由 `_single_click_timeout()` 非同步任務處理，避免阻塞，即使是多個按鈕也不會互相干擾。
4. **等待與閒置**
   - 若未按下，短暫 sleep_ms(10)。

#### 單擊延遲判斷 `_single_click_timeout()`

- 等待 double_ms 毫秒（雙擊窗口），若仍 click_pending（代表只有單擊沒有第二次按下），才觸發單擊事件（on_click）。

***

### 優點分析

- **防抖動與誤觸**：多層消抖，能有效過濾機械開關雜訊。
- **精確雙擊/單擊分辨**：採用 click_pending 與定時任務，未立即觸發單擊，可正確分辨雙擊與單擊，減少誤判。
- **長按準確且可定義**：可連續偵測長按。
- **非阻塞（asyncio）設計**：可並行管理多個按鍵與其他 async 任務，資源輕盈，適合 IoT 實時應用。
- **易於擴展**：on_click、on_double、on_long 只需設 callback，即可客製功能。

***

### 缺點與潛在風險

- **快按下釋放不一定能100%消抖**：若 debounce_ms 設太小，可能還是有雜訊；太大則降低反應速度。
- **雙擊分辨速度有限制**：若使用者雙擊超過 double_ms 時窗就判為單擊，部分用戶習慣不同需自行調整參數。
- **高頻率操作（如超快多次點擊）極端情況下可能判斷失誤**。

***

### 適用情境

- IoT 按鍵操作複雜需求（如智能家居開關）。
- 多個按鍵並行判斷，且需要與 async 通訊、其他任務協同。
- 需要單擊、雙擊、長按多種輸入分辨的設備。

***

### 技術細節關鍵

- `asyncio.sleep_ms()` 為微秒級非阻塞延遲，對即時反應有助益。
- `click_pending` 為單擊延遲鎖，最大程度減少誤判雙擊。
- 動態創建 timeout 任務，確保單擊、雙擊判斷互不干擾並能精準響應。

***

整體而言，這利用 asyncio 的按鍵偵測演算法，兼顧精確性與資源管理，在 ESP32 或同類 MCU 上是非常實用且具可擴展性的選擇，特別適合現代 IoT 需求。
