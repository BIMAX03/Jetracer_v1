import time
from drivers.pca9685 import PCA9685
from drivers.esc import ESC

pca = PCA9685(address=0x40, bus=1)
pca.wake()

# Khởi tạo ESC trên channel 1 
throttle = ESC(
    pca,
    channel=1,
    min_pulse_us=1000,
    max_pulse_us=2000,
)

print("Đưa ESC về mức trung tính (0.0)...")
throttle.neutral()
time.sleep(3) 

print("Tiến (0.4) trong 3 giây...")
throttle.write(0.4)
time.sleep(3) # Thay đổi thành 3 giây

print("Dừng động cơ...")
throttle.neutral() # Đưa về mức trung tính để dừng
