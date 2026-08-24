"""Module điều khiển chính vòng lặp tự chạy (Line Following Pilot).

Kết hợp các module `LineDetector` và `LineFollowController` (PID + state
machine xử lý cua gấp) để đọc khung hình từ camera CSI, tính toán sai số,
xuất góc lái và tốc độ ga thích hợp rồi truyền trực tiếp xuống lớp điều
khiển phần cứng `Car`.
"""

import time
from car import Car
from line_following.pid import LineFollowController


class _SilentLogger:
    """Fallback khi thiếu structlog — pilot vẫn chạy bình thường."""

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass


class LineFollowingPilot:
    """Vòng lặp điều khiển lái tự động theo line (Autopilot).

    Lớp này CHỈ lo vòng lặp I/O, logging, debug streaming và đảm bảo an
    toàn (dừng xe khi thoát). Mọi quyết định lái/ga được uỷ thác hoàn toàn
    cho `LineFollowController.update()` — bao gồm cả chế độ "chạy mù" qua
    cua gấp (BLIND_TURN) và "mất line dừng hẳn" (LOST).
    """

    def __init__(self, car: Car, detector, controller: LineFollowController, base_throttle: float) -> None:
        """Khởi tạo với các thành phần điều khiển xe, dò line và controller.

        Args:
            car: Đối tượng Car điều khiển phần cứng của xe JetRacer.
            detector: Instance của LineDetector (cung cấp `get_line_error()`
                và `predict_turn_ahead()`).
            controller: Instance `LineFollowController` bao bọc PID + state
                machine xử lý cua gấp. Nhận trực tiếp `base_throttle` qua
                thuộc tính, nên `pilot` chỉ cần giữ tham số này để log/UI.
            base_throttle: Tốc độ ga cơ bản (tham chiếu, controller đã có).
        """
        self.car = car
        self.detector = detector
        self.controller = controller
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

        try:
            import structlog
            logger = structlog.get_logger()
        except ImportError:
            logger = _SilentLogger()

        try:
            logger.info(
                "line_following_pilot_started",
                base_throttle=self.base_throttle,
                blind_turn_duration_sec=self.controller.blind_turn_duration_sec,
            )
            self.car.arm()  # Kích hoạt động cơ
            self.controller.pid.reset()
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
            blind_turn_events = 0
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

                # 2. Dự đoán cua gấp phía trước (dựa trên mask của frame này)
                turn_incoming, turn_direction, turn_severity = self.detector.predict_turn_ahead(mask)

                # 3. Tính dt cho PID / state machine
                now = time.monotonic()
                dt = now - last_time
                last_time = now

                if error is not None:
                    line_hits += 1

                prev_state = self.controller.state
                cmd = self.controller.update(
                    error=error,
                    turn_incoming=turn_incoming,
                    turn_direction=turn_direction,
                    turn_severity=turn_severity,
                    dt=dt,
                )
                if prev_state != cmd.state:
                    logger.warning(
                        "drive_state_change",
                        from_state=str(prev_state.value),
                        to_state=str(cmd.state.value),
                        error=error,
                        turn_incoming=turn_incoming,
                        turn_direction=turn_direction,
                        turn_severity=round(turn_severity, 3),
                    )
                if cmd.state.value == "BLIND_TURN" and prev_state.value != "BLIND_TURN":
                    blind_turn_events += 1

                steering = cmd.steering
                throttle = cmd.throttle
                confidence = turn_severity
                direction = turn_direction

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
                    pid_terms = self.controller.pid.last_terms

                    if cmd.state.value == "NORMAL":
                        status_text = "line_ok"
                    elif cmd.state.value == "BLIND_TURN":
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
                            "state": cmd.state.value,
                            "blind_turn_elapsed": cmd.blind_turn_elapsed,
                        },
                    )
                    last_render_time = render_start
                    debug_streamer.publish_metrics({
                        "ts": time.monotonic(),
                        "uptime_s": now - start_time,
                        "status": status_text,
                        "state": cmd.state.value,
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
                        "blind_turn_events": blind_turn_events,
                        "blind_turn_elapsed": cmd.blind_turn_elapsed,
                        "kp": self.controller.pid.kp,
                        "ki": self.controller.pid.ki,
                        "kd": self.controller.pid.kd,
                        "base_throttle": self.base_throttle,
                    })
                    debug_streamer.publish(overlay)

                now = time.monotonic()
                if now - last_stats_log >= 5.0:
                    logger.info(
                        "pilot_status",
                        frames_ok=frames_ok,
                        line_hits=line_hits,
                        blind_turn_events=blind_turn_events,
                        state=cmd.state.value,
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
    controller = LineFollowController(
        pid=pid,
        base_throttle=config.BASE_THROTTLE,
        max_steering_limit=config.MAX_STEERING_LIMIT,
        blind_turn_duration_sec=config.BLIND_TURN_DURATION_SEC,
        blind_turn_throttle=config.BLIND_TURN_THROTTLE,
        blind_turn_steer_ratio=config.BLIND_TURN_STEER_RATIO,
    )

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

    pilot = LineFollowingPilot(car, detector, controller, config.BASE_THROTTLE)

    print("Bắt đầu chạy dò line tự động... Nhấn Ctrl+C để dừng và tắt động cơ.")
    try:
        pilot.run(camera, debug_streamer=streamer)
    finally:
        car.stop()
        camera.release()
        if streamer is not None:
            streamer.stop()
