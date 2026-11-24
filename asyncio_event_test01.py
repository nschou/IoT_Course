import uasyncio

async def producer():
    while True:
        state['value'] = state['value']+1
        print('--- producer --- : ', state['value'])
        event.set()
        await uasyncio.sleep(1)

async def consumer1():
    while True:
        await event.wait()
        event.clear()
        print('consumer1: ', state['value'])
        await uasyncio.sleep(1)
        
async def consumer2():
    while True:
        await event.wait()
        event.clear()
        print('consumer2: ', state['value'])
        await uasyncio.sleep(4)        

async def main():
    await uasyncio.gather(
        producer(),
        consumer1(),
        consumer2(),
    )

state = {'value': 0}
event = uasyncio.Event()

uasyncio.run(main())