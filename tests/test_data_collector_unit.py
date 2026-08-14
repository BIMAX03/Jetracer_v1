"""Unit tests cho dataset recorder; không truy cập camera hay phần cứng."""

import csv
import tempfile
import time
import unittest
from pathlib import Path

from web_control.data_collector import DataCollector


class FakeController:
    def __init__(self):
        self.steering = 0.25
        self.throttle = 0.30

    def get_status(self):
        return {"steering": self.steering, "throttle": self.throttle}


class FakeFrames:
    def __init__(self):
        self.number = 0

    def __call__(self, after_frame_number, timeout=2.0):
        self.number += 1
        jpeg = "fake-jpeg-{}".format(self.number).encode()
        return self.number, jpeg, 1723276800.0 + self.number / 10.0


def wait_for_samples(collector, count, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if collector.status()["sample_count"] >= count:
            return
        time.sleep(0.005)
    raise AssertionError("recorder did not produce {} samples".format(count))


class DataCollectorTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dataset_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_writes_one_image_and_one_csv_row_per_sample(self):
        collector = DataCollector(
            controller=FakeController(),
            frame_provider=FakeFrames(),
            camera_starter=lambda: True,
            dataset_dir=str(self.dataset_dir),
            normal_hz=50,
            curve_hz=100,
        )

        started = collector.start()
        wait_for_samples(collector, 3)
        stopped = collector.stop()

        session_dir = self.dataset_dir / started["session_id"]
        images = sorted(session_dir.glob("*.jpg"))
        with (session_dir / "labels.csv").open(newline="") as labels_file:
            rows = list(csv.DictReader(labels_file))

        self.assertEqual(len(images), stopped["sample_count"])
        self.assertEqual(len(images), len(rows))
        self.assertEqual(images[0].name, "frame_000001.jpg")
        self.assertEqual(rows[0]["filename"], "frame_000001.jpg")
        self.assertEqual(rows[0]["steering_prev"], "0.000000")
        self.assertEqual(rows[1]["steering_prev"], rows[0]["steering"])
        self.assertEqual(rows[0]["steering"], "0.250000")
        self.assertTrue(all(
            row["session_id"] == started["session_id"] for row in rows
        ))

    def test_new_session_resets_previous_steering_and_curve_rate(self):
        controller = FakeController()
        collector = DataCollector(
            controller=controller,
            frame_provider=FakeFrames(),
            camera_starter=lambda: True,
            dataset_dir=str(self.dataset_dir),
            normal_hz=30,
            curve_hz=60,
        )

        first = collector.start()
        wait_for_samples(collector, 1)
        self.assertEqual(collector.set_curve_mode(True)["rate_hz"], 60)
        collector.stop()

        controller.steering = -0.5
        second = collector.start()
        wait_for_samples(collector, 1)
        collector.stop()

        self.assertNotEqual(first["session_id"], second["session_id"])
        labels_path = self.dataset_dir / second["session_id"] / "labels.csv"
        with labels_path.open(newline="") as labels_file:
            first_row = next(csv.DictReader(labels_file))
        self.assertEqual(first_row["steering"], "-0.500000")
        self.assertEqual(first_row["steering_prev"], "0.000000")


if __name__ == "__main__":
    unittest.main()
