"""Unit tests for drivers; no physical I2C/PWM hardware is touched."""

import unittest

import config
from drivers.esc import ESC
from drivers.i2c import I2C
from drivers.ina219 import INA219
from drivers.pca9685 import PCA9685
from drivers.servo import Servo


class FakeSMBus:
    def __init__(self):
        self.registers = {}
        self.word_registers = {}
        self.writes = []
        self.read_failures = 0
        self.closed = False

    def write_byte_data(self, address, register, value):
        self.registers[(address, register)] = value
        self.writes.append(("byte", address, register, value))

    def read_byte_data(self, address, register):
        if self.read_failures:
            self.read_failures -= 1
            raise OSError("temporary I2C error")
        return self.registers.get((address, register), 0)

    def write_i2c_block_data(self, address, register, values):
        if len(values) == 2:
            self.word_registers[(address, register)] = (
                (values[0] << 8) | values[1]
            )
        for offset, value in enumerate(values):
            self.registers[(address, register + offset)] = value
        self.writes.append(("block", address, register, list(values)))

    def read_i2c_block_data(self, address, register, length):
        if length == 2 and (address, register) in self.word_registers:
            value = self.word_registers[(address, register)]
            return [(value >> 8) & 0xFF, value & 0xFF]
        return [
            self.registers.get((address, register + offset), 0)
            for offset in range(length)
        ]

    def close(self):
        self.closed = True


class FakePCA:
    def __init__(self):
        self.frequency = None
        self.frequency_calls = 0
        self.pulses = []
        self.off_channels = []

    def set_pwm_freq(self, frequency):
        self.frequency = float(frequency)
        self.frequency_calls += 1
        return self.frequency

    def pulse_us_to_counts(self, pulse_us):
        return int(float(pulse_us) / 20000.0 * 4096.0 + 0.5)

    def set_pulse_us(self, channel, pulse_us):
        self.pulses.append((channel, float(pulse_us)))

    def channel_off(self, channel):
        self.off_channels.append(channel)


class I2CTest(unittest.TestCase):
    def test_retry_and_big_endian_helpers(self):
        backend = FakeSMBus()
        bus = I2C(backend=backend, retries=1, retry_delay=0)
        backend.read_failures = 1
        backend.registers[(0x41, 0x01)] = 0xAB
        self.assertEqual(bus.read_byte(0x41, 0x01), 0xAB)

        bus.write_u16_be(0x41, 0x02, 0x1234)
        self.assertEqual(bus.read_u16_be(0x41, 0x02), 0x1234)

    def test_close_is_idempotent(self):
        backend = FakeSMBus()
        bus = I2C(backend=backend)
        bus.close()
        bus.close()
        self.assertTrue(backend.closed)


class PCA9685Test(unittest.TestCase):
    def setUp(self):
        self.backend = FakeSMBus()
        self.i2c = I2C(backend=self.backend)
        self.pca = PCA9685(i2c=self.i2c)
        self.backend.registers[(0x40, PCA9685.MODE1)] = 0x01
        self.backend.registers[(0x40, PCA9685.MODE2)] = 0x04

    def test_frequency_is_calculated_once(self):
        self.pca.wake()
        actual = self.pca.set_pwm_freq(50)
        self.assertEqual(self.pca.prescale, 121)
        self.assertAlmostEqual(actual, 50.0288, places=3)
        writes_before = len(self.backend.writes)
        self.pca.set_pwm_freq(50)
        self.assertEqual(len(self.backend.writes), writes_before)

    def test_channel_block_write_and_all_off(self):
        self.pca.wake()
        self.pca.set_pwm_freq(50)
        self.pca.set_pwm(0, 0, 307)
        self.assertEqual(
            [
                self.backend.registers[(0x40, 0x06 + offset)]
                for offset in range(4)
            ],
            [0x00, 0x00, 0x33, 0x01],
        )
        self.pca.all_off()
        self.assertEqual(self.backend.registers[(0x40, 0xFD)], 0x10)


class ServoTest(unittest.TestCase):
    def test_asymmetric_mapping_and_reverse_gain(self):
        pca = FakePCA()
        servo = Servo(
            pca,
            channel=0,
            min_pulse_us=1100,
            center_pulse_us=1500,
            max_pulse_us=1900,
            gain=-1,
        )
        self.assertEqual(servo.write(-1), 1900)
        self.assertEqual(servo.center(), 1500)
        self.assertEqual(servo.write(1), 1100)


class ESCTest(unittest.TestCase):
    def test_default_mapping_matches_legacy_driver(self):
        esc = ESC(FakePCA(), channel=1)
        self.assertEqual(esc.neutral(), 1500)
        self.assertEqual(esc.write(0.2), 1600)
        self.assertEqual(esc.write(-0.2), 1400)

    def test_forward_deadband_compensation(self):
        esc = ESC(
            FakePCA(),
            channel=1,
            forward_start_pulse_us=1560,
        )
        self.assertEqual(esc.write(0.2), 1648)

    def test_project_calibration_arms_and_clears_forward_deadband(self):
        esc = ESC(
            FakePCA(),
            channel=config.THROTTLE_CHANNEL,
            min_pulse_us=config.THROTTLE_MIN_PULSE_US,
            max_pulse_us=config.THROTTLE_MAX_PULSE_US,
            neutral_pulse_us=config.THROTTLE_NEUTRAL_PULSE_US,
            forward_start_pulse_us=config.THROTTLE_FORWARD_START_PULSE_US,
            reverse_start_pulse_us=config.THROTTLE_REVERSE_START_PULSE_US,
        )
        esc.arm(duration=0)
        self.assertTrue(esc.armed)
        self.assertEqual(esc.pulse_us, 1500)
        self.assertEqual(esc.write(0.15), 1626)

    def test_neutral_ignores_calibration_offset(self):
        esc = ESC(FakePCA(), channel=1, offset=0.1)
        self.assertEqual(esc.neutral(), 1500)
        self.assertEqual(esc.write(0.0), 1500)


class INA219Test(unittest.TestCase):
    def setUp(self):
        self.backend = FakeSMBus()
        self.i2c = I2C(backend=self.backend)
        self.sensor = INA219(i2c=self.i2c, auto_configure=False)

    def set_u16(self, register, value):
        self.backend.word_registers[(0x41, register)] = value

    def test_voltage_conversion(self):
        self.set_u16(INA219.REG_BUS_VOLTAGE, (3000 << 3) | 0x02)
        self.set_u16(INA219.REG_SHUNT_VOLTAGE, 1000)
        self.assertAlmostEqual(self.sensor.bus_voltage_v(), 12.0)
        self.assertAlmostEqual(self.sensor.shunt_voltage_v(), 0.01)
        self.assertAlmostEqual(self.sensor.load_voltage_v(), 12.01)

    def test_default_address_avoids_pca9685(self):
        self.assertEqual(self.sensor.address, 0x41)


if __name__ == "__main__":
    unittest.main()
