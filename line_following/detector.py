"""Module xử lý ảnh tìm kiếm vạch kẻ đường (Line Detector)."""

from line_following.config import SCAN_LINE_Y_PCT
from typing import Optional, Tuple
import cv2
import numpy as np

from line_following import config


class LineDetector:
    """Lớp xử lý ảnh và phát hiện line màu bằng OpenCV."""

    def __init__(self, lower_color: np.ndarray, upper_color: np.ndarray) -> None:
        self.lower_color = lower_color
        self.upper_color = upper_color
        # Khởi tạo sẵn biến để tránh AttributeError
        self.last_left_score: float = 0.0
        self.last_right_score: float = 0.0

    def get_line_error_moments(self, frame: np.ndarray) -> Tuple[Optional[float], np.ndarray, np.ndarray]:
        h, w, _ = frame.shape
        
        # 1. Cắt ROI
        roi_start_y = int(h * config.ROI_START_ROW_PCT)
        roi_start_y = int(h * config.ROI_START_ROW_PCT)
        roi = frame[roi_start_y:h, :] # Lấy từ roi_start_y đến hết đáy (h)
        roi_h, roi_w = roi.shape[:2]
        center_x = roi_w // 2

        # 2. Lọc màu HSV & làm sạch
        blurred = cv2.GaussianBlur(roi, (5, 5), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_color, self.upper_color)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # 3. Tìm các đường bao (Contour) trên ảnh mask
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        error: Optional[float] = None
        debug_frame = roi.copy()

        if contours:
            # Lấy contour có diện tích lớn nhất (chính là đường line, loại bỏ nhiễu hạt vụn)
            largest_contour = max(contours, key=cv2.contourArea)
            
            # Chỉ xử lý nếu contour đủ lớn (tránh nhận diện nhầm đốm sáng nhỏ ngoài sàn)
            if cv2.contourArea(largest_contour) > 100:
                M = cv2.moments(largest_contour)
                
                # Kiểm tra m00 > 0 để tránh chia cho 0
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])

                    # Tính error chuẩn hóa [-1.0, 1.0]
                    error = (cx - center_x) / (roi_w / 2.0)

                    # Vẽ viền contour và điểm tâm khối lên debug frame
                    cv2.drawContours(debug_frame, [largest_contour], -1, (0, 255, 0), 2)
                    cv2.circle(debug_frame, (cx, cy), 7, (0, 0, 255), -1)

        # Vẽ trục tâm xe (màu xanh dương)
        cv2.line(debug_frame, (center_x, 0), (center_x, roi_h), (255, 0, 0), 1)

        return error, mask, debug_frame
            
    def check_sharp_turn(self, mask: Optional[np.ndarray]) -> Tuple[int, float]:
        """Phát hiện cua gắt dựa trên độ vắt ngang (Bounding Box) của vạch kẻ."""
        if mask is None:
            return 0, 0.0

        # 1. Tìm các đường bao khối vạch kẻ
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return 0, 0.0

        # Lấy khối to nhất để tránh nhiễu
        largest_contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest_contour) < 300:
            return 0, 0.0

        # 2. Đóng khung hình chữ nhật quanh khối vạch kẻ
        x, y, w, h = cv2.boundingRect(largest_contour)
        img_h, img_w = mask.shape
        
        # Tỷ lệ chiều rộng khối so với chiều rộng màn hình
        width_pct = w / float(img_w)
        
        # Tỷ lệ khung hình (Rộng / Cao)
        aspect_ratio = w / float(max(1, h))

        # 3. ĐIỀU KIỆN CUA GẮT: Khối phải VẮT NGANG (> 40% màn hình) và bề ngang to hơn dọc
        if width_pct > 0.40 and aspect_ratio > 1.2:
            
            # Tính độ tin cậy: Càng vắt ngang dài thì điểm càng cao (tối đa 1.0)
            confidence = min(1.0, width_pct * 1.5)
            
            # Đếm pixel để biết nó vắt sang trái hay vắt sang phải
            left_pixels = cv2.countNonZero(mask[:, :img_w//2])
            right_pixels = cv2.countNonZero(mask[:, img_w//2:])
            
            if left_pixels > right_pixels * 1.5:
                return -1, confidence  # Cua trái
            elif right_pixels > left_pixels * 1.5:
                return 1, confidence   # Cua phải
                
        return 0, 0.0