"""Centralized configuration for the JetRacer project.

Every tunable parameter lives here — hardware channels, PWM calibration,
safety limits, and web server settings.  Other modules import from this
file so there are zero magic numbers scattered around the codebase.
"""


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
THROTTLE_GAIN = 1.0
THROTTLE_OFFSET = 0.0

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
