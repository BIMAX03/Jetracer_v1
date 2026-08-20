"""Module bộ điều khiển PID (Proportional-Integral-Derivative Controller).

Chứa lớp `PIDController` dùng để tính toán giá trị góc lái phản hồi nhằm
giảm thiểu sai số lệch tâm của xe so với line.
"""


from typing import Tuple


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
        pass
