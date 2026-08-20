# JetRacer Autonomous Driving Project (Jetracer_v1)

Dự án điều khiển xe tự hành JetRacer sử dụng nền tảng NVIDIA Jetson Nano. Dự án tích hợp các trình điều khiển phần cứng cấp thấp (I2C, PWM PCA9685, Servo, ESC, cảm biến INA219), hệ thống điều khiển Web Remote Control thời gian thực để thu thập dữ liệu hành trình (Dataset Collection), và module chạy tự động (Autopilot) dựa trên mô hình Deep Learning (Behavior Cloning) được tối ưu hóa bằng TensorRT.

---

## 1. Cấu trúc mã nguồn

Dưới đây là sơ đồ cấu trúc của dự án. Nhấp vào các liên kết file để xem chi tiết mã nguồn:

- [main.py](file:///home/baymax/code/github/Jetracer_v1/main.py): Entry point khởi động Flask Web Server phục vụ giao diện điều khiển và thu thập dữ liệu.
- [config.py](file:///home/baymax/code/github/Jetracer_v1/config.py): Tệp cấu hình tập trung chứa toàn bộ tham số phần cứng, hiệu chuẩn xung PWM, giới hạn an toàn và thông số Flask server.
- [car.py](file:///home/baymax/code/github/Jetracer_v1/car.py): Controller cấp cao đóng vai trò giao diện điều khiển duy nhất của xe, gộp Servo lái và ESC ga.
- **[drivers/](file:///home/baymax/code/github/Jetracer_v1/drivers)**: Chứa các trình điều khiển phần cứng cấp thấp qua giao tiếp I2C.
  - [i2c.py](file:///home/baymax/code/github/Jetracer_v1/drivers/i2c.py): Quản lý kết nối I2C bus (`/dev/i2c-1`), hỗ trợ ghi/đọc block dữ liệu và tự động retry khi gặp lỗi.
  - [pca9685.py](file:///home/baymax/code/github/Jetracer_v1/drivers/pca9685.py): Trình điều khiển chip PWM PCA9685 (16 kênh, tần số chung 50 Hz).
  - [servo.py](file:///home/baymax/code/github/Jetracer_v1/drivers/servo.py): Điều khiển Servo lái (Kênh 0) với các cơ chế hiệu chuẩn xung lệch tâm và giới hạn tốc độ đổi góc lái.
  - [esc.py](file:///home/baymax/code/github/Jetracer_v1/drivers/esc.py): Điều khiển động cơ ga thông qua ESC (Kênh 1) hỗ trợ bù vùng chết (deadband) tiến/lùi và kích hoạt ESC (arm).
  - [ina219.py](file:///home/baymax/code/github/Jetracer_v1/drivers/ina219.py): Đọc thông số điện áp, dòng điện và công suất tiêu thụ từ cảm biến INA219.
- **[web_control/](file:///home/baymax/code/github/Jetracer_v1/web_control)**: Tầng web phục vụ điều khiển thủ công và thu thập tập dữ liệu.
  - [app.py](file:///home/baymax/code/github/Jetracer_v1/web_control/app.py): Khởi tạo Flask Application Factory, inject controller và đăng ký các blueprint.
  - [routes.py](file:///home/baymax/code/github/Jetracer_v1/web_control/routes.py): Định tuyến phục vụ giao diện trang chủ điều khiển HTML.
  - [api.py](file:///home/baymax/code/github/Jetracer_v1/web_control/api.py): REST API điều khiển xe (`/api/control`, `/api/stop`, v.v.) và quản lý phiên ghi dữ liệu (`/api/recording/*`).
  - [camera.py](file:///home/baymax/code/github/Jetracer_v1/web_control/camera.py): Pipeline GStreamer tối ưu độ trễ thấp để truyền hình ảnh MJPEG từ camera CSI.
  - [data_collector.py](file:///home/baymax/code/github/Jetracer_v1/web_control/data_collector.py): Tiến trình nền thu thập ảnh camera đồng bộ với nhãn điều khiển (`steering`, `throttle`) ghi ra file CSV.
- **[auto_car/](file:///home/baymax/code/github/Jetracer_v1/auto_car)**: Hệ thống lái tự động (Autopilot).
  - [convert_trt.py](file:///home/baymax/code/github/Jetracer_v1/auto_car/convert_trt.py): Convert model PyTorch (`.pth`) sang dạng TensorRT (`_trt.pth`) tối ưu hóa trực tiếp trên phần cứng Jetson Nano.
  - [autopilot.py](file:///home/baymax/code/github/Jetracer_v1/auto_car/autopilot.py): Vòng lặp inference tự động đọc camera CSI, dự đoán góc lái qua model TensorRT và gửi lệnh tới Servo/ESC.
- **[tests/](file:///home/baymax/code/github/Jetracer_v1/tests)**: Thư mục chứa các kịch bản kiểm thử độc lập và kiểm thử phần cứng.

---

## 2. Input - Output của bài toán

Dự án JetRacer giải quyết các bài toán với luồng dữ liệu vào/ra rõ ràng như sau:

### A. Bài toán Thu thập dữ liệu (Data Collection)
*   **Input**:
    *   Lệnh điều khiển lái và ga từ người dùng thông qua giao diện Web (hoặc Gamepad USB/Bluetooth).
    *   Luồng video thời gian thực từ camera CSI góc rộng (được cấu hình qua GStreamer).
*   **Output**: 
    *   Thư mục session được tạo trong `datasets/` (ví dụ `sess_20260810_143000/`).
    *   Chuỗi ảnh chụp hành trình dạng JPEG: `frame_000001.jpg`, `frame_000002.jpg`,...
    *   File nhãn `labels.csv` lưu các thông tin đồng bộ:
        ```csv
        frame_id,filename,steering,steering_prev,throttle,timestamp,session_id
        ```
        *(Trong đó `steering_prev` là góc lái ở bước liền trước, được sử dụng làm thông tin bổ trợ quan trọng khi huấn luyện mô hình bám làn).*

### B. Bài toán Huấn luyện mô hình (Behavior Cloning)
*   **Input**:
    *   Ảnh camera đầu vào được xử lý về kích thước `224x224` (RGB).
    *   Dữ liệu telemetry phụ trợ: `[steering_prev, throttle]`.
*   **Output**:
    *   Mô hình `MultiInputSteeringNet` (kết hợp mạng ResNet-18 trích xuất đặc trưng ảnh và một MLP xử lý telemetry đầu vào phụ).
    *   Dự đoán góc lái tối ưu `steering` (giá trị thực nằm trong khoảng `[-1.0, 1.0]`).
    *   Tệp trọng số đã huấn luyện: `road_following_model.pth`.

### C. Bài toán Lái tự động (Autopilot Inference)
*   **Input**:
    *   Hình ảnh thực tế thu được từ camera CSI trên Jetson Nano.
    *   Thông số góc lái của chu kỳ trước đó (`prev_steering`) và tốc độ ga mặc định (`throttle = 0.2`).
*   **Output**:
    *   Giá trị điều khiển Servo lái thực tế được gửi liên tục tới chip PCA9685 qua I2C để xe tự bám theo làn đường.

---

## 3. Luồng xử lý chi tiết (Step-by-step Guide)

Mục tiêu của hướng dẫn này là giúp bất kỳ ai cũng có thể vận hành hệ thống JetRacer từ bước thiết lập cho đến khi chạy tự động hoàn toàn.

### Bước 1: Chuẩn bị phần cứng & Kết nối
1. Đảm bảo camera CSI được kết nối chắc chắn với cổng MIPI-CSI trên Jetson Nano.
2. Kết nối mạch mở rộng điều khiển động cơ PCA9685 vào bus I2C số 1 (chân SDA/SCL trên Jetson Nano).
3. Cắm Servo lái vào Kênh 0 và ESC điều khiển động cơ vào Kênh 1 của PCA9685.
4. Kết nối cảm biến đo dòng INA219 vào cùng đường I2C (đảm bảo địa chỉ I2C của INA219 được đặt là `0x41` để tránh xung đột với PCA9685 tại địa chỉ `0x40`).

> [!WARNING]
> **LUÔN LUÔN** nâng bánh xe của JetRacer lên khỏi mặt đất (đặt xe lên giá đỡ) trước khi thực hiện các bài kiểm tra chạy thử hoặc khởi động hệ thống tự hành để đảm bảo an toàn, tránh việc xe tự phóng ngoài ý muốn.

### Bước 2: Hiệu chuẩn & Chạy thử độc lập
Trước khi chạy hệ thống Web hoặc Autopilot, hãy tiến hành chạy các bài test để kiểm tra phần cứng:

1.  **Chạy unit tests giả lập (không chạm phần cứng)** để xác minh driver hoạt động đúng logic:
    ```bash
    python3 -m unittest tests.test_drivers_unit -v
    ```
2.  **Kiểm tra camera CSI** (kết nối màn hình hoặc dùng X11 forwarding):
    ```bash
    python3 tests/test_camera.py
    ```
    *(Nhấn `q` để thoát camera).*
3.  **Kiểm tra kết nối I2C và đánh thức chip PCA9685**:
    ```bash
    python3 tests/test_pca9685.py
    ```
    *(Kỳ vọng hiển thị chế độ MODE1 trước và sau khi đánh thức, kiểm tra xem có lỗi bus I2C hay không).*

### Bước 3: Khởi động Web Remote Control & Thu thập dữ liệu
1.  Khởi chạy Flask server điều khiển trên Jetson Nano:
    ```bash
    python3 main.py
    ```
2.  Mở trình duyệt trên điện thoại hoặc máy tính nằm chung mạng WiFi với Jetson Nano theo địa chỉ:
    ```
    http://<IP-CUA-JETSON>:5000
    ```
3.  **Thu thập Dataset**:
    *   Bấm **BẮT ĐẦU GHI** trên giao diện Web để bắt đầu ghi hình hành trình (tần số 10 Hz).
    *   Bấm **CUA 15 HZ** khi xe vào các khúc cua gắt để tăng tần số lấy mẫu lên 15 Hz giúp mô hình học tốt hơn ở các góc cua.
    *   Bấm **DỪNG GHI** để lưu lại phiên chạy. Dataset sẽ nằm tại thư mục `datasets/` trên Jetson.

### Bước 4: Huấn luyện mô hình (Thực hiện trên GPU Server)
1.  Nén và chuyển thư mục `datasets/` từ Jetson Nano lên server huấn luyện có GPU mạnh.
2.  Định nghĩa kiến trúc mạng `MultiInputSteeringNet` và thực hiện huấn luyện bằng tệp `train.py` (trên Server).
3.  Sau khi huấn luyện hoàn tất, xuất tệp trọng số `road_following_model.pth`.

### Bước 5: Chuyển đổi mô hình sang TensorRT (Thực hiện trên Jetson Nano)
1.  Chuyển tệp `road_following_model.pth` từ server huấn luyện ngược lại thư mục `auto_car/` trên Jetson Nano:
    ```bash
    scp road_following_model.pth jet-ai-lab@<jetson-ip>:~/Jetracer_v1/auto_car/
    ```
2.  Chạy script convert để biên dịch mô hình tối ưu cho GPU của Jetson:
    ```bash
    python3 -m auto_car.convert_trt
    ```
    *Kết quả sinh ra tệp tối ưu TensorRT: `auto_car/road_following_trt.pth`.*

### Bước 6: Khởi chạy lái tự động (Autopilot)
1.  Đảm bảo xe vẫn đang đặt trên giá đỡ an toàn.
2.  **Tắt web service trước** — camera CSI chỉ mở được bởi một tiến trình duy nhất, nếu web_control đang chạy thì pilot không nhận được frame nào và xe sẽ đứng yên:
    ```bash
    sudo systemctl stop jetracer
    sudo ss -ltnp | grep ':5000 '    # phải không có kết quả (cổng 5000 đã trống)
    ```
3.  Chạy chương trình tự hành:
    ```bash
    python3 -m line_following.pilot
    ```
4.  **Quan sát trực quan khi xe đang chạy**: mở trình duyệt (điện thoại/máy tính cùng WiFi) tại
    ```
    http://<IP-JETSON>:5001/dashboard
    ```
    Dashboard hiển thị: ảnh camera kèm overlay (trạng thái LINE OK / CUA TRÁI·PHẢI / LINE LOST, error, steering, throttle, P/I/D, Hz, frame, mặt nạ HSV), đồ thị cuộn 15s của error/steering/throttle và các thành phần PID, thanh gauge lái/ga, số frame rỗng (camera bị chiếm) và uptime. Nếu chỉ cần xem video thuần, mở `http://<IP-JETSON>:5001/`.
5.  Quan sát phản ứng của bánh lái khi bạn di chuyển sa bàn hoặc vật cản trước camera. Khi xác nhận phản ứng của Servo là chính xác (xoay sang trái khi vạch kẻ làn lệch sang phải, và ngược lại), bạn có thể đặt xe xuống sa bàn thật để chạy.
6.  Để dừng xe lập tức, nhấn `Ctrl+C` trong terminal. Chương trình sẽ tự động đưa Servo lái về chính giữa và dừng ga (ESC ga về neutral).
7.  Mỗi 5 giây pilot in log `pilot_status` (số frame nhận được, số lần nhận diện được vạch, giá trị lái/ga đang gửi). Nếu `line_hits` luôn bằng 0 mà `frames_ok` tăng, vạch vàng chưa được lọc đúng — hãy chạy `python3 -m line_following.calibrate` để tinh chỉnh dải HSV.

---

## 4. Các thư viện và yêu cầu hệ thống

Hệ thống yêu cầu các gói thư viện Python và cấu hình hệ thống cụ thể như sau:

### Gói Python cơ bản (Cài đặt qua pip)
Các thư viện được định nghĩa trong `requirements.txt`:
*   `torch >= 2.0`
*   `torchvision >= 0.15`
*   `opencv-python >= 4.8.0.76`
*   `pandas >= 2.0`
*   `numpy >= 1.24`
*   `Flask` (cho web remote control)
*   `structlog` (cho ghi log có cấu trúc trong autopilot)

Bạn có thể cài đặt nhanh bằng lệnh:
```bash
pip3 install -r requirements.txt
pip3 install Flask structlog
```

### Thư viện Tối ưu hóa TensorRT (Yêu cầu bắt buộc cho Autopilot)
*   **torch2trt**: Bộ chuyển đổi mô hình PyTorch sang TensorRT.
    *   *Hướng dẫn cài đặt*:
        ```bash
        git clone https://github.com/NVIDIA-AI-IOT/torch2trt
        cd torch2trt
        sudo python3 setup.py install --plugins
        ```

### Yêu cầu Hệ thống
*   Hệ điều hành JetPack (đã được cài sẵn driver GStreamer và driver GPU CUDA).
*   Giao tiếp I2C được kích hoạt trên Jetson Nano (`/dev/i2c-1`). Nếu chưa kích hoạt, cần phân quyền người dùng:
    ```bash
    sudo usermod -aG i2c $USER
    ```

---

## 5. Kết quả thực nghiệm và Các lưu ý quan trọng

Qua các lần chạy thử nghiệm thực tế, dưới đây là các cấu hình và kinh nghiệm vận hành tối ưu:

### A. Hiệu chuẩn Lái (Steering Calibration)
*   Tham số hiệu chỉnh cơ khí nằm ở `STEERING_OFFSET` trong `config.py`. Nếu xe chạy thẳng nhưng bánh hơi lệch sang một bên, hãy điều chỉnh nhẹ offset này (ví dụ `0.05` hoặc `-0.05`) thay vì can thiệp cơ khí.
*   `STEERING_GAIN` mặc định là `-1.0` để khớp hướng xoay trên giao diện Web với hướng quay thực tế của bánh xe. Nếu bánh lái bị ngược chiều, đổi giá trị này thành `1.0`.

### B. Hiệu chuẩn Ga & Bù vùng chết động cơ (ESC Calibration)
*   Hầu hết các bộ ESC xe mô hình đều có vùng chết (deadband) xung quanh xung Neutral (`1500 µs`). Xe chỉ bắt đầu di chuyển khi xung vượt qua deadband.
*   Trong `config.py`, hai tham số bù vùng chết đã được cấu hình tối ưu:
    *   `THROTTLE_FORWARD_START_PULSE_US = 1560` (Bắt đầu tiến từ 1560 µs thay vì 1500 µs).
    *   `THROTTLE_REVERSE_START_PULSE_US = 1440` (Bắt đầu lùi từ 1440 µs thay vì 1500 µs).
*   Nếu thay đổi ESC khác, hãy thử nghiệm tăng/giảm các tham số này từng bước 10 µs để xe có thể di chuyển êm ái ở tốc độ cực thấp.

### C. Giới hạn An toàn (Safety Limits)
*   Trong quá trình thử nghiệm ban đầu, luôn đặt cấu hình ga tối đa an toàn `THROTTLE_LIMIT = 0.5` hoặc thấp hơn (ví dụ `0.25`) trong `config.py` để bảo vệ phần cứng và tránh va chạm tốc độ cao.
*   Khi xe đã chạy ổn định và mượt mà, bạn có thể nâng giới hạn này lên để tăng tốc độ chạy trên sa bàn.

### D. Tần số vòng lặp và Chế độ FP16 (Autopilot Performance)
*   **Tần số Autopilot**: Vòng lặp inference trong `autopilot.py` được khống chế ở `20 Hz` (`LOOP_HZ = 20`). Tần số này đủ nhanh để xử lý thời gian thực mà không làm quá tải CPU/GPU của Jetson Nano.
*   **Chế độ FP16**: Khi chuyển đổi sang TensorRT bằng `convert_trt.py`, cờ `USE_FP16 = True` được bật. Việc này giúp tận dụng nhân Tensor trên Jetson Nano để tính toán với độ chính xác nửa (Half Precision), giảm dung lượng mô hình và tăng tốc độ suy luận gấp ~3 lần so với FP32 mà không làm giảm độ chính xác bám làn của xe.
