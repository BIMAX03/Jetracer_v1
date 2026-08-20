"""Camera và luồng debug trực quan cho chế độ dò line (Line Following).

Cung cấp:
    - ``PilotCamera``: mở camera CSI, cảnh báo rõ ràng nếu bị web_control chiếm.
    - ``render_debug_frame``: vẽ overlay chi tiết (ROI, Scan line, Error, P/I/D,
      Steering, Throttle, tần số vòng lặp, mặt nạ HSV) lên ảnh camera.
    - ``DebugStreamer``: HTTP server nhỏ (mặc định cổng 5001) phục vụ:
        * ``/``           — luồng MJPEG ảnh debug (xem trực tiếp từ trình duyệt).
        * ``/dashboard``  — trang dashboard đầy đủ: video + chỉ số + đồ thị.
        * ``/metrics``    — JSON telemetry mới nhất (dashboard poll định kỳ).
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

from line_following import config
from line_following.dashboard import dashboard_page


# ─── Pipeline camera CSI (giữ cùng tham số với web_control) ──────────────
def gstreamer_pipeline():
    """Pipeline CSI độ trễ thấp, tương đương web_control/camera.py."""
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
    """Mở camera CSI cho vòng lặp pilot (một tiến trình duy nhất)."""

    def __init__(self, device_id: int = 0) -> None:
        try:
            self.cap = cv2.VideoCapture(gstreamer_pipeline(), cv2.CAP_GSTREAMER)
        except Exception:
            self.cap = cv2.VideoCapture(device_id)
        if not self.cap.isOpened():
            self.cap.release()
            raise RuntimeError(
                "Không mở được camera CSI. Camera chỉ dùng được bởi một tiến trình — "
                "web_control đang chạy sẽ chiếm camera.\n"
                "  Dừng web trước khi chạy pilot:\n"
                "    sudo systemctl stop jetracer\n"
                "  Kiểm tra cổng 5000 đã giải phóng:\n"
                "    sudo ss -ltnp | grep ':5000 '"
            )

    def read(self):
        ok, frame = self.cap.read()
        return frame if ok else None

    def release(self) -> None:
        self.cap.release()


# ─── Vẽ overlay debug ────────────────────────────────────────────────────
def render_debug_frame(
    frame: np.ndarray,
    mask: np.ndarray,
    error: float,
    steering: float,
    throttle: float,
    pid_terms: dict,
    meta: dict,
) -> np.ndarray:
    """Vẽ toàn bộ thông số dò line lên ảnh camera.

    Args:
        frame: Ảnh BGR gốc từ camera.
        mask: Mặt nạ nhị phân sau lọc màu HSV (dùng cho ảnh nhỏ góc phải).
        error: Sai số lệch tâm hiện tại (None nếu mất dấu line).
        steering: Góc lái đang gửi xuống xe.
        throttle: Tốc độ ga đang gửi xuống xe.
        pid_terms: Các thành phần PID (p, i, d, dt) từ PIDController.
        meta: Dict chứa thêm thông tin (frames, line_hits, loop_hz, fps,
              direction, confidence, base_throttle).
    """
    h, w, _ = frame.shape
    debug_img = frame.copy()

    roi_start_y = int(h * config.ROI_START_ROW_PCT)
    roi_h = h - roi_start_y
    center_x = w // 2

    # 1. Khung ROI
    cv2.rectangle(debug_img, (0, roi_start_y), (w - 1, h - 1), (0, 255, 255), 2)

    # 2. Đường quét Scan Line
    scan_line_y = roi_start_y + int(roi_h * config.SCAN_LINE_Y_PCT)
    cv2.line(debug_img, (0, scan_line_y), (w, scan_line_y), (0, 255, 0), 2)

    # 3. Đường tâm xe
    cv2.line(debug_img, (center_x, roi_start_y), (center_x, h), (255, 0, 0), 1)

    # 4. Điểm dò thấy line + mũi tên lệch tâm
    status_text = "LINE LOST"
    status_color = (0, 0, 255)
    if error is not None:
        line_center_x = int(center_x + error * (w / 2.0))
        cv2.circle(debug_img, (line_center_x, scan_line_y), 8, (0, 0, 255), -1)
        cv2.line(
            debug_img,
            (center_x, scan_line_y),
            (line_center_x, scan_line_y),
            (0, 0, 255),
            2,
        )
        status_text = "LINE OK"
        status_color = (0, 255, 0)
    else:
        direction = meta.get("direction", 0)
        confidence = meta.get("confidence", 0.0)
        if confidence > 0.25:
            status_text = "SHARP TURN " + ("LEFT" if direction < 0 else "RIGHT")
            status_color = (0, 165, 255)

    # 5. Bảng thông số (góc trên trái)
    terms = pid_terms or {}
    lines = [
        "STATUS: {}".format(status_text),
        "error   : {:+.3f}".format(error if error is not None else 0.0),
        "steering: {:+.3f}".format(steering),
        "throttle: {:+.3f}".format(throttle),
        "P {:+.3f}  I {:+.3f}  D {:+.3f}".format(
            terms.get("p", 0.0), terms.get("i", 0.0), terms.get("d", 0.0)
        ),
        "Kp {:.2f}  Ki {:.2f}  Kd {:.2f}".format(config.KP, config.KI, config.KD),
        "dt {:.0f} ms | loop {:.0f} Hz | fps {:.1f}".format(
            meta.get("dt_ms", 0.0), meta.get("loop_hz", 0.0), meta.get("fps", 0.0)
        ),
        "frames {:d} | line_hits {:d}".format(
            meta.get("frames", 0), meta.get("line_hits", 0)
        ),
        "base_throttle {:.3f}".format(meta.get("base_throttle", config.BASE_THROTTLE)),
    ]
    cv2.rectangle(debug_img, (8, 8), (360, 8 + 22 * len(lines) + 8), (0, 0, 0), -1)
    for idx, text in enumerate(lines):
        color = status_color if idx == 0 else (255, 255, 255)
        cv2.putText(
            debug_img, text, (16, 26 + 22 * idx),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1,
        )

    # 6. Ảnh nhỏ mặt nạ HSV (góc phải dưới) để kiểm tra bộ lọc màu
    mask_h, mask_w = mask.shape[:2]
    thumb_w, thumb_h = 200, int(200 * mask_h / mask_w)
    thumb = cv2.resize(mask, (thumb_w, thumb_h), interpolation=cv2.INTER_NEAREST)
    thumb_bgr = cv2.cvtColor(thumb, cv2.COLOR_GRAY2BGR)
    x0, y0 = w - thumb_w - 10, h - thumb_h - 10
    debug_img[y0:y0 + thumb_h, x0:x0 + thumb_w] = thumb_bgr
    cv2.rectangle(debug_img, (x0, y0), (x0 + thumb_w, y0 + thumb_h), (0, 0, 0), 2)
    cv2.putText(
        debug_img, "HSV MASK", (x0 + 6, y0 + 18),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
    )

    return debug_img


# ─── HTTP server (MJPEG + dashboard + metrics) ───────────────────────────
class _StreamHandler(BaseHTTPRequestHandler):
    server: "DebugStreamer"  # noqa: F821

    def do_GET(self):
        streamer = self.server._streamer
        if self.path == "/":
            self._serve_stream(streamer)
        elif self.path == "/dashboard":
            self._serve_bytes(
                dashboard_page(), "text/html; charset=utf-8"
            )
        elif self.path == "/metrics":
            payload = json.dumps(streamer.latest_metrics).encode("utf-8")
            self._serve_bytes(payload, "application/json")
        else:
            self.send_error(404)

    def _serve_bytes(self, payload: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _serve_stream(self, streamer) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        while not self.server._stop_event.is_set():
            jpeg = streamer.latest_jpeg
            if jpeg is None:
                time.sleep(0.05)
                continue
            try:
                self.wfile.write(
                    b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                )
            except (BrokenPipeError, ConnectionResetError):
                break
            time.sleep(1.0 / max(1.0, config.DEBUG_STREAM_FPS))
        try:
            self.wfile.flush()
        except Exception:
            pass

    def log_message(self, format, *args):
        pass


class DebugStreamer:
    """Chạy HTTP server nền, publish frame + telemetry debug mới nhất.

    Mở trình duyệt tại ``http://<ip-jetson>:<port>/dashboard`` để xem toàn bộ
    chỉ số và đồ thị realtime khi pilot đang chạy (hoặc ``/`` cho luồng MJPEG).
    """

    def __init__(self, host: str = None, port: int = None) -> None:
        self.host = host or config.DEBUG_STREAM_HOST
        self.port = port or config.DEBUG_STREAM_PORT
        self.latest_jpeg = None
        self.latest_metrics = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._httpd = None
        self._thread = None

    def start(self) -> bool:
        """Khởi động server; trả False nếu cổng bị chiếm (không gây lỗi pilot)."""
        try:
            self._httpd = ThreadingHTTPServer((self.host, self.port), _StreamHandler)
        except OSError:
            return False
        self._httpd._stop_event = self._stop_event
        self._httpd._streamer = self
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return True

    def publish(self, frame: np.ndarray) -> None:
        """Encode ảnh debug thành JPEG và cập nhật frame mới nhất."""
        if self._httpd is None:
            return
        ok, encoded = cv2.imencode(
            ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), config.DEBUG_STREAM_JPEG_QUALITY]
        )
        if ok:
            with self._lock:
                self.latest_jpeg = encoded.tobytes()

    def publish_metrics(self, metrics: dict) -> None:
        """Cập nhật điểm telemetry mới nhất (dashboard poll qua /metrics)."""
        if self._httpd is None:
            return
        with self._lock:
            self.latest_metrics = dict(metrics)

    def stop(self) -> None:
        self._stop_event.set()
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
