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

    def check_sharp_turn(self, mask) -> Tuple[int, float]:
        """Phát hiện các góc cua vuông hoặc cua gấp đột ngột khi line đi ngang.

        Args:
            mask: Ảnh nhị phân từ hàm get_line_error. Chấp nhận None (trả về 0, 0.0).

        Returns:
            Một tuple gồm:
            - direction: -1 (cua trái), 1 (cua phải), 0 (không cua gấp).
            - confidence: độ tin cậy của phát hiện cua gấp [0.0, 1.0].
        """
        if mask is None:
            self.last_left_score = 0.0
            self.last_right_score = 0.0
            return 0, 0.0
        h, w = mask.shape
        direction, confidence, l_score, r_score = self._right_angle_hint(mask, w // 2)
        self.last_left_score = l_score
        self.last_right_score = r_score
        return direction, confidence

    @staticmethod
    def _right_angle_hint(mask: np.ndarray, center_x: int) -> Tuple[int, float, float, float]:
        """Phát hiện các góc cua vuông hoặc cua gấp đột ngột khi line đi ngang.

        Phương pháp: quét 2 vùng theo chiều dọc ROI:
          - Vùng DƯỚI (0% – 60% chiều cao): nơi scan-line chạy ngang, phát hiện
            line đang tiến vào cua (line bên phải hoặc trái).
          - Vùng TRÊN (40% – 80% chiều cao): nơi line vừa vòng lên/ra ngoài ROI.
        Nếu cả 2 vùng đều đồng thuận về hướng → confidence cao hơn.

        Args:
            mask: Ảnh nhị phân.
            center_x: Tọa độ X trung tâm.

        Returns:
            Một tuple gồm:
            - direction: -1 (cua trái), 1 (cua phải), 0 (không cua gấp).
            - confidence: độ tin cậy của phát hiện cua gấp [0.0, 1.0].
            - left_score: điểm mật độ tổng hợp phía trái.
            - right_score: điểm mật độ tổng hợp phía phải.
        """
        h, w = mask.shape
        center_x = max(1, min(w - 1, center_x))

        # Vùng biên trái/phải để tránh nhiễu mép ảnh
        x_margin = max(1, int(w * 0.05))
        x_left = x_margin
        x_right = w - x_margin

        # --- Vùng DƯỚI: phát hiện line chạy ngang (tiếp cận góc cua) ---
        bot_r_start = int(h * 0.0)
        bot_r_end   = int(h * 0.60)

        # --- Vùng TRÊN: phát hiện line đã bắt đầu vòng vào corner ---
        top_r_start = int(h * 0.40)
        top_r_end   = int(h * 0.80)

        def _density(r0, r1, cx0, cx1):
            area = max(1, (r1 - r0) * (cx1 - cx0))
            px   = np.sum(mask[r0:r1, cx0:cx1] == 255)
            return float(px) / area

        # Vùng dưới
        bot_left  = _density(bot_r_start, bot_r_end, x_left,    center_x)
        bot_right = _density(bot_r_start, bot_r_end, center_x,  x_right)

        # Vùng trên
        top_left  = _density(top_r_start, top_r_end, x_left,    center_x)
        top_right = _density(top_r_start, top_r_end, center_x,  x_right)

        # Kết hợp: trọng số cao hơn cho vùng dưới (gần scan-line hơn)
        left_score  = 0.65 * bot_left  + 0.35 * top_left
        right_score = 0.65 * bot_right + 0.35 * top_right

        # Ngưỡng phát hiện
        threshold = 0.15
        if left_score > threshold and left_score > right_score * 1.3:
            return -1, left_score, left_score, right_score
        elif right_score > threshold and right_score > left_score * 1.3:
            return 1, right_score, left_score, right_score

        return 0, 0.0, left_score, right_score

