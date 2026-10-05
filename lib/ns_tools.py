import ntptime, time, network, utime
from machine import Pin, PWM, RTC
import uasyncio as asyncio

# 標準西洋音階頻率對照（C4為中央C）
NOTE_FREQS = {
    'C4': 262,  # Do
    'D4': 294,  # Re
    'E4': 330,  # Mi
    'F4': 349,  # Fa
    'G4': 392,  # So
    'A4': 440,  # La
    'B4': 494,  # Si
    'C5': 523,  # 高音Do
    'Bb4':466,  # 升A(降B)
    'G3': 196,
    'E5': 659,
    'D#5': 622,
    'D5': 587,
    'Ab4': 415,
    'REST': 0   # 休止符
}

NOTES_0 = [('C4', 0.3), ('E4', 0.3), ('D4', 0.3), ('G3', 0.3), ('REST', 0.2)]

# 初始化揚聲器，預設靜音
def speaker_init(pin=6):
    speaker = PWM(Pin(pin, Pin.OUT))  # 揚聲器腳位 (輸出 PWM 訊號)
    speaker.duty(0)  # 將 PWM 占空比設為 0，即靜音
    speaker.freq(1000)  # 預設頻率
    
    return speaker


# 靜音並釋放揚聲器
def speaker_deinit(speaker):
    speaker.duty(0)  # 將 PWM 占空比設為 0，即靜音
    speaker.deinit()  # 釋放 PWM
    speaker = None  # 重置揚聲器為 None
    
    return speaker

def play_song(speaker, notes=NOTES_0):
    for note, duration in notes:
        freq = NOTE_FREQS[note]
        if freq == 0:
            speaker.duty(0)
        else:
            speaker.duty(512)
            speaker.freq(freq)
        if duration<=5:
            utime.sleep(duration)
        else:
            utime.sleep_ms(duration)
    speaker.duty(0)

def mySetTime(timezone=8, max_retries=3):
    # 预定义多个可靠的 NTP 服务器列表
    ntp_servers = [
        "time.stdtime.gov.tw",    # 台灣國家級NTP伺服器
        "tw.pool.ntp.org",        # 台灣NTP Pool專區
        "pool.ntp.org",           # 全球公共 NTP 池
        "time.google.com",        # Google 时间服务
        "time.windows.com",       # Microsoft 时间服务
        "cn.pool.ntp.org",        # （中國）	中國/亞洲
        "ntp.aliyun.com",         # 阿里云 NTP
        "cn.ntp.org.cn",          # 中国 NTP 服务器
        "ntp1.aliyun.com"         # 阿里云备用
    ]
    '''
    cn.pool.ntp.org（中國）	中國/亞洲	20~50ms ntppool
    asia.pool.ntp.org（亞洲）	亞洲	30~60ms ntppool
    time.cloudflare.com	全球節點/亞洲	15~40ms sidnlabs
    stdtime.gov.hk（香港天文台）	香港/華南	10~30ms hko
    time.asia.apple.com	亞洲	20~60ms sidnlabs
    '''
    utc_offset = timezone * 3600  # 时区偏移量（秒）
    synced = False
    
    # 尝试每个服务器最多 max_retries 次
    for server in ntp_servers:
        for attempt in range(1, max_retries + 1):
            try:
                print(f"尝试从 [{server}] 同步时间 (尝试 {attempt}/{max_retries})")
                
                # 设置当前 NTP 服务器
                ntptime.host = server
                ntptime.settime()
                
                # 获取并调整时区
                current_time = time.time() + utc_offset
                tm = time.localtime(current_time)
                
                # 设置 RTC 时间 (年,月,日,星期,时,分,秒,微秒)
                RTC().datetime((tm[0], tm[1], tm[2], tm[6], tm[3], tm[4], tm[5], 0))
                
                # 验证时间是否合理（年份 > 2020）
                if tm[0] > 2020:
                    synced = True
                    print(f"成功从 [{server}] 同步时间: {tm[0]}/{tm[1]}/{tm[2]}-{tm[3]}:{tm[4]}:{tm[5]} (週{tm[6]+1})")
                    return True
                else:
                    print("警告：获取到无效时间，重试中...")
                    
            except Exception as e:
                error_type = str(e)
                # 跳过已知的解析错误
                if "invalid date" in error_type or "EINVAL" in error_type:
                    print(f"服务器 {server} 返回无效数据")
                else:
                    print(f"同步失败 ({type(e).__name__}): {e}")
            
            # 指数退避等待 (1s, 2s, 4s...)
            wait_time = min(2 ** attempt, 30)  # 上限 30 秒
            time.sleep(wait_time)
    
    # 所有服务器均失败时的处理
    if not synced:
        print("所有 NTP 服务器同步失败，使用最后已知时间")
        try:
            # 尝试使用 RTC 的现有时间
            tm = time.localtime(time.time() + utc_offset)
            RTC().datetime((tm[0], tm[1], tm[2], tm[6], tm[3], tm[4], tm[5], 0))
            return True
        except:
            print("无法设置备用时间")
            return False

# 取得格式化的本地當前日期、星期、時間
def myGetTime():
    # 星期名稱對應表（可選中文或英文）
    WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]
    #WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    
    # 取得本地當前時間
    now = time.localtime()  
    # 格式化日期成 YYYY/MM/DD
    date_str = '{:04d}/{:02d}/{:02d}'.format(now[0], now[1], now[2])
    # 格式化時間成 HH:MM:SS
    time_str = '{:02d}:{:02d}:{:02d}'.format(now[3], now[4], now[5])
    # 根據星期索引取得對應的星期名稱，now[6] 是星期值 (0~6)
    weekday_str = WEEKDAYS[now[6]]

    return date_str, weekday_str, time_str

def connect_to_known_wifi(profiles, try_time=10):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    print("Scanning for WiFi networks...")
    networks = wlan.scan()   # 回傳 (ssid, bssid, channel, RSSI, authmode, hidden)
    available = {ssid.decode(): ssid for ssid, *_ in networks}
    print("Found SSIDs:", list(available.keys()))

    known_ssids = set(profiles.keys()) & set(available.keys())
    if not known_ssids:
        print("No known SSID found, cannot connect.")
        return ['', '']

    # 優先連到訊號最強的已知AP
    candidates = [n for n in networks if n[0].decode() in known_ssids]
    target = max(candidates, key=lambda x: x[3])  # 按 RSSI 選
    ssid = target[0].decode()
    passwd = profiles[ssid]
    print(f"Connecting to {ssid}...")

    wlan.connect(ssid, passwd)
    for _ in range(try_time):
        if wlan.isconnected():
            print("WiFi connected! IP:", wlan.ifconfig()[0])
            return [ssid, passwd]
        time.sleep(1)
        print(".", end="")
    print("\nFailed to connect.")
    return ['', '']
   
class DebouncedButton:
    def __init__(self, pinNo, id=None , on_click=None, on_long=None, on_double=None, debounce_ms=30, long_ms=800, double_ms=400):
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
    