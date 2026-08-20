"""Script hỗ trợ hiệu chuẩn thông số (Calibration Tool).

Sử dụng OpenCV window với thanh trượt (Trackbars) để người dùng có thể
tự do tinh chỉnh dải màu HSV (Lower/Upper) và các tham số PID trực quan
trên luồng camera trực tiếp của xe trước khi cho chạy thật.
"""

import os
import cv2
import numpy as np
from line_following import config
from line_following.detector import LineDetector


def nothing(x):
    pass


def main():
    """Tạo cửa sổ GUI hiển thị và thanh trượt tinh chỉnh thông số."""
    cv2.namedWindow("Calibration")
    
    # Lấy các thông số hiện tại từ config
    h_min, s_min, v_min = config.LOWER_YELLOW
    h_max, s_max, v_max = config.UPPER_YELLOW
    
    kp_val = int(config.KP * 100)
    kd_val = int(config.KD * 100)

    # Khởi tạo các thanh trượt
    cv2.createTrackbar("H Min", "Calibration", h_min, 180, nothing)
    cv2.createTrackbar("H Max", "Calibration", h_max, 180, nothing)
    cv2.createTrackbar("S Min", "Calibration", s_min, 255, nothing)
    cv2.createTrackbar("S Max", "Calibration", s_max, 255, nothing)
    cv2.createTrackbar("V Min", "Calibration", v_min, 255, nothing)
    cv2.createTrackbar("V Max", "Calibration", v_max, 255, nothing)
    
    cv2.createTrackbar("Kp x100", "Calibration", kp_val, 500, nothing)
    cv2.createTrackbar("Kd x100", "Calibration", kd_val, 500, nothing)

    # Khởi tạo camera
    try:
        from web_control.camera import gstreamer_pipeline
        cap = cv2.VideoCapture(gstreamer_pipeline(), cv2.CAP_GSTREAMER)
    except Exception:
        cap = cv2.VideoCapture(config.CAMERA_DEVICE_ID)

    if not cap.isOpened():
        print("Không thể mở Camera.")
        return

    print("\n=== CÔNG CỤ HIỆU CHUẨN DÒ LINE (OPENCV) ===")
    print("1. Kéo các thanh trượt HSV để lọc sạch vạch màu vàng.")
    print("2. Kéo thanh trượt Kp/Kd để điều chỉnh độ bẻ lái nhạy hay êm.")
    print("3. Nhấn phím 's' để lưu cấu hình đè vào tệp config.py.")
    print("4. Nhấn phím 'q' hoặc ESC để thoát ứng dụng.")
    print("============================================\n")

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            print("Không đọc được frame từ camera.")
            break

        # Lấy giá trị thanh trượt hiện tại
        h_min = cv2.getTrackbarPos("H Min", "Calibration")
        h_max = cv2.getTrackbarPos("H Max", "Calibration")
        s_min = cv2.getTrackbarPos("S Min", "Calibration")
        s_max = cv2.getTrackbarPos("S Max", "Calibration")
        v_min = cv2.getTrackbarPos("V Min", "Calibration")
        v_max = cv2.getTrackbarPos("V Max", "Calibration")
        
        kp_track = cv2.getTrackbarPos("Kp x100", "Calibration") / 100.0
        kd_track = cv2.getTrackbarPos("Kd x100", "Calibration") / 100.0

        lower_color = np.array([h_min, s_min, v_min], dtype=np.uint8)
        upper_color = np.array([h_max, s_max, v_max], dtype=np.uint8)

        detector = LineDetector(lower_color, upper_color)
        error, mask, debug_frame = detector.get_line_error(frame)

        # Hiển thị ảnh debug và mặt nạ nhị phân
        cv2.imshow("Original / Debug", debug_frame)
        cv2.imshow("Yellow Mask", mask)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('s'):
            config_path = os.path.join(os.path.dirname(__file__), "config.py")
            config_content = f"""\"\"\"Cấu hình cho thuật toán dò line (Line Following).

Chứa các tham số hiệu chỉnh màu sắc, bộ điều khiển PID và các thiết lập
vận hành của xe khi chạy chế độ dò line.
\"\"\"

import numpy as np

# --- Cấu hình lọc màu HSV (Yellow Line) ---
# Dải màu vàng mặc định cho sa bàn (cần tinh chỉnh tùy điều kiện ánh sáng thực tế)
LOWER_YELLOW = np.array([{h_min}, {s_min}, {v_min}], dtype=np.uint8)
UPPER_YELLOW = np.array([{h_max}, {s_max}, {v_max}], dtype=np.uint8)

# --- Cấu hình Vùng quan tâm (ROI) ---
# Chỉ xử lý phần dưới của bức ảnh để tránh nhiễu và tăng tốc độ xử lý
ROI_START_ROW_PCT = {config.ROI_START_ROW_PCT}  # Bắt đầu lấy từ 50% chiều cao ảnh xuống dưới

# --- Đường quét đích (Scan Line) ---
# Tỷ lệ chiều cao dòng quét trên vùng ROI dùng để tính sai số lệch tâm
SCAN_LINE_Y_PCT = {config.SCAN_LINE_Y_PCT}    # Nằm ở 60% chiều cao của vùng ROI

# --- Cấu hình bộ điều khiển PID ---
KP = {kp_track:.2f}
KI = {config.KI}
KD = {kd_track:.2f}

# --- Cấu hình tốc độ chạy ---
BASE_THROTTLE = {config.BASE_THROTTLE}     # Tốc độ ga cơ bản khi chạy thẳng
MAX_STEERING_LIMIT = {config.MAX_STEERING_LIMIT} # Giới hạn góc lái tối đa

# --- Thiết lập camera & Vòng lặp ---
CAMERA_DEVICE_ID = {config.CAMERA_DEVICE_ID}
LOOP_HZ = {config.LOOP_HZ}             # Tần số xử lý (Hz)

# --- Luồng debug trực quan (MJPEG trên trình duyệt) ---
# Bật để xem ảnh camera + thông số theo thời gian thực tại:
#     http://<IP-JETSON>:<port>
# khi pilot đang chạy (không chiếm cổng 5000 của web_control).
DEBUG_STREAM_ENABLED = {config.DEBUG_STREAM_ENABLED}
DEBUG_STREAM_HOST = "{config.DEBUG_STREAM_HOST}"
DEBUG_STREAM_PORT = {config.DEBUG_STREAM_PORT}
DEBUG_STREAM_FPS = {config.DEBUG_STREAM_FPS}      # Tần số publish frame lên trình duyệt
DEBUG_STREAM_JPEG_QUALITY = {config.DEBUG_STREAM_JPEG_QUALITY}
"""
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(config_content)
            print(f"Đã lưu cấu hình mới thành công vào {config_path}!")
            print(f"LOWER_YELLOW = [{h_min}, {s_min}, {v_min}]")
            print(f"UPPER_YELLOW = [{h_max}, {s_max}, {v_max}]")
            print(f"KP = {kp_track:.2f}, KD = {kd_track:.2f}")

        elif key == ord('q') or key == 27:  # q hoặc ESC để thoát
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
