"""
Convert model PyTorch (.pth) sang TensorRT de toi uu toc do tren Jetson Nano.

QUAN TRONG: script nay phai chay TREN Jetson Nano, khong phai tren server
da dung de train -- vi TensorRT toi uu theo dung phan cung se chay inference,
convert tren may khac se khong dung duoc tren Nano.

Truoc khi chay: copy road_following_model.pth tu server train sang thu muc
xe_tu_chay/ tren Jetson Nano.

Usage:
    python3 -m xe_tu_chay.convert_trt
"""

import os
import torch
import structlog

try:
    from torch2trt import torch2trt
except ImportError as exc:
    raise ImportError(
        "torch2trt chua duoc cai. Cai theo huong dan: "
        "https://github.com/NVIDIA-AI-IOT/torch2trt"
    ) from exc

from xe_tu_chay.model import MultiInputSteeringNet

logger = structlog.get_logger()

# Named constants
INPUT_MODEL_PATH = os.path.join(os.path.dirname(__file__), "road_following_model.pth")
OUTPUT_TRT_PATH = os.path.join(os.path.dirname(__file__), "road_following_trt.pth")
IMAGE_SIZE = (224, 224)
USE_FP16 = True  # fp16 nhanh hon dang ke tren Jetson Nano, sai so khong dang ke voi bai toan nay


def convert(input_path: str = INPUT_MODEL_PATH, output_path: str = OUTPUT_TRT_PATH) -> None:
    if not os.path.exists(input_path):
        raise FileNotFoundError(
            f"Khong tim thay {input_path}. "
            f"Hay copy model da train tu server vao xe_tu_chay/ truoc."
        )

    logger.info("loading_model", path=input_path)
    model = MultiInputSteeringNet(pretrained=False)
    model.load_state_dict(torch.load(input_path, map_location="cuda"))
    model = model.eval().cuda()

    # torch2trt can input mau dung shape that -- 2 input vi model nhan (image, extras)
    x_image = torch.ones((1, 3, *IMAGE_SIZE)).cuda()
    x_extras = torch.ones((1, 2)).cuda()

    logger.info("converting_to_tensorrt", fp16=USE_FP16)
    model_trt = torch2trt(model, [x_image, x_extras], fp16_mode=USE_FP16)

    torch.save(model_trt.state_dict(), output_path)
    logger.info("conversion_done", output=output_path)


if __name__ == "__main__":
    convert()