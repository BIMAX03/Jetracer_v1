"""Module điều khiển chính vòng lặp tự chạy (Line Following Pilot).

Kết hợp các module `LineDetector` và `PIDController` để đọc khung hình từ
camera CSI, tính toán sai số, xuất góc lái và tốc độ ga thích hợp rồi
truyền trực tiếp xuống lớp điều khiển phần cứng `Car`.
"""

import time
from car import Car


class _SilentLogger:
    """Fallback khi thiếu structlog — pilot vẫn chạy bình thường."""

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass


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

        # Trạng thái cua mù (blind turn) khi gặp góc cua gấp 90 độ
        self._blind_turn_active = False
        self._blind_turn_direction = 0
        self._blind_turn_start_time = 0.0

    def run(self, camera, debug_streamer=None) -> None:
        """Khởi chạy vòng lặp lái tự động.

        Args:
            camera: Đối tượng camera (có hàm .read() trả về BGR frame).
            debug_streamer: DebugStreamer tùy chọn — publish ảnh + thông số
                dò line lên trình duyệt mỗi vòng lặp.
        """
        self._running = True

        try:
            import structlog
            logger = structlog.get_logger()
        except ImportError:
            logger = _SilentLogger()

        try:
            logger.info("line_following_pilot_started", base_throttle=self.base_throttle)
            self.car.arm()  # Kích hoạt động cơ
            self.pid.reset()
        except BaseException:
            # Ctrl+C/exception trong lúc arm cũng phải dừng động cơ ngay
            self.stop()
            raise

        interval = 1.0 / 20.0  # Mặc định 20 Hz
        try:
            from line_following import config
            interval = 1.0 / config.LOOP_HZ
        except ImportError:
            pass

        try:
            last_time = time.monotonic()
            start_time = time.monotonic()
            frames_ok = 0
            empty_frames = 0
            line_hits = 0
            last_empty_warn = 0.0
            last_stats_log = 0.0
            last_render_time = time.monotonic()
            while self._running:
                start_loop = time.monotonic()
                frame = camera.read()
                if frame is None:
                    empty_frames += 1
                    # Không giữ ga cũ — đứng yên chờ camera trả frame trở lại
                    self.car.stop()
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

                try:
                    from line_following import config as lf_config
                    sharp_turn_thresh = getattr(lf_config, "SHARP_TURN_CONFIDENCE_THRESHOLD", 0.25)
                    blind_turn_timeout = getattr(lf_config, "BLIND_TURN_TIMEOUT", 2.0)
                    blind_turn_throttle_factor = getattr(lf_config, "BLIND_TURN_THROTTLE_FACTOR", 0.6)
                except ImportError:
                    sharp_turn_thresh = 0.25
                    blind_turn_timeout = 2.0
                    blind_turn_throttle_factor = 0.6

                # Luôn kiểm tra cua gấp trên MỌI frame (kể cả khi line OK)
                # Điều này cho phép phát hiện góc 90° SỚM, trước khi line thoát khỏi ROI
                # Lưu ý: check_sharp_turn xử lý mask=None bên trong bằng cách trả (0, 0.0)
                direction, confidence = self.detector.check_sharp_turn(mask)

                if error is not None:
                    line_hits += 1

                    if confidence > sharp_turn_thresh:
                        # Phát hiện góc cua gấp ngay cả khi error còn hợp lệ:
                        # Kích hoạt / làm mới blind turn, override PID bằng max steering
                        if not self._blind_turn_active:
                            self._blind_turn_active = True
                            self._blind_turn_direction = direction
                            self._blind_turn_start_time = now
                            logger.warning(
                                "blind_turn_started_early",
                                direction=direction,
                                confidence=round(confidence, 3),
                                error=round(error, 3),
                                timeout=blind_turn_timeout,
                            )
                        else:
                            # Làm mới timer khi vẫn thấy line và còn trong góc cua
                            self._blind_turn_start_time = now

                        steering = float(direction) * 1.0
                        throttle = self.base_throttle * blind_turn_throttle_factor

                    elif self._blind_turn_active:
                        # Đang trong blind turn, confidence đã giảm nhưng vẫn thấy line.
                        # Chỉ thoát blind turn khi error đủ nhỏ (xe đã thẳng hàng trở lại).
                        # KHÔNG thoát chỉ vì confidence giảm 1 frame (tránh bị abort giữa cua).
                        if abs(error) < 0.3:
                            self._blind_turn_active = False
                            logger.info("blind_turn_recovered_line", error=round(error, 3))

                        # Dù thoát hay không, vẫn bám line bằng PID
                        steering = self.pid.compute(error, dt)
                        throttle_scale = max(0.0, 1.0 - abs(error))
                        throttle = self.base_throttle * (0.6 + 0.4 * throttle_scale)

                    else:
                        # Bình thường: bám line theo PID
                        steering = self.pid.compute(error, dt)
                        throttle_scale = max(0.0, 1.0 - abs(error))
                        throttle = self.base_throttle * (0.6 + 0.4 * throttle_scale)

                else:
                    # error is None - mất dấu scan line
                    if self._blind_turn_active:
                        # Kiểm tra xem đã hết thời gian cua mù chưa
                        if now - self._blind_turn_start_time > blind_turn_timeout:
                            self._blind_turn_active = False
                            steering = 0.0
                            throttle = 0.0
                            logger.warning("blind_turn_timeout_stopping")
                        else:
                            # Tiếp tục rẽ mù theo hướng đã bắt đầu
                            steering = float(self._blind_turn_direction) * 1.0
                            throttle = self.base_throttle * blind_turn_throttle_factor
                            # Gán lại direction và confidence cho telemetry debug
                            direction = self._blind_turn_direction
                            confidence = 1.0  # Đánh dấu đang giữ cua mù
                    elif confidence > sharp_turn_thresh:
                        # Phát hiện cua lần đầu khi đã mất line - kích hoạt blind turn
                        self._blind_turn_active = True
                        self._blind_turn_direction = direction
                        self._blind_turn_start_time = now

                        steering = float(direction) * 1.0
                        throttle = self.base_throttle * blind_turn_throttle_factor
                        logger.warning(
                            "blind_turn_started",
                            direction=direction,
                            confidence=round(confidence, 3),
                            timeout=blind_turn_timeout,
                        )
                    else:
                        # Mất dấu hoàn toàn -> dừng hẳn
                        steering = 0.0
                        throttle = 0.0
                        logger.warning("line_lost_stopping")

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
        car.stop()
        camera.release()
        if streamer is not None:
            streamer.stop()
