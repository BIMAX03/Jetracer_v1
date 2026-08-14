"""Entry point — khởi động JetRacer Web Remote Control.

Cách chạy:
    python3 main.py

Sau khi chạy, mở trình duyệt trên điện thoại và truy cập:
    http://<jetson-ip>:5000
"""

import errno
import sys

import config
from web_control.app import create_app
from web_control.camera import shutdown_camera


def main() -> int:
    """Khởi tạo Flask app và chạy web server."""

    app = create_app()

    print("=" * 50)
    print("  JetRacer Web Remote Control")
    print("=" * 50)
    print("  Server:  http://{}:{}".format(config.WEB_HOST, config.WEB_PORT))
    print("  Mở trình duyệt trên điện thoại và truy cập")
    print("  địa chỉ IP của Jetson Nano trên cùng mạng WiFi.")
    print("=" * 50)

    try:
        app.run(
            host=config.WEB_HOST,
            port=config.WEB_PORT,
            debug=config.WEB_DEBUG,
            # MJPEG giữ kết nối lâu; cần thread riêng để API lái/ga vẫn phản hồi.
            threaded=True
        )
    except OSError as exc:
        if exc.errno != errno.EADDRINUSE:
            raise
        print(
            "\nLỗi: cổng {} đang được một tiến trình khác sử dụng."
            .format(config.WEB_PORT),
            file=sys.stderr,
        )
        print(
            "Service JetRacer có thể đang chạy sẵn. Mở "
            "http://<IP-JETSON>:{} hoặc dừng service trước khi chạy thủ công."
            .format(config.WEB_PORT),
            file=sys.stderr,
        )
        print(
            "Kiểm tra: sudo ss -ltnp | grep ':{} '"
            .format(config.WEB_PORT),
            file=sys.stderr,
        )
        print(
            "Dừng service: sudo systemctl stop jetracer",
            file=sys.stderr,
        )
        return 2
    finally:
        app.extensions["data_collector"].stop()
        # Nhả CSI/Argus sạch khi Ctrl+C hoặc systemd restart dịch vụ.
        shutdown_camera()
    return 0


if __name__ == "__main__":
    sys.exit(main())
