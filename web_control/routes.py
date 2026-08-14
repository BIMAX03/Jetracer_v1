"""Page routes — phục vụ giao diện HTML cho trình duyệt.

Chỉ có một route duy nhất: GET / → trả về trang điều khiển.
Tách riêng khỏi api.py vì phục vụ HTML và xử lý JSON
là hai trách nhiệm hoàn toàn khác nhau.
"""

from flask import Blueprint, render_template


# Blueprint — nhóm các page route
page_bp = Blueprint(
    "pages",
    __name__,
    template_folder="templates",
    static_folder="static"
)


@page_bp.route("/")
def index():
    """Trang chủ — giao diện điều khiển JetRacer.

    Trả về index.html, trình duyệt sẽ tải thêm style.css và script.js
    từ thư mục static/.
    """
    return render_template("index.html")
