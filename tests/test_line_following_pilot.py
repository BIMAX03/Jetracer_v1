"""Regression tests: pilot phải luôn dừng động cơ khi thoát.

Không truy cập phần cứng — dùng FakeCar/FakeCam ghi lại các lệnh.

Test cả 2 lớp:
- LineFollowingPilot: vòng lặp I/O + an toàn (stop khi thoát).
- LineFollowController: state machine NORMAL/BLIND_TURN/LOST.
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

from line_following.pid import DriveState, LineFollowController, PIDController  # noqa: E402
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
    """Detector giả lập — trả None cho mọi thứ (mất line, không có cua)."""

    def __init__(self, error=None, turn_incoming=False, turn_direction=0, turn_severity=0.0):
        self._error = error
        self._turn_incoming = turn_incoming
        self._turn_direction = turn_direction
        self._turn_severity = turn_severity

    def get_line_error(self, frame):
        return self._error, None, None

    def predict_turn_ahead(self, mask):
        return self._turn_incoming, self._turn_direction, self._turn_severity


class FakePid:
    def __init__(self):
        self.reset_calls = 0

    def reset(self):
        self.reset_calls += 1

    def compute(self, error, dt):
        return 0.0

    @property
    def kp(self):
        return 0.0

    @property
    def ki(self):
        return 0.0

    @property
    def kd(self):
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


def _arm_then_raise_keyboard_interrupt(self, duration=2.0):
    self.calls.append(("arm", duration))
    raise KeyboardInterrupt


def _make_controller(pid=None):
    """Tạo LineFollowController với config giống production."""
    if pid is None:
        pid = FakePid()
        # FakePid không phải PIDController thật, nhưng LineFollowController
        # chỉ cần thuộc tính pid.compute / pid.reset. Để type-check pass, dùng
        # thật nhưng giá trị 0 ở test dưới.
    return LineFollowController(
        pid=pid,
        base_throttle=0.22,
        max_steering_limit=1.0,
        blind_turn_duration_sec=2.0,
        blind_turn_throttle=0.08,
        blind_turn_steer_ratio=1.0,
    )


class PilotSafetyTest(unittest.TestCase):
    def setUp(self):
        self.car = FakeCar()
        self.pid = PIDController(0.0, 0.0, 0.0)
        self.controller = _make_controller(pid=self.pid)

    def make_pilot(self):
        return LineFollowingPilot(self.car, FakeDetector(), self.controller, 0.22)

    def test_interrupt_during_arm_stops_car(self):
        interrupted = FakeCar()
        interrupted.arm = types.MethodType(_arm_then_raise_keyboard_interrupt, interrupted)
        pilot = LineFollowingPilot(interrupted, FakeDetector(), self.controller, 0.22)
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

    def test_line_lost_sets_throttle_to_zero_after_blind_turn_times_out(self):
        """Sau khi mất line đột ngột -> LineFollowController vào BLIND_TURN
        (giữ throttle > 0 để rẽ theo hướng lệch gần nhất). Khi chạy mù quá
        BLIND_TURN_DURATION_SEC mà vẫn không thấy line -> LOST, throttle=0.

        Regression test cho bug 'xe vẫn chạy khi không bắt line': đảm bảo
        cuối cùng xe vẫn DỪNG an toàn, không chạy mù vô hạn.
        """
        # Dùng blind_dur ngắn để pilot kịp hết hạn trong vài frame
        controller = LineFollowController(
            pid=self.pid,
            base_throttle=0.22,
            max_steering_limit=1.0,
            blind_turn_duration_sec=0.05,  # 50ms
            blind_turn_throttle=0.08,
            blind_turn_steer_ratio=1.0,
        )
        # Frame đầu chạy mù, frame thứ 2 vẫn mất line -> chuyển LOST
        # FakeCam.read() sleep 0 không có; dùng dt đủ lớn để vượt duration
        cam = FakeCam(frames=[object(), object(), object(), _InterruptSentinel()])
        pilot = LineFollowingPilot(self.car, FakeDetector(), controller, 0.22)
        pilot.run(cam)
        throttle_calls = [c for c in self.car.calls if c[0] == "throttle"]
        self.assertTrue(len(throttle_calls) >= 1, "pilot phải gọi throttle ít nhất 1 lần")
        # Frame cuối cùng PHẢI là throttle=0 (đã vào LOST)
        self.assertEqual(
            throttle_calls[-1][1], 0.0,
            f"Sau BLIND_TURN hết hạn phải throttle=0 (LOST), nhưng nhận {throttle_calls[-1][1]!r}",
        )

    def test_sharp_turn_keeps_some_throttle(self):
        """Khi predict_turn_ahead báo cua sắp tới, LineFollowController vào
        BLIND_TURN và giữ throttle = blind_turn_throttle (> 0) để rẽ —
        đây không phải 'mất line hoàn toàn'.
        """
        detector = FakeDetector(error=None, turn_incoming=True, turn_direction=1, turn_severity=0.9)
        cam = FakeCam(frames=[object(), _InterruptSentinel()])
        pilot = LineFollowingPilot(self.car, detector, self.controller, 0.22)
        pilot.run(cam)
        throttle_calls = [c for c in self.car.calls if c[0] == "throttle"]
        self.assertTrue(len(throttle_calls) >= 1)
        # Khi sharp turn (BLIND_TURN), throttle phải = 0.08 (blind_turn_throttle)
        self.assertGreater(throttle_calls[-1][1], 0.0)
        self.assertAlmostEqual(throttle_calls[-1][1], 0.08, places=5)


class LineFollowControllerTest(unittest.TestCase):
    """Unit test state machine của LineFollowController (không qua pilot)."""

    def _make(self, base=0.22, blind_dur=2.0, blind_thr=0.08, blind_ratio=1.0, kp=1.2):
        return LineFollowController(
            pid=RealPid(kp=kp),
            base_throttle=base,
            max_steering_limit=1.0,
            blind_turn_duration_sec=blind_dur,
            blind_turn_throttle=blind_thr,
            blind_turn_steer_ratio=blind_ratio,
        )

    def test_normal_sees_line_returns_pid(self):
        c = self._make(kp=1.2)
        cmd = c.update(error=0.1, turn_incoming=False, turn_direction=0, turn_severity=0.0, dt=0.05)
        self.assertEqual(cmd.state, DriveState.NORMAL)
        self.assertEqual(cmd.throttle, 0.22)
        # PID với kp=1.2, error=0.1 -> steering=0.12
        self.assertAlmostEqual(cmd.steering, 0.12, places=5)

    def test_turn_incoming_enters_blind_turn(self):
        c = self._make()
        cmd = c.update(error=0.1, turn_incoming=True, turn_direction=-1, turn_severity=0.9, dt=0.05)
        self.assertEqual(cmd.state, DriveState.BLIND_TURN)
        # max_steering * ratio * direction = 1.0 * 1.0 * -1
        self.assertEqual(cmd.steering, -1.0)
        self.assertEqual(cmd.throttle, 0.08)

    def test_blind_turn_sees_line_exits_immediately(self):
        c = self._make()
        # Bước 1: vào BLIND_TURN
        c.update(error=None, turn_incoming=True, turn_direction=1, turn_severity=0.9, dt=0.05)
        self.assertEqual(c.state, DriveState.BLIND_TURN)
        # Bước 2: thấy lại line -> về NORMAL ngay, KHÔNG cần đợi hết duration
        cmd = c.update(error=-0.2, turn_incoming=False, turn_direction=0, turn_severity=0.0, dt=0.05)
        self.assertEqual(cmd.state, DriveState.NORMAL)
        self.assertEqual(cmd.throttle, 0.22)

    def test_blind_turn_timeout_becomes_lost(self):
        c = self._make(blind_dur=0.1)
        # Vào BLIND_TURN
        c.update(error=None, turn_incoming=True, turn_direction=1, turn_severity=0.9, dt=0.05)
        # Chạy mù quá thời gian cho phép mà vẫn không thấy line -> LOST
        cmd = c.update(error=None, turn_incoming=False, turn_direction=0, turn_severity=0.0, dt=0.2)
        self.assertEqual(cmd.state, DriveState.LOST)
        self.assertEqual(cmd.throttle, 0.0)
        self.assertEqual(cmd.steering, 0.0)

    def test_sudden_line_lost_uses_last_error_sign(self):
        """Khi mất line đột ngột không có cảnh báo trước, controller dùng
        dấu lệch gần nhất làm hướng khóa lái (tránh đứng im giữa cua).
        """
        c = self._make()
        # Vừa thấy line lệch phải (error dương)
        c.update(error=0.2, turn_incoming=False, turn_direction=0, turn_severity=0.0, dt=0.05)
        # Mất line đột ngột (không có cảnh báo) -> BLIND_TURN hướng +1
        cmd = c.update(error=None, turn_incoming=False, turn_direction=0, turn_severity=0.0, dt=0.05)
        self.assertEqual(cmd.state, DriveState.BLIND_TURN)
        self.assertEqual(cmd.steering, 1.0)

    def test_lost_sees_line_resumes_normal(self):
        c = self._make(blind_dur=0.1)
        c.update(error=None, turn_incoming=True, turn_direction=1, turn_severity=0.9, dt=0.05)
        c.update(error=None, turn_incoming=False, turn_direction=0, turn_severity=0.0, dt=0.2)
        self.assertEqual(c.state, DriveState.LOST)
        # Thấy lại line -> NORMAL
        cmd = c.update(error=0.0, turn_incoming=False, turn_direction=0, turn_severity=0.0, dt=0.05)
        self.assertEqual(cmd.state, DriveState.NORMAL)


class RealPid:
    """PIDController thật nhưng trả 0 để giữ test đơn giản khi cần."""

    def __init__(self, kp=0.0, ki=0.0, kd=0.0):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self._last_terms = {}
        self._integral = 0.0
        self._prev_error = 0.0

    def reset(self):
        self._prev_error = 0.0
        self._integral = 0.0

    def compute(self, error, dt):
        if dt <= 0.0:
            return 0.0
        out = self.kp * error
        self._last_terms = {"p": out, "i": 0.0, "d": 0.0, "error": error}
        return out

    @property
    def last_terms(self):
        return dict(self._last_terms)


if __name__ == "__main__":
    unittest.main()
