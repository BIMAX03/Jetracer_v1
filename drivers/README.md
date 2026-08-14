# JetRacer hardware drivers

Luồng điều khiển:

```text
Car -> Servo / ESC -> PCA9685 -> I2C -> phần cứng
                       |
INA219 ----------------+----> đo điện áp, dòng và công suất
```

## I2C

`I2C` mở `/dev/i2c-1`, kiểm tra dữ liệu 7/8/16 bit, khóa các giao dịch giữa
thread, retry lỗi `OSError`, hỗ trợ block read/write và đóng bus. Có thể truyền
`backend` giả để unit test mà không chạm phần cứng.

## PCA9685

PCA9685 có 16 channel PWM nhưng chỉ có **một tần số chung**. Với oscillator
25 MHz và PWM 50 Hz:

```text
prescale = round(25,000,000 / (4096 * 50) - 1) = 121
frequency thực = 25,000,000 / (4096 * 122) = 50.0288 Hz
```

Một tick dài khoảng 4.88 microsecond. Pulse 1500 microsecond tương đương khoảng
307 count. Driver cache tần số để Servo và ESC cùng yêu cầu 50 Hz không làm chip
sleep/restart hai lần. Bốn byte của một channel được gửi bằng một block write.

## Servo

Input logic vẫn là `-1..1`. Sau `gain` và `offset`, pulse được nội suy riêng cho
hai nửa:

```text
-1 -> min_pulse_us
 0 -> center_pulse_us
+1 -> max_pulse_us
```

Ba điểm có thể bất đối xứng để khớp cơ khí thật. `max_rate_per_second` là tùy
chọn để hạn chế tốc độ thay đổi lệnh; `center(immediate=True)` bỏ giới hạn này
cho dừng khẩn cấp.

## ESC

ESC dùng bốn mốc độc lập:

```text
min reverse -> reverse start -> neutral -> forward start -> max forward
```

Nếu không cấu hình start pulse, mapping giống driver cũ. Khi đã đo deadband,
`forward_start_pulse_us` giúp lệnh ga nhỏ vượt vùng ESC chưa quay. `arm()` giữ
neutral trong thời gian yêu cầu của ESC.

## INA219

INA219 đọc:

- bus voltage, LSB 4 mV;
- shunt voltage, LSB 10 microvolt;
- current từ calibration/current LSB;
- power với `power_lsb = 20 * current_lsb`.

PCA9685 của dự án dùng `0x40`, vì vậy INA219 mặc định dùng `0x41`. Phải cấu hình
chân địa chỉ A0/A1 của module INA219 tương ứng; hai thiết bị không thể cùng dùng
`0x40` trên một bus.

## Calibration an toàn

1. Nâng bánh xe khỏi mặt đất.
2. Tìm pulse tâm servo trước.
3. Tăng từng bước nhỏ để tìm giới hạn trái/phải không ép cơ khí.
4. Giữ ESC neutral khi khởi động.
5. Đo pulse bắt đầu quay tiến/lùi rồi mới cấu hình deadband.
6. Chỉ sau đó mới tăng giới hạn ga trong `config.py`.

Chạy unit test không phần cứng:

```bash
python3 -m unittest tests.test_drivers_unit -v
```
