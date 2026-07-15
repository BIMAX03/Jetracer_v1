/* ═══════════════════════════════════════════════════════════════════
   JetRacer Futuristic Cockpit — Client Logic
   ═══════════════════════════════════════════════════════════════════ */

(function () {
    "use strict";

    /* ── Cấu hình & Trạng thái ──────────────────────────────────── */
    var currentSteering = 0.0;
    var currentThrottle = 0.0;
    var currentGear = 1; // Mặc định số 1 (chạy chậm an toàn)

    // Tỉ lệ ga tương ứng với từng Gear (chế độ số)
    var GEAR_MULTIPLIERS = {
        1: 0.35,  // Số 1: Ga tối đa 35% của giới hạn phần cứng
        2: 0.65,  // Số 2: Ga tối đa 65% của giới hạn phần cứng
        3: 1.00   // Số 3: Ga tối đa 100% của giới hạn phần cứng
    };

    var isCruiseActive = false;
    var cruiseInterval = null;

    /* ── DOM Elements ──────────────────────────────────────────── */
    var statusDot = document.getElementById("btn-wifi");
    
    // Cần ga dọc
    var throttleSlider = document.getElementById("throttle-slider");
    var throttleDirection = document.getElementById("throttle-direction");
    var throttlePercent = document.getElementById("throttle-percent");
    var btnCruise = document.getElementById("btn-cruise");
    
    // Nút khẩn cấp
    var btnBack = document.getElementById("btn-back");

    // Chọn số (Gear)
    var gearButtons = {
        1: document.getElementById("gear-1"),
        2: document.getElementById("gear-2"),
        3: document.getElementById("gear-3")
    };

    // Dashboard hiển thị
    var valSpeed = document.getElementById("val-speed");
    var valAngle = document.getElementById("val-angle");
    var gaugeFill = document.getElementById("gauge-fill");
    var gaugeNeedle = document.getElementById("gauge-needle");

    // Camera trung tâm
    var cameraFeed = document.getElementById("camera-feed");
    var cameraStatus = document.getElementById("camera-status");
    var cameraRetryTimer = null;

    // Vô lăng
    var steeringWheel = document.getElementById("steering-wheel");

    cameraFeed.addEventListener("load", function () {
        if (cameraRetryTimer) {
            clearTimeout(cameraRetryTimer);
            cameraRetryTimer = null;
        }
        cameraStatus.textContent = "CAMERA LIVE";
        cameraStatus.classList.add("live");
    });

    cameraFeed.addEventListener("error", function () {
        cameraStatus.textContent = "CAMERA OFFLINE";
        cameraStatus.classList.remove("live");

        // Argus có thể cần một lúc để nhả camera sau khi refresh trang.
        if (!cameraRetryTimer) {
            cameraRetryTimer = setTimeout(function () {
                cameraRetryTimer = null;
                cameraStatus.textContent = "CAMERA RECONNECTING";
                cameraFeed.src = "/camera/stream?t=" + Date.now();
            }, 2000);
        }
    });

    /* ── Gửi lệnh API ──────────────────────────────────────────── */

    function apiPost(endpoint, body) {
        fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: body !== undefined ? JSON.stringify(body) : undefined
        })
        .then(function (res) { return res.json(); })
        .then(function (data) {
            if (data.status === "ok") {
                updateDashboard(data.steering, data.throttle);
                setConnected(true);
            }
        })
        .catch(function () {
            setConnected(false);
        });
    }

    function sendSteering(val) {
        currentSteering = val;
        apiPost("/api/steering", { value: val });
    }

    function sendThrottle(val) {
        currentThrottle = val;
        apiPost("/api/throttle", { value: val });
    }

    function sendEmergencyStop() {
        if (isCruiseActive) {
            toggleCruise(false);
        }
        resetThrottleSlider(false);
        apiPost("/api/stop");
    }

    /* ── Thiết lập kết nối ──────────────────────────────────────── */
    function setConnected(connected) {
        if (connected) {
            statusDot.style.color = "#00f0ff";
            statusDot.style.boxShadow = "0 0 10px rgba(0, 240, 255, 0.4)";
        } else {
            statusDot.style.color = "#ff3b30";
            statusDot.style.boxShadow = "0 0 10px rgba(255, 59, 48, 0.4)";
        }
    }

    /* ── Đồng hồ Dashboard hiển thị ────────────────────────────── */
    function updateDashboard(steering, throttle) {
        var speedRatio = Math.max(0, Math.min(1, Math.abs(throttle)));

        // Cập nhật text hiển thị số
        valSpeed.textContent = Math.round(speedRatio * 100) + "%";
        valAngle.textContent = steering.toFixed(2);

        // Cập nhật kim đồng hồ tốc độ (Ga)
        // Cung tròn kim quay từ -90 độ (ga = 0) đến +90 độ (ga = tối đa)
        var needleRotation = speedRatio * 180 - 90;
        gaugeNeedle.setAttribute(
            "transform",
            "rotate(" + needleRotation + " 100 90)"
        );

        // Cập nhật vòng cung LED sáng xanh
        // pathLength=100 nên 100 là rỗng, 0 là đầy toàn bộ nửa vòng.
        var dashOffset = 100 - speedRatio * 100;
        gaugeFill.style.strokeDashoffset = dashOffset;
    }

    /* ── Điều khiển số (Gear 1, 2, 3) ───────────────────────────── */
    function selectGear(gearNum) {
        currentGear = gearNum;
        Object.keys(gearButtons).forEach(function (key) {
            if (parseInt(key, 10) === gearNum) {
                gearButtons[key].classList.add("active");
            } else {
                gearButtons[key].classList.remove("active");
            }
        });

        // Nếu đang giữ cần ga, áp dụng giới hạn tốc độ của số mới ngay lập tức.
        if (isThrottleSliding) {
            applyThrottleSlider();
        } else {
            updateThrottleReadout(Number(throttleSlider.value));
        }
    }

    Object.keys(gearButtons).forEach(function (key) {
        var gearNum = parseInt(key, 10);
        gearButtons[key].addEventListener("click", function () {
            selectGear(gearNum);
        });
    });

    /* ── Cần ga dọc (Tiến/Lùi theo tỉ lệ) ────────────────────────── */
    var isThrottleSliding = false;
    var throttlePointerId = null;

    function updateThrottleReadout(rawValue) {
        var effectiveValue = rawValue / 100 * GEAR_MULTIPLIERS[currentGear];
        var direction = "DỪNG";

        if (rawValue > 0) direction = "TIẾN";
        if (rawValue < 0) direction = "LÙI";

        throttleDirection.textContent = direction;
        throttlePercent.textContent = Math.round(Math.abs(effectiveValue) * 100) + "%";
        throttleSlider.setAttribute(
            "aria-valuetext",
            direction === "DỪNG"
                ? "Dừng"
                : direction + " " + Math.round(Math.abs(effectiveValue) * 100) + "%"
        );
    }

    function applyThrottleSlider() {
        var rawValue = Number(throttleSlider.value);
        var targetValue = rawValue / 100 * GEAR_MULTIPLIERS[currentGear];

        updateThrottleReadout(rawValue);
        sendThrottle(targetValue);
    }

    function resetThrottleSlider(sendNeutral) {
        isThrottleSliding = false;
        throttlePointerId = null;
        throttleSlider.value = "0";
        updateThrottleReadout(0);

        if (sendNeutral !== false) {
            sendThrottle(0.0);
        }
    }

    function setThrottleFromPointer(clientY) {
        var rect = throttleSlider.getBoundingClientRect();
        var position = (clientY - rect.top) / rect.height;
        var rawValue = Math.round((1 - position * 2) * 100);

        rawValue = Math.max(-100, Math.min(100, rawValue));
        throttleSlider.value = String(rawValue);
        applyThrottleSlider();
    }

    function startThrottle(direction) {
        if (isCruiseActive) toggleCruise(false);
        var speedMultiplier = GEAR_MULTIPLIERS[currentGear];
        var targetValue = direction === "forward" ? speedMultiplier : -speedMultiplier;
        sendThrottle(targetValue);
    }

    function stopThrottle() {
        if (!isCruiseActive) {
            sendThrottle(0.0);
        }
    }

    throttleSlider.addEventListener("pointerdown", function (e) {
        // Mỗi bộ điều khiển giữ một pointerId riêng để hỗ trợ hai ngón tay.
        if (throttlePointerId !== null) return;
        if (isCruiseActive) toggleCruise(false);

        e.preventDefault();
        isThrottleSliding = true;
        throttlePointerId = e.pointerId;
        throttleSlider.setPointerCapture(e.pointerId);
        setThrottleFromPointer(e.clientY);
    });

    throttleSlider.addEventListener("pointermove", function (e) {
        if (e.pointerId !== throttlePointerId) return;
        e.preventDefault();
        setThrottleFromPointer(e.clientY);
    });

    throttleSlider.addEventListener("pointerup", function (e) {
        if (e.pointerId !== throttlePointerId) return;
        resetThrottleSlider(true);
    });

    throttleSlider.addEventListener("pointercancel", function (e) {
        if (e.pointerId !== throttlePointerId) return;
        resetThrottleSlider(true);
    });

    // Giữ khả năng điều khiển bằng bàn phím khi input đang focus.
    throttleSlider.addEventListener("input", function () {
        if (throttlePointerId === null) {
            isThrottleSliding = true;
            applyThrottleSlider();
        }
    });

    throttleSlider.addEventListener("keyup", function () {
        resetThrottleSlider(true);
    });

    /* ── Chế độ Ngựa Bập Bênh (Rocking Horse Cruise Mode) ─────────── */
    function toggleCruise(forceState) {
        var nextState = forceState !== undefined ? forceState : !isCruiseActive;
        if (nextState) {
            isCruiseActive = true;
            btnCruise.classList.add("active");
            var step = 0;
            // Bập bênh: mỗi giây thay đổi ga tiến/lùi nhẹ tạo nhịp bập bênh như ngựa gỗ
            cruiseInterval = setInterval(function () {
                var swing = (step % 2 === 0) ? 0.15 : -0.15;
                sendThrottle(swing);
                step++;
            }, 1000);
        } else {
            isCruiseActive = false;
            btnCruise.classList.remove("active");
            if (cruiseInterval) {
                clearInterval(cruiseInterval);
                cruiseInterval = null;
            }
            sendThrottle(0.0);
        }
    }

    btnCruise.addEventListener("click", function () {
        toggleCruise();
    });

    /* ── Cơ chế kéo xoay VÔ LĂNG (Steering Wheel Drag) ────────────── */
    var isDraggingWheel = false;
    var steeringPointerId = null;
    var wheelCenter = { x: 0, y: 0 };
    var maxWheelAngle = 90; // Góc xoay vô lăng ảo tối đa sang mỗi bên (độ)

    function getAngle(x, y) {
        var dx = x - wheelCenter.x;
        var dy = y - wheelCenter.y;
        return Math.atan2(dy, dx) * (180 / Math.PI);
    }

    var startAngle = 0;
    var currentWheelAngle = 0;

    function handleStart(clientX, clientY) {
        var rect = steeringWheel.getBoundingClientRect();
        wheelCenter.x = rect.left + rect.width / 2;
        wheelCenter.y = rect.top + rect.height / 2;
        
        startAngle = getAngle(clientX, clientY) - currentWheelAngle;
        isDraggingWheel = true;
        
        // Bật lớp chuyển tiếp nhanh khi kéo
        steeringWheel.style.transition = "none";
    }

    function handleMove(clientX, clientY) {
        if (!isDraggingWheel) return;
        
        var angle = getAngle(clientX, clientY) - startAngle;
        
        // Chuẩn hóa góc quay trong khoảng [-180, 180]
        if (angle > 180) angle -= 360;
        if (angle < -180) angle += 360;
        
        // Giới hạn góc xoay tối đa (Ví dụ: -90 độ đến 90 độ)
        if (angle > maxWheelAngle) angle = maxWheelAngle;
        if (angle < -maxWheelAngle) angle = -maxWheelAngle;
        
        currentWheelAngle = angle;
        steeringWheel.style.transform = "rotate(" + angle + "deg)";
        
        // Map góc xoay ra giá trị lái steering: [-maxWheelAngle, maxWheelAngle] -> [-1.0, 1.0]
        var steerVal = angle / maxWheelAngle;
        sendSteering(steerVal);
    }

    function handleEnd() {
        if (!isDraggingWheel) return;
        isDraggingWheel = false;
        steeringPointerId = null;
        
        // Bật transition mượt mà khi vô lăng tự động trả về giữa
        steeringWheel.style.transition = "transform 0.25s cubic-bezier(0.175, 0.885, 0.32, 1.275)";
        
        currentWheelAngle = 0;
        steeringWheel.style.transform = "rotate(0deg)";
        sendSteering(0.0);
    }

    // Pointer Events hỗ trợ đồng thời chuột, cảm ứng và nhiều ngón tay.
    steeringWheel.addEventListener("pointerdown", function (e) {
        if (steeringPointerId !== null) return;

        e.preventDefault();
        steeringPointerId = e.pointerId;
        steeringWheel.setPointerCapture(e.pointerId);
        handleStart(e.clientX, e.clientY);
    });

    steeringWheel.addEventListener("pointermove", function (e) {
        if (e.pointerId !== steeringPointerId) return;

        e.preventDefault();
        handleMove(e.clientX, e.clientY);
    });

    steeringWheel.addEventListener("pointerup", function (e) {
        if (e.pointerId !== steeringPointerId) return;
        handleEnd();
    });

    steeringWheel.addEventListener("pointercancel", function (e) {
        if (e.pointerId !== steeringPointerId) return;
        handleEnd();
    });

    /* ── Nút dừng khẩn cấp & Quay lại ────────────────────────────── */
    btnBack.addEventListener("click", function () {
        window.history.back();
    });

    /* ── Phím nóng bàn phím hỗ trợ Test trên máy tính ──────────────── */
    document.addEventListener("keydown", function (e) {
        if (e.target === throttleSlider) return;

        var key = e.key.toLowerCase();
        
        // Điều khiển ga
        if (key === "arrowup" || key === "w") {
            startThrottle("forward");
        } else if (key === "arrowdown" || key === "s") {
            startThrottle("reverse");
        }
        
        // Điều khiển lái bằng phím (A/D hoặc Mũi tên trái/phải)
        if (key === "arrowleft" || key === "a") {
            steeringWheel.style.transition = "transform 0.15s ease-out";
            steeringWheel.style.transform = "rotate(-45deg)";
            sendSteering(-0.5);
        } else if (key === "arrowright" || key === "d") {
            steeringWheel.style.transition = "transform 0.15s ease-out";
            steeringWheel.style.transform = "rotate(45deg)";
            sendSteering(0.5);
        }

        // Chuyển nhanh Gear bằng số 1, 2, 3
        if (key === "1") selectGear(1);
        if (key === "2") selectGear(2);
        if (key === "3") selectGear(3);

        // Phím cách dừng khẩn cấp
        if (e.key === " ") {
            sendEmergencyStop();
        }
    });

    document.addEventListener("keyup", function (e) {
        if (e.target === throttleSlider) return;

        var key = e.key.toLowerCase();
        
        // Thả nút ga
        if (key === "arrowup" || key === "w" || key === "arrowdown" || key === "s") {
            stopThrottle();
        }

        // Thả nút lái -> tự trả lái
        if (key === "arrowleft" || key === "a" || key === "arrowright" || key === "d") {
            steeringWheel.style.transition = "transform 0.2s ease-out";
            steeringWheel.style.transform = "rotate(0deg)";
            sendSteering(0.0);
        }
    });

})();
