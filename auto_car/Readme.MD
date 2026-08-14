# xe_tu_chay

Module chạy tự động (autopilot) cho JetRacer, dùng model behavior cloning
đã train (`ResNet-18 + steering_prev/throttle multi-input`).

## Cấu trúc

```
xe_tu_chay/
├── model.py                  # định nghĩa kiến trúc MultiInputSteeringNet (dùng chung train + inference)
├── convert_trt.py            # convert .pth -> TensorRT (.pth -> _trt.pth)
├── autopilot.py               # vòng lặp inference thật, điều khiển xe
├── road_following_model.pth   # <- copy model đã train từ server vào đây
├── road_following_trt.pth     # <- sinh ra sau khi chạy convert_trt.py
└── README.md
```

## Quy trình sử dụng

### 1. Copy model đã train

Từ server đã chạy `train.py`, copy file `road_following_model.pth` vào
đúng thư mục `xe_tu_chay/` trên Jetson Nano.

```bash
scp road_following_model.pth jet-ai-lab@jetailab-desktop:~/Jetracer/JetRacer/xe_tu_chay/
```

### 2. Convert sang TensorRT (chạy TRÊN Jetson Nano)

```bash
cd ~/Jetracer/JetRacer
python3 -m xe_tu_chay.convert_trt
```

Kết quả: file `xe_tu_chay/road_following_trt.pth` được tạo ra.

### 3. Chạy autopilot

**Trước tiên, đặt xe lên giá đỡ (bánh không chạm đất)** để kiểm tra servo
phản ứng hợp lý theo camera trước khi cho xe chạy thật.

```bash
python3 -m xe_tu_chay.autopilot
```

Mặc định `throttle = 0.2` (rất chậm) — chỉnh trong `autopilot.py`
(`DEFAULT_THROTTLE`) sau khi đã xác nhận an toàn.

Dừng bằng `Ctrl+C` — servo/esc sẽ tự động về vị trí trung lập (`stop()`
được gọi trong khối `finally`).

## Lưu ý quan trọng

- **Import `drivers.servo.Servo` và `drivers.esc.ESC`** trong `autopilot.py`
  giả định interface `set_position(-1..1)` và `set_throttle(-1..1)` đã có
  sẵn — chỉnh lại đường dẫn import nếu cấu trúc thực tế khác.
- `model.py` phải **khớp tuyệt đối** với kiến trúc dùng lúc train — nếu
  `train.py` bên ngoài `xe_tu_chay/` định nghĩa `MultiInputSteeringNet`
  riêng, nên sửa `train.py` để import từ `xe_tu_chay.model` thay vì định
  nghĩa lặp lại, tránh lệch kiến trúc giữa train và inference.
- `convert_trt.py` phải chạy **trên chính Jetson Nano**, không chạy trên
  server train — TensorRT tối ưu theo phần cứng cụ thể.