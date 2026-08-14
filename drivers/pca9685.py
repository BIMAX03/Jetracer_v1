import time

from drivers.i2c import I2C


class PCA9685:
    """Low-level driver cho chip PCA9685 (16-channel PWM/Servo driver).

    Chỉ chứa các thao tác thuần hardware theo datasheet.
    Không chứa logic servo/steering/duty-cycle theo góc.
    """

    MODE1 = 0x00
    MODE2 = 0x01

    PRESCALE = 0xFE

    LED0 = 0x06  # base register, mỗi channel chiếm 4 thanh ghi liên tiếp
    ALL_LED_ON_L = 0xFA
    ALL_LED_OFF_H = 0xFD

    SLEEP = 0x10
    RESTART = 0x80
    AUTO_INCREMENT = 0x20
    FULL_ON_OFF = 0x10
    OSCILLATOR_HZ = 25000000.0
    COUNTS = 4096

    def __init__(self,
                 address=0x40,
                 bus=1,
                 i2c=None):

        self.i2c = I2C(bus) if i2c is None else i2c
        self.address = int(address)
        self.frequency = None
        self.prescale = None

    def read(self, reg):
        """Đọc 1 byte từ thanh ghi reg."""
        return self.i2c.read_byte(
            self.address,
            reg
        )

    def write(self,
              reg,
              value):
        """Ghi 1 byte value vào thanh ghi reg."""
        self.i2c.write_byte(
            self.address,
            reg,
            value
        )

    def wake(self):
        """Wake up PCA9685 bằng cách clear bit SLEEP trong MODE1."""

        mode = self.read(self.MODE1)

        mode = (mode & ~self.SLEEP) | self.AUTO_INCREMENT

        self.write(
            self.MODE1,
            mode
        )

        time.sleep(0.001)

    def sleep(self):
        """Đưa PCA9685 vào chế độ sleep bằng cách set bit SLEEP trong MODE1."""

        mode = self.read(self.MODE1)

        mode |= self.SLEEP

        self.write(
            self.MODE1,
            mode
        )

    def reset(self):
        """Reset MODE1 về giá trị mặc định (0x00). Hữu ích khi debug."""

        self.write(self.MODE1, 0x00)

        time.sleep(0.005)

    def set_pwm_freq(self, frequency):
        """Thiết lập tần số PWM (Hz) bằng cách ghi thanh ghi PRESCALE.

        Theo datasheet:
            Read MODE1 -> Sleep -> Write PRESCALE ->
            Restore MODE1 -> delay 5ms -> MODE1 | RESTART
        """

        frequency = float(frequency)
        if frequency <= 0.0:
            raise ValueError("frequency must be positive")

        prescale_val = self.OSCILLATOR_HZ
        prescale_val /= self.COUNTS
        prescale_val /= frequency
        prescale_val -= 1.0

        prescale = int(prescale_val + 0.5)  # làm tròn
        if not 3 <= prescale <= 255:
            raise ValueError("frequency is outside the PCA9685 range")

        # Servo and ESC share the chip frequency. Avoid restarting the PWM
        # generator when both request the same setting.
        if self.prescale == prescale:
            return self.frequency

        old_mode = self.read(self.MODE1)

        sleep_mode = (old_mode & ~self.RESTART) | self.SLEEP

        self.write(self.MODE1, sleep_mode)

        self.write(self.PRESCALE, prescale)

        run_mode = (old_mode | self.AUTO_INCREMENT) & ~self.SLEEP
        self.write(self.MODE1, run_mode)

        time.sleep(0.005)

        self.write(self.MODE1, run_mode | self.RESTART)

        self.prescale = prescale
        self.frequency = (
            self.OSCILLATOR_HZ / (self.COUNTS * (prescale + 1))
        )
        return self.frequency

    def set_pwm(self,
                channel,
                on,
                off):
        """Ghi giá trị on/off (0-4095) cho 1 channel (0-15)."""

        if not 0 <= channel <= 15:
            raise ValueError("Channel must be between 0 and 15")

        if not 0 <= on <= 4095:
            raise ValueError("on must be between 0 and 4095")

        if not 0 <= off <= 4095:
            raise ValueError("off must be between 0 and 4095")

        base = self.LED0 + 4 * channel
        self.i2c.write_block(
            self.address,
            base,
            [
                on & 0xFF,
                (on >> 8) & 0x0F,
                off & 0xFF,
                (off >> 8) & 0x0F,
            ],
        )

    def pulse_us_to_counts(self, pulse_us):
        """Convert a pulse width to the nearest 12-bit PWM count."""
        if self.frequency is None:
            raise RuntimeError("PWM frequency has not been configured")
        pulse_us = float(pulse_us)
        if pulse_us < 0.0:
            raise ValueError("pulse_us must not be negative")
        counts = int(
            pulse_us * self.frequency * self.COUNTS / 1000000.0 + 0.5
        )
        if counts > 4095:
            raise ValueError("pulse_us exceeds one PWM period")
        return counts

    def set_pulse_us(self, channel, pulse_us):
        """Output a high pulse of ``pulse_us`` microseconds on a channel."""
        self.set_pwm(channel, 0, self.pulse_us_to_counts(pulse_us))

    def channel_off(self, channel):
        """Disable one output using the PCA9685 full-off bit."""
        channel = int(channel)
        if not 0 <= channel <= 15:
            raise ValueError("Channel must be between 0 and 15")
        base = self.LED0 + 4 * channel
        self.i2c.write_block(
            self.address,
            base,
            [0, 0, 0, self.FULL_ON_OFF],
        )

    def all_off(self):
        """Disable all 16 outputs immediately."""
        self.write(self.ALL_LED_OFF_H, self.FULL_ON_OFF)

    def all_on(self):
        """Enable the PCA9685 full-on override for all channels."""
        self.i2c.write_block(
            self.address,
            self.ALL_LED_ON_L,
            [0, self.FULL_ON_OFF, 0, 0],
        )
