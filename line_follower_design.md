# Thiết Kế Thuật Toán Dò Line Vàng Bằng OpenCV Cho JetRacer

Tài liệu này trình bày ý tưởng thiết kế, luồng xử lý ảnh và mã nguồn thử nghiệm (prototype) cho thuật toán dò line vàng trên nền xám, giúp xe JetRacer tự bám làn đường một cách ổn định và mượt mà.

---

## 1. Phân Tích Hình Ảnh Thực Tế

Dựa trên hai ảnh mẫu sa bàn thực tế của bạn:
1.  **Đường thẳng**: Vạch vàng đi từ góc dưới chính giữa hướng thẳng lên trên. Nền sàn có màu xám/xanh xám.
2.  **Khúc cua phải**: Vạch vàng rẽ ngang gắt về phía bên phải của khung hình.

**Nhận xét:**
*   Vạch màu vàng có độ bão hòa (saturation) và độ tương phản rất cao so với nền xám của sàn.
*   Nửa trên của ảnh chứa cảnh nền xung quanh (nhiễu), không cần thiết cho việc tính toán lái.
*   Khi vào cua gấp, phần đầu của vạch kẻ đường sẽ lệch hẳn sang một bên của ảnh.

---

## 2. Luồng Xử Lý Ảnh (Pipeline) Chi Tiết

Quy trình xử lý một khung hình từ camera bao gồm 6 bước chính:

```text
+------------------+     +------------------+     +------------------+
|  Ảnh Thô Camera  | --> | Cắt Vùng ROI     | --> | Chuyển Hệ HSV    |
+------------------+     | (Nửa dưới ảnh)   |     +------------------+
                         +------------------+               |
                                                            v
+------------------+     +------------------+     +------------------+
| Điều khiển PID   | <-- | Tính toán Error  | <-- | Lọc Màu & Nhiễu  |
| (Servo & Throttle|     | (Lệch tâm / Cua) |     | (Binary Mask)    |
+------------------+     +------------------+     +------------------+
```

### Bước 1: Chọn Vùng Quan Tâm (ROI - Region of Interest)
*   **Mục đích**: Loại bỏ nhiễu từ trần nhà, tường, hoặc người đứng xung quanh và giảm khối lượng tính toán.
*   **Thực hiện**: Chỉ lấy khoảng **50% đến 60% phần dưới** của bức ảnh. Ví dụ, nếu ảnh gốc là $640 \times 480$, ta chỉ xử lý vùng từ dòng $240$ đến $480$.

### Bước 2: Chuyển đổi màu sang hệ HSV
*   Hệ màu BGR thông thường rất nhạy cảm với cường độ ánh sáng (bóng đổ, đèn neon phản chiếu).
*   Chuyển sang hệ màu **HSV (Hue - Saturation - Value)** giúp tách biệt thông tin màu sắc (Hue) khỏi độ sáng (Value).

### Bước 3: Lọc màu vàng (Thresholding & Morphological Operations)
*   Áp dụng ngưỡng lọc màu vàng trong không gian HSV:
    *   `Lower Yellow = [15, 80, 100]`
    *   `Upper Yellow = [35, 255, 255]`
*   **Lọc nhiễu**:
    *   Dùng bộ lọc Gaussian Blur trước khi lọc màu để làm mịn ảnh.
    *   Áp dụng phép toán hình thái học **Morphological Opening** (Erode rồi Dilate) để triệt tiêu các chấm nhiễu nhỏ màu vàng ngoài sa bàn.
    *   Kết quả ta có một ảnh nhị phân (Binary Mask) với line vàng là màu trắng (255), nền là đen (0).

### Bước 4: Tính toán sai số lệch tâm (Error)
Để tính toán góc lái, ta chia vùng ROI thành các dải ngang (Strips) hoặc dùng một đường quét đích:
*   **Phương pháp dải ngang (Multi-strip Centroid)**:
    *   Chia ROI làm 3 phần: **Dưới** (gần xe), **Giữa**, và **Trên** (xa xe).
    *   Với mỗi phần, tính tọa độ $X$ trung bình của các pixel trắng (trọng tâm - Centroid $C_x$):
        $$C_x = \frac{\sum X_i}{N}$$
    *   **Dải Dưới** xác định vị trí hiện tại của xe so với line.
    *   **Dải Trên** xác định xu hướng cua tiếp theo của đường để đánh lái sớm.
    *   **Sai số điều khiển (Error)**: Độ lệch giữa tâm dải mục tiêu và tâm của khung hình.
*   **Gợi ý nhận diện cua gấp**: Nếu dải trên hoàn toàn không tìm thấy pixel màu vàng, nhưng dải giữa/dưới lệch cực lớn sang một bên, xe đang tiếp cận góc cua vuông/gấp.

### Bước 5: Bộ Điều Khiển PID (Proportional-Integral-Derivative)
Chuyển đổi `Error` thành góc lái `steering` trong khoảng `[-1.0, 1.0]`:
*   Sử dụng bộ điều khiển **PD** (thường bỏ thành phần tích phân $I$ để tránh trễ vô hạn):
    $$\text{Steering} = K_p \times \text{Error} + K_d \times (\text{Error} - \text{Prev\_Error})$$
*   $K_p$: Giúp xe phản ứng nhanh với khúc cua. Nếu quá lớn xe sẽ bị lắc.
*   $K_d$: Giảm chấn, ngăn hiện tượng bánh lái bị lắc qua lại (oscillation) trên đường thẳng.

### Bước 6: Điều Phối Tốc Độ Tự Động (Dynamic Throttle)
*   **Đi thẳng**: Khi `Error` gần bằng 0, tăng ga (`throttle = 0.25 - 0.35`) để xe chạy nhanh.
*   **Vào cua**: Khi `Error` lớn hoặc phát hiện khúc cua vuông, tự động giảm ga xuống mức tối thiểu (`throttle = 0.15 - 0.18`) để tránh trượt bánh ly tâm dẫn đến mất dấu line.

---

## 3. Mã Nguồn Tham Khảo (Python & OpenCV Prototype)

Dưới đây là một class Python tự chứa mẫu phát hiện vạch vàng và tính toán góc lái:

```python
import cv2
import numpy as np

class YellowLineDetector:
    def __init__(self):
        # Thiết lập dải màu vàng trong hệ HSV (Cần tinh chỉnh theo ánh sáng phòng thực tế)
        self.lower_yellow = np.array([15, 80, 80], dtype=np.uint8)
        self.upper_yellow = np.array([35, 255, 255], dtype=np.uint8)
        
        # Biến lưu trữ sai số trước đó cho đạo hàm Kd
        self.prev_error = 0.0

    def process_frame(self, frame, kp=1.0, kd=0.1, base_throttle=0.2):
        """
        Xử lý frame hình đầu vào và trả về góc lái (steering) và tốc độ ga (throttle) đề xuất.
        """
        h, w, _ = frame.shape
        
        # 1. Định nghĩa vùng ROI (Lấy 50% bên dưới ảnh)
        roi_start_y = int(h * 0.5)
        roi = frame[roi_start_y:h, :]
        roi_h, roi_w = roi.shape[0], roi.shape[1]
        center_x = roi_w // 2

        # 2. Tiền xử lý & lọc màu
        blurred = cv2.GaussianBlur(roi, (5, 5), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.lower_yellow, self.upper_yellow)
        
        # Phép toán Opening để xóa nhiễu
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # 3. Tính toán trọng tâm line theo các vùng (Quét 1 đường ngang đại diện tại 70% chiều cao ROI)
        scan_line_y = int(roi_h * 0.6)
        row_pixels = mask[scan_line_y, :]
        white_pixel_indices = np.where(row_pixels == 255)[0]

        # Khởi tạo trạng thái mặc định nếu mất dấu line hoàn toàn
        steering = 0.0
        throttle = base_throttle * 0.7  # Đi chậm dò lại đường khi mất dấu

        if len(white_pixel_indices) > 0:
            # Điểm tâm của line màu vàng trên đường quét
            line_center_x = int(np.mean(white_pixel_indices))
            
            # 4. Tính toán sai số (Error) chuẩn hóa về đoạn [-1.0, 1.0]
            error = (line_center_x - center_x) / (roi_w / 2.0)
            
            # 5. Bộ điều khiển PD
            derivative = error - self.prev_error
            steering = kp * error + kd * derivative
            self.prev_error = error
            
            # Giới hạn góc lái trong khoảng [-1.0, 1.0]
            steering = max(-1.0, min(1.0, steering))
            
            # 6. Điều khiển ga động (Dynamic Throttle)
            # Lệch tâm càng lớn (cua gấp) -> ga càng nhỏ
            throttle_scale = max(0.0, 1.0 - abs(error))
            throttle = base_throttle * (0.5 + 0.5 * throttle_scale)
            
            # Vẽ minh họa debug lên ảnh
            cv2.circle(roi, (line_center_x, scan_line_y), 8, (0, 0, 255), -1)
            cv2.line(roi, (center_x, 0), (center_x, roi_h), (255, 0, 0), 1)
        else:
            # Góc cua vuông đột ngột: Nếu mất dấu ở đường quét chính, thử quét góc cua gấp
            direction, confidence = self._right_angle_hint(mask, roi_w)
            if confidence > 0.25:
                # Đánh lái kịch sàn theo hướng cua vuông
                steering = float(direction) * 1.0 
                throttle = base_throttle * 0.5
                self.prev_error = steering

        return steering, throttle, mask, roi

    @staticmethod
    def _right_angle_hint(mask, width):
        """
        Hàm gợi ý hướng cua vuông khi vạch vàng nằm ngang ở góc trái hoặc góc phải (giống tests).
        """
        h, w = mask.shape
        # Chia khung hình làm 2 nửa trái và phải ở phần giữa ảnh
        left_zone = mask[int(h*0.3):int(h*0.7), 0:int(w*0.4)]
        right_zone = mask[int(h*0.3):int(h*0.7), int(w*0.6):w]
        
        left_density = np.sum(left_zone == 255) / left_zone.size
        right_density = np.sum(right_zone == 255) / right_zone.size
        
        if left_density > right_density and left_density > 0.2:
            return -1, left_density # Cua trái
        elif right_density > left_density and right_density > 0.2:
            return 1, right_density # Cua phải
        
        return 0, 0.0
```

---

## 4. Cách Tích Hợp Vào Xe JetRacer

Để đưa thuật toán này vào xe tự chạy thực tế:

1.  **Chỉnh cấu hình camera**: Nhận luồng hình ảnh từ CSI camera giống như trong [camera.py](file:///home/baymax/code/github/Jetracer_v1/web_control/camera.py).
2.  **Khởi tạo đối tượng Xe**: Import class `Car` từ [car.py](file:///home/baymax/code/github/Jetracer_v1/car.py).
3.  **Vòng lặp điều khiển**:
    ```python
    from car import Car
    import cv2
    # Khởi tạo xe và detector
    car = Car()
    car.arm()
    detector = YellowLineDetector()
    
    cap = cv2.VideoCapture(gstreamer_pipeline(), cv2.CAP_GSTREAMER)
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            # Xử lý ảnh tính toán lệnh lái/ga
            steering, throttle, mask, debug_img = detector.process_frame(
                frame, kp=1.2, kd=0.15, base_throttle=0.25
            )
            
            # Gửi lệnh trực tiếp điều khiển xe
            car.steering(steering)
            car.throttle(throttle)
    finally:
        car.stop() # Dừng xe an toàn khi kết thúc kịch bản
    ```
