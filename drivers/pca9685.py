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

    SLEEP = 0x10
    RESTART = 0x80

    def __init__(self,
                 address=0x40,
                 bus=1):

        self.i2c = I2C(bus)

        self.address = address

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

        mode &= ~self.SLEEP

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

        prescale_val = 25000000.0          # oscillator nội bộ 25MHz
        prescale_val /= 4096.0             # 12-bit resolution
        prescale_val /= float(frequency)
        prescale_val -= 1.0

        prescale = int(prescale_val + 0.5)  # làm tròn

        old_mode = self.read(self.MODE1)

        sleep_mode = (old_mode & 0x7F) | self.SLEEP

        self.write(self.MODE1, sleep_mode)

        self.write(self.PRESCALE, prescale)

        self.write(self.MODE1, old_mode)

        time.sleep(0.005)

        self.write(self.MODE1, old_mode | self.RESTART)

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

        self.write(base, on & 0xFF)
        self.write(base + 1, (on >> 8) & 0xFF)
        self.write(base + 2, off & 0xFF)
        self.write(base + 3, (off >> 8) & 0xFF)

    # get_pwm(), all_off(), all_on() sẽ được thêm ở bước sau