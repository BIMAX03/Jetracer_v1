"""Module xử lý ảnh tìm kiếm vạch kẻ đường (Line Detector).

Định nghĩa lớp `LineDetector` chịu trách nhiệm tiền xử lý ảnh BGR, chuyển đổi
sang hệ màu HSV, lọc mặt nạ nhị phân và tính toán sai số vị trí (Error) của
line so với tâm xe.
"""

import cv2
import numpy as np
from typing import Tuple

from line_following import config



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

    def get_line_error(self, frame: np.ndarray) -> Tuple[float, np.ndarray, np.ndarray]:
        """Tính toán sai số lệch tâm của line so với xe.

        Args:
            frame: Ảnh gốc BGR từ camera.

        Returns:
            Một tuple gồm:
            - error: float trong khoảng [-1.0, 1.0] (None nếu mất dấu line).
            - mask: Ảnh nhị phân sau khi lọc màu và xóa nhiễu.
            - debug_frame: Ảnh ROI đã vẽ các điểm chỉ dẫn để hiển thị debug.
        """
        h, w, _ = frame.shape
        
        # 1. Định nghĩa vùng ROI (Lấy phần bên dưới ảnh theo config)
        roi_start_y = int(h * config.ROI_START_ROW_PCT)
        roi = frame[roi_start_y:h, :]
        roi_h, roi_w = roi.shape[0], roi.shape[1]
        center_x = roi_w // 2

        # 2. Tiền xử lý & lọc màu HSV
        blurred = cv2.GaussianBlur(roi, (5, 5), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_color, self.upper_color)
        
        # Phép toán Morphological Opening để lọc nhiễu
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # 3. Tính toán trọng tâm line theo dòng quét (Scan Line)
        scan_line_y = int(roi_h * config.SCAN_LINE_Y_PCT)
        row_pixels = mask[scan_line_y, :]
        white_pixel_indices = np.where(row_pixels == 255)[0]

        error = None
        debug_frame = roi.copy()

        if len(white_pixel_indices) > 0:
            # Điểm tâm của line màu vàng trên đường quét
            line_center_x = int(np.mean(white_pixel_indices))
            
            # Tính toán sai số (Error) chuẩn hóa về đoạn [-1.0, 1.0]
            error = (line_center_x - center_x) / (roi_w / 2.0)
            
            # Vẽ minh họa debug lên ảnh
            cv2.circle(debug_frame, (line_center_x, scan_line_y), 8, (0, 0, 255), -1)
            
        # Vẽ các đường dẫn hướng debug
        cv2.line(debug_frame, (center_x, 0), (center_x, roi_h), (255, 0, 0), 1)
        cv2.line(debug_frame, (0, scan_line_y), (roi_w, scan_line_y), (0, 255, 0), 1)

        return error, mask, debug_frame

    def check_sharp_turn(self, mask: np.ndarray) -> Tuple[int, float]:
        """Phát hiện các góc cua vuông hoặc cua gấp đột ngột khi line đi ngang.

        Args:
            mask: Ảnh nhị phân từ hàm get_line_error.

        Returns:
            Một tuple gồm:
            - direction: -1 (cua trái), 1 (cua phải), 0 (không cua gấp).
            - confidence: độ tin cậy của phát hiện cua gấp [0.0, 1.0].
        """
        h, w = mask.shape
        return self._right_angle_hint(mask, w // 2)

    @staticmethod
    def _right_angle_hint(mask: np.ndarray, center_x: int) -> Tuple[int, float]:
        """Phát hiện các góc cua vuông hoặc cua gấp đột ngột khi line đi ngang.

        Args:
            mask: Ảnh nhị phân.
            center_x: Tọa độ X trung tâm.

        Returns:
            Một tuple gồm:
            - direction: -1 (cua trái), 1 (cua phải), 0 (không cua gấp).
            - confidence: độ tin cậy của phát hiện cua gấp [0.0, 1.0].
        """
        h, w = mask.shape
        
        # Thiết lập các khoảng quét ngang theo tỷ lệ ảnh
        r_start, r_end = int(h * 0.35), int(h * 0.45)
        c_left_start = int(center_x * 0.2)
        c_right_end = int(center_x * 1.8)
        
        # Đảm bảo các chỉ số không vượt quá biên ảnh
        r_start = max(0, min(h - 1, r_start))
        r_end = max(0, min(h, r_end))
        c_left_start = max(0, min(w - 1, c_left_start))
        c_right_end = max(0, min(w, c_right_end))
        center_x = max(0, min(w, center_x))
        
        left_area = (r_end - r_start) * (center_x - c_left_start)
        right_area = (r_end - r_start) * (c_right_end - center_x)
        
        if left_area <= 0 or right_area <= 0:
            return 0, 0.0
            
        left_pixels = np.sum(mask[r_start:r_end, c_left_start:center_x] == 255)
        right_pixels = np.sum(mask[r_start:r_end, center_x:c_right_end] == 255)
        
        left_density = float(left_pixels) / left_area
        right_density = float(right_pixels) / right_area
        
        # Ngưỡng phát hiện góc rẽ gắt
        threshold = 0.25
        if left_density > threshold and left_density > right_density:
            return -1, left_density
        elif right_density > threshold and right_density > left_density:
            return 1, right_density
            
        return 0, 0.0

