"""Web căn chỉnh góc camera CSI của JetRacer.

Chạy từ thư mục gốc dự án:

    python3 -m tests.web.camera_setup

Ứng dụng này chỉ mở camera. Nó không import hoặc điều khiển Servo/ESC.
"""

from __future__ import print_function

import argparse
import atexit
import threading
import time

from flask import Flask, Response, jsonify, render_template

try:
    import cv2
except ImportError:
    cv2 = None


def gstreamer_pipeline(
    sensor_id=0,
    capture_width=1920,
    capture_height=1080,
    display_width=960,
    display_height=540,
    framerate=30,
    flip_method=0,
):
    """Tạo pipeline CSI sử dụng nvarguscamerasrc trên Jetson."""
    source = "nvarguscamerasrc"
    if sensor_id:
        source += " sensor-id={}".format(sensor_id)

    return (
        "{source} ! "
        "video/x-raw(memory:NVMM), "
        "width=(int){capture_width}, height=(int){capture_height}, "
        "format=(string)NV12, framerate=(fraction){framerate}/1 ! "
        "nvvidconv flip-method={flip_method} ! "
        "video/x-raw, width=(int){display_width}, height=(int){display_height}, "
        "format=(string)BGRx ! "
        "videoconvert ! video/x-raw, format=(string)BGR ! "
        "appsink"
    ).format(
        source=source,
        capture_width=capture_width,
        capture_height=capture_height,
        display_width=display_width,
        display_height=display_height,
        framerate=framerate,
        flip_method=flip_method,
    )


class CameraStream(object):
    """Đọc camera một lần và chia sẻ frame mới nhất cho mọi trình duyệt."""

    def __init__(self, pipeline, jpeg_quality=82):
        self.pipeline = pipeline
        self.jpeg_quality = int(jpeg_quality)
        self._condition = threading.Condition()
        self._capture = None
        self._thread = None
        self._running = False
        self._jpeg = None
        self._sequence = 0
        self._frame_time = 0.0
        self._fps = 0.0
        self._width = 0
        self._height = 0
        self._error = ""
        self._reconnects = 0

    def start(self):
        """Khởi chạy luồng camera nếu nó chưa chạy."""
        with self._condition:
            if self._running:
                return
            self._running = True
            self._error = "Đang mở camera..."
            self._thread = threading.Thread(
                target=self._capture_loop,
                name="camera-setup-capture",
            )
            self._thread.daemon = True
            self._thread.start()

    def stop(self):
        """Dừng luồng và giải phóng CaptureSession của Argus."""
        with self._condition:
            self._running = False
            self._condition.notify_all()

        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

        capture = self._capture
        self._capture = None
        if capture is not None:
            capture.release()

    def _capture_loop(self):
        if cv2 is None:
            with self._condition:
                self._error = (
                    "Thiếu OpenCV (cv2). Hãy chạy ứng dụng bằng Python trên "
                    "Jetson có cài OpenCV GStreamer."
                )
                self._running = False
                self._condition.notify_all()
            return

        previous_time = None
        smoothed_fps = 0.0

        while True:
            with self._condition:
                if not self._running:
                    break

            capture = cv2.VideoCapture(self.pipeline, cv2.CAP_GSTREAMER)
            self._capture = capture
            if not capture.isOpened():
                capture.release()
                self._capture = None
                with self._condition:
                    self._reconnects += 1
                    self._error = (
                        "Không mở được camera; đang tự thử lại.\n"
                        "Hãy dừng dịch vụ hoặc Python khác đang giữ camera."
                    )
                    self._condition.notify_all()
                    self._condition.wait(timeout=1.5)
                continue

            with self._condition:
                self._error = ""

            while True:
                with self._condition:
                    if not self._running:
                        break

                ok, frame = capture.read()
                now = time.monotonic()

                if not ok or frame is None:
                    with self._condition:
                        self._reconnects += 1
                        self._error = (
                            "Camera không trả về frame; đang tự kết nối lại.\n"
                            "Nguyên nhân thường là camera đang bị tiến trình khác giữ."
                        )
                        self._condition.notify_all()
                    break

                encode_ok, encoded = cv2.imencode(
                    ".jpg",
                    frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality],
                )
                if not encode_ok:
                    continue

                if previous_time is not None:
                    delta = max(now - previous_time, 0.000001)
                    instant_fps = 1.0 / delta
                    if smoothed_fps == 0.0:
                        smoothed_fps = instant_fps
                    else:
                        smoothed_fps = (smoothed_fps * 0.9) + (instant_fps * 0.1)
                previous_time = now

                height, width = frame.shape[:2]
                with self._condition:
                    self._jpeg = encoded.tobytes()
                    self._sequence += 1
                    self._frame_time = now
                    self._fps = smoothed_fps
                    self._width = width
                    self._height = height
                    self._error = ""
                    self._condition.notify_all()

            capture.release()
            self._capture = None

            with self._condition:
                if self._running:
                    self._condition.wait(timeout=1.0)

        self._capture = None

    def wait_for_jpeg(self, previous_sequence, timeout=2.0):
        """Đợi frame mới; trả về (sequence, jpeg) hoặc frame hiện tại."""
        with self._condition:
            self._condition.wait_for(
                lambda: (
                    self._sequence != previous_sequence
                    or not self._running
                ),
                timeout=timeout,
            )
            return self._sequence, self._jpeg

    def latest_jpeg(self):
        with self._condition:
            return self._jpeg

    def status(self):
        with self._condition:
            age = None
            if self._frame_time:
                age = max(0.0, time.monotonic() - self._frame_time)
            return {
                "running": self._running,
                "ready": self._jpeg is not None and age is not None and age < 2.0,
                "error": self._error,
                "fps": round(self._fps, 1),
                "width": self._width,
                "height": self._height,
                "frames": self._sequence,
                "age_seconds": None if age is None else round(age, 2),
                "reconnects": self._reconnects,
            }


def create_app(camera):
    app = Flask(__name__)

    @app.route("/")
    def index():
        camera.start()
        return render_template("index.html")

    @app.route("/stream.mjpg")
    def stream():
        camera.start()

        def generate():
            sequence = -1
            while True:
                new_sequence, jpeg = camera.wait_for_jpeg(sequence)
                if new_sequence == sequence:
                    continue
                sequence = new_sequence
                if jpeg is None:
                    if not camera.status()["running"]:
                        break
                    continue
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Cache-Control: no-store\r\n\r\n"
                    + jpeg
                    + b"\r\n"
                )

        return Response(
            generate(),
            mimetype="multipart/x-mixed-replace; boundary=frame",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )

    @app.route("/snapshot.jpg")
    def snapshot():
        camera.start()
        jpeg = camera.latest_jpeg()
        if jpeg is None:
            return Response("Camera chưa có hình ảnh.", status=503)
        return Response(
            jpeg,
            mimetype="image/jpeg",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )

    @app.route("/api/status")
    def status():
        camera.start()
        return jsonify(camera.status())

    return app


def parse_args():
    parser = argparse.ArgumentParser(
        description="Web căn chỉnh camera CSI cho JetRacer"
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5002)
    parser.add_argument("--sensor-id", type=int, default=0)
    parser.add_argument(
        "--capture-width",
        type=int,
        default=1920,
        help="Chiều rộng mode cảm biến; mặc định dùng mode 1920x1080@30",
    )
    parser.add_argument(
        "--capture-height",
        type=int,
        default=1080,
        help="Chiều cao mode cảm biến; mặc định dùng mode 1920x1080@30",
    )
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--flip-method", type=int, default=0)
    parser.add_argument("--jpeg-quality", type=int, default=82)
    return parser.parse_args()


def main():
    args = parse_args()
    pipeline = gstreamer_pipeline(
        sensor_id=args.sensor_id,
        capture_width=args.capture_width,
        capture_height=args.capture_height,
        display_width=args.width,
        display_height=args.height,
        framerate=args.fps,
        flip_method=args.flip_method,
    )
    camera = CameraStream(pipeline, jpeg_quality=args.jpeg_quality)
    app = create_app(camera)
    atexit.register(camera.stop)
    camera.start()

    print("=" * 58)
    print("  JetRacer Camera Setup")
    print("  Web: http://<IP-Jetson>:{}/".format(args.port))
    print("  Chỉ mở camera - KHÔNG điều khiển servo hoặc ESC")
    print("=" * 58)

    try:
        app.run(
            host=args.host,
            port=args.port,
            debug=False,
            threaded=True,
            use_reloader=False,
        )
    finally:
        camera.stop()


if __name__ == "__main__":
    main()
