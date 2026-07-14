import smbus

bus = smbus.SMBus(1)

value = bus.read_byte_data(0x40, 0x00)

print("open ok")
print(hex(value))

