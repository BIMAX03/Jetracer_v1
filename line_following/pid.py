"""Bộ điều khiển PID để tính toán góc đánh lái (Steering)."""

import time
from typing import Optional, Tuple
from line_following import config

class PIDController:
    """Bộ điều khiển PID chuyên biệt cho xe tự hành."""

    def __init__(self, kp: float = config.KP, ki: float = config.KI, kd: float = config.KD) -> None:
        self.kp = kp
        self.ki = ki
        self.kd = kd
        
        # Biến lưu trữ trạng thái của quá khứ
        self.prev_error: float = 0.0
        self.integral: float = 0.0
        self.last_time: Optional[float] = None

    def compute(self, error: Optional[float]) -> Tuple[float, dict]:
        """Tính toán góc bẻ lái dựa trên sai số Error.

        Args:
            error: Lệch tâm [-1.0, 1.0] lấy từ LineDetector. None nếu mất dấu line.

        Returns:
            Một Tuple gồm:
            - steering: Góc bẻ lái gửi xuống bánh xe [-1.0 (Trái), 1.0 (Phải)]
            - debug_terms: Dict chứa các thông số p, i, d để hiển thị lên màn hình.
        """
        current_time = time.time()

        # Xử lý trường hợp lần đầu chạy hoặc bị mất dấu line
        if self.last_time is None or error is None:
            self.last_time = current_time
            self.prev_error = error if error is not None else 0.0
            self.integral = 0.0
            return 0.0, {"p": 0.0, "i": 0.0, "d": 0.0, "dt": 0.0}

        # Tính thời gian đã trôi qua kể từ khung hình trước (Delta Time)
        dt = current_time - self.last_time
        self.last_time = current_time
        
        # Chống chia cho 0 nếu loop chạy quá nhanh
        if dt <= 0.0:
            dt = 0.01 

        # 1. Tính khâu tỷ lệ (P)
        p_term = self.kp * error

        # 2. Tính khâu tích phân (I)
        # Giới hạn vùng nhớ I để tránh lỗi "Integral Windup" (cộng dồn quá lớn khiến xe kẹt vô lăng)
        self.integral += error * dt
        self.integral = max(-1.0, min(1.0, self.integral)) 
        i_term = self.ki * self.integral

        # 3. Tính khâu vi phân (D) - Tốc độ thay đổi của sai số
        d_term = self.kd * ((error - self.prev_error) / dt)
        self.prev_error = error

        # 4. Tổng hợp góc lái (Steering)
        steering = p_term + i_term + d_term
        
        # Giới hạn góc lái không vượt ngưỡng cơ khí an toàn
        steering = max(-config.MAX_STEERING, min(config.MAX_STEERING, steering))

        # Lưu lại để hiển thị debug
        debug_terms = {
            "p": p_term,
            "i": i_term,
            "d": d_term,
            "dt": dt * 1000  # Đổi ra ms để dễ đọc
        }

        return steering, debug_terms

    def reset(self) -> None:
        """Xóa bộ nhớ quá khứ khi dừng xe hoặc mất line quá lâu."""
        self.prev_error = 0.0
        self.integral = 0.0
        self.last_time = None