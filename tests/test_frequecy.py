import smbus
import time

BUS = 1
ADDR = 0x40

MODE1 = 0x00
PRESCALE = 0xFE

bus = smbus.SMBus(BUS)

old = bus.read_byte_data(ADDR, MODE1)

print("MODE1 =", hex(old))

# Sleep
sleep = (old & 0x7F) | 0x10
bus.write_byte_data(ADDR, MODE1, sleep)

# Prescale = 121 (50Hz)
bus.write_byte_data(ADDR, PRESCALE, 121)

# Wake up
bus.write_byte_data(ADDR, MODE1, old)

time.sleep(0.005)

# Restart
bus.write_byte_data(ADDR, MODE1, old | 0x80)

print("PWM Frequency = 50Hz")