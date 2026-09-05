import cv2
import numpy as np
from typing import Optional, Tuple

def gstreamer_pipeline() -> str:
    """Tạo chuỗi GStreamer cấu hình riêng cho camera CSI trên Jetson."""
    return (
        "nvarguscamerasrc sensor-id=0 ! "
        "video/x-raw(memory:NVMM), "
        "width=(int)1280, height=(int)720, "
        "format=(string)NV12, framerate=(fraction)30/1 ! "
        "nvvidconv flip-method=0 ! "
        "video/x-raw, width=(int)960, height=(int)540, "
        "format=(string)BGRx ! videoconvert ! "
        "video/x-raw, format=(string)BGR ! "
        "appsink drop=true max-buffers=1 sync=false"
    )

class PilotCamera:
    """Mở và đọc dữ liệu từ camera CSI cấp cho LineDetector."""

    def __init__(self, device_id: int = 0) -> None:
        # Thử mở bằng GStreamer (dành cho Jetson)
        try:
            self.cap = cv2.VideoCapture(gstreamer_pipeline(), cv2.CAP_GSTREAMER)
        except Exception:
            # Dự phòng mở bằng USB Camera thông thường nếu GStreamer lỗi
            self.cap = cv2.VideoCapture(device_id)

        # Kiểm tra nếu không mở được
        if not self.cap.isOpened():
            self.cap.release()
            raise RuntimeError(
                "Không mở được camera CSI. Camera chỉ dùng được bởi một tiến trình.\n"
                "Nếu web_control đang chạy, hãy dừng nó trước:\n"
                "  sudo systemctl stop jetracer\n"
            )

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Đọc và trả về khung hình mới nhất."""
        ok, frame = self.cap.read()
        if not ok:
            return False, None
        return True, frame

    def release(self) -> None:
        """Tắt camera giải phóng tài nguyên."""
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()

