(function () {
    "use strict";

    var stream = document.getElementById("camera-stream");
    var zones = document.getElementById("zones");
    var guides = document.getElementById("distance-guides");
    var crosshair = document.getElementById("crosshair");
    var message = document.getElementById("camera-message");
    var livePill = document.getElementById("live-pill");
    var liveLabel = document.getElementById("live-label");
    var resolution = document.getElementById("resolution");
    var fps = document.getElementById("fps");
    var frameAge = document.getElementById("frame-age");
    var freezeButton = document.getElementById("freeze");
    var frozen = false;
    var liveStreamUrl = stream.src;

    function bindToggle(buttonId, target) {
        var button = document.getElementById(buttonId);
        button.addEventListener("click", function () {
            var hidden = target.classList.toggle("is-hidden");
            button.classList.toggle("is-active", !hidden);
        });
    }

    bindToggle("toggle-zones", zones);
    bindToggle("toggle-grid", guides);
    bindToggle("toggle-center", crosshair);

    var opacity = document.getElementById("overlay-opacity");
    var opacityValue = document.getElementById("opacity-value");
    opacity.addEventListener("input", function () {
        var value = Number(opacity.value);
        document.documentElement.style.setProperty(
            "--overlay-opacity",
            String(value / 100)
        );
        opacityValue.textContent = value + "%";
    });

    freezeButton.addEventListener("click", function () {
        frozen = !frozen;
        if (frozen) {
            stream.src = "/snapshot.jpg?t=" + Date.now();
            freezeButton.textContent = "Tiếp tục trực tiếp";
            freezeButton.classList.add("is-active");
        } else {
            stream.src = liveStreamUrl.split("?")[0] + "?t=" + Date.now();
            freezeButton.textContent = "Đóng băng ảnh";
            freezeButton.classList.remove("is-active");
        }
    });

    function setConnectionState(kind, label, detail) {
        livePill.classList.remove("is-live", "is-error");
        if (kind === "live") {
            livePill.classList.add("is-live");
        } else if (kind === "error") {
            livePill.classList.add("is-error");
        }
        liveLabel.textContent = label;

        if (kind === "live") {
            message.classList.add("is-hidden");
            message.classList.remove("is-error");
        } else {
            message.textContent = detail || label;
            message.classList.remove("is-hidden");
            message.classList.toggle("is-error", kind === "error");
        }
    }

    function updateStatus() {
        fetch("/api/status", { cache: "no-store" })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("HTTP " + response.status);
                }
                return response.json();
            })
            .then(function (status) {
                resolution.textContent = status.width && status.height
                    ? status.width + " × " + status.height
                    : "— × —";
                fps.textContent = status.fps ? status.fps.toFixed(1) + " FPS" : "— FPS";
                frameAge.textContent = status.age_seconds === null
                    ? "FRAME —"
                    : "FRAME " + status.age_seconds.toFixed(2) + " s";

                if (status.ready) {
                    setConnectionState("live", frozen ? "ĐÓNG BĂNG" : "TRỰC TIẾP");
                } else if (status.error) {
                    setConnectionState(
                        "error",
                        status.running ? "ĐANG THỬ LẠI" : "LỖI CAMERA",
                        status.error
                    );
                } else {
                    setConnectionState(
                        "loading",
                        "ĐANG KẾT NỐI",
                        status.error || "Đang chờ frame đầu tiên…"
                    );
                }
            })
            .catch(function () {
                setConnectionState(
                    "error",
                    "MẤT KẾT NỐI",
                    "Không kết nối được với web camera."
                );
            });
    }

    stream.addEventListener("error", function () {
        if (!frozen) {
            setConnectionState(
                "error",
                "LỖI LUỒNG",
                "Luồng hình ảnh bị gián đoạn. Kiểm tra trạng thái camera."
            );
        }
    });

    updateStatus();
    window.setInterval(updateStatus, 1000);
}());
