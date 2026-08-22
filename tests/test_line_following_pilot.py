"""Regression tests: pilot phải luôn dừng động cơ khi thoát.

Không truy cập phần cứng — dùng FakeCar/FakeCam ghi lại các lệnh.
"""
import os
import sys
import time
import types
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

def _fake_logger():
    return types.SimpleNamespace(
        info=lambda *a, **k: None,
        warning=lambda *a, **k: None,
    )

structlog = types.SimpleNamespace(get_logger=_fake_logger)
sys.modules.setdefault("structlog", structlog)

pca9685 = types.ModuleType("drivers.pca9685")
pca9685.PCA9685 = lambda *a, **k: None
sys.modules.setdefault("drivers.pca9685", pca9685)

from line_following.pilot import LineFollowingPilot  # noqa: E402


class _InterruptSentinel:
    pass


class FakeCar:
    def __init__(self):
        self.calls = []

    def arm(self, duration=2.0):
        self.calls.append(("arm", duration))
        time.sleep(min(duration, 0.05))

    def stop(self):
        self.calls.append(("stop",))

    def steering(self, value):
        self.calls.append(("steering", value))

    def throttle(self, value):
        self.calls.append(("throttle", value))


class FakeDetector:
    def get_line_error(self, frame):
        return None, None, None

    def check_sharp_turn(self, mask):
        return 0, 0.0


class FakePid:
    def reset(self):
        pass

    def compute(self, error, dt):
        return 0.0

    @property
    def last_terms(self):
        return {}


class FakeCam:
    def __init__(self, frames, on_abort=None):
        self.frames = list(frames)
        self.on_abort = on_abort

    def read(self):
        if not self.frames:
            self._abort()
        item = self.frames.pop(0)
        if isinstance(item, _InterruptSentinel):
            self._abort()
        return item

    def _abort(self):
        if self.on_abort is not None:
            self.on_abort()
        raise KeyboardInterrupt

    def release(self):
        pass


class PilotSafetyTest(unittest.TestCase):
    def setUp(self):
        self.car = FakeCar()

    def make_pilot(self):
        return LineFollowingPilot(self.car, FakeDetector(), FakePid(), 0.22)

    def test_interrupt_during_arm_stops_car(self):
        interrupted = FakeCar()
        interrupted.arm = types.MethodType(_arm_then_raise_keyboard_interrupt, interrupted)
        pilot = LineFollowingPilot(interrupted, FakeDetector(), FakePid(), 0.22)
        with self.assertRaises(KeyboardInterrupt):
            pilot.run(FakeCam(frames=[]))
        self.assertIn(("stop",), interrupted.calls)

    def test_interrupt_in_loop_stops_car(self):
        pilot = self.make_pilot()
        pilot.run(FakeCam(frames=[object(), object()]))
        self.assertIn(("stop",), self.car.calls)

    def test_empty_frames_command_stop_before_abort(self):
        cam = FakeCam(
            frames=[None, None, None, None, _InterruptSentinel()],
            on_abort=lambda: self.car.calls.append(("interrupt",)),
        )
        self.make_pilot().run(cam)
        self.assertLess(
            self.car.calls.index(("stop",)),
            self.car.calls.index(("interrupt",)),
        )

    def test_missing_structlog_still_stops_car(self):
        saved = sys.modules.pop("structlog")
        try:
            self.make_pilot().run(FakeCam(frames=[]))
        finally:
            sys.modules["structlog"] = saved
        self.assertIn(("stop",), self.car.calls)

    def test_line_lost_sets_throttle_to_zero(self):
        """Khi detector trả error=None và check_sharp_turn trả confidence=0,
        pilot phải set throttle=0 (không 'chạy chậm tìm line' nữa).
        Đây là regression test cho bug 'xe vẫn chạy khi không bắt line'.
        """
        cam = FakeCam(frames=[object(), _InterruptSentinel()])
        self.make_pilot().run(cam)
        throttle_calls = [c for c in self.car.calls if c[0] == "throttle"]
        self.assertTrue(len(throttle_calls) >= 1, "pilot phải gọi throttle ít nhất 1 lần")
        for call in throttle_calls:
            self.assertEqual(
                call[1], 0.0,
                f"Mất line hoàn toàn phải throttle=0, nhưng nhận {call[1]!r}",
            )

    def test_sharp_turn_still_keeps_some_throttle(self):
        """Khi phát hiện cua gấp (confidence > 0.25), pilot vẫn được phép
        giữ throttle > 0 để rẽ — đây không phải 'mất line hoàn toàn'.
        """
        class SharpTurnDetector(FakeDetector):
            def check_sharp_turn(self, mask):
                return 1, 0.9

        cam = FakeCam(frames=[object(), _InterruptSentinel()])
        pilot = LineFollowingPilot(self.car, SharpTurnDetector(), FakePid(), 0.22)
        pilot.run(cam)
        throttle_calls = [c for c in self.car.calls if c[0] == "throttle"]
        self.assertTrue(len(throttle_calls) >= 1)
        # Khi sharp turn, throttle phải > 0 (0.22 * 0.6 = 0.132)
        self.assertGreater(throttle_calls[-1][1], 0.0)


def _arm_then_raise_keyboard_interrupt(self, duration=2.0):
    self.calls.append(("arm", duration))
    raise KeyboardInterrupt


if __name__ == "__main__":
    unittest.main()