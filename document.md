# Tài Liệu Tính Năng Hệ Thống JetRacer (Jetracer_v1)

Tài liệu này tóm tắt ngắn gọn và đầy đủ hai tính năng cốt lõi của dự án JetRacer: **Điều khiển từ xa qua giao diện Web (Web Remote Control)** và **Hệ thống thu thập dữ liệu hành trình (Dataset Collection)**.

---

## 1. Tính Năng Điều Khiển Từ Xa (Remote Control)

Tính năng này cho phép điều khiển góc lái (steering) và tốc độ ga (throttle) của xe theo thời gian thực thông qua kết nối không dây (WiFi).

### Kiến Trúc & Luồng Điều Khiển
```text
Web UI (Điện thoại/PC) ---> HTTP API (Flask Server) ---> CarController ---> Car (High-level Interface) ---> PCA9685/I2C ---> Servo/ESC
```

### Các Đặc Điểm Kỹ Thuật Chính:
*   **Giao diện điều khiển**: Trình duyệt phía Client sử dụng các Joystick ảo hoặc tay cầm chơi game để tương tác và gửi dữ liệu dạng JSON.
*   **API tối ưu hóa băng thông**: Thay vì gửi các yêu cầu riêng lẻ làm nghẽn bus I2C (giao tiếp tuần tự), giao diện sử dụng endpoint gộp `POST /api/control` để cập nhật đồng thời cả hai giá trị `steering` và `throttle` trong cùng một critical section.
*   **Khởi động an toàn (Arming ESC)**: Khi Flask server khởi động, `CarController` sẽ tự động thực hiện tiến trình `arm()` trong 3 giây để cấp xung trung lập (`1500 µs`) liên tục cho ESC, giúp mở khóa (unlock) ESC trước khi xe có thể di chuyển.
*   **Giới hạn an toàn (Safety Clamp)**:
    *   Mọi giá trị ga và lái gửi từ Web đều được giới hạn tự động bằng tham số cấu hình `STEERING_LIMIT` và `THROTTLE_LIMIT` trong [config.py](file:///home/baymax/code/github/Jetracer_v1/config.py) trước khi ghi xuống thanh ghi PWM.

---

## 2. Tính Năng Thu Thập Dữ Liệu Tích Hợp (Data Collection)

Hệ thống ghi nhận hành trình lái xe thực tế để tạo tập dữ liệu (dataset) phục vụ huấn luyện mô hình học máy (Behavior Cloning). Tính năng này được tích hợp trực tiếp vào tầng `web_control` và chạy đồng bộ với camera.

### Cơ Chế Hoạt Động & Quy Trình Ghi:
*   **Quản lý phiên (Session)**: Mỗi lần bấm nút **BẮT ĐẦU GHI** trên Web, hệ thống tạo một thư mục mới có tên định dạng `datasets/sess_YYYYMMDD_HHMMSS/` để lưu trữ độc lập.
*   **Luồng ghi nền (Background Thread)**: Tiến trình `dataset-recorder` chạy trong một thread riêng biệt để không làm ảnh hưởng đến tốc độ phản hồi điều khiển của Flask server. Thread này sẽ:
    1.  Chờ nhận frame ảnh thô mới nhất từ camera CSI thông qua GStreamer.
    2.  Lưu ảnh camera dưới dạng JPEG (`frame_XXXXXX.jpg`) vào thư mục session.
    3.  Ghi tiếp nhận thông tin telemetry tương ứng vào file `labels.csv`. Nếu việc ghi file nhãn thất bại, tệp ảnh vừa lưu sẽ bị xóa để tránh dữ liệu mồ côi.
*   **Tần số lấy mẫu linh hoạt (Dynamic Rate)**:
    *   **Chế độ thông thường**: Tần số lấy mẫu là **10 Hz** (`DATASET_NORMAL_HZ`).
    *   **Chế độ cua**: Khi bật nút **CUA 15 HZ** (API `/api/recording/rate`), tần số lấy mẫu tự động tăng lên **15 Hz** để ghi lại nhiều khung hình chi tiết hơn trong các đoạn cua gắt.

### Cấu Trúc Dữ Liệu Thu Thập (Data Structure):

#### 1. Cấu trúc Thư mục Lưu trữ:
Dataset thu thập được lưu trữ tập trung tại thư mục `datasets/` ở gốc dự án với cấu trúc phân cấp theo từng phiên chạy (session):
```text
datasets/
└── sess_20260810_143000/              # Tên thư mục khớp với session_id
    ├── labels.csv                    # File chứa nhãn điều khiển và telemetry của session
    ├── frame_000001.jpg              # Ảnh camera ở khung hình thứ 1
    ├── frame_000002.jpg              # Ảnh camera ở khung hình thứ 2
    └── ...
```

#### 2. Cấu trúc File Nhãn `labels.csv`:
Tệp CSV lưu trữ nhãn và telemetry đồng bộ của từng khung hình. Cú pháp hàng tiêu đề (header row) và mô tả chi tiết từng cột dữ liệu như sau:

```text
frame_id,filename,steering,steering_prev,throttle,timestamp,session_id
```

| Tên Cột | Kiểu Dữ Liệu | Mô Tả Chi Tiết | Ví dụ |
| :--- | :--- | :--- | :--- |
| **`frame_id`** | Số nguyên (`int`) | Mã số định danh tự tăng dần bắt đầu từ `1` cho mỗi phiên ghi hình. | `1` |
| **`filename`** | Chuỗi ký tự (`str`) | Tên tệp ảnh tương ứng, được định dạng chuẩn hóa bằng 6 chữ số: `frame_{frame_id:06d}.jpg`. | `frame_000001.jpg` |
| **`steering`** | Số thực (`float`) | Giá trị góc lái tại thời điểm chụp, nằm trong khoảng `[-1.0, 1.0]` (âm là rẽ trái, dương là rẽ phải). Ghi định dạng 6 chữ số thập phân. | `-0.254100` |
| **`steering_prev`**| Số thực (`float`) | Góc lái của khung hình liền kề trước đó trong phiên chạy (khung hình đầu tiên mặc định là `0.000000`). | `-0.210000` |
| **`throttle`** | Số thực (`float`) | Giá trị tốc độ ga tại thời điểm chụp, nằm trong khoảng `[-1.0, 1.0]` (âm là lùi, dương là tiến). Ghi định dạng 6 chữ số thập phân. | `0.200000` |
| **`timestamp`** | Số thực (`float`) | Thời gian Epoch (Unix timestamp) khi camera chụp được frame hình, lấy độ chính xác micro giây từ camera driver. | `1786801800.123456` |
| **`session_id`** | Chuỗi ký tự (`str`) | Mã định danh duy nhất của phiên ghi dữ liệu (định dạng `sess_YYYYMMDD_HHMMSS`). | `sess_20260810_143000` |

> [!NOTE]
> **Vai trò của `steering_prev` (Góc lái trước đó)**: 
> Giá trị góc lái ở frame liền kề trước đó trong cùng session được ghi nhận trực tiếp vào nhãn. Khi huấn luyện mô hình mạng hồi quy đa đầu vào (Multi-Input Steering Net), `steering_prev` giúp mô hình có thêm thông tin ngữ cảnh về quỹ đạo chuyển động, từ đó đưa ra quyết định lái tiếp theo mượt mà hơn và hạn chế hiện tượng rung lắc (oscillation) của bánh lái trên sa bàn.

