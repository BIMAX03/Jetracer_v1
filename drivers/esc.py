import time

from drivers.pca9685 import PCA9685


class ESC:
    """ Điều khiển ESC (Electronic Speed Controller) qua PCA9685

    ESC nhận tín hiệu PWM kiểu RC giống servo, nhưn!g ý nghĩa khác:
        min_pulse_us     -> lùi hết
        neutral          -> dừng (1500 us)
        max_pulse_us     -> tiến hết
    """

    def __init__(self,
                 pca,
                 channel,
                 freq=50,
                 min_pulse_us=1000,
                 max_pulse_us=2000,
                 gain=1.0,
                 offset=0.0):

        self.pca = pca
        self.channel = channel

        self.freq = freq
        self.min_pulse_us = min_pulse_us
        self.max_pulse_us = max_pulse_us

        # Hiệu chỉnh (gain/offset) nếu cần
        self.gain = gain
        self.offset = offset

        self.pca.set_pwm_freq(freq)

    def _us_to_counts(self, pulse_us):
        """Đổi độ rộng xung (us) sang giá trị 12-bit (0-4095) của PCA9685."""

        period_us = 1_000_000.0 / self.freq   # 50Hz -> 20000us
        counts = int(pulse_us / period_us * 4096.0 + 0.5)

        return max(0, min(4095, counts))

    def write(self, value):
        """value: -1.0 .. 1.0 (lùi hết .. tiến hết)"""

        value = max(-1.0, min(1.0, value))

        # Áp gain/offset rồi clamp lại lần nữa
        calibrated = value * self.gain + self.offset
        calibrated = max(-1.0, min(1.0, calibrated))

        # Map -1..1 -> min_pulse_us..max_pulse_us
        pulse_us = self.min_pulse_us + (calibrated + 1.0) / 2.0 * (
            self.max_pulse_us - self.min_pulse_us
        )

        counts = self._us_to_counts(pulse_us)

        self.pca.set_pwm(self.channel, 0, counts)

    def neutral(self):
        """Đưa ESC về mức trung tính (dừng)."""
        self.write(0.0)