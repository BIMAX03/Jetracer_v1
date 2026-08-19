"""Unit tests cho nhận diện hướng cua; không truy cập camera/phần cứng."""

import unittest

try:
    import cv2  # noqa: F401
    import numpy as np
    from line_following.detector import LineDetector as YellowLineDetector
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False


@unittest.skipUnless(VISION_AVAILABLE, "OpenCV/NumPy chưa được cài")
class RightAngleHintTest(unittest.TestCase):
    def setUp(self):
        self.mask = np.zeros((200, 400), dtype=np.uint8)

    def test_left_and_right_branches(self):
        self.mask[78:84, 40:206] = 255
        direction, confidence = YellowLineDetector._right_angle_hint(
            self.mask, 200
        )
        self.assertEqual(direction, -1)
        self.assertGreater(confidence, 0.25)

        self.mask[:] = 0
        self.mask[78:84, 194:361] = 255
        direction, confidence = YellowLineDetector._right_angle_hint(
            self.mask, 200
        )
        self.assertEqual(direction, 1)
        self.assertGreater(confidence, 0.25)

    def test_rejects_straight_and_disconnected_yellow_line(self):
        self.mask[:, 190:211] = 255
        self.assertEqual(
            YellowLineDetector._right_angle_hint(self.mask, 200)[0], 0
        )

        self.mask[:] = 0
        self.mask[78:84, 0:101] = 255
        self.assertEqual(
            YellowLineDetector._right_angle_hint(self.mask, 200)[0], 0
        )


if __name__ == "__main__":
    unittest.main()
