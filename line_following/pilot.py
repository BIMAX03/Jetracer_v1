"""Module điều khiển chính vòng lặp tự chạy (Line Following Pilot).

Kết hợp các module `LineDetector` và `PIDController` để đọc khung hình từ
camera CSI, tính toán sai số, xuất góc lái và tốc độ ga thích hợp rồi
truyền trực tiếp xuống lớp điều khiển phần cứng `Car`.
"""

import time
from car import Car


class LineFollowingPilot:
    """Vòng lặp điều khiển lái tự động theo line (Autopilot)."""

    def __init__(self, car: Car, detector, pid_controller, base_throttle: float) -> None:
        """Khởi tạo với các thành phần điều khiển xe, dò line và PID.

        Args:
            car: Đối tượng Car điều khiển phần cứng của xe JetRacer.
            detector: Instance của LineDetector.
            pid_controller: Instance của PIDController.
            base_throttle: Tốc độ ga cơ bản.
        """
        self.car = car
        self.detector = detector
        self.pid = pid_controller
        self.base_throttle = base_throttle
        self._running = False

    def run(self, camera) -> None:
        """Khởi chạy vòng lặp lái tự động.

        Args:
            camera: Đối tượng camera (có hàm .read() trả về BGR frame).
        """
        self._running = True
        self.car.arm()  # Kích hoạt động cơ
        self.pid.reset()

        # TODO: Implement main while self._running loop
        # TODO: Read frame from camera
        # TODO: Get error from detector
        # TODO: Feed error to PID to get steering
        # TODO: Apply dynamic throttle based on error size
        # TODO: Set steering and throttle on car
        # TODO: Implement KeyboardInterrupt handler for safety
        pass

    def stop(self) -> None:
        """Dừng khẩn cấp và tắt động cơ an toàn."""
        self._running = False
        self.car.stop()
        pass
