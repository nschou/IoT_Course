import uasyncio as asyncio
from machine import Pin

async def wait_pin_change(pin):  # co-routine
    cur_value = pin.value()
    counter = 0
    while counter < 20:  # 到達穩定狀態後延遲20ms再離開
        if pin.value() != cur_value:
            counter += 1
        else:
            counter = 0
        await asyncio.sleep_ms(1)

async def button_monitor(pin, handler):
    while True:       
        if pin.value() == 0:
            await wait_pin_change(pin)
            handler()        
        await asyncio.sleep_ms(10)

def button1_handler():
    global cnt1
    cnt1 = (cnt1+1) %100
    print(f"Button 1 pressed: {cnt1} times")

def button2_handler():
    global cnt2
    cnt2 = (cnt2+1) %100
    print(f"Button 2 pressed: {cnt2} times")

async def main():
    global pin1, pin2
    
    asyncio.create_task(button_monitor(pin1, button1_handler))
    asyncio.create_task(button_monitor(pin2, button2_handler))
    while True:
        await asyncio.sleep(1)

#----------------------------------------------
pin1 = Pin(17, Pin.IN, Pin.PULL_UP)
pin2 = Pin(21, Pin.IN, Pin.PULL_UP)

cnt1 = cnt2 = 0
#----------------------------------------------

asyncio.run(main())