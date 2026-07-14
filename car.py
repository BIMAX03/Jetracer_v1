"""High-level vehicle controller.

Gộp Servo (lái) + ESC (ga) thành một giao diện duy nhất.
Đây là lớp mà tầng web sẽ gọi — không bao giờ truy cập
PCA9685 hay driver cấp thấp trực tiếp.

Ví dụ sử dụng:
    car = Car()
    car.steering(-0.5)   # rẽ trái 50%
    car.throttle(0.4)    # tiến 40%
    car.stop()           # dừng khẩn cấp
"""

import config
from drivers.pca9685 import PCA9685
from drivers.servo import Servo
from drivers.esc import ESC


class Car:
    """Đối tượng xe cấp cao — giao diện duy nhất để điều khiển JetRacer.

    Attributes:
        _pca:      Instance PCA9685 duy nhất, chia sẻ cho servo và ESC.
        _servo:    Điều khiển servo lái (channel 0).
        _esc:      Điều khiển ESC ga (channel 1).
    """

    def __init__(self) -> None:
        # Tạo 1 PCA9685 duy nhất — cả servo và ESC đều dùng chung chip
        self._pca = PCA9685(
            address=config.PCA9685_ADDRESS,
            bus=config.PCA9685_BUS
        )

        self._pca.wake()

        # Servo lái — channel 0
        self._servo = Servo(
            pca=self._pca,
            channel=config.STEERING_CHANNEL,
            freq=config.STEERING_FREQ,
            min_pulse_us=config.STEERING_MIN_PULSE_US,
            max_pulse_us=config.STEERING_MAX_PULSE_US,
            gain=config.STEERING_GAIN,
            offset=config.STEERING_OFFSET
        )

        # ESC ga — channel 1
        self._esc = ESC(
            pca=self._pca,
            channel=config.THROTTLE_CHANNEL,
            freq=config.THROTTLE_FREQ,
            min_pulse_us=config.THROTTLE_MIN_PULSE_US,
            max_pulse_us=config.THROTTLE_MAX_PULSE_US,
            gain=config.THROTTLE_GAIN,
            offset=config.THROTTLE_OFFSET
        )

    def steering(self, value: float) -> None:
        """Điều khiển lái.

        Args:
            value: -1.0 (trái hết) → 0.0 (thẳng) → 1.0 (phải hết)
                   Giá trị sẽ bị clamp theo STEERING_LIMIT trong config.
        """
        limit = config.STEERING_LIMIT
        clamped = max(-limit, min(limit, value))
        self._servo.write(clamped)

    def throttle(self, value: float) -> None:
        """Điều khiển ga.

        Args:
            value: -1.0 (lùi hết) → 0.0 (dừng) → 1.0 (tiến hết)
                   Giá trị sẽ bị clamp theo THROTTLE_LIMIT trong config.
        """
        limit = config.THROTTLE_LIMIT
        clamped = max(-limit, min(limit, value))
        self._esc.write(clamped)

    def stop(self) -> None:
        """Dừng khẩn cấp — ga về 0 VÀ lái về giữa ngay lập tức."""
        self._esc.neutral()
        self._servo.center()
