"""Cấu hình cho thuật toán dò line (Line Following).

Chứa các tham số hiệu chỉnh màu sắc, bộ điều khiển PID và các thiết lập
vận hành của xe khi chạy chế độ dò line.
"""

import numpy as np

# --- Cấu hình lọc màu HSV (Yellow Line) ---
# Dải màu vàng mặc định cho sa bàn (cần tinh chỉnh tùy điều kiện ánh sáng thực tế)
LOWER_YELLOW = np.array([15, 80, 80], dtype=np.uint8)
UPPER_YELLOW = np.array([35, 255, 255], dtype=np.uint8)

# --- Cấu hình Vùng quan tâm (ROI) ---
# Chỉ xử lý phần dưới của bức ảnh để tránh nhiễu và tăng tốc độ xử lý
ROI_START_ROW_PCT = 0.3  # phần trăm chiều cao ảnh được giữ lại

# --- Đường quét đích (Scan Line) ---
# Tỷ lệ chiều cao dòng quét trên vùng ROI dùng để tính sai số lệch tâm
SCAN_LINE_Y_PCT = 0.6    # Nằm ở 60% chiều cao của vùng ROI

# Cấu hình Camera
CAMERA_INDEX = 0          # 0: Camera mặc định / USB Cam, hoặc đường dẫn RTSP / video file
FRAME_WIDTH = 640         # Khuyến nghị 320x240 hoặc 640x360 để giữ FPS > 30 trên Raspberry Pi/Jetson
FRAME_HEIGHT = 480
FRAME_FPS = 30

# Thông số PID cho vô lăng (steering)
KP = 0.3 # Tỷ lệ phần trăm vô lăng cần bẻ so với góc lệch tâm
KI = 0.0 # Tỷ lệ phần trăm vô lăng cần bẻ so với tổng sai số tích lũy
KD = 0.07 # Tỷ lệ phần trăm vô lăng cần bẻ so với tốc độ thay đổi của sai số

BASE_THROTTLE = 0.10 # Tốc độ cơ bản khi chạy thẳng

MAX_STEERING = 1.0 # gốc lái tối đa

# Ngưỡng quyết định rẽ gấp (Tăng lên nếu xe bị rẽ nhầm ở đoạn thẳng)
SHARP_TURN_CONFIDENCE = 0.46
