import smbus


class I2C:
    """Driver giao tiếp I2C sử dụng Linux SMBus.

    Đây là tầng thấp nhất, chỉ biết đọc/ghi thanh ghi (register).
    Không biết gì về ý nghĩa của thanh ghi hay thiết bị đang giao tiếp
    (PCA9685, sensor, v.v). Các driver cấp cao hơn (PCA9685, Servo...)
    sẽ dùng lớp này để thao tác với phần cứng.
    """

    def __init__(self, bus=1):
        self.bus = smbus.SMBus(bus)

    def write_byte(self, address, register, value):
        """Ghi 1 byte value vào thanh ghi register của thiết bị address."""

        self.bus.write_byte_data(
            address,
            register,
            value
        )

    def read_byte(self, address, register):
        """Đọc 1 byte từ thanh ghi register của thiết bị address."""

        return self.bus.read_byte_data(
            address,
            register
        )