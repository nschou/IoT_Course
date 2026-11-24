"""Raw UART diagnostic for the LD2410 enter-configuration command.

This bypasses the driver parser. It distinguishes a missing TX/ACK path from
an ACK parsing problem.
"""

import time

from machine import Pin, UART


uart = UART(1, baudrate=115200, bits=8, parity=None, stop=1,
            tx=Pin(15), rx=Pin(16))
enter_config = bytes((
    0xFD, 0xFC, 0xFB, 0xFA,
    0x04, 0x00,
    0xFF, 0x00, 0x01, 0x00,
    0x04, 0x03, 0x02, 0x01,
))

# Remove data already emitted before the command.
while uart.any():
    count = uart.any()
    if not uart.read(count):
        break

print("TX:", enter_config.hex())
print("Sending enter-configuration command...")
uart.write(enter_config)

received = bytearray()
deadline = time.ticks_add(time.ticks_ms(), 1000)
while time.ticks_diff(deadline, time.ticks_ms()) > 0:
    count = uart.any()
    if count:
        data = uart.read(count)
        if data:
            received.extend(data)
    else:
        time.sleep_ms(1)

print("RX bytes:", len(received))
print("RX:", bytes(received).hex())
ack = bytes((0xFD, 0xFC, 0xFB, 0xFA, 0x08, 0x00,
             0xFF, 0x01, 0x00, 0x00))
if ack in received:
    print("ACK detected: TX and radar command response are working")
    exit_config = bytes((0xFD, 0xFC, 0xFB, 0xFA,
                         0x02, 0x00, 0xFE, 0x00,
                         0x04, 0x03, 0x02, 0x01))
    uart.write(exit_config)
else:
    print("ACK not detected: check ESP32 TX15 -> LD2410 RX, baudrate, and GND")
