"""Line Following Autopilot — Vòng lặp chính điều khiển xe dò line."""

from line_following.camera import PilotCamera
from line_following.detector import LineDetector
from line_following.pid import PIDController
from line_following import config
from car import Car

# ─── Khởi tạo ───────────────────────────────────────────────────
car = Car()
car.arm(duration=3.0)

cam = PilotCamera()
detector = LineDetector(config.LOWER_YELLOW, config.UPPER_YELLOW)
pid = PIDController()

# Thêm 2 biến này để xe "nhớ" trạng thái đang trong cua
is_turning = False
turn_dir = 0

print("Xe bắt đầu chạy... Nhấn Ctrl+C để dừng.")

try:
    while True:
        ok, frame = cam.read()
        if not ok or frame is None:
            continue

        error, mask, debug_frame = detector.get_line_error_moments(frame)
        direction, confidence = detector.check_sharp_turn(mask)

        # --- BƯỚC 1: CẬP NHẬT TRẠNG THÁI ---
        # Bắt đầu vào cua nếu confidence vọt qua ngưỡng
        if not is_turning and direction != 0 and confidence > config.SHARP_TURN_CONFIDENCE:
            is_turning = True
            turn_dir = direction
            print("\n>>> BẮT ĐẦU VÀO CUA GẮT <<<")

        # Kiểm tra xem đã rẽ xong chưa?
        if is_turning:
            # CHỈ thoát cua khi đã TÌM THẤY LINE (error != None) VÀ line đã nằm gần tâm
            if error is not None and abs(error) < 0.4:
                is_turning = False
                print(">>> ĐÃ THOÁT CUA, TRẢ LẠI CHO PID <<<\n")

            # ĐÃ XÓA NHÁNH `elif error is None: is_turning = False`
            # Giờ đây nếu error = None, xe vẫn giữ nguyên cờ is_turning = True để xoay tiếp

        # --- BƯỚC 2: THỰC THI LỆNH THEO TRẠNG THÁI ---
        if is_turning:
            # 1. Đang trong cua: Giữ chết vô lăng và đi chậm
            steering = turn_dir * config.MAX_STEERING
            throttle = 0.07
            pid.reset()  # Giữ PID ở trạng thái sạch chờ khi thoát cua

        elif error is not None:
            # 2. Đang đi thẳng: PID điều khiển
            steering, pid_terms = pid.compute(error)
            throttle = config.BASE_THROTTLE

        else:
            # 3. Lệch khỏi đường: Dừng khẩn cấp
            steering = 0.0
            throttle = 0.0
            pid.reset()

        # 3. CHÂN TAY LÀM: Truyền lệnh xuống bánh xe
        car.steering(steering)
        car.throttle(throttle)

        # Log ra màn hình để theo dõi
        err_str = f"{error:.1f}" if error is not None else "None"
        turn_status = "TURN" if is_turning else "PID "
        print(f"[{turn_status}] Error: {err_str:>6} | Steering: {steering:>5.2f} | Throttle: {throttle:>4.2f} | Turn Conf: {confidence:.2f}")

except KeyboardInterrupt:
    print("\nĐã nhận Ctrl+C.")

finally:
    # LUÔN dừng xe trước khi thoát
    car.stop()
    cam.release()
    print("Đã dừng xe và tắt camera.")