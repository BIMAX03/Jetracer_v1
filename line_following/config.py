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
MIN_LINE_WIDTH_PX = 15   # Số lượng pixel tối thiểu trên đường quét để coi là phát hiện được line

# --- Cấu hình dự đoán cua gấp phía trước (Look-ahead Turn Prediction) ---
# Dùng bởi LineDetector.predict_turn_ahead(): quét nhiều dòng từ xa -> gần
# trong ROI để phát hiện cua gấp TRƯỚC KHI mất dấu line hoàn toàn.
LOOKAHEAD_SCAN_PCTS = [0.05, 0.15, 0.25, 0.35]  # % chiều cao ROI, xa -> gần
TURN_EDGE_MARGIN_PX = 20          # px, ngưỡng coi là line "chạm mép" ROI
TURN_DRIFT_THRESHOLD_PX = 150     # px trôi ngang giữa các dòng để coi là cua gấp

# --- Cấu hình bộ điều khiển PID ---
KP = 1.20
KI = 0.0
KD = 0.15

# --- Cấu hình tốc độ chạy ---
BASE_THROTTLE = 0.12     # Tốc độ ga cơ bản khi chạy thẳng
MAX_STEERING_LIMIT = 1.0 # Giới hạn góc lái tối đa

# --- Cấu hình chế độ "đánh lái mù" khi phát hiện cua gấp (Blind Turn) ---
# Khi LineDetector.predict_turn_ahead() báo có cua sắp tới (hoặc line mất
# đột ngột), xe sẽ đánh lái tối đa theo hướng cua và chạy "mù" (không cần
# thấy line) tối đa BLIND_TURN_DURATION_SEC giây để đi hết khúc cua 90 độ.
# Nếu trong lúc đó thấy lại line thì thoát chế độ này ngay lập tức.
BLIND_TURN_DURATION_SEC = 2.0     # Thời gian tối đa chạy mù qua cua (giây)
BLIND_TURN_THROTTLE = 0.08        # Ga chậm hơn bình thường khi chạy mù qua cua
BLIND_TURN_STEER_RATIO = 1.0      # Tỉ lệ nhân với MAX_STEERING_LIMIT khi khóa lái

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