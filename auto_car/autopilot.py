"""
Vong lap inference chay model TensorRT de tu dong lai xe.

Model can steering_prev lam input phu -- vi vay loop nay PHAI tu luu lai
gia tri steering vua xuat ra de dua vao lan du doan ke tiep (khac luc train,
khi steering_prev doc san tu CSV).

Usage:
    python3 -m xe_tu_chay.autopilot

CANH BAO AN TOAN: luon test voi throttle rat thap truoc, va dat xe tren gia
do (banh khong cham dat) o lan chay dau tien de kiem tra servo phan ung
hop ly truoc khi cho xe chay that.
"""

import os
import time
import cv2
import torch
import structlog

try:
    from torch2trt import TRTModule
except ImportError as exc:
    raise ImportError("torch2trt chua duoc cai, khong the load model TensorRT.") from exc

# --- Chinh lai import nay cho khop voi cau truc project thuc te ---
# Gia dinh: drivers/servo.py va drivers/esc.py da co san interface
# set_position(-1..1) va set_throttle(-1..1) nhu da mo ta truoc do.
from drivers.servo import Servo
from drivers.esc import ESC

logger = structlog.get_logger()

# Named constants
MODEL_TRT_PATH = os.path.join(os.path.dirname(__file__), "road_following_trt.pth")
IMAGE_SIZE = (224, 224)
DEFAULT_THROTTLE = 0.2          # BAT DAU RAT THAP, tang dan sau khi xac nhan an toan
STEERING_CLAMP = 1.0            # gioi han an toan, de phong model doan ngoai khoang
CAMERA_DEVICE_ID = 0
LOOP_HZ = 20                    # tan so inference loop -- khong can cao hon toc do camera/servo


def preprocess(frame) -> torch.Tensor:
    """Resize + convert BGR->RGB + normalize ve tensor, giong het transform luc train."""
    img = cv2.resize(frame, IMAGE_SIZE)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    tensor = torch.from_numpy(img).permute(2, 0, 1).float().div(255.0)
    tensor = tensor.unsqueeze(0).cuda()
    return tensor


class Autopilot:
    def __init__(self, model_path: str = MODEL_TRT_PATH, throttle: float = DEFAULT_THROTTLE):
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Khong tim thay {model_path}. Chay convert_trt.py truoc."
            )

        self.model_trt = TRTModule()
        self.model_trt.load_state_dict(torch.load(model_path))

        self.servo = Servo()
        self.esc = ESC()

        self.throttle = throttle
        self.prev_steering = 0.0
        self._running = False

        logger.info("autopilot_initialized", throttle=throttle, model=model_path)

    def _predict_steering(self, frame) -> float:
        image_tensor = preprocess(frame)
        extras_tensor = torch.tensor([[self.prev_steering, self.throttle]]).cuda()

        with torch.no_grad():
            output = self.model_trt(image_tensor, extras_tensor)

        steering = float(output.item())
        # Clamp an toan -- model co the doan gia tri ngoai [-1, 1] trong truong hop hiem
        steering = max(-STEERING_CLAMP, min(STEERING_CLAMP, steering))
        return steering

    def run(self, camera) -> None:
        """
        Vong lap chinh. `camera` can co method .read() tra ve frame (np.ndarray BGR).
        Truyen camera tu ben ngoai (khong tu khoi tao trong class nay) de de test
        va de tai su dung chung camera object voi web_control neu can.
        """
        self._running = True
        interval = 1.0 / LOOP_HZ

        logger.info("autopilot_started")
        try:
            while self._running:
                start = time.time()

                frame = camera.read()
                if frame is None:
                    logger.warning("empty_frame_skipped")
                    continue

                steering = self._predict_steering(frame)

                self.servo.set_position(steering)
                self.esc.set_throttle(self.throttle)

                self.prev_steering = steering

                elapsed = time.time() - start
                time.sleep(max(0.0, interval - elapsed))
        except KeyboardInterrupt:
            logger.info("autopilot_interrupted_by_user")
        finally:
            self.stop()

    def stop(self) -> None:
        """Dung an toan -- dua servo/esc ve trung lap truoc khi thoat."""
        self._running = False
        self.servo.set_position(0.0)
        self.esc.set_throttle(0.0)
        logger.info("autopilot_stopped")


if __name__ == "__main__":
    # Import camera o day de tranh phu thuoc cung khi chi muon dung class Autopilot rieng le
    import cv2 as _cv2

    class SimpleCamera:
        def __init__(self, device_id: int = CAMERA_DEVICE_ID):
            self.cap = _cv2.VideoCapture(device_id)

        def read(self):
            ok, frame = self.cap.read()
            return frame if ok else None

    camera = SimpleCamera()
    pilot = Autopilot(throttle=DEFAULT_THROTTLE)
    pilot.run(camera)