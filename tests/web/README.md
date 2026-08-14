# JetRacer Camera Setup Web

Ứng dụng web độc lập để chỉnh góc camera CSI. Chương trình không import `Car`,
`Servo`, `ESC` hay PCA9685, vì vậy không phát lệnh làm xe di chuyển.

## Chạy

Từ thư mục gốc của dự án trên Jetson:

```bash
cd /home/jet-ai-lab/Jetracer/JetRacer
python3 -m tests.web.camera_setup
```

Mặc định ứng dụng lấy mode cảm biến `1920x1080@30 FPS` rồi dùng
`nvvidconv` hạ xuống `960x540` để truyền lên web. Không dùng
`1280x720@30` vì cảm biến này chỉ công bố mode `1280x720` ở 60/120 FPS.

Mở trên điện thoại hoặc máy tính:

```text
http://<IP-Jetson>:5002/
```

Ví dụ khi Jetson dùng hotspot của điện thoại:

```text
http://172.20.10.2:5002/
```

Có thể đổi cổng hoặc xoay ảnh:

```bash
python3 -m tests.web.camera_setup --port 5002 --flip-method 0
```

Xem tất cả tùy chọn:

```bash
python3 -m tests.web.camera_setup --help
```

## Tránh lỗi Argus

Camera CSI chỉ nên do một tiến trình `nvarguscamerasrc` sử dụng. Trước khi mở
trang này, hãy dừng web/camera khác:

```bash
sudo systemctl stop jetracer
pkill -f test_camera.py
```

Nếu terminal vẫn báo `Failed to create CaptureSession`, dừng web bằng `Ctrl+C`,
khởi động lại Argus rồi chạy web lần nữa:

```bash
sudo systemctl restart nvargus-daemon
python3 -m tests.web.camera_setup
```

Sau khi đóng ứng dụng bằng `Ctrl+C`, CaptureSession sẽ được giải phóng.

## Đặt mốc để chỉnh góc

Đo từ đầu xe và dán băng dính ngang sàn tại `10`, `30`, `50`, `100` và
`150 cm`. Chỉnh camera sao cho:

- mốc `10 cm` xuất hiện gần đáy ảnh;
- mốc `50 cm` nằm gần giữa ảnh;
- vẫn nhìn rõ mốc `100–150 cm` ở phần trên;
- hai bên hành lang đều nằm trong khung hình.

Các đường khoảng cách trên giao diện chỉ là đường tham chiếu bố cục, không phải
phép đo khoảng cách từ camera. Muốn biến pixel thành khoảng cách thật cần hiệu
chỉnh camera và homography ở bước tiếp theo.
