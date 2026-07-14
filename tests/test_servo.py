import time

from drivers.pca9685 import PCA9685
from drivers.servo import Servo

pca = PCA9685(address=0x40, bus=1)
pca.wake()

steering = Servo(
    pca,
    channel=0,
    min_pulse_us=1000,
    max_pulse_us=2000,
)

print("Center...")
steering.center()
time.sleep(1)

print("Left (-1.0)...")
steering.write(-1.0)
time.sleep(1)

print("Right (1.0)...")
steering.write(1.0)
time.sleep(1)

print("Back to center...")
steering.center()
