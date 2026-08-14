"""MJPEG stream dùng chung cho camera CSI của Jetson."""

import threading
import time

from flask import Blueprint, Response, jsonify, stream_with_context

try:
    import cv2
except ImportError:
    cv2 = None


camera_bp = Blueprint("camera", __name__, url_prefix="/camera")

# Một producer đọc Argus; mọi trình duyệt cùng nhận frame mới nhất từ producer này.
_start_lock = threading.Lock()
_frame_condition = threading.Condition()
_latest_jpeg = None
_latest_timestamp = None
_frame_number = 0
_camera_running = False
_capture = None
_camera_worker = None
_stop_event = threading.Event()


def gstreamer_pipeline():
    """Pipeline CSI tối ưu cho stream web độ trễ thấp."""
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


def _open_camera():
    capture = cv2.VideoCapture(gstreamer_pipeline(), cv2.CAP_GSTREAMER)
    if not capture.isOpened():
        capture.release()
        return None
    return capture


def _capture_frames(capture):
    """Đọc và encode camera trong một background thread duy nhất."""
    global _latest_jpeg, _latest_timestamp, _frame_number
    global _camera_running, _capture, _camera_worker

    try:
        while not _stop_event.is_set():
            ok, frame = capture.read()
            if not ok or frame is None:
                break
            frame_timestamp = time.time()

            encoded, jpeg = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), 70],
            )
            if not encoded:
                continue

            with _frame_condition:
                _latest_jpeg = jpeg.tobytes()
                # Epoch timestamp của frame, dùng để kiểm tra đồng bộ dataset.
                _latest_timestamp = frame_timestamp
                _frame_number += 1
                _frame_condition.notify_all()
    finally:
        capture.release()
        with _frame_condition:
            _camera_running = False
            _capture = None
            _camera_worker = None
            _frame_condition.notify_all()


def _ensure_camera_started():
    """Mở Argus một lần, kể cả khi nhiều client kết nối đồng thời."""
    global _latest_jpeg, _camera_running, _capture, _camera_worker

    with _start_lock:
        if _camera_running:
            return True

        capture = _open_camera()
        if capture is None:
            return False

        with _frame_condition:
            _latest_jpeg = None
            _camera_running = True
            _capture = capture
            _stop_event.clear()

        worker = threading.Thread(target=_capture_frames, args=(capture,))
        worker.daemon = True
        _camera_worker = worker
        worker.start()
        return True


def ensure_camera_started():
    """Public wrapper để bộ thu thập có thể chạy dù chưa mở MJPEG stream."""
    if cv2 is None:
        return False
    return _ensure_camera_started()


def wait_for_frame(after_frame_number=None, timeout=2.0):
    """Chờ một camera frame mới và trả ``(number, jpeg, timestamp)``.

    ``after_frame_number`` giúp recorder không bao giờ ghi lặp lại cùng một
    frame khi producer camera bị chậm.
    """
    with _frame_condition:
        ready = _frame_condition.wait_for(
            lambda: (
                _latest_jpeg is not None
                and (after_frame_number is None or _frame_number != after_frame_number)
            ) or not _camera_running,
            timeout=timeout,
        )
        if not ready or _latest_jpeg is None:
            return None
        if after_frame_number is not None and _frame_number == after_frame_number:
            return None
        return _frame_number, _latest_jpeg, _latest_timestamp


def shutdown_camera():
    """Dừng producer và nhả Argus sạch trước khi tiến trình thoát."""
    global _camera_running, _capture, _camera_worker

    _stop_event.set()
    with _frame_condition:
        _camera_running = False
        worker = _camera_worker
        capture = _capture
        _frame_condition.notify_all()

    # Bình thường capture.read() trả về trong một frame (~33 ms).
    if worker is not None and worker.is_alive():
        worker.join(timeout=2.0)

    # Nếu GStreamer đang kẹt, release từ thread chính để đánh thức read().
    if worker is not None and worker.is_alive() and capture is not None:
        capture.release()
        worker.join(timeout=2.0)

    with _frame_condition:
        _capture = None
        _camera_worker = None
        _frame_condition.notify_all()


def _generate_frames():
    """Mỗi client chờ frame mới nhưng không tự mở thêm camera."""
    last_frame_number = -1

    while True:
        with _frame_condition:
            _frame_condition.wait_for(
                lambda: _frame_number != last_frame_number or not _camera_running,
                timeout=5.0,
            )

            if _frame_number == last_frame_number:
                if not _camera_running:
                    break
                continue

            jpeg = _latest_jpeg
            last_frame_number = _frame_number

        if jpeg is None:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" +
            jpeg +
            b"\r\n"
        )


@camera_bp.route("/stream")
def stream():
    """Phát cùng một camera tới nhiều thẻ img dưới dạng MJPEG."""
    if cv2 is None:
        return jsonify({
            "status": "error",
            "message": "OpenCV (cv2) is not installed",
        }), 503

    if not _ensure_camera_started():
        return jsonify({
            "status": "error",
            "message": "Cannot open CSI camera",
        }), 503

    response = Response(
        stream_with_context(_generate_frames()),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response
