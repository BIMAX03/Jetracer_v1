"""REST API endpoints cho điều khiển JetRacer.

Mỗi endpoint nhận JSON, gọi CarController, trả JSON.
Sử dụng Flask Blueprint để tách riêng API routes khỏi page routes.

Endpoints:
    POST /api/steering   {"value": float}   → điều khiển lái
    POST /api/throttle   {"value": float}   → điều khiển ga
    POST /api/stop       (không cần body)   → dừng khẩn cấp
"""

from flask import Blueprint, request, jsonify


# Blueprint — nhóm các route bắt đầu bằng /api
api_bp = Blueprint("api", __name__, url_prefix="/api")

# Controller sẽ được inject từ app.py qua hàm init_api()
_controller = None


def init_api(controller) -> None:
    """Inject CarController vào module này.

    Được gọi một lần duy nhất từ app.py khi khởi tạo Flask app.
    Cách này tránh import vòng (circular import) giữa các module.

    Args:
        controller: Instance CarController đã được tạo sẵn.
    """
    global _controller
    _controller = controller


@api_bp.route("/steering", methods=["POST"])
def steering():
    """Đặt giá trị lái.

    Request JSON:
        {"value": -1.0 .. 1.0}

    Response JSON:
        {"status": "ok", "steering": float, "throttle": float}
    """
    data = request.get_json(silent=True)

    if data is None or "value" not in data:
        return jsonify({"status": "error", "message": "Missing 'value'"}), 400

    try:
        value = float(data["value"])
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid 'value'"}), 400

    result = _controller.set_steering(value)

    return jsonify({"status": "ok", **result})


@api_bp.route("/throttle", methods=["POST"])
def throttle():
    """Đặt giá trị ga.

    Request JSON:
        {"value": -1.0 .. 1.0}

    Response JSON:
        {"status": "ok", "steering": float, "throttle": float}
    """
    data = request.get_json(silent=True)

    if data is None or "value" not in data:
        return jsonify({"status": "error", "message": "Missing 'value'"}), 400

    try:
        value = float(data["value"])
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid 'value'"}), 400

    result = _controller.set_throttle(value)

    return jsonify({"status": "ok", **result})


@api_bp.route("/stop", methods=["POST"])
def stop():
    """Dừng khẩn cấp — không cần gửi body.

    Response JSON:
        {"status": "ok", "steering": 0.0, "throttle": 0.0}
    """
    result = _controller.stop()

    return jsonify({"status": "ok", **result})
