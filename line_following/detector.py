"""Module xử lý ảnh tìm kiếm vạch kẻ đường (Line Detector).

Định nghĩa lớp `LineDetector` chịu trách nhiệm tiền xử lý ảnh BGR, chuyển đổi
sang hệ màu HSV, lọc mặt nạ nhị phân và tính toán sai số vị trí (Error) của
line so với tâm xe.
"""

import cv2
import numpy as np
from typing import Optional, Tuple

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

        # Kiểm tra nếu số lượng pixel trắng trên đường quét đủ lớn (lọc bỏ nhiễu nhỏ)
        min_width = getattr(config, "MIN_LINE_WIDTH_PX", 15)
        if len(white_pixel_indices) >= min_width:
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

    def predict_turn_ahead(self, mask: np.ndarray) -> Tuple[bool, int, float]:
        """Dự đoán TRƯỚC khi xe đi vào cua gấp, trước khi camera mất dấu line.

        Ý tưởng: `get_line_error` chỉ nhìn 1 dòng quét gần đáy ROI (gần xe).
        Khi cua 90 độ, line sẽ "chạy ngang" và biến mất khỏi các dòng quét
        ở PHÍA TRÊN ROI (xa xe hơn, ứng với vị trí xe sẽ tới trong ~vài
        frame tới) trước khi nó biến mất khỏi dòng quét chính. Hàm này quét
        nhiều dòng từ xa -> gần và phát hiện 2 dấu hiệu cảnh báo sớm:

        1. Line "chạm mép" ROI ở một dòng xa (line đang đi gần như ngang).
        2. Line biến mất hoàn toàn ở các dòng xa nhưng vẫn còn ở dòng gần
           (nghĩa là nó sắp ra khỏi khung hình khi xe tiến thêm).
        3. Xu hướng (trend) tâm line dịch chuyển nhanh về 1 phía khi so
           sánh dòng xa với dòng gần (line đang "cong gấp").

        Args:
            mask: Ảnh nhị phân (đã qua morphology) trả về từ `get_line_error`.

        Returns:
            Một tuple gồm:
            - turn_incoming: True nếu phát hiện cua gấp sắp tới.
            - direction: -1 (trái), 1 (phải), 0 (không xác định/không cua).
            - severity: độ tin cậy / độ gấp của cảnh báo, trong [0.0, 1.0].
        """
        roi_h, roi_w = mask.shape
        center_x = roi_w // 2
        min_width = getattr(config, "MIN_LINE_WIDTH_PX", 15)
        edge_margin = getattr(config, "TURN_EDGE_MARGIN_PX", int(roi_w * 0.05))
        drift_threshold = getattr(config, "TURN_DRIFT_THRESHOLD_PX", int(roi_w * 0.35))

        # Các dòng quét theo % chiều cao ROI, sắp xếp XA -> GẦN.
        # (0.0 = đỉnh ROI/xa xe nhất, gần config.SCAN_LINE_Y_PCT = gần xe nhất)
        scan_pcts = getattr(
            config, "LOOKAHEAD_SCAN_PCTS", [0.05, 0.15, 0.25, 0.35]
        )

        centers = []  # (pct, line_center_x) hoặc (pct, None) nếu mất line ở dòng đó
        for pct in scan_pcts:
            y = int(np.clip(roi_h * pct, 0, roi_h - 1))
            row = mask[y, :]
            idx = np.where(row == 255)[0]

            if len(idx) < min_width:
                centers.append((pct, None))
                continue

            cx = int(np.mean(idx))
            centers.append((pct, cx))

            # Dấu hiệu 1: line chạm sát mép ROI ở dòng xa -> cua rất gấp,
            # gần như chắc chắn sắp mất line nếu không xử lý sớm.
            if idx.min() <= edge_margin or idx.max() >= roi_w - edge_margin:
                direction = -1 if cx < center_x else 1
                return True, direction, 0.95

        valid = [(pct, cx) for pct, cx in centers if cx is not None]
        missing = [pct for pct, cx in centers if cx is None]

        # Dấu hiệu 2: các dòng XA NHẤT không thấy line, nhưng có dòng gần
        # hơn vẫn thấy -> line sắp ra khỏi khung hình khi xe tiến tới.
        if centers and centers[0][1] is None and valid:
            # Suy ra hướng cua dựa trên dòng gần nhất còn thấy line, so với
            # dòng còn có dữ liệu trước đó (xu hướng đang lệch về đâu).
            nearest_pct, nearest_cx = valid[0]
            direction = -1 if nearest_cx < center_x else 1
            # Càng nhiều dòng xa bị mất -> càng gấp
            severity = min(1.0, 0.5 + 0.15 * len(missing))
            return True, direction, severity

        # Dấu hiệu 3: xu hướng dịch chuyển tâm line giữa các dòng còn lại.
        if len(valid) >= 2:
            xs = np.array([pct for pct, _ in valid])
            ys = np.array([cx for _, cx in valid])
            slope, _ = np.polyfit(xs, ys, 1)  # px dịch chuyển / (1.0 pct chiều cao ROI)

            if abs(slope) > drift_threshold:
                direction = -1 if slope < 0 else 1
                severity = min(1.0, abs(slope) / roi_w)
                return True, direction, severity

        return False, 0, 0.0