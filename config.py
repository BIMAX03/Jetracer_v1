"""Centralized configuration for the JetRacer project.

Every tunable parameter lives here — hardware channels, PWM calibration,
safety limits, and web server settings.  Other modules import from this
file so there are zero magic numbers scattered around the codebase.
"""

import os


# ─── I2C / PCA9685 ──────────────────────────────────────────────────
PCA9685_ADDRESS = 0x40
PCA9685_BUS = 1

# ─── Steering Servo  (Channel 0) ────────────────────────────────────
STEERING_CHANNEL = 0
STEERING_FREQ = 50               # Hz  (standard RC servo frequency)
STEERING_MIN_PULSE_US = 1000     # µs  – full left
STEERING_MAX_PULSE_US = 2000     # µs  – full right
STEERING_GAIN = -1.0             # đảo chiều: xoay trái UI -> servo quay trái
STEERING_OFFSET = 0.0            # mechanical calibration offset

# ─── ESC / Motor  (Channel 1) ───────────────────────────────────────
THROTTLE_CHANNEL = 1
THROTTLE_FREQ = 50               # Hz  (standard RC ESC frequency)
THROTTLE_MIN_PULSE_US = 1000     # µs  – full reverse
THROTTLE_MAX_PULSE_US = 2000     # µs  – full forward
THROTTLE_NEUTRAL_PULSE_US = 1500 # µs  – ESC neutral/stop
# Bù vùng chết của ESC: lệnh tiến nhỏ bắt đầu từ 1560 µs thay vì 1500 µs.
# Hiệu chỉnh từng bước 10 µs nếu motor thực tế cần ngưỡng khác.
THROTTLE_FORWARD_START_PULSE_US = 1560
THROTTLE_REVERSE_START_PULSE_US = 1440
THROTTLE_GAIN = 1.0
THROTTLE_OFFSET = 0.0
ESC_ARM_SECONDS = 3.0            # giữ neutral khi web server khởi động

# ─── Safety limits ──────────────────────────────────────────────────
# Every incoming value is clamped to [-1.0, 1.0] at the driver level,
# but we can further restrict the range here for safety while learning.
STEERING_LIMIT = 1.0             # max absolute steering  (0.0 – 1.0)
THROTTLE_LIMIT = 0.5             # max absolute throttle  (0.0 – 1.0)
                                 # ↑ start conservative — raise later

# ─── Flask web server ───────────────────────────────────────────────
WEB_HOST = "0.0.0.0"            # listen on all interfaces (WiFi access)
WEB_PORT = 5000
WEB_DEBUG = False                # NEVER True in production on hardware

# ─── Driving dataset collection ────────────────────────────────────
# Mỗi lần bấm REC tạo một thư mục sess_YYYYMMDD_HHMMSS riêng bên dưới.
DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datasets")
DATASET_NORMAL_HZ = 10
DATASET_CURVE_HZ = 15

# ─── USB / Bluetooth gamepad ────────────────────────────────────────
GAMEPAD_DEADZONE = 0.10          # bỏ stick drift quanh vị trí giữa
GAMEPAD_RECONNECT_SECONDS = 2.0  # chu kỳ tìm lại controller khi mất kết nối
