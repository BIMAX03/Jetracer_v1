"""Unit tests cho web controller; không truy cập I2C thật."""

import unittest

import config
from web_control.controller import CarController


class FakeCar:
    def __init__(self):
        self.calls = []

    def steering(self, value):
        self.calls.append(("steering", value))

    def throttle(self, value):
        self.calls.append(("throttle", value))

    def stop(self):
        self.calls.append(("stop",))

    def arm(self, duration=3.0):
        self.calls.append(("arm", duration))


class CarControllerTest(unittest.TestCase):
    def test_combined_control_updates_both_values(self):
        car = FakeCar()
        controller = CarController(car=car)

        status = controller.set_control(0.4, 0.3)

        self.assertEqual(status, {"steering": 0.4, "throttle": 0.3})
        self.assertEqual(car.calls, [("steering", 0.4), ("throttle", 0.3)])

    def test_combined_control_clamps_values(self):
        car = FakeCar()
        controller = CarController(car=car)

        status = controller.set_control(5, -4)

        self.assertEqual(
            status,
            {"steering": 1.0, "throttle": -config.THROTTLE_LIMIT},
        )

    def test_arm_initializes_neutral_state(self):
        car = FakeCar()
        controller = CarController(car=car)

        status = controller.arm(duration=0)

        self.assertEqual(status, {"steering": 0.0, "throttle": 0.0})
        self.assertEqual(car.calls, [("arm", 0)])


if __name__ == "__main__":
    unittest.main()
