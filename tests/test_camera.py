"""Test Camera trên Web — truy cập từ trình duyệt máy khác.

Chạy:
    python3 -m tests.test_camera

Mở trình duyệt trên máy khác (cùng mạng LAN):
    http://<IP_JETSON>:5050
"""

import threading
import time

import cv2
import numpy as np
from flask import Flask, Response, render_template_string

from line_following.camera import PilotCamera
from line_following.detector import LineDetector
from line_following import config

# ═══════════════════════════════════════════════════════════════════
# Cấu hình
# ═══════════════════════════════════════════════════════════════════
HOST = "0.0.0.0"   # Cho phép truy cập từ máy khác
PORT = 5050         # Tránh trùng port 5000 của web_control
JPEG_QUALITY = 70

# ═══════════════════════════════════════════════════════════════════
# Biến chia sẻ giữa thread camera và các request
# ═══════════════════════════════════════════════════════════════════
_lock = threading.Lock()
_condition = threading.Condition(_lock)
_latest_frame = None       # BGR ndarray
_frame_number = 0
_running = False

# ═══════════════════════════════════════════════════════════════════
# Background thread: đọc camera liên tục
# ═══════════════════════════════════════════════════════════════════

def _camera_loop(cam: PilotCamera):
    """Đọc frame từ camera CSI và cập nhật vào biến dùng chung."""
    global _latest_frame, _frame_number, _running

    while _running:
        ok, frame = cam.read()
        if not ok or frame is None:
            time.sleep(0.01)
            continue

        with _condition:
            _latest_frame = frame
            _frame_number += 1
            _condition.notify_all()

    cam.release()

# ═══════════════════════════════════════════════════════════════════
# MJPEG generator
# ═══════════════════════════════════════════════════════════════════

def _generate_mjpeg(mode: str, detector: LineDetector):
    """Yield từng JPEG frame theo chuẩn MJPEG multipart."""
    last_num = -1

    while True:
        with _condition:
            _condition.wait_for(
                lambda: _frame_number != last_num or not _running,
                timeout=5.0,
            )
            if not _running and _frame_number == last_num:
                break
            frame = _latest_frame
            last_num = _frame_number

        if frame is None:
            continue

        # Chọn chế độ hiển thị
        if mode == "debug":
            output = _build_debug_overlay(frame, detector)
        elif mode == "mask":
            _, mask, _ = detector.get_line_error_moments(frame)
            output = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        else:
            output = frame

        ok, jpeg = cv2.imencode(
            ".jpg", output, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
        )
        if not ok:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" +
            jpeg.tobytes() +
            b"\r\n"
        )


def _build_debug_overlay(frame: np.ndarray, detector: LineDetector) -> np.ndarray:
    """Vẽ overlay ROI + scan line + error lên ảnh gốc (dành cho ROI phía dưới)."""
    error, mask, _ = detector.get_line_error_moments(frame)
    debug_img = frame.copy()
    h, w = debug_img.shape[:2]

    # 1. Vẽ khung ROI (Kéo từ roi_y xuống đáy màn hình)
    roi_y = int(h * config.ROI_START_ROW_PCT)
    cv2.rectangle(debug_img, (0, roi_y), (w - 1, h - 1), (0, 255, 255), 2)
    cv2.putText(debug_img, "ROI", (10, roi_y - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

    # 2. Đường tâm xe (Vẽ từ roi_y xuống đáy màn hình)
    cx = w // 2
    cv2.line(debug_img, (cx, roi_y), (cx, h), (255, 0, 0), 1)

    # 3. Kết quả dò vạch
    if error is not None:
        line_cx = int(cx + error * (w / 2.0))
        roi_h = h - roi_y
        scan_y = roi_y + int(roi_h * config.SCAN_LINE_Y_PCT)
        
        cv2.line(debug_img, (0, scan_y), (w, scan_y), (0, 255, 0), 2)
        cv2.circle(debug_img, (line_cx, scan_y), 10, (0, 0, 255), -1)
        cv2.line(debug_img, (cx, scan_y), (line_cx, scan_y), (0, 0, 255), 2)
        status = "Error: {:+.2f}".format(error)
        color = (0, 255, 0)
    else:
        direction, confidence = detector.check_sharp_turn(mask)
        if confidence > 0.25:
            turn = "LEFT" if direction < 0 else "RIGHT"
            status = "SHARP TURN: {}".format(turn)
            color = (0, 165, 255)
        else:
            status = "LINE LOST!"
            color = (0, 0, 255)

    cv2.rectangle(debug_img, (10, 10), (320, 50), (0, 0, 0), -1)
    cv2.putText(debug_img, status, (20, 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2)
    return debug_img

# ═══════════════════════════════════════════════════════════════════
# Flask app
# ═══════════════════════════════════════════════════════════════════

HTML_PAGE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Jetracer — Test Camera</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: #0f0f0f;
    color: #e0e0e0;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  header {
    width: 100%;
    padding: 18px 0;
    text-align: center;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-bottom: 2px solid #0f3460;
  }
  header h1 {
    font-size: 1.5rem;
    font-weight: 600;
    background: linear-gradient(90deg, #00d2ff, #3a7bd5);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: 1px;
  }
  .controls {
    display: flex;
    gap: 10px;
    margin: 20px 0;
  }
  .controls button {
    padding: 10px 22px;
    border: 1px solid #333;
    border-radius: 8px;
    background: #1e1e2e;
    color: #ccc;
    font-size: 0.9rem;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .controls button:hover {
    background: #2a2a3e;
    border-color: #3a7bd5;
    color: #fff;
  }
  .controls button.active {
    background: linear-gradient(135deg, #3a7bd5, #00d2ff);
    color: #fff;
    border-color: transparent;
    font-weight: 600;
    box-shadow: 0 0 12px rgba(0,210,255,0.3);
  }
  .stream-container {
    position: relative;
    border: 2px solid #222;
    border-radius: 12px;
    overflow: hidden;
    background: #000;
    box-shadow: 0 4px 30px rgba(0,0,0,0.6);
    max-width: 960px;
    width: 95%;
  }
  .stream-container img {
    display: block;
    width: 100%;
    height: auto;
  }
  .badge {
    position: absolute;
    top: 12px;
    right: 12px;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
  }
  .badge.live {
    background: rgba(220, 38, 38, 0.85);
    color: #fff;
    animation: pulse 1.5s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
  footer {
    margin-top: 24px;
    padding: 14px;
    font-size: 0.8rem;
    color: #555;
  }
</style>
</head>
<body>
  <header>
    <h1>🚗 Jetracer — Test Camera Stream</h1>
  </header>

  <div class="controls">
    <button id="btn-raw" class="active" onclick="switchMode('raw')">📷 Raw</button>
    <button id="btn-debug" onclick="switchMode('debug')">🔍 Debug</button>
    <button id="btn-mask" onclick="switchMode('mask')">🎭 Mask</button>
  </div>

  <div class="stream-container">
    <img id="stream" src="/stream?mode=raw" alt="Camera Stream">
    <span class="badge live">● LIVE</span>
  </div>

  <footer>Truy cập từ máy cùng mạng LAN &middot; Port {{ port }}</footer>

  <script>
    function switchMode(mode) {
      document.getElementById('stream').src = '/stream?mode=' + mode + '&t=' + Date.now();
      document.querySelectorAll('.controls button').forEach(b => b.classList.remove('active'));
      document.getElementById('btn-' + mode).classList.add('active');
    }
  </script>
</body>
</html>
"""

app = Flask(__name__)


@app.route("/")
def index():
    return render_template_string(HTML_PAGE, port=PORT)


@app.route("/stream")
def stream():
    from flask import request
    mode = request.args.get("mode", "raw").lower()

    detector = LineDetector(
        lower_color=config.LOWER_YELLOW,
        upper_color=config.UPPER_YELLOW,
    )

    return Response(
        _generate_mjpeg(mode, detector),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )


# ═══════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════

def main():
    global _running

    # 1. Mở camera
    cam = PilotCamera()
    _running = True

    # 2. Chạy thread đọc camera nền
    t = threading.Thread(target=_camera_loop, args=(cam,), daemon=True)
    t.start()

    print("=" * 50)
    print("  Camera stream đang phát tại:")
    print("  http://0.0.0.0:{}".format(PORT))
    print("  Mở trình duyệt trên máy khác cùng LAN để xem.")
    print("  Nhấn Ctrl+C để dừng.")
    print("=" * 50)

    try:
        # 3. Chạy Flask (blocking)
        app.run(host=HOST, port=PORT, threaded=True)
    except KeyboardInterrupt:
        pass
    finally:
        _running = False
        t.join(timeout=2.0)
        print("\nĐã dừng camera.")


if __name__ == "__main__":
    main()