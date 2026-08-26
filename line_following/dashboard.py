"""Dashboard debug trực quan cho pilot (Line Following).

Trang web tự chứa (không cần CDN / internet trên Jetson) hiển thị:
    - Luồng video MJPEG + overlay từ DebugStreamer (route ``/``).
    - Giải thích chi tiết & trực quan 4 thuật toán dò line theo thời gian thực (realtime).

Mở trình duyệt tại ``http://<ip-jetson>:5001/dashboard`` khi pilot đang chạy.
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>Pilot Debug Dashboard - Line Following Algorithms</title>
<style>
:root{
  --bg:#070d19; --panel:#0e172a; --panel2:#0a1224; --border:#1e293b;
  --text:#f1f5f9; --dim:#94a3b8; --green:#22c55e; --red:#ef4444;
  --blue:#38bdf8; --yellow:#eab308; --orange:#f97316; --purple:#c084fc;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;font-size:13px}
body{padding:12px;overflow-x:hidden}

header{
  display:flex;align-items:center;gap:12px;padding:10px 16px;
  background:var(--panel);border:1px solid var(--border);border-radius:10px;margin-bottom:12px;
}
.brand{font-size:16px;font-weight:800;letter-spacing:0.5px}
.brand span{color:var(--yellow)}
.pill{
  padding:4px 12px;border-radius:999px;font-weight:700;font-size:11px;
  letter-spacing:0.5px;border:1px solid var(--border);background:var(--panel2);
}
.pill-idle{color:var(--dim)}
.pill-ok{background:rgba(34,197,94,.15);color:var(--green);border-color:rgba(34,197,94,.4)}
.pill-turn{background:rgba(249,115,22,.15);color:var(--orange);border-color:rgba(249,115,22,.4)}
.pill-lost{background:rgba(239,68,68,.15);color:var(--red);border-color:rgba(239,68,68,.4)}
.hmeta{margin-left:auto;display:flex;gap:16px;color:var(--dim);font-size:12px}
.hmeta b{color:var(--text)}

#conn-banner{
  display:none;position:fixed;top:10px;left:50%;transform:translateX(-50%);
  background:rgba(239,68,68,.9);color:#fff;padding:8px 20px;border-radius:8px;
  font-weight:700;z-index:99;box-shadow:0 4px 12px rgba(0,0,0,.5);
}
body.offline #conn-banner{display:block}
body.offline .video-card img{opacity:.35}

main{
  display:grid;grid-template-columns:1fr 1fr;gap:12px;align-items:start;
}
@media (max-width:1150px){main{grid-template-columns:1fr}}

.card{
  background:var(--panel);border:1px solid var(--border);border-radius:10px;
  padding:14px;margin-bottom:12px;box-shadow:0 2px 8px rgba(0,0,0,.2);
}
.card-header{
  display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;
}
.card-title{
  font-size:13px;font-weight:700;letter-spacing:0.5px;color:var(--blue);
  display:flex;align-items:center;gap:6px;
}
.card-title .num{
  background:rgba(56,189,248,.15);color:var(--blue);padding:2px 7px;
  border-radius:4px;font-size:11px;
}
.formula-box{
  background:var(--panel2);border:1px solid var(--border);border-radius:6px;
  padding:8px 12px;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;
  font-size:12px;color:var(--yellow);margin-bottom:10px;word-break:break-all;
}

.video-card img{width:100%;aspect-ratio:16/9;display:block;border-radius:8px;background:#000;object-fit:cover}

/* Gauges */
.gauge-container{margin:8px 0}
.g-head{display:flex;justify-content:space-between;font-size:11px;color:var(--dim);margin-bottom:3px;font-weight:600}
.g-track{
  position:relative;height:12px;background:#030712;border:1px solid var(--border);
  border-radius:6px;overflow:hidden;
}
.g-zero{position:absolute;left:50%;top:0;bottom:0;width:2px;background:#475569;z-index:2}
.g-fill{position:absolute;top:0;bottom:0;left:50%;width:0;background:var(--blue);transition:all .1s ease-out}

/* Grid & Tables */
.val-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:8px;margin-bottom:10px}
.val-card{background:var(--panel2);border:1px solid var(--border);padding:8px;border-radius:6px}
.val-card .lbl{font-size:10px;color:var(--dim);text-transform:uppercase;margin-bottom:2px}
.val-card .val{font-size:14px;font-weight:700;color:var(--text)}

.guide-table{width:100%;border-collapse:collapse;margin-top:8px;font-size:11px}
.guide-table th,.guide-table td{border:1px solid var(--border);padding:5px 8px;text-align:left}
.guide-table th{background:var(--panel2);color:var(--dim);font-weight:600}

/* Diagrams */
.roi-diagram{
  display:grid;grid-template-columns:1fr 1fr;gap:4px;background:#030712;
  border:1px dashed var(--border);padding:6px;border-radius:6px;margin:8px 0;text-align:center;
}
.roi-zone{background:rgba(30,41,59,.5);padding:8px 4px;border-radius:4px;font-size:10px;color:var(--dim)}
.roi-zone b{display:block;font-size:12px;color:var(--text);margin-top:2px}

/* Flowchart */
.flowchart{display:flex;gap:6px;margin:10px 0}
.flow-node{
  flex:1;background:var(--panel2);border:1px solid var(--border);border-radius:6px;
  padding:8px 4px;text-align:center;font-size:10px;color:var(--dim);transition:all .2s;
}
.flow-node.active{background:rgba(34,197,94,.15);border-color:var(--green);color:var(--green);font-weight:700}
.flow-node.active-turn{background:rgba(249,115,22,.15);border-color:var(--orange);color:var(--orange);font-weight:700}
.flow-node.active-stop{background:rgba(239,68,68,.15);border-color:var(--red);color:var(--red);font-weight:700}

/* Chart */
canvas{width:100%;height:140px;display:block}
</style>
</head>
<body>
<div id="conn-banner">MẤT KẾT NỐI VỚI PILOT — kiểm tra pilot còn chạy không</div>

<header>
  <div class="brand">PILOT <span>DEBUG DASHBOARD</span></div>
  <div id="status-pill" class="pill pill-idle">INIT</div>
  <div class="hmeta">
    <span>UPTIME: <b id="v-uptime">--</b></span>
    <span id="v-clock">--:--:--</span>
  </div>
</header>

<main>
  <!-- NỬA TRÁI: CAMERA STREAM + CHART LỊCH SỬ -->
  <section class="col-left">
    <div class="card video-card">
      <div class="card-header">
        <div class="card-title">🎥 Live Camera CSI + Visual Overlay</div>
        <div style="font-size:11px;color:var(--dim)"><span id="v-fps">--</span> FPS | <span id="v-hz">--</span> Hz</div>
      </div>
      <img id="stream" src="/" alt="camera stream">
    </div>

    <div class="card">
      <div class="card-header">
        <div class="card-title">📈 Đồ thị Tín hiệu Điều khiển (15 giây)</div>
        <div style="font-size:10px;color:var(--dim);display:flex;gap:10px">
          <span style="color:var(--yellow)">■ Error</span>
          <span style="color:var(--blue)">■ Steering</span>
          <span style="color:var(--green)">■ Throttle</span>
        </div>
      </div>
      <canvas id="chart-control"></canvas>
    </div>
  </section>

  <!-- NỬA PHẢI: TRỰC QUAN HÓA 4 THUẬT TOÁN REALTIME -->
  <section class="col-right">
    
    <!-- 1. PID CONTROLLER -->
    <div class="card">
      <div class="card-header">
        <div class="card-title"><span class="num">1</span> PID Controller — Bám line đường thẳng</div>
      </div>
      <div class="formula-box">steering = KP × error + KI × ∫error·dt + KD × (d_error / dt)</div>
      
      <!-- Live Error Gauge -->
      <div class="gauge-container">
        <div class="g-head"><span>TÂM CAMERA (-1.0 Trái ← 0.0 → +1.0 Phải)</span><span id="v-error" style="color:var(--yellow)">0.000</span></div>
        <div class="g-track"><div class="g-zero"></div><div class="g-fill" id="g-error"></div></div>
      </div>

      <div class="val-grid">
        <div class="val-card"><div class="lbl">P Term</div><div class="val" id="v-p">+0.000</div></div>
        <div class="val-card"><div class="lbl">I Term</div><div class="val" id="v-i">+0.000</div></div>
        <div class="val-card"><div class="lbl">D Term</div><div class="val" id="v-d">+0.000</div></div>
        <div class="val-card"><div class="lbl">Raw Steering</div><div class="val" id="v-steer-raw" style="color:var(--blue)">+0.000</div></div>
        <div class="val-card"><div class="lbl">Filtered Steer</div><div class="val" id="v-steer-smooth" style="color:var(--green)">+0.000</div></div>
      </div>

      <div class="val-grid" style="grid-template-columns:repeat(4,1fr)">
        <div class="val-card"><div class="lbl">KP</div><div class="val" id="v-kp">0.40</div></div>
        <div class="val-card"><div class="lbl">KI</div><div class="val" id="v-ki">0.00</div></div>
        <div class="val-card"><div class="lbl">KD</div><div class="val" id="v-kd">0.05</div></div>
        <div class="val-card"><div class="lbl">Deadzone</div><div class="val" id="v-deadzone">0.06</div></div>
      </div>

      <table class="guide-table">
        <thead>
          <tr><th>Thành phần</th><th>Tác dụng</th><th>Điều chỉnh</th></tr>
        </thead>
        <tbody>
          <tr><td><b>KP (Tỉ lệ)</b></td><td>Phản ứng theo độ lệch hiện tại</td><td>Quá cao → zigzag; Quá thấp → chậm</td></tr>
          <tr><td><b>KI (Tích phân)</b></td><td>Bù sai số tích lũy lâu dài</td><td>Thường = 0 nếu xe cân bằng tốt</td></tr>
          <tr><td><b>KD (Đạo hàm)</b></td><td>Dự đoán xu hướng, dập dao động</td><td>Giúp mượt hơn; quá cao → nhiễu camera</td></tr>
        </tbody>
      </table>
    </div>

    <!-- 2. DYNAMIC THROTTLE -->
    <div class="card">
      <div class="card-header">
        <div class="card-title"><span class="num">2</span> Dynamic Throttle — Ga động theo độ cong</div>
        <div id="v-throt-badge" class="pill pill-ok">TỐI ĐA 100%</div>
      </div>
      <div class="formula-box">
        throttle_scale = max(0.0, 1.0 - |error|)<br>
        throttle = BASE_THROTTLE × (0.6 + 0.4 × scale)
      </div>

      <div class="gauge-container">
        <div class="g-head"><span>THROTTLE SCALE (Tỷ lệ ga theo đường thẳng/cong)</span><span id="v-throt-scale">100%</span></div>
        <div class="g-track"><div class="g-fill" id="g-throt-scale" style="left:0;background:var(--green)"></div></div>
      </div>

      <div class="val-grid" style="grid-template-columns:1fr 1fr">
        <div class="val-card"><div class="lbl">BASE THROTTLE</div><div class="val" id="v-base-throt">0.150</div></div>
        <div class="val-card"><div class="lbl">LỆNH GA GỬI ĐỘNG CƠ</div><div class="val" id="v-throt-out" style="color:var(--green)">+0.150</div></div>
      </div>
    </div>

    <!-- 3. SHARP TURN DETECTION -->
    <div class="card">
      <div class="card-header">
        <div class="card-title"><span class="num">3</span> Sharp Turn Detection — Phát hiện góc 90°</div>
        <div id="v-turn-verdict" class="pill pill-idle">THẲNG</div>
      </div>
      <div class="formula-box">
        left_score = 0.65 × bot_left + 0.35 × top_left<br>
        right_score = 0.65 × bot_right + 0.35 × top_right
      </div>

      <div class="roi-diagram">
        <div class="roi-zone">TRÊN TRÁI (40%-80%)<b id="v-top-left">--</b></div>
        <div class="roi-zone">TRÊN PHẢI (40%-80%)<b id="v-top-right">--</b></div>
        <div class="roi-zone">DƯỚI TRÁI (0%-60%)<b id="v-bot-left">--</b></div>
        <div class="roi-zone">DƯỚI PHẢI (0%-60%)<b id="v-bot-right">--</b></div>
      </div>

      <div class="val-grid" style="grid-template-columns:repeat(3,1fr)">
        <div class="val-card"><div class="lbl">LEFT SCORE</div><div class="val" id="v-lscore">0.00</div></div>
        <div class="val-card"><div class="lbl">RIGHT SCORE</div><div class="val" id="v-rscore">0.00</div></div>
        <div class="val-card"><div class="lbl">CONFIDENCE</div><div class="val" id="v-conf" style="color:var(--orange)">0.00</div></div>
      </div>
    </div>

    <!-- 4. BLIND TURN STATE MACHINE -->
    <div class="card">
      <div class="card-header">
        <div class="card-title"><span class="num">4</span> Blind Turn State Machine — Cua mù 90°</div>
        <div id="v-blind-enable" class="pill pill-idle">OFF</div>
      </div>

      <div class="flowchart">
        <div id="node-pid" class="flow-node active">1. PID TRACKING<br>(Đường thẳng/cong)</div>
        <div id="node-blind" class="flow-node">2. BLIND TURN<br>(Khóa lái ±1.0)</div>
        <div id="node-stop" class="flow-node">3. SAFETY STOP<br>(Dừng an toàn)</div>
      </div>

      <div class="val-grid" style="grid-template-columns:1fr 1fr">
        <div class="val-card"><div class="lbl">TRẠNG THÁI CUA MÙ</div><div class="val" id="v-blind-state">INACTIVE</div></div>
        <div class="val-card"><div class="lbl">TIMER CUA MÙ</div><div class="val" id="v-blind-timer">0.0s / 2.0s</div></div>
      </div>
    </div>

  </section>
</main>

<script>
(function(){
  var MAX_HIST = 600, WINDOW = 15.0, POLL_MS = 200, STALE_MS = 2500;
  var hist = [], lastOk = 0;

  function el(id){ return document.getElementById(id); }
  function finite(v){ return v !== null && v !== undefined && isFinite(v); }
  function fmt(v, d){
    d = d || 3;
    if (!finite(v)) return "--";
    var s = v.toFixed(d);
    return (v >= 0 ? "+" : "") + s;
  }
  function fmtUptime(s){
    if (!finite(s)) return "--";
    s = Math.floor(s);
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
    return (h > 0 ? h + ":" : "") + ("0" + m).slice(-2) + ":" + ("0" + x).slice(-2);
  }

  function renderValues(m){
    // Status Pill
    var pill = el("status-pill");
    var st = (m.status || "").toLowerCase();
    pill.className = "pill";
    if (st.indexOf("ok") >= 0){ pill.textContent = "LINE OK"; pill.classList.add("pill-ok"); }
    else if (st.indexOf("turn") >= 0){ pill.textContent = "SHARP TURN"; pill.classList.add("pill-turn"); }
    else { pill.textContent = "LINE LOST"; pill.classList.add("pill-lost"); }

    el("v-uptime").textContent = fmtUptime(m.uptime_s);
    el("v-fps").textContent = finite(m.fps) ? m.fps.toFixed(1) : "--";
    el("v-hz").textContent = finite(m.loop_hz) ? m.loop_hz.toFixed(1) : "--";

    // 1. PID Controller
    var err = m.error;
    el("v-error").textContent = fmt(err, 3);
    var gErr = el("g-error");
    if (finite(err)){
      var pct = Math.min(1.0, Math.max(-1.0, err));
      if (pct >= 0){
        gErr.style.left = "50%";
        gErr.style.width = (pct * 50) + "%";
        gErr.style.background = "var(--blue)";
      }else{
        gErr.style.left = (50 + pct * 50) + "%";
        gErr.style.width = (-pct * 50) + "%";
        gErr.style.background = "var(--yellow)";
      }
    }else{
      gErr.style.width = "0%";
    }

    el("v-p").textContent = fmt(m.p);
    el("v-i").textContent = fmt(m.i);
    el("v-d").textContent = fmt(m.d);
    el("v-steer-raw").textContent = fmt(m.steering);
    el("v-steer-smooth").textContent = fmt(m.smoothed_steering || m.steering);

    el("v-kp").textContent = finite(m.kp) ? m.kp.toFixed(2) : "--";
    el("v-ki").textContent = finite(m.ki) ? m.ki.toFixed(2) : "--";
    el("v-kd").textContent = finite(m.kd) ? m.kd.toFixed(2) : "--";
    el("v-deadzone").textContent = finite(m.error_deadzone) ? m.error_deadzone.toFixed(2) : "--";

    // 2. Dynamic Throttle
    var errAbs = finite(err) ? Math.abs(err) : 0.0;
    var scale = Math.max(0.0, 1.0 - errAbs);
    el("v-throt-scale").textContent = (scale * 100).toFixed(0) + "%";
    el("g-throt-scale").style.width = (scale * 100) + "%";
    el("v-base-throt").textContent = finite(m.base_throttle) ? m.base_throttle.toFixed(3) : "--";
    el("v-throt-out").textContent = fmt(m.throttle);

    var thBadge = el("v-throt-badge");
    if (scale > 0.85){
      thBadge.textContent = "TỐI ĐA 100%"; thBadge.className = "pill pill-ok";
    }else{
      thBadge.textContent = "GIẢM GA (" + (scale * 100).toFixed(0) + "%)"; thBadge.className = "pill pill-turn";
    }

    // 3. Sharp Turn Detection
    var lScore = m.left_score || 0.0;
    var rScore = m.right_score || 0.0;
    var conf = m.confidence || 0.0;
    var dir = m.direction || 0;

    el("v-lscore").textContent = lScore.toFixed(2);
    el("v-rscore").textContent = rScore.toFixed(2);
    el("v-conf").textContent = (conf * 100).toFixed(0) + "%";

    var turnBadge = el("v-turn-verdict");
    if (conf > 0.15 && dir < 0){
      turnBadge.textContent = "CUA TRÁI ◄"; turnBadge.className = "pill pill-turn";
    }else if (conf > 0.15 && dir > 0){
      turnBadge.textContent = "CUA PHẢI ►"; turnBadge.className = "pill pill-turn";
    }else{
      turnBadge.textContent = "THẲNG ▲"; turnBadge.className = "pill pill-idle";
    }

    // 4. Blind Turn State Machine
    var blindEn = !!m.enable_blind_turn;
    var blindActive = !!m.blind_turn_active;
    var timer = m.blind_turn_timer || 0.0;

    var bEnPill = el("v-blind-enable");
    bEnPill.textContent = blindEn ? "ON" : "OFF";
    bEnPill.className = blindEn ? "pill pill-ok" : "pill pill-idle";

    el("v-blind-state").textContent = blindActive ? "ACTIVE" : "INACTIVE";
    el("v-blind-state").style.color = blindActive ? "var(--orange)" : "var(--dim)";
    el("v-blind-timer").textContent = timer.toFixed(1) + "s / 2.0s";

    var nPid = el("node-pid"), nBlind = el("node-blind"), nStop = el("node-stop");
    nPid.className = "flow-node"; nBlind.className = "flow-node"; nStop.className = "flow-node";

    if (st.indexOf("lost") >= 0 && !blindActive){
      nStop.className = "flow-node active-stop";
    }else if (blindActive){
      nBlind.className = "flow-node active-turn";
    }else{
      nPid.className = "flow-node active";
    }
  }

  // Chart Rendering
  var canvas = el("chart-control"), ctx = canvas.getContext("2d");
  function resizeCanvas(){
    var rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * (window.devicePixelRatio || 1);
    canvas.height = rect.height * (window.devicePixelRatio || 1);
  }
  window.addEventListener("resize", resizeCanvas);
  resizeCanvas();

  function renderChart(){
    var w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    ctx.strokeStyle = "#1e293b"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0, h/2); ctx.lineTo(w, h/2); ctx.stroke();

    if (hist.length < 2) return;
    var now = hist[hist.length - 1].ts;
    var minTs = now - WINDOW;

    function drawLine(key, color){
      ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.beginPath();
      var started = false;
      for (var i = 0; i < hist.length; i++){
        var pt = hist[i];
        if (pt.ts < minTs) continue;
        var val = pt[key];
        if (!finite(val)) continue;
        var x = ((pt.ts - minTs) / WINDOW) * w;
        var y = (h / 2) - (val * (h * 0.45));
        if (!started){ ctx.moveTo(x, y); started = true; }
        else { ctx.lineTo(x, y); }
      }
      ctx.stroke();
    }

    drawLine("error", "#eab308");
    drawLine("steering", "#38bdf8");
    drawLine("throttle", "#22c55e");
  }

  function loop(){
    renderChart();
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);

  async function poll(){
    try{
      var r = await fetch("/metrics", {cache: "no-store"});
      if (!r.ok) throw new Error("HTTP " + r.status);
      var m = await r.json();
      if (!m || typeof m.ts !== "number") throw new Error("bad payload");
      lastOk = Date.now();
      hist.push(m);
      if (hist.length > MAX_HIST) hist.shift();
      renderValues(m);
    }catch(e){}
  }
  setInterval(poll, POLL_MS);

  setInterval(function(){
    var stale = Date.now() - lastOk > STALE_MS;
    document.body.classList.toggle("offline", stale);
  }, 500);

  setInterval(function(){
    var d = new Date();
    el("v-clock").textContent = ("0" + d.getHours()).slice(-2) + ":" +
      ("0" + d.getMinutes()).slice(-2) + ":" + ("0" + d.getSeconds()).slice(-2);
  }, 1000);

  poll();
})();
</script>
</body>
</html>
"""


def dashboard_page() -> bytes:
    """Trả về nội dung trang dashboard dưới dạng bytes (UTF-8)."""
    return DASHBOARD_HTML.encode("utf-8")