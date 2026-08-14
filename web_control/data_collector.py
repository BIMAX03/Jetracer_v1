"""Thu thập ảnh và nhãn điều khiển đồng bộ theo từng driving session."""

import csv
import os
import threading
import time
from datetime import datetime


CSV_FIELDS = (
    "frame_id",
    "filename",
    "steering",
    "steering_prev",
    "throttle",
    "timestamp",
    "session_id",
)


class DataCollector:
    """Background recorder 10 Hz, có thể chuyển tức thời sang 15 Hz."""

    def __init__(self, controller, frame_provider, camera_starter, dataset_dir,
                 normal_hz=10, curve_hz=15):
        self._controller = controller
        self._frame_provider = frame_provider
        self._camera_starter = camera_starter
        self._dataset_dir = os.path.abspath(dataset_dir)
        self._normal_hz = int(normal_hz)
        self._curve_hz = int(curve_hz)
        if self._normal_hz <= 0 or self._curve_hz <= 0:
            raise ValueError("Dataset sampling rates must be positive")

        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread = None
        self._recording = False
        self._curve_mode = False
        self._session_id = None
        self._session_dir = None
        self._sample_count = 0
        self._error = None

    def _new_session(self):
        base_id = datetime.now().strftime("sess_%Y%m%d_%H%M%S")
        session_id = base_id
        suffix = 2
        while os.path.exists(os.path.join(self._dataset_dir, session_id)):
            session_id = "{}_{}".format(base_id, suffix)
            suffix += 1
        return session_id, os.path.join(self._dataset_dir, session_id)

    def start(self):
        """Mở camera (nếu cần) và bắt đầu một session hoàn toàn mới."""
        with self._lock:
            if self._recording:
                return self.status()
            if not self._camera_starter():
                raise RuntimeError("Cannot open CSI camera; dataset recording was not started")

            session_id, session_dir = self._new_session()
            try:
                os.makedirs(session_dir)
                labels_path = os.path.join(session_dir, "labels.csv")
                with open(labels_path, "w", newline="") as labels_file:
                    csv.DictWriter(labels_file, fieldnames=CSV_FIELDS).writeheader()
            except (OSError, IOError, csv.Error) as exc:
                raise RuntimeError("Cannot create dataset session: {}".format(exc))

            self._session_id = session_id
            self._session_dir = session_dir
            self._sample_count = 0
            self._error = None
            self._curve_mode = False
            self._recording = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._record_loop,
                name="dataset-recorder",
            )
            self._thread.daemon = True
            self._thread.start()
        return self.status()

    def stop(self):
        """Dừng session hiện tại và đợi dòng CSV cuối được flush."""
        with self._lock:
            if not self._recording:
                return self.status()
            self._stop_event.set()
            thread = self._thread

        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=3.0)

        with self._lock:
            self._recording = False
            self._curve_mode = False
            self._thread = None
        return self.status()

    def set_curve_mode(self, enabled):
        with self._lock:
            if not self._recording:
                raise RuntimeError("Start dataset recording before enabling 15 Hz mode")
            self._curve_mode = bool(enabled)
        return self.status()

    def status(self):
        with self._lock:
            rate = self._curve_hz if self._curve_mode else self._normal_hz
            return {
                "recording": self._recording,
                "curve_mode": self._curve_mode,
                "rate_hz": rate,
                "sample_count": self._sample_count,
                "session_id": self._session_id,
                "session_dir": self._session_dir,
                "error": self._error,
            }

    def _record_loop(self):
        previous_steering = 0.0
        last_camera_frame = None
        deadline = time.monotonic()

        while not self._stop_event.is_set():
            delay = deadline - time.monotonic()
            if delay > 0 and self._stop_event.wait(delay):
                break

            try:
                frame = self._frame_provider(last_camera_frame, timeout=2.0)
            except Exception as exc:  # Giữ lỗi background thread trong API status.
                self._set_error("Camera read failed: {}".format(exc))
                self._stop_event.set()
                break
            if frame is None:
                self._set_error("Camera did not provide a new frame")
                deadline = time.monotonic() + 0.1
                continue

            camera_frame_number, jpeg, frame_timestamp = frame
            control = self._controller.get_status()
            try:
                self._write_sample(
                    jpeg=jpeg,
                    steering=control["steering"],
                    steering_prev=previous_steering,
                    throttle=control["throttle"],
                    timestamp=frame_timestamp if frame_timestamp is not None else time.time(),
                )
            except (OSError, IOError, csv.Error) as exc:
                self._set_error("Dataset write failed: {}".format(exc))
                self._stop_event.set()
                break

            previous_steering = control["steering"]
            last_camera_frame = camera_frame_number
            self._set_error(None)

            with self._lock:
                rate = self._curve_hz if self._curve_mode else self._normal_hz
            deadline += 1.0 / rate
            now = time.monotonic()
            if deadline < now:
                deadline = now

        with self._lock:
            self._recording = False
            self._curve_mode = False

    def _write_sample(self, jpeg, steering, steering_prev, throttle, timestamp):
        with self._lock:
            frame_id = self._sample_count + 1
            session_id = self._session_id
            session_dir = self._session_dir

        filename = "frame_{:06d}.jpg".format(frame_id)
        image_path = os.path.join(session_dir, filename)
        labels_path = os.path.join(session_dir, "labels.csv")

        # Ảnh được ghi xong trước khi CSV tham chiếu đến nó.
        with open(image_path, "wb") as image_file:
            image_file.write(jpeg)
            image_file.flush()

        try:
            with open(labels_path, "a", newline="") as labels_file:
                writer = csv.DictWriter(labels_file, fieldnames=CSV_FIELDS)
                writer.writerow({
                    "frame_id": frame_id,
                    "filename": filename,
                    "steering": "{:.6f}".format(steering),
                    "steering_prev": "{:.6f}".format(steering_prev),
                    "throttle": "{:.6f}".format(throttle),
                    "timestamp": "{:.6f}".format(timestamp),
                    "session_id": session_id,
                })
                labels_file.flush()
        except (OSError, IOError, csv.Error):
            # Không để lại ảnh mồ côi nếu dòng nhãn tương ứng ghi thất bại.
            try:
                os.remove(image_path)
            except OSError:
                pass
            raise

        with self._lock:
            self._sample_count = frame_id

    def _set_error(self, message):
        with self._lock:
            self._error = message
