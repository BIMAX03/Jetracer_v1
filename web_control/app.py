"""Flask Application Factory — lắp ráp toàn bộ web layer.

Hàm create_app() thực hiện:
    1. Tạo Flask app.
    2. Tạo CarController (instance duy nhất).
    3. Inject controller vào api module.
    4. Đăng ký Blueprint: api_bp (/api/...) và page_bp (/).

main.py chỉ cần gọi create_app() rồi app.run().
"""

from flask import Flask

from web_control.controller import CarController
from web_control.api import api_bp, init_api
from web_control.camera import (
    camera_bp,
    ensure_camera_started,
    wait_for_frame,
)
from web_control.data_collector import DataCollector
from web_control.routes import page_bp
import config


def create_app() -> Flask:
    """Tạo và cấu hình Flask application.

    Returns:
        Flask app đã sẵn sàng chạy.
    """
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static"
    )

    # ── Tạo controller (instance duy nhất cho toàn app) ──────────
    controller = CarController()
    # ESC cần nhận neutral liên tục trước lệnh ga đầu tiên. Đây cũng đưa servo
    # về giữa, giống trình tự trong tests/test_esc.py.
    controller.arm(duration=config.ESC_ARM_SECONDS)
    collector = DataCollector(
        controller=controller,
        frame_provider=wait_for_frame,
        camera_starter=ensure_camera_started,
        dataset_dir=config.DATASET_DIR,
        normal_hz=config.DATASET_NORMAL_HZ,
        curve_hz=config.DATASET_CURVE_HZ,
    )

    # ── Inject controller vào api module ─────────────────────────
    init_api(controller, collector)

    # Cho main.py/tests có thể dừng recorder sạch trước khi thoát.
    app.extensions["data_collector"] = collector

    # ── Đăng ký Blueprints ───────────────────────────────────────
    app.register_blueprint(api_bp)      # POST /api/steering, /api/throttle, /api/stop
    app.register_blueprint(camera_bp)   # GET /camera/stream
    app.register_blueprint(page_bp)     # GET /

    return app
