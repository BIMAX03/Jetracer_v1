"""Module xử lý ảnh tìm kiếm vạch kẻ đường (Line Detector).

Định nghĩa lớp `LineDetector` chịu trách nhiệm tiền xử lý ảnh BGR, chuyển đổi
sang hệ màu HSV, lọc mặt nạ nhị phân và tính toán sai số vị trí (Error) của
line so với tâm xe.
"""

import cv2
import numpy as np


class LineDetector:
    """Lớp xử lý ảnh và phát hiện line màu bằng OpenCV."""

    def __init__(self, lower_color: np.ndarray, upper_color: np.ndarray) -> None:
        """Khởi tạo detector với dải màu cần phát hiện.

        Args:
            lower_color: Ngưỡng màu HSV thấp nhất.
            upper_color: Ngưỡng màu HSV cao nhất.
        """
        self.lower_color = lower_color
        self.upper_color = upper_color

    def get_line_error(self, frame: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
        """Tính toán sai số lệch tâm của line so với xe.

        Args:
            frame: Ảnh gốc BGR từ camera.

        Returns:
            Một tuple gồm:
            - error: float trong khoảng [-1.0, 1.0] (None nếu mất dấu line).
            - mask: Ảnh nhị phân sau khi lọc màu và xóa nhiễu.
            - debug_frame: Ảnh ROI đã vẽ các điểm chỉ dẫn để hiển thị debug.
        """
        # TODO: Implement ROI crop
        # TODO: Apply Gaussian Blur and HSV thresholding
        # TODO: Apply Morphological opening to clear noise
        # TODO: Find centroid on target scan line
        # TODO: Return (error, mask, debug_frame)
        pass

    def check_sharp_turn(self, mask: np.ndarray) -> tuple[int, float]:
        """Phát hiện các góc cua vuông hoặc cua gấp đột ngột khi line đi ngang.

        Args:
            mask: Ảnh nhị phân từ hàm get_line_error.

        Returns:
            Một tuple gồm:
            - direction: -1 (cua trái), 1 (cua phải), 0 (không cua gấp).
            - confidence: độ tin cậy của phát hiện cua gấp [0.0, 1.0].
        """
        # TODO: Implement density checks on left and right side of mask
        pass
