# JetRacer Web Remote Control

Ứng dụng điều khiển JetRacer từ điện thoại hoặc máy tính qua trình duyệt. Giao diện hỗ trợ camera CSI trực tiếp, cần ga dọc, vô lăng đa điểm và phanh khẩn cấp.

## Tính năng

- Điều khiển servo lái và ESC qua PCA9685.
- Cần ga dọc hai chiều: tiến, dừng và lùi.
- Điều khiển ga và vô lăng đồng thời bằng hai ngón tay.
- Ba mức giới hạn tốc độ.
- Camera CSI MJPEG dùng chung cho nhiều thiết bị.
- Emergency Brake đưa ga và vô lăng về neutral.
- Tự chạy khi Jetson khởi động bằng systemd.
- Chế độ điều khiển độc lập bằng USB/Bluetooth gamepad.
- Chế độ tự hành bám vạch bằng OpenCV và PID.

## Phần cứng

- NVIDIA Jetson Nano hoặc Jetson tương thích.
- PCA9685 tại địa chỉ I2C `0x40`, bus `1`.
- Servo lái trên PCA9685 channel `0`.
- ESC trên PCA9685 channel `1`.
- Camera CSI tương thích `nvarguscamerasrc`.
- Nguồn riêng phù hợp cho servo và động cơ; Jetson, PCA9685 và nguồn servo phải nối chung GND.

## Cấu trúc dự án

```text
JetRacer/
├── main.py                 # Điểm khởi chạy web server
├── config.py               # Kênh, giới hạn và hiệu chỉnh phần cứng
├── car.py                  # API điều khiển xe cấp cao
├── auto/                   # Camera, nhận diện vạch, PID và vòng tự hành
├── drivers/                # I2C, PCA9685, servo và ESC
├── web/
│   ├── api.py              # REST API ga/lái/dừng
│   ├── camera.py           # Camera CSI MJPEG broadcast
│   ├── controller.py       # Cầu nối web và phần cứng
│   ├── templates/          # Giao diện HTML
│   └── static/             # CSS và JavaScript
├── tests/                  # Script kiểm tra phần cứng
└── deploy/                 # Dịch vụ systemd và script cài đặt
```

## Cài đặt

Ứng dụng cần Python 3 cùng các package Flask, OpenCV có GStreamer và SMBus. Trên Jetson, OpenCV thường được cung cấp cùng JetPack.

```bash
sudo apt update
sudo apt install python3-flask python3-smbus python3-opencv
```

Kiểm tra PCA9685:

```bash
sudo i2cdetect -y -r 1
```

Kết quả cần hiển thị thiết bị tại địa chỉ `40`.

## Chạy thủ công

```bash
cd ~/Jetracer/JetRacer
python3 main.py
```

Trên thiết bị cùng mạng Wi-Fi, mở:

```text
http://<IP-CUA-JETSON>:5000
```

Ví dụ:

```text
http://192.168.106.193:5000
```

Không chạy `tests.test_camera` đồng thời với web server vì Argus chỉ nên được một producer camera sử dụng.

## Tự khởi động cùng Jetson

File service mặc định sử dụng user `jet-ai-lab` và thư mục `/home/jet-ai-lab/Jetracer/JetRacer`. Nếu cài ở vị trí khác, chỉnh `deploy/jetracer.service` trước khi cài.

```bash
cd ~/Jetracer/JetRacer
chmod +x deploy/install_service.sh
./deploy/install_service.sh
```

Các lệnh quản lý:

```bash
sudo systemctl status jetracer --no-pager
sudo systemctl restart jetracer
sudo journalctl -u jetracer -f
```

Gỡ dịch vụ:

```bash
./deploy/uninstall_service.sh
```

## Điều khiển bằng gamepad

Gamepad mode chạy độc lập với web mode và dùng mapping:

```text
Left stick Y   → ga tiến/lùi
Right stick X  → lái trái/phải
START          → arm/disarm controller
A / Cross      → dừng khẩn cấp và disarm
```

Cài driver và service một lần:

```bash
cd ~/Jetracer/JetRacer
chmod +x deploy/install_gamepad_service.sh deploy/set_control_mode.sh
./deploy/install_gamepad_service.sh
```

Nếu dùng USB, cắm controller rồi kiểm tra:

```bash
python3 gamepad_main.py --list
```

Nếu dùng Bluetooth, pair và trust controller bằng `bluetoothctl`, sau đó chuyển mode:

```bash
./deploy/set_control_mode.sh gamepad
sudo journalctl -u jetracer-gamepad -f
```

Khi controller kết nối, nhấn `START` để arm. Xe luôn dừng khi mới kết nối, khi nhấn A, khi disarm hoặc khi controller mất kết nối.

Quay lại giao diện web:

```bash
./deploy/set_control_mode.sh web
```

Hai service có cấu hình xung đột và không chạy đồng thời để tránh tranh chấp PCA9685/I2C.

## Tự hành bám vạch

Chế độ tự hành tự chọn detector vạch vàng/đen, xử lý vùng nhìn xa 260 pixel,
lấy tâm near/far rồi đưa sai số chuẩn hóa qua PID. Góc vuông được nhận dạng từ
hình chữ L và xử lý bằng state machine giảm tốc
`FOLLOW -> APPROACH -> TURN -> FOLLOW`. Trước khi
chạy phải tắt web và gamepad để giải phóng camera cùng phần cứng điều khiển:

```bash
sudo systemctl stop jetracer jetracer-gamepad
python3 -m auto.main --dry-run
```

Khi telemetry nhận đúng vạch, nâng bánh xe lên khỏi mặt đất và thử ở ga 20%:

```bash
python3 -m auto.main --speed 0.20
```

Trong khi auto chạy, theo dõi camera đã đánh dấu vạch và toàn bộ telemetry tại:

```text
http://<IP-CUA-JETSON>:5001
```

Dashboard có nút dừng khẩn cấp và không mở thêm camera CSI; frame được chia sẻ
trực tiếp từ vòng xử lý tự hành.

Xe tự đưa ga về neutral khi mất vạch, camera lỗi, nhấn `Ctrl+C` hoặc process
nhận SIGTERM. Xem toàn bộ cách hiệu chỉnh threshold, PID và chiều lái tại
[`auto/README.md`](auto/README.md).

## Hiệu chỉnh

Các thông số nằm trong `config.py`:

- `STEERING_GAIN = -1.0`: đảo chiều servo lái.
- `STEERING_OFFSET`: chỉnh vị trí lái giữa.
- `STEERING_MIN_PULSE_US` và `STEERING_MAX_PULSE_US`: giới hạn servo.
- `THROTTLE_LIMIT`: giới hạn ga tối đa.
- `WEB_HOST = "0.0.0.0"`: cho phép thiết bị trong mạng truy cập.

Sau khi đổi cấu hình:

```bash
sudo systemctl restart jetracer
```

## API

```text
POST /api/steering  {"value": -1.0 .. 1.0}
POST /api/throttle  {"value": -1.0 .. 1.0}
POST /api/stop
GET  /camera/stream
```

## Lưu ý an toàn

- Nâng bánh xe khỏi mặt đất khi thử ESC lần đầu.
- Luôn bảo đảm Emergency Brake có thể thao tác được.
- Không cấp nguồn servo trực tiếp từ chân nguồn yếu của Jetson.
- Web API hiện dành cho mạng LAN tin cậy và chưa có xác thực người dùng.
- Các file trong `tests/` là kiểm tra phần cứng và có thể làm servo hoặc động cơ chuyển động.
