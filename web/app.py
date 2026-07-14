"""Flask Application Factory — lắp ráp toàn bộ web layer.

Hàm create_app() thực hiện:
    1. Tạo Flask app.
    2. Tạo CarController (instance duy nhất).
    3. Inject controller vào api module.
    4. Đăng ký Blueprint: api_bp (/api/...) và page_bp (/).

main.py chỉ cần gọi create_app() rồi app.run().
"""

from flask import Flask

from web.controller import CarController
from web.api import api_bp, init_api
from web.camera import camera_bp
from web.routes import page_bp


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

    # ── Inject controller vào api module ─────────────────────────
    init_api(controller)

    # ── Đăng ký Blueprints ───────────────────────────────────────
    app.register_blueprint(api_bp)      # POST /api/steering, /api/throttle, /api/stop
    app.register_blueprint(camera_bp)   # GET /camera/stream
    app.register_blueprint(page_bp)     # GET /

    return app
