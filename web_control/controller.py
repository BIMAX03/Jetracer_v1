"""Cầu nối giữa tầng web (Flask) và tầng phần cứng (Car).

Flask routes gọi CarController — CarController gọi Car.
Không bao giờ gọi Car trực tiếp từ Flask.

Lớp này đảm nhận:
    1. Giữ instance Car duy nhất (tránh xung đột I2C).
    2. Validate + clamp giá trị đầu vào từ web.
    3. Theo dõi trạng thái hiện tại (steering, throttle).
"""

import threading

import config
from car import Car


class CarController:
    """Bộ điều khiển trung gian — validate input rồi chuyển xuống Car.

    Attributes:
        _car:               Instance Car duy nhất.
        _current_steering:  Giá trị lái hiện tại (-1.0 .. 1.0).
        _current_throttle:  Giá trị ga hiện tại  (-1.0 .. 1.0).
    """

    def __init__(self, car=None) -> None:
        self._car = Car() if car is None else car
        self._state_lock = threading.Lock()
        self._current_steering: float = 0.0
        self._current_throttle: float = 0.0

    @staticmethod
    def _clamp(value: float,
               min_val: float = -1.0,
               max_val: float = 1.0) -> float:
        """Giới hạn value trong khoảng [min_val, max_val]."""
        return max(min_val, min(max_val, value))

    def set_steering(self, value: float) -> dict:
        """Đặt giá trị lái và trả về trạng thái.

        Args:
            value: -1.0 (trái hết) → 0.0 (thẳng) → 1.0 (phải hết)

        Returns:
            dict chứa trạng thái hiện tại, dùng để Flask trả JSON.
        """
        clamped = self._clamp(
            value,
            -config.STEERING_LIMIT,
            config.STEERING_LIMIT,
        )
        with self._state_lock:
            self._car.steering(clamped)
            self._current_steering = clamped

        return self.get_status()

    def set_throttle(self, value: float) -> dict:
        """Đặt giá trị ga và trả về trạng thái.

        Args:
            value: -1.0 (lùi hết) → 0.0 (dừng) → 1.0 (tiến hết)

        Returns:
            dict chứa trạng thái hiện tại.
        """
        clamped = self._clamp(
            value,
            -config.THROTTLE_LIMIT,
            config.THROTTLE_LIMIT,
        )
        with self._state_lock:
            self._car.throttle(clamped)
            self._current_throttle = clamped

        return self.get_status()

    def set_control(self, steering: float, throttle: float) -> dict:
        """Cập nhật lái và ga trong cùng một critical section I2C.

        Web dùng endpoint này để một thao tác kéo chỉ tạo một request và không
        làm hàng trăm request steering/throttle cũ xếp hàng.
        """
        steering = self._clamp(
            steering,
            -config.STEERING_LIMIT,
            config.STEERING_LIMIT,
        )
        throttle = self._clamp(
            throttle,
            -config.THROTTLE_LIMIT,
            config.THROTTLE_LIMIT,
        )
        with self._state_lock:
            self._car.steering(steering)
            self._car.throttle(throttle)
            self._current_steering = steering
            self._current_throttle = throttle
            return {
                "steering": self._current_steering,
                "throttle": self._current_throttle,
            }

    def arm(self, duration: float = 3.0) -> dict:
        """Center servo và giữ ESC neutral trước khi cho phép điều khiển."""
        with self._state_lock:
            self._car.arm(duration=duration)
            self._current_steering = 0.0
            self._current_throttle = 0.0
            return {
                "steering": self._current_steering,
                "throttle": self._current_throttle,
            }

    def stop(self) -> dict:
        """Dừng khẩn cấp — ga về 0, lái về giữa.

        Returns:
            dict chứa trạng thái sau khi dừng.
        """
        with self._state_lock:
            self._car.stop()
            self._current_steering = 0.0
            self._current_throttle = 0.0

        return self.get_status()

    def get_status(self) -> dict:
        """Trả về trạng thái hiện tại dưới dạng dict (Flask sẽ convert sang JSON).

        Returns:
            {"steering": float, "throttle": float}
        """
        with self._state_lock:
            return {
                "steering": self._current_steering,
                "throttle": self._current_throttle
            }
