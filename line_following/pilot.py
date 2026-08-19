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

        import structlog
        logger = structlog.get_logger()
        logger.info("line_following_pilot_started", base_throttle=self.base_throttle)

        interval = 1.0 / 20.0  # Mặc định 20 Hz
        try:
            from line_following import config
            interval = 1.0 / config.LOOP_HZ
        except ImportError:
            pass

        last_time = time.monotonic()
        try:
            while self._running:
                start_loop = time.monotonic()
                frame = camera.read()
                if frame is None:
                    logger.warning("pilot_empty_frame")
                    time.sleep(0.01)
                    continue

                # 1. Tính toán sai số lệch tâm
                error, mask, debug_frame = self.detector.get_line_error(frame)
                
                # 2. Tính dt cho PID
                now = time.monotonic()
                dt = now - last_time
                last_time = now

                steering = 0.0
                throttle = 0.0

                if error is not None:
                    # Phát hiện line -> tính toán góc lái và ga động
                    steering = self.pid.compute(error, dt)
                    
                    # Ga động: đi thẳng -> nhanh hơn, cua -> chậm lại
                    throttle_scale = max(0.0, 1.0 - abs(error))
                    throttle = self.base_throttle * (0.6 + 0.4 * throttle_scale)
                else:
                    # Mất dấu ở dòng quét chính -> Kiểm tra cua vuông góc
                    direction, confidence = self.detector.check_sharp_turn(mask)
                    if confidence > 0.25:
                        steering = float(direction) * 1.0  # Đánh lái kịch sàn theo hướng rẽ
                        throttle = self.base_throttle * 0.6
                        logger.warning("sharp_turn_detected", direction=direction, confidence=confidence)
                    else:
                        # Mất dấu hoàn toàn -> chạy rất chậm tìm lại đường
                        steering = 0.0
                        throttle = self.base_throttle * 0.4
                        logger.warning("line_lost_searching")

                # Gửi lệnh trực tiếp điều khiển xe
                self.car.steering(steering)
                self.car.throttle(throttle)

                # Giới hạn tần số vòng lặp
                elapsed = time.monotonic() - start_loop
                sleep_time = max(0.0, interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("pilot_interrupted_by_user")
        finally:
            self.stop()

    def stop(self) -> None:
        """Dừng khẩn cấp và tắt động cơ an toàn."""
        self._running = False
        self.car.stop()
        pass


if __name__ == "__main__":
    import cv2 as _cv2
    from line_following import config
    from line_following.detector import LineDetector
    from line_following.pid import PIDController
    
    class SimpleCamera:
        def __init__(self, device_id: int = 0):
            try:
                from web_control.camera import gstreamer_pipeline
                self.cap = _cv2.VideoCapture(gstreamer_pipeline(), _cv2.CAP_GSTREAMER)
            except Exception:
                self.cap = _cv2.VideoCapture(device_id)

        def read(self):
            ok, frame = self.cap.read()
            return frame if ok else None

    car = Car()
    detector = LineDetector(config.LOWER_YELLOW, config.UPPER_YELLOW)
    pid = PIDController(config.KP, config.KI, config.KD)
    
    pilot = LineFollowingPilot(car, detector, pid, config.BASE_THROTTLE)
    camera = SimpleCamera(config.CAMERA_DEVICE_ID)
    
    print("Bắt đầu chạy dò line tự động... Nhấn Ctrl+C để dừng và tắt động cơ.")
    pilot.run(camera)
