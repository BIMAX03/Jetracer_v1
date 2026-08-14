"""INA219 voltage/current/power monitor.

PCA9685 normally occupies 0x40 in this project.  Configure the INA219 A0/A1
address pins and use 0x41 (the default below) to avoid an address collision.
"""

import time

from drivers.i2c import I2C


class INA219:
    REG_CONFIG = 0x00
    REG_SHUNT_VOLTAGE = 0x01
    REG_BUS_VOLTAGE = 0x02
    REG_POWER = 0x03
    REG_CURRENT = 0x04
    REG_CALIBRATION = 0x05

    CONFIG_RESET = 0x8000
    CONFIG_BUS_RANGE_32V = 0x2000
    CONFIG_GAIN_320MV = 0x1800
    CONFIG_BUS_ADC_12BIT = 0x0180
    CONFIG_SHUNT_ADC_12BIT = 0x0018
    CONFIG_MODE_CONTINUOUS = 0x0007
    CONFIG_MODE_POWER_DOWN = 0x0000

    DEFAULT_CONFIG = (
        CONFIG_BUS_RANGE_32V
        | CONFIG_GAIN_320MV
        | CONFIG_BUS_ADC_12BIT
        | CONFIG_SHUNT_ADC_12BIT
        | CONFIG_MODE_CONTINUOUS
    )

    def __init__(
        self,
        address=0x41,
        bus=1,
        i2c=None,
        shunt_ohms=0.1,
        max_expected_amps=3.2,
        auto_configure=True,
    ):
        self.address = int(address)
        self.shunt_ohms = float(shunt_ohms)
        self.max_expected_amps = float(max_expected_amps)
        if not 0 <= self.address <= 0x7F:
            raise ValueError("INA219 address must be a 7-bit value")
        if self.shunt_ohms <= 0.0:
            raise ValueError("shunt_ohms must be positive")
        if self.max_expected_amps <= 0.0:
            raise ValueError("max_expected_amps must be positive")

        self._owns_i2c = i2c is None
        self.i2c = i2c if i2c is not None else I2C(bus)

        minimum_current_lsb = self.max_expected_amps / 32767.0
        calibration_limited_lsb = (
            0.04096 / (65535.0 * self.shunt_ohms)
        )
        self.current_lsb = max(
            minimum_current_lsb,
            calibration_limited_lsb,
        )
        self.power_lsb = 20.0 * self.current_lsb
        self.calibration = int(
            0.04096 / (self.current_lsb * self.shunt_ohms)
        )
        self.calibration = max(1, min(0xFFFF, self.calibration))
        self.config = self.DEFAULT_CONFIG

        if auto_configure:
            self.configure()

    def _write_register(self, register, value):
        self.i2c.write_u16_be(self.address, register, value)

    def _read_u16(self, register):
        return self.i2c.read_u16_be(self.address, register)

    def _read_s16(self, register):
        return self.i2c.read_s16_be(self.address, register)

    def configure(self, config=None):
        if config is not None:
            self.config = int(config) & 0x7FFF
        self._write_register(self.REG_CONFIG, self.config)
        self._write_register(self.REG_CALIBRATION, self.calibration)

    def reset(self):
        self._write_register(self.REG_CONFIG, self.CONFIG_RESET)
        time.sleep(0.002)
        self.configure()

    def sleep(self):
        self._write_register(
            self.REG_CONFIG,
            (self.config & ~0x0007) | self.CONFIG_MODE_POWER_DOWN,
        )

    def wake(self):
        self.configure()
        time.sleep(0.001)

    def shunt_voltage_v(self):
        """Voltage across the shunt; one raw bit is 10 microvolts."""
        return self._read_s16(self.REG_SHUNT_VOLTAGE) * 0.00001

    def bus_voltage_v(self):
        """Bus voltage; bits 15..3 have a 4 mV LSB."""
        raw = self._read_u16(self.REG_BUS_VOLTAGE)
        if raw & 0x0001:
            raise OverflowError("INA219 math overflow")
        return (raw >> 3) * 0.004

    def conversion_ready(self):
        return bool(self._read_u16(self.REG_BUS_VOLTAGE) & 0x0002)

    def current_a(self):
        # Calibration can be cleared by a brownout, so restore it before reads.
        self._write_register(self.REG_CALIBRATION, self.calibration)
        return self._read_s16(self.REG_CURRENT) * self.current_lsb

    def power_w(self):
        self._write_register(self.REG_CALIBRATION, self.calibration)
        return self._read_u16(self.REG_POWER) * self.power_lsb

    def load_voltage_v(self):
        return self.bus_voltage_v() + self.shunt_voltage_v()

    def read(self):
        """Return one human-readable measurement snapshot."""
        bus_voltage = self.bus_voltage_v()
        shunt_voltage = self.shunt_voltage_v()
        return {
            "bus_voltage_v": bus_voltage,
            "shunt_voltage_v": shunt_voltage,
            "load_voltage_v": bus_voltage + shunt_voltage,
            "current_a": self.current_a(),
            "power_w": self.power_w(),
        }

    def close(self):
        if self._owns_i2c:
            self.i2c.close()
