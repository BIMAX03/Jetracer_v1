import smbus
import time 

I2C_BUS  = 1
PCA9658_ADDR = 0x40
MODE1 = 0x00

bus = smbus.SMBus(I2C_BUS)

# đọc mode1
mode1 = bus.read_byte_data(PCA9658_ADDR, MODE1)
print("Before: ", hex(mode1))

# xóa bit SLEEP (bit 4)
mode1 &= ~0x10

# ghi lại 
bus.write_byte_data(PCA9658_ADDR, MODE1, mode1)

time.sleep(0.001)

# đọc lại
mode1 = bus.read_byte_data(PCA9658_ADDR, MODE1)
print("After :", hex(mode1))