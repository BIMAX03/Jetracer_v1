"""Module bộ điều khiển PID (Proportional-Integral-Derivative Controller).

Chứa lớp `PIDController` dùng để tính toán giá trị góc lái phản hồi nhằm
giảm thiểu sai số lệch tâm của xe so với line.

Ngoài ra chứa lớp `LineFollowController`: bộ điều khiển bậc cao hơn, bọc
quanh `PIDController`, quản lý một state machine đơn giản để xe có thể đi
qua các khúc cua gấp (~90 độ) mà camera không kịp thấy line liên tục — xem
docstring của `LineFollowController` để biết chi tiết.
"""

from enum import Enum
from typing import NamedTuple, Optional, Tuple


class PIDController:
    """Lớp điều khiển phản hồi PID độc lập."""

    def __init__(self, kp: float, ki: float, kd: float, output_limits: Tuple[float, float] = (-1.0, 1.0)) -> None:
        """Khởi tạo các hệ số PID và giới hạn đầu ra.

        Args:
            kp: Hệ số tỉ lệ (Proportional).
            ki: Hệ số tích phân (Integral).
            kd: Hệ số đạo hàm (Derivative).
            output_limits: Giới hạn giá trị trả về (min, max).
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.min_val, self.max_val = output_limits

        self._prev_error = 0.0
        self._integral = 0.0
        self._last_terms = {"p": 0.0, "i": 0.0, "d": 0.0}

    def compute(self, error: float, dt: float) -> float:
        """Tính toán đầu ra dựa trên sai số và khoảng thời gian chu kỳ.

        Args:
            error: Sai số hiện tại (lệch tâm).
            dt: Khoảng thời gian từ lần tính trước (giây).

        Returns:
            Giá trị điều khiển (ví dụ: góc lái) đã được giới hạn.
        """
        if dt <= 0.0:
            return 0.0

        # Proportional term
        p_term = self.kp * error

        # Integral term with clamping anti-windup
        self._integral += error * dt
        if self.ki != 0.0:
            # Simple clamping anti-windup: limit integration when output saturates
            # Limit integral term based on other contributions
            d_term_approx = self.kd * (error - self._prev_error) / dt
            max_i = (self.max_val - p_term - d_term_approx) / self.ki
            min_i = (self.min_val - p_term - d_term_approx) / self.ki
            if min_i > max_i:
                min_i, max_i = max_i, min_i
            self._integral = max(min_i, min(max_i, self._integral))
            i_term = self.ki * self._integral
        else:
            i_term = 0.0

        # Derivative term
        d_term = self.kd * (error - self._prev_error) / dt
        self._prev_error = error

        # Compute output and clamp to limits
        output = p_term + i_term + d_term
        self._last_terms = {
            "p": p_term,
            "i": i_term,
            "d": d_term,
            "error": error,
        }
        return max(self.min_val, min(self.max_val, output))

    @property
    def last_terms(self) -> dict:
        """Các thành phần P/I/D của lần compute() gần nhất (dùng cho debug)."""
        return dict(self._last_terms)

    def reset(self) -> None:
        """Đặt lại các biến trạng thái tích phân và sai số cũ."""
        self._prev_error = 0.0
        self._integral = 0.0


class DriveState(str, Enum):
    """Các trạng thái của state machine trong `LineFollowController`."""

    NORMAL = "NORMAL"          # Thấy line, chạy PID bình thường
    BLIND_TURN = "BLIND_TURN"  # Đang "chạy mù" qua cua gấp theo hướng đã khóa
    LOST = "LOST"              # Hết thời gian chạy mù mà vẫn không thấy line -> dừng


class DriveCommand(NamedTuple):
    """Kết quả trả về của `LineFollowController.update()`."""

    steering: float
    throttle: float
    state: DriveState
    blind_turn_elapsed: float = 0.0


class LineFollowController:
    """Bộ điều khiển bậc cao: PID + xử lý cua gấp bằng "đánh lái mù".

    Vấn đề cần giải quyết: ở các khúc cua ~90 độ, ngay trước khi camera mất
    hẳn dấu line, `LineDetector.predict_turn_ahead()` đã kịp báo trước
    hướng cua sắp tới. Thay vì đợi tới lúc `error is None` rồi mới phản ứng
    (lúc đó xe thường đã đi thẳng ra ngoài line và đứng im), controller này
    sẽ CHỦ ĐỘNG khóa lái tối đa theo hướng cua ngay khi có cảnh báo, và giữ
    nguyên lái đó trong tối đa `BLIND_TURN_DURATION_SEC` giây kể cả khi
    không còn thấy line — đủ để xe xoay hết khúc cua.

    Quy tắc chuyển trạng thái:
        NORMAL --(dự đoán có cua, có hướng)--> BLIND_TURN
        NORMAL --(mất line đột ngột, không có cảnh báo trước)--> BLIND_TURN
                (dùng hướng lệch gần nhất làm hướng khóa lái)
        BLIND_TURN --(thấy lại line, BẤT KỲ lúc nào < thời gian tối đa)--> NORMAL
        BLIND_TURN --(hết BLIND_TURN_DURATION_SEC mà vẫn không thấy line)--> LOST
        LOST --(thấy lại line)--> NORMAL
        LOST --(vẫn không thấy line)--> LOST (đứng im, chờ)

    Ví dụ: cua trái được phát hiện -> khóa lái = -MAX_STEERING_LIMIT, chạy
    tối đa 2 giây. Nếu ở giây thứ 1 đã thấy lại line thì thoát BLIND_TURN
    ngay lập tức và chạy PID bình thường, không đợi đủ 2 giây.
    """

    def __init__(
        self,
        pid: PIDController,
        base_throttle: float,
        max_steering_limit: float,
        blind_turn_duration_sec: float,
        blind_turn_throttle: float,
        blind_turn_steer_ratio: float = 1.0,
    ) -> None:
        """Khởi tạo controller.

        Args:
            pid: Instance `PIDController` dùng cho chế độ chạy bình thường.
            base_throttle: Ga mặc định khi chạy bình thường (thấy line).
            max_steering_limit: Giới hạn góc lái tối đa của xe (vd 1.0).
            blind_turn_duration_sec: Thời gian tối đa "chạy mù" qua cua (giây).
            blind_turn_throttle: Ga dùng khi đang chạy mù qua cua (thường
                chậm hơn base_throttle để an toàn).
            blind_turn_steer_ratio: Hệ số nhân với max_steering_limit khi
                khóa lái (1.0 = đánh lái hết cỡ theo hướng cua).
        """
        self.pid = pid
        self.base_throttle = base_throttle
        self.max_steering_limit = max_steering_limit
        self.blind_turn_duration_sec = blind_turn_duration_sec
        self.blind_turn_throttle = blind_turn_throttle
        self.blind_turn_steer_ratio = blind_turn_steer_ratio

        self.state = DriveState.NORMAL
        self._blind_turn_direction = 0
        self._blind_turn_elapsed = 0.0
        self._last_error_sign = 0  # dấu lệch line gần nhất khi còn NORMAL, dùng làm fallback

    def update(
        self,
        error: Optional[float],
        turn_incoming: bool,
        turn_direction: int,
        turn_severity: float,
        dt: float,
    ) -> DriveCommand:
        """Tính lệnh lái/ga cho 1 chu kỳ điều khiển.

        Args:
            error: Sai số lệch tâm từ `LineDetector.get_line_error()`, None
                nếu mất dấu line ở dòng quét chính.
            turn_incoming: Kết quả `predict_turn_ahead()` — có cua sắp tới.
            turn_direction: Hướng cua dự đoán (-1 trái, 1 phải, 0 không rõ).
            turn_severity: Độ tin cậy/độ gấp của dự đoán cua, [0.0, 1.0].
            dt: Khoảng thời gian từ chu kỳ trước (giây).

        Returns:
            `DriveCommand` gồm steering, throttle, state hiện tại và thời
            gian đã chạy mù (nếu đang ở BLIND_TURN, dùng để log/debug).
        """
        if error is not None:
            self._last_error_sign = -1 if error < 0 else (1 if error > 0 else self._last_error_sign)

        if self.state == DriveState.NORMAL:
            return self._handle_normal(error, turn_incoming, turn_direction, dt)

        if self.state == DriveState.BLIND_TURN:
            return self._handle_blind_turn(error, dt)

        # DriveState.LOST
        return self._handle_lost(error, dt)

    def _handle_normal(
        self, error: Optional[float], turn_incoming: bool, turn_direction: int, dt: float
    ) -> DriveCommand:
        # Có cảnh báo cua sắp tới với hướng rõ ràng -> chủ động khóa lái mù
        # NGAY, trước khi thật sự mất line.
        if turn_incoming and turn_direction != 0:
            self._enter_blind_turn(turn_direction)
            return self._blind_turn_command()

        # Mất line đột ngột mà không có cảnh báo trước (vd nhiễu, chưa kịp
        # dự đoán) -> vẫn vào chế độ mù, dùng hướng lệch gần nhất làm hướng
        # khóa lái để không đứng im giữa cua.
        if error is None:
            fallback_direction = self._last_error_sign if self._last_error_sign != 0 else 1
            self._enter_blind_turn(fallback_direction)
            return self._blind_turn_command()

        # Trường hợp bình thường: còn thấy line, chưa có cảnh báo cua -> PID
        steering = self.pid.compute(error, dt)
        return DriveCommand(steering=steering, throttle=self.base_throttle, state=self.state)

    def _handle_blind_turn(self, error: Optional[float], dt: float) -> DriveCommand:
        # Thấy lại line BẤT KỲ lúc nào trong lúc chạy mù -> thoát ngay lập
        # tức, không cần đợi hết blind_turn_duration_sec.
        if error is not None:
            self._exit_blind_turn(resume_normal=True)
            self.pid.reset()  # tránh cú giật do sai số/đạo hàm tích lũy trong lúc chạy mù
            steering = self.pid.compute(error, dt)
            return DriveCommand(steering=steering, throttle=self.base_throttle, state=self.state)

        self._blind_turn_elapsed += dt
        if self._blind_turn_elapsed >= self.blind_turn_duration_sec:
            # Hết thời gian cho phép mà vẫn không thấy line -> dừng lại,
            # tránh xe lao mù vô định.
            self.state = DriveState.LOST
            return DriveCommand(steering=0.0, throttle=0.0, state=self.state)

        return self._blind_turn_command()

    def _handle_lost(self, error: Optional[float], dt: float) -> DriveCommand:
        if error is not None:
            self._exit_blind_turn(resume_normal=True)
            self.pid.reset()
            steering = self.pid.compute(error, dt)
            return DriveCommand(steering=steering, throttle=self.base_throttle, state=self.state)

        # Vẫn không thấy line -> đứng im chờ (có thể mở rộng thêm hành vi
        # "dò tìm" - vd xoay tại chỗ - nếu cần sau này).
        return DriveCommand(steering=0.0, throttle=0.0, state=self.state)

    def _enter_blind_turn(self, direction: int) -> None:
        self.state = DriveState.BLIND_TURN
        self._blind_turn_direction = -1 if direction < 0 else 1
        self._blind_turn_elapsed = 0.0

    def _exit_blind_turn(self, resume_normal: bool) -> None:
        self._blind_turn_direction = 0
        self._blind_turn_elapsed = 0.0
        if resume_normal:
            self.state = DriveState.NORMAL

    def _blind_turn_command(self) -> DriveCommand:
        steering = self.max_steering_limit * self.blind_turn_steer_ratio * self._blind_turn_direction
        return DriveCommand(
            steering=steering,
            throttle=self.blind_turn_throttle,
            state=self.state,
            blind_turn_elapsed=self._blind_turn_elapsed,
        )