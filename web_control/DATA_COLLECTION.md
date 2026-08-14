# Thu thập driving dataset

Chạy web như bình thường bằng `python3 main.py`. Trên thanh phía trên:

- `BẮT ĐẦU GHI` tạo một session mới và ghi ở 10 Hz.
- `CUA 15 HZ` bật/tắt lấy mẫu nhanh cho đoạn cua.
- `DỪNG GHI` đóng session hiện tại; lần ghi tiếp theo luôn là session mới.

Dataset được lưu tại `datasets/` ở thư mục gốc dự án:

```text
datasets/
└── sess_20260810_143000/
    ├── labels.csv
    ├── frame_000001.jpg
    ├── frame_000002.jpg
    └── ...
```

`labels.csv` có đúng các cột:

```text
frame_id,filename,steering,steering_prev,throttle,timestamp,session_id
```

`steering_prev` là steering của sample đã ghi ngay trước trong cùng session;
sample đầu tiên luôn dùng `0.0`. `timestamp` là Unix timestamp lúc camera tạo
frame. Khi train, chỉ dùng ảnh, `steering_prev`, `throttle` làm input và
`steering` làm label; không đưa `timestamp` hoặc `session_id` vào model.
