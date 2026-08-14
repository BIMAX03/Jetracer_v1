"""Calibrated positional servo driven by a PCA9685 channel."""

import time


class Servo:
    """Map a normalized steering command to an asymmetric pulse range.

    Public input remains compatible with the old driver:
    ``-1.0`` = logical left, ``0.0`` = center, ``1.0`` = logical right.
    ``gain=-1`` reverses physical direction and ``offset`` is normalized.
    """

    def __init__(
        self,
        pca,
        channel,
        freq=50,
        min_pulse_us=1000,
        max_pulse_us=2000,
        gain=1.0,
        offset=0.0,
        center_pulse_us=None,
        max_rate_per_second=None,
    ):
        self.pca = pca
        self.channel = int(channel)
        self.freq = float(freq)
        self.min_pulse_us = float(min_pulse_us)
        self.max_pulse_us = float(max_pulse_us)
        self.center_pulse_us = (
            (self.min_pulse_us + self.max_pulse_us) / 2.0
            if center_pulse_us is None
            else float(center_pulse_us)
        )
        self.gain = float(gain)
        self.offset = float(offset)
        self.max_rate_per_second = (
            None
            if max_rate_per_second is None
            else abs(float(max_rate_per_second))
        )

        if self.freq <= 0.0:
            raise ValueError("servo frequency must be positive")
        if not (
            self.min_pulse_us
            < self.center_pulse_us
            < self.max_pulse_us
        ):
            raise ValueError(
                "servo pulse calibration must satisfy min < center < max"
            )
        if (
            self.max_rate_per_second is not None
            and self.max_rate_per_second == 0.0
        ):
            raise ValueError("max_rate_per_second must be positive")

        self._command = None
        self._calibrated = None
        self._pulse_us = None
        self._last_update = None
        self.pca.set_pwm_freq(self.freq)

    @staticmethod
    def _clamp(value):
        return max(-1.0, min(1.0, float(value)))

    def _rate_limit(self, command, now, immediate):
        if (
            immediate
            or self.max_rate_per_second is None
            or self._command is None
            or self._last_update is None
        ):
            return command

        elapsed = max(0.0, now - self._last_update)
        maximum_change = self.max_rate_per_second * elapsed
        return max(
            self._command - maximum_change,
            min(self._command + maximum_change, command),
        )

    def value_to_pulse_us(self, value):
        """Pure conversion useful for calibration and unit tests."""
        calibrated = self._clamp(value * self.gain + self.offset)
        if calibrated < 0.0:
            pulse_us = self.center_pulse_us + calibrated * (
                self.center_pulse_us - self.min_pulse_us
            )
        else:
            pulse_us = self.center_pulse_us + calibrated * (
                self.max_pulse_us - self.center_pulse_us
            )
        return calibrated, pulse_us

    def _us_to_counts(self, pulse_us):
        """Backward-compatible helper using PCA9685's calibrated frequency."""
        return self.pca.pulse_us_to_counts(pulse_us)

    def write(self, value, immediate=False):
        now = time.monotonic()
        command = self._rate_limit(self._clamp(value), now, immediate)
        calibrated, pulse_us = self.value_to_pulse_us(command)
        self.pca.set_pulse_us(self.channel, pulse_us)

        self._command = command
        self._calibrated = calibrated
        self._pulse_us = pulse_us
        self._last_update = now
        return pulse_us

    def center(self, immediate=True):
        """Center immediately; emergency stops must not wait for slew limiting."""
        return self.write(0.0, immediate=immediate)

    def detach(self):
        self.pca.channel_off(self.channel)

    @property
    def command(self):
        return self._command

    @property
    def pulse_us(self):
        return self._pulse_us
