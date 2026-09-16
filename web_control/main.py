"""Entry point — khởi động JetRacer Web Remote Control.

Cách chạy từ thư mục gốc dự án Jetson:
    python3 -m web_control.main
Hoặc:
    python3 web_control/main.py

Sau khi chạy, mở trình duyệt trên thiết bị và truy cập:
    http://<jetson-ip>:5000
"""

import errno
import os
import sys

# Đảm bảo thư mục gốc dự án (Jetson) nằm trong sys.path để import config và web_control
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import config
from web_control.app import create_app
from web_control.camera import shutdown_camera


def main() -> int:
    """Khởi tạo Flask app và chạy web server với dọn dẹp tài nguyên an toàn."""

    app = create_app()

    print("=" * 50)
    print("  JetRacer Web Remote Control")
    print("=" * 50)
    print(f"  Server:  http://{config.WEB_HOST}:{config.WEB_PORT}")
    print("  Mở trình duyệt trên điện thoại/PC và truy cập")
    print("  địa chỉ IP của Jetson Nano trên cùng mạng WiFi.")
    print("=" * 50)

    try:
        app.run(
            host=config.WEB_HOST,
            port=config.WEB_PORT,
            debug=config.WEB_DEBUG,
            # MJPEG giữ kết nối lâu; cần thread riêng để API lái/ga vẫn phản hồi.
            threaded=True,
        )
    except OSError as exc:
        if exc.errno != errno.EADDRINUSE:
            raise
        print(
            f"\nLỗi: cổng {config.WEB_PORT} đang được một tiến trình khác sử dụng.",
            file=sys.stderr,
        )
        print(
            f"Service JetRacer có thể đang chạy sẵn. Mở http://<IP-JETSON>:{config.WEB_PORT} "
            "hoặc dừng service trước khi chạy thủ công.",
            file=sys.stderr,
        )
        print(
            f"Kiểm tra: sudo ss -ltnp | grep ':{config.WEB_PORT} '",
            file=sys.stderr,
        )
        print(
            "Dừng service: sudo systemctl stop jetracer",
            file=sys.stderr,
        )
        return 2
    except KeyboardInterrupt:
        print("\n[INFO] Nhận tín hiệu dừng từ người dùng (Ctrl+C).")
    finally:
        print("[INFO] Đang dọn dẹp tài nguyên...")
        # Dừng thu thập dữ liệu nếu đang quay
        if "data_collector" in app.extensions:
            try:
                app.extensions["data_collector"].stop()
            except Exception as e:
                print(f"[WARN] Lỗi khi dừng data_collector: {e}", file=sys.stderr)

        # Dừng camera CSI/Argus sạch sẽ
        try:
            shutdown_camera()
        except Exception as e:
            print(f"[WARN] Lỗi khi dừng camera: {e}", file=sys.stderr)

        print("[INFO] Đã dọn dẹp xong tài nguyên web_control.")

    return 0


if __name__ == "__main__":
    sys.exit(main())