"""Entry point — khởi động JetRacer Web Remote Control.

Cách chạy:
    python3 main.py

Sau khi chạy, mở trình duyệt trên điện thoại và truy cập:
    http://<jetson-ip>:5000
"""

import config
from web.app import create_app
from web.camera import shutdown_camera


def main() -> None:
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
    finally:
        # Nhả CSI/Argus sạch khi Ctrl+C hoặc systemd restart dịch vụ.
        shutdown_camera()


if __name__ == "__main__":
    main()
