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
ROI_START_ROW_PCT = 0.5  # Bắt đầu lấy từ 50% chiều cao ảnh xuống dưới

# --- Đường quét đích (Scan Line) ---
# Tỷ lệ chiều cao dòng quét trên vùng ROI dùng để tính sai số lệch tâm
SCAN_LINE_Y_PCT = 0.6    # Nằm ở 60% chiều cao của vùng ROI

# --- Cấu hình bộ điều khiển PID ---
KP = 1.20
KI = 0.0
KD = 0.15

# --- Cấu hình tốc độ chạy ---
BASE_THROTTLE = 0.22     # Tốc độ ga cơ bản khi chạy thẳng
MAX_STEERING_LIMIT = 1.0 # Giới hạn góc lái tối đa

# --- Thiết lập camera & Vòng lặp ---
CAMERA_DEVICE_ID = 0
LOOP_HZ = 20             # Tần số xử lý (Hz)

# --- Luồng debug trực quan (Dashboard web trên trình duyệt) ---
# Bật để xem ảnh camera + toàn bộ chỉ số + đồ thị realtime tại:
#     http://<IP-JETSON>:<port>/dashboard   ← dashboard đầy đủ (khuyến nghị)
#     http://<IP-JETSON>:<port>/            ← chỉ luồng MJPEG video
# khi pilot đang chạy (không chiếm cổng 5000 của web_control).
DEBUG_STREAM_ENABLED = True
DEBUG_STREAM_HOST = "0.0.0.0"
DEBUG_STREAM_PORT = 5001
DEBUG_STREAM_FPS = 20      # Tần số publish frame lên trình duyệt
DEBUG_STREAM_JPEG_QUALITY = 70
