"""Kiểm tra motor.py độc lập mà không truy cập I2C thật."""

import unittest

from code_dum_ros2.motor import JetRacerMotor


class FakeSMBus:
    def __init__(self):
        self.registers = {JetRacerMotor.MODE1: 0x01}
        self.byte_writes = []
        self.block_writes = []
        self.closed = False

    def read_byte_data(self, _address, register):
        return self.registers.get(register, 0)

    def write_byte_data(self, address, register, value):
        self.registers[register] = value
        self.byte_writes.append((address, register, value))

    def write_i2c_block_data(self, address, register, values):
        self.block_writes.append((address, register, list(values)))

    def close(self):
        self.closed = True


class StandaloneMotorTest(unittest.TestCase):
    def setUp(self):
        self.bus = FakeSMBus()
        self.motor = JetRacerMotor(bus_backend=self.bus)

    def tearDown(self):
        self.motor.close()

    def test_neutral_is_the_first_motor_command(self):
        self.assertEqual(self.motor.last_throttle, 0.0)
        self.assertEqual(self.motor.last_pulse_us, 1500.0)
        self.assertTrue(self.bus.block_writes)

    def test_arm_and_forward_deadband_compensation(self):
        self.motor.arm(duration=0)
        self.assertTrue(self.motor.armed)
        pulse_us = self.motor.set_throttle(0.15)
        self.assertEqual(pulse_us, 1626.0)
        self.assertEqual(self.motor.last_throttle, 0.15)
        self.motor.stop()
        self.assertEqual(self.motor.last_pulse_us, 1500.0)

    def test_throttle_is_clamped_to_safe_limit(self):
        self.motor.arm(duration=0)
        pulse_us = self.motor.set_throttle(1.0)
        self.assertEqual(self.motor.last_throttle, 0.5)
        self.assertEqual(pulse_us, 1780.0)

    def test_close_stops_motor_and_closes_bus(self):
        self.motor.arm(duration=0)
        self.motor.set_throttle(0.2)
        self.motor.close()
        self.assertEqual(self.motor.last_pulse_us, 1500.0)
        self.assertTrue(self.bus.closed)

    def test_nonzero_throttle_requires_arm(self):
        with self.assertRaises(RuntimeError):
            self.motor.set_throttle(0.15)


if __name__ == "__main__":
    unittest.main()
