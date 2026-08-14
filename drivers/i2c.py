"""Thread-safe I2C/SMBus transport used by every hardware driver."""

import threading
import time

try:
    import smbus
except ImportError:
    smbus = None


class I2C:
    """Small, device-agnostic wrapper around Linux SMBus.

    ``retries`` is the number of retries after the first attempt.  A backend
    can be injected for unit tests; normal code opens ``/dev/i2c-<bus>``.
    """

    def __init__(
        self,
        bus=1,
        retries=2,
        retry_delay=0.002,
        backend=None,
    ):
        if backend is None:
            if smbus is None:
                raise ImportError(
                    "Missing smbus. Install python3-smbus on the Jetson."
                )
            backend = smbus.SMBus(bus)

        self.bus_number = int(bus)
        self.bus = backend
        self.retries = max(0, int(retries))
        self.retry_delay = max(0.0, float(retry_delay))
        self._lock = threading.RLock()
        self._closed = False

    @staticmethod
    def _byte(value, name):
        value = int(value)
        if not 0 <= value <= 0xFF:
            raise ValueError("{} must be between 0 and 255".format(name))
        return value

    @staticmethod
    def _address(address):
        address = int(address)
        if not 0 <= address <= 0x7F:
            raise ValueError("I2C address must be a 7-bit value")
        return address

    def _call(self, operation, *args):
        with self._lock:
            if self._closed:
                raise RuntimeError("I2C bus is closed")

            last_error = None
            for attempt in range(self.retries + 1):
                try:
                    return operation(*args)
                except OSError as error:
                    last_error = error
                    if attempt >= self.retries:
                        raise
                    time.sleep(self.retry_delay)
            raise last_error

    def write_byte(self, address, register, value):
        """Write one byte to an 8-bit register."""
        address = self._address(address)
        register = self._byte(register, "register")
        value = self._byte(value, "value")
        return self._call(
            self.bus.write_byte_data,
            address,
            register,
            value,
        )

    def read_byte(self, address, register):
        """Read one unsigned byte from an 8-bit register."""
        address = self._address(address)
        register = self._byte(register, "register")
        return self._call(
            self.bus.read_byte_data,
            address,
            register,
        )

    def write_block(self, address, register, values):
        """Write up to 32 sequential bytes in one SMBus transaction."""
        address = self._address(address)
        register = self._byte(register, "register")
        values = [self._byte(value, "block value") for value in values]
        if not 1 <= len(values) <= 32:
            raise ValueError("I2C block length must be between 1 and 32")
        return self._call(
            self.bus.write_i2c_block_data,
            address,
            register,
            values,
        )

    def read_block(self, address, register, length):
        """Read 1..32 sequential bytes."""
        address = self._address(address)
        register = self._byte(register, "register")
        length = int(length)
        if not 1 <= length <= 32:
            raise ValueError("I2C block length must be between 1 and 32")
        return self._call(
            self.bus.read_i2c_block_data,
            address,
            register,
            length,
        )

    def write_u16_be(self, address, register, value):
        """Write an unsigned 16-bit value, most-significant byte first."""
        value = int(value)
        if not 0 <= value <= 0xFFFF:
            raise ValueError("16-bit value must be between 0 and 65535")
        return self.write_block(
            address,
            register,
            [(value >> 8) & 0xFF, value & 0xFF],
        )

    def read_u16_be(self, address, register):
        """Read an unsigned big-endian 16-bit register."""
        high, low = self.read_block(address, register, 2)
        return (high << 8) | low

    def read_s16_be(self, address, register):
        """Read a signed big-endian 16-bit register."""
        value = self.read_u16_be(address, register)
        return value - 0x10000 if value & 0x8000 else value

    def close(self):
        with self._lock:
            if self._closed:
                return
            close = getattr(self.bus, "close", None)
            if close is not None:
                close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.close()
