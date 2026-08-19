"""Script hỗ trợ hiệu chuẩn thông số (Calibration Tool).

Sử dụng OpenCV window với thanh trượt (Trackbars) để người dùng có thể
tự do tinh chỉnh dải màu HSV (Lower/Upper) và các tham số PID trực quan
trên luồng camera trực tiếp của xe trước khi cho chạy thật.
"""

import cv2
import numpy as np


def main():
    """Tạo cửa sổ GUI hiển thị và thanh trượt tinh chỉnh thông số."""
    # TODO: Khởi tạo camera
    # TODO: Tạo cửa sổ OpenCV và Trackbars cho H, S, V (Min/Max), và PID (Kp, Kd)
    # TODO: Đọc luồng camera, áp dụng LineDetector và hiển thị ảnh Mask, ảnh debug
    # TODO: Cho phép lưu lại các tham số cấu hình tối ưu vào file config
    pass


if __name__ == "__main__":
    main()
