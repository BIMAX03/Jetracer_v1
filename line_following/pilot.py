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

    def run(self, camera, debug_streamer=None) -> None:
        """Khởi chạy vòng lặp lái tự động.

        Args:
            camera: Đối tượng camera (có hàm .read() trả về BGR frame).
            debug_streamer: DebugStreamer tùy chọn — publish ảnh + thông số
                dò line lên trình duyệt mỗi vòng lặp.
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
        start_time = time.monotonic()
        frames_ok = 0
        empty_frames = 0
        line_hits = 0
        last_empty_warn = 0.0
        last_stats_log = 0.0
        last_render_time = time.monotonic()
        try:
            while self._running:
                start_loop = time.monotonic()
                frame = camera.read()
                if frame is None:
                    empty_frames += 1
                    now = time.monotonic()
                    if now - last_empty_warn >= 1.0:
                        logger.warning(
                            "pilot_empty_frame",
                            hint="Camera không trả frame — web_control đang chiếm camera? "
                                 "Dừng: sudo systemctl stop jetracer",
                        )
                        last_empty_warn = now
                    time.sleep(0.01)
                    continue
                frames_ok += 1

                # 1. Tính toán sai số lệch tâm
                error, mask, _ = self.detector.get_line_error(frame)
                
                # 2. Tính dt cho PID
                now = time.monotonic()
                dt = now - last_time
                last_time = now

                steering = 0.0
                throttle = 0.0
                direction = 0
                confidence = 0.0

                if error is not None:
                    # Phát hiện line -> tính toán góc lái và ga động
                    line_hits += 1
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

                # Publish frame debug + telemetry lên dashboard trình duyệt
                if debug_streamer is not None:
                    from line_following.camera import render_debug_frame
                    render_start = time.monotonic()
                    now = time.monotonic()
                    loop_hz = 1.0 / max(dt, 1e-6)
                    render_fps = 1.0 / max(render_start - last_render_time, 1e-6)
                    pid_terms = self.pid.last_terms

                    if error is not None:
                        status_text = "line_ok"
                    elif confidence > 0.25:
                        status_text = "sharp_turn"
                    else:
                        status_text = "line_lost"

                    overlay = render_debug_frame(
                        frame,
                        mask=mask,
                        error=error,
                        steering=steering,
                        throttle=throttle,
                        pid_terms=pid_terms,
                        meta={
                            "frames": frames_ok,
                            "line_hits": line_hits,
                            "loop_hz": loop_hz,
                            "fps": render_fps,
                            "dt_ms": dt * 1000.0,
                            "base_throttle": self.base_throttle,
                            "direction": direction,
                            "confidence": confidence,
                        },
                    )
                    last_render_time = render_start
                    debug_streamer.publish_metrics({
                        "ts": time.monotonic(),
                        "uptime_s": now - start_time,
                        "status": status_text,
                        "error": error,
                        "steering": steering,
                        "throttle": throttle,
                        "p": pid_terms.get("p", 0.0),
                        "i": pid_terms.get("i", 0.0),
                        "d": pid_terms.get("d", 0.0),
                        "direction": direction,
                        "confidence": confidence,
                        "loop_hz": loop_hz,
                        "fps": render_fps,
                        "dt_ms": dt * 1000.0,
                        "frames": frames_ok,
                        "line_hits": line_hits,
                        "empty_frames": empty_frames,
                        "kp": self.pid.kp,
                        "ki": self.pid.ki,
                        "kd": self.pid.kd,
                        "base_throttle": self.base_throttle,
                    })
                    debug_streamer.publish(overlay)

                now = time.monotonic()
                if now - last_stats_log >= 5.0:
                    logger.info(
                        "pilot_status",
                        frames_ok=frames_ok,
                        line_hits=line_hits,
                        steering=round(steering, 3),
                        throttle=round(throttle, 3),
                    )
                    last_stats_log = now

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
    import sys as _sys
    from line_following import config
    from line_following.camera import DebugStreamer, PilotCamera
    from line_following.detector import LineDetector
    from line_following.pid import PIDController

    car = Car()
    detector = LineDetector(config.LOWER_YELLOW, config.UPPER_YELLOW)
    pid = PIDController(config.KP, config.KI, config.KD)

    try:
        camera = PilotCamera(config.CAMERA_DEVICE_ID)
    except RuntimeError as exc:
        print(exc, file=_sys.stderr)
        _sys.exit(1)

    streamer = None
    if config.DEBUG_STREAM_ENABLED:
        streamer = DebugStreamer()
        if streamer.start():
            print("Debug dashboard: http://<IP-JETSON>:{}/dashboard".format(streamer.port))
            print("Video only    : http://<IP-JETSON>:{}/".format(streamer.port))
        else:
            print(
                "Cảnh báo: không mở được debug stream cổng {} "
                "(có thể bị chiếm). Pilot vẫn chạy bình thường."
                .format(streamer.port),
                file=_sys.stderr,
            )

    pilot = LineFollowingPilot(car, detector, pid, config.BASE_THROTTLE)

    print("Bắt đầu chạy dò line tự động... Nhấn Ctrl+C để dừng và tắt động cơ.")
    try:
        pilot.run(camera, debug_streamer=streamer)
    finally:
        camera.release()
        if streamer is not None:
            streamer.stop()
