"""Calibrated bidirectional RC ESC driven by PCA9685."""

import time


class ESC:
    """Map normalized throttle to reverse/neutral/forward pulse widths.

    The legacy constructor remains valid.  New optional start pulses compensate
    for a measured ESC deadband without changing commands used by upper layers.
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
        neutral_pulse_us=None,
        forward_start_pulse_us=None,
        reverse_start_pulse_us=None,
        max_rate_per_second=None,
    ):
        self.pca = pca
        self.channel = int(channel)
        self.freq = float(freq)
        self.min_pulse_us = float(min_pulse_us)
        self.max_pulse_us = float(max_pulse_us)
        self.neutral_pulse_us = (
            (self.min_pulse_us + self.max_pulse_us) / 2.0
            if neutral_pulse_us is None
            else float(neutral_pulse_us)
        )
        self.forward_start_pulse_us = (
            self.neutral_pulse_us
            if forward_start_pulse_us is None
            else float(forward_start_pulse_us)
        )
        self.reverse_start_pulse_us = (
            self.neutral_pulse_us
            if reverse_start_pulse_us is None
            else float(reverse_start_pulse_us)
        )
        self.gain = float(gain)
        self.offset = float(offset)
        self.max_rate_per_second = (
            None
            if max_rate_per_second is None
            else abs(float(max_rate_per_second))
        )

        if self.freq <= 0.0:
            raise ValueError("ESC frequency must be positive")
        if not (
            self.min_pulse_us
            < self.neutral_pulse_us
            < self.max_pulse_us
        ):
            raise ValueError(
                "ESC calibration must satisfy min < neutral < max"
            )
        if not (
            self.neutral_pulse_us
            <= self.forward_start_pulse_us
            <= self.max_pulse_us
        ):
            raise ValueError(
                "forward_start_pulse_us must be between neutral and max"
            )
        if not (
            self.min_pulse_us
            <= self.reverse_start_pulse_us
            <= self.neutral_pulse_us
        ):
            raise ValueError(
                "reverse_start_pulse_us must be between min and neutral"
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
        self._armed = False
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
        value = self._clamp(value)
        # Zero throttle is a safety invariant: offset must never move neutral.
        calibrated = (
            0.0
            if value == 0.0
            else self._clamp(value * self.gain + self.offset)
        )
        if calibrated == 0.0:
            pulse_us = self.neutral_pulse_us
        elif calibrated > 0.0:
            pulse_us = self.forward_start_pulse_us + calibrated * (
                self.max_pulse_us - self.forward_start_pulse_us
            )
        else:
            magnitude = -calibrated
            pulse_us = self.reverse_start_pulse_us - magnitude * (
                self.reverse_start_pulse_us - self.min_pulse_us
            )
        return calibrated, pulse_us

    def _us_to_counts(self, pulse_us):
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

    def neutral(self, immediate=True):
        return self.write(0.0, immediate=immediate)

    def arm(self, duration=1.0):
        """Hold neutral so an RC ESC can complete its startup arming sequence."""
        duration = max(0.0, float(duration))
        self.neutral(immediate=True)
        if duration:
            time.sleep(duration)
        self._armed = True

    def detach(self):
        self.pca.channel_off(self.channel)
        self._armed = False

    @property
    def command(self):
        return self._command

    @property
    def pulse_us(self):
        return self._pulse_us

    @property
    def armed(self):
        return self._armed
