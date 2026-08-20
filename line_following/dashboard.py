"""Dashboard debug trực quan cho pilot (Line Following).

Trang web tự chứa (không cần CDN / internet trên Jetson) hiển thị:

    - Luồng video MJPEG + overlay từ DebugStreamer (route ``/``).
    - Toàn bộ chỉ số telemetry realtime: error, steering, throttle,
      P/I/D, tần số vòng lặp, fps, dt, frame đếm, cua gấp...
    - Đồ thị cuộn theo thời gian (canvas) và thanh gauge trực quan.

Mở trình duyệt tại ``http://<ip-jetson>:5001/dashboard`` khi pilot đang chạy.
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>Pilot Debug Dashboard</title>
<style>
:root{
  --bg:#0b1220; --panel:#101a30; --panel2:#0d1628; --border:#1e2a44;
  --text:#c9d4ee; --dim:#6f7f9f; --green:#22c55e; --red:#ef4444;
  --blue:#38bdf8; --yellow:#eab308; --orange:#f97316;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{
  background:var(--bg);color:var(--text);
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  font-size:13px;padding:10px;
}
header{
  display:flex;align-items:center;gap:14px;flex-wrap:wrap;
  padding:8px 12px;background:var(--panel);border:1px solid var(--border);
  border-radius:10px;margin-bottom:10px;
}
.brand{font-size:15px;font-weight:700;letter-spacing:1px}
.brand span{color:var(--yellow)}
.hmeta{margin-left:auto;display:flex;gap:14px;color:var(--dim)}
.hmeta b{color:var(--text);font-weight:600}
.pill{
  padding:5px 14px;border-radius:999px;font-weight:700;font-size:12px;
  letter-spacing:1px;border:1px solid var(--border);background:var(--panel2);
}
.pill-idle{color:var(--dim)}
.pill-ok{background:rgba(34,197,94,.12);color:var(--green);border-color:rgba(34,197,94,.45)}
.pill-turn{background:rgba(249,115,22,.12);color:var(--orange);border-color:rgba(249,115,22,.45)}
.pill-lost{background:rgba(239,68,68,.12);color:var(--red);border-color:rgba(239,68,68,.45)}
#conn-banner{
  display:none;position:fixed;top:8px;left:50%;transform:translateX(-50%);
  background:rgba(239,68,68,.15);border:1px solid var(--red);color:var(--red);
  padding:8px 18px;border-radius:8px;font-weight:700;z-index:9;letter-spacing:.5px;
}
body.offline #conn-banner{display:block}
body.offline .video-card img{opacity:.35}
main{
  display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:10px;
  align-items:start;
}
@media (max-width:1100px){main{grid-template-columns:1fr}}
.card{
  background:var(--panel);border:1px solid var(--border);border-radius:10px;
  padding:10px;margin-bottom:10px;
}
.card-title{
  font-size:11px;font-weight:700;letter-spacing:1.5px;color:var(--dim);
  text-transform:uppercase;margin-bottom:8px;
}
.card-title .hint{color:#46536e;letter-spacing:0;text-transform:none;font-weight:400}
.video-card img{width:100%;display:block;border-radius:6px;background:#000}
.chart-head{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:6px}
.legend{font-size:11px;color:var(--dim);display:flex;gap:10px;align-items:center}
.legend i{display:inline-block;width:10px;height:3px;margin-right:4px;vertical-align:middle;border-radius:2px}
canvas{width:100%;height:150px;display:block}
#chart-pid{height:120px}
.grid-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.small{grid-column:span 3}
.card .stat{background:var(--panel2);border:1px solid var(--border);border-radius:8px;padding:8px 10px}
.stat .k{font-size:10px;color:var(--dim);letter-spacing:1px;text-transform:uppercase;margin-bottom:3px}
.stat .v{font-size:17px;font-weight:700;white-space:nowrap}
.stat .v.sub{font-size:12px;font-weight:600;color:var(--dim)}
.v-pos{color:var(--green)}
.gauge{margin-bottom:12px}
.gauge .g-label{
  display:flex;justify-content:space-between;font-size:10px;letter-spacing:1px;
  color:var(--dim);text-transform:uppercase;margin-bottom:4px;
}
.g-track{
  position:relative;height:14px;background:#0a1230;border:1px solid var(--border);
  border-radius:7px;overflow:hidden;
}
.g-zero{position:absolute;left:50%;top:0;bottom:0;width:2px;background:#5b6b8f;z-index:2}
.g-fill{position:absolute;top:0;bottom:0;left:50%;width:0;background:#38bdf8;transition:width .12s linear,left .12s linear}
.g-val{font-size:12px;color:var(--dim);margin-top:3px;font-weight:600}
.hr{border:none;border-top:1px solid var(--border);margin:10px 0}
</style>
</head>
<body>
<div id="conn-banner">MẤT KẾT NỐI VỚI PILOT — kiểm tra pilot còn chạy không</div>

<header>
  <div class="brand">PILOT <span>DEBUG DASHBOARD</span></div>
  <div id="status-pill" class="pill pill-idle">--</div>
  <div class="hmeta">
    <span>UPTIME <b id="v-uptime">--</b></span>
    <span id="v-clock">--:--:--</span>
  </div>
</header>

<main>
  <section class="col-left">
    <div class="card video-card">
      <div class="card-title">Camera CSI + Overlay <span class="hint">— MJPEG realtime</span></div>
      <img id="stream" src="/" alt="camera stream">
    </div>
    <div class="card">
      <div class="chart-head">
        <span class="chart-title card-title">Điều khiển (15s)</span>
        <span class="legend">
          <i style="background:var(--yellow)"></i>error
          <i style="background:var(--blue)"></i>steering
          <i style="background:var(--green)"></i>throttle
        </span>
      </div>
      <canvas id="chart-control"></canvas>
    </div>
    <div class="card">
      <div class="chart-head">
        <span class="chart-title card-title">PID terms (15s)</span>
        <span class="legend">
          <i style="background:#f87171"></i>P
          <i style="background:#fb923c"></i>I
          <i style="background:#c084fc"></i>D
        </span>
      </div>
      <canvas id="chart-pid"></canvas>
    </div>
  </section>

  <section class="col-right">
    <div class="card">
      <div class="card-title">Gauges</div>
      <div class="gauge">
        <div class="g-label"><span>ERROR (lệch tâm)</span><span id="v-error-g">--</span></div>
        <div class="g-track"><div class="g-zero"></div><div class="g-fill" id="g-error"></div></div>
      </div>
      <div class="gauge">
        <div class="g-label"><span>STEERING (góc lái)</span><span id="v-steer-g">--</span></div>
        <div class="g-track"><div class="g-zero"></div><div class="g-fill" id="g-steer"></div></div>
      </div>
      <div class="gauge">
        <div class="g-label"><span>THROTTLE (ga)</span><span id="v-throt-g">--</span></div>
        <div class="g-track"><div class="g-fill" id="g-throt"></div></div>
      </div>
      <hr class="hr">
      <div class="grid-stats">
        <div class="stat"><div class="k">loop</div><div class="v" id="v-loop">--</div></div>
        <div class="stat"><div class="k">loop avg</div><div class="v" id="v-loop-avg">--</div></div>
        <div class="stat"><div class="k">fps</div><div class="v" id="v-fps">--</div></div>
        <div class="stat"><div class="k">dt</div><div class="v" id="v-dt">--</div></div>
        <div class="stat"><div class="k">frames</div><div class="v" id="v-frames">--</div></div>
        <div class="stat"><div class="k">line hits</div><div class="v" id="v-hits">--</div></div>
        <div class="stat"><div class="k">empty frame</div><div class="v" id="v-empty">--</div></div>
        <div class="stat"><div class="k">direction</div><div class="v" id="v-dir">--</div></div>
        <div class="stat"><div class="k">confidence</div><div class="v" id="v-conf">--</div></div>
        <div class="stat"><div class="k">P</div><div class="v" id="v-p">--</div></div>
        <div class="stat"><div class="k">I</div><div class="v" id="v-i">--</div></div>
        <div class="stat"><div class="k">D</div><div class="v" id="v-d">--</div></div>
        <div class="stat"><div class="k">Kp</div><div class="v sub" id="v-kp">--</div></div>
        <div class="stat"><div class="k">Ki</div><div class="v sub" id="v-ki">--</div></div>
        <div class="stat"><div class="k">Kd</div><div class="v sub" id="v-kd">--</div></div>
        <div class="stat small">
          <div class="k">base throttle</div>
          <div class="v" id="v-base">--</div>
        </div>
      </div>
    </div>
  </section>
</main>

<script>
(function(){
  var MAX_HIST = 600, WINDOW = 15.0, POLL_MS = 250, STALE_MS = 2500;
  var hist = [], last = null, lastOk = 0;

  function el(id){ return document.getElementById(id); }
  function finite(v){ return v !== null && v !== undefined && isFinite(v); }
  function fmt(v, d){
    d = d || 3;
    if (!finite(v)) return "--";
    var s = v.toFixed(d);
    return (v >= 0 ? "+" : "") + s;
  }
  function fmtHz(v){ return finite(v) ? v.toFixed(1) : "--"; }
  function fmtInt(v){ return finite(v) ? String(Math.round(v)) : "--"; }
  function fmtUptime(s){
    if (!finite(s)) return "--";
    s = Math.floor(s);
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
    m = h > 0 ? ("0" + m).slice(-2) : m;
    return (h > 0 ? h + ":" : "") + m + ":" + ("0" + x).slice(-2);
  }
  function avg(key, n){
    var a = hist.slice(-(n || 60)), s = 0, c = 0;
    for (var i = 0; i < a.length; i++){
      if (finite(a[i][key])) { s += a[i][key]; c++; }
    }
    return c ? s / c : null;
  }

  function setCenterGauge(id, v){
    var fill = el(id), ok = finite(v);
    var a = ok ? Math.min(1, Math.abs(v)) : 0;
    var w = a * 50;
    fill.style.width = w.toFixed(1) + "%";
    fill.style.left = (50 - (v < 0 ? w : 0)).toFixed(1) + "%";
    var c = "#334155";
    if (ok){ c = a >= 0.95 ? "#ef4444" : (a >= 0.5 ? "#f97316" : "#38bdf8"); }
    fill.style.background = c;
  }
  function setLeftGauge(id, v, scale){
    var fill = el(id), ok = finite(v);
    var a = ok ? Math.max(0, Math.min(1, v / scale)) : 0;
    fill.style.width = (a * 100).toFixed(1) + "%";
    fill.style.left = "0%";
    fill.style.background = ok ? "#22c55e" : "#334155";
  }

  function renderValues(m){
    el("v-error-g").textContent = fmt(m.error);
    el("v-steer-g").textContent = fmt(m.steering);
    el("v-throt-g").textContent = fmt(m.throttle);
    setCenterGauge("g-error", m.error);
    setCenterGauge("g-steer", m.steering);
    var scale = Math.max(0.5, finite(m.base_throttle) ? m.base_throttle * 1.25 : 0.5);
    setLeftGauge("g-throt", m.throttle, scale);
    el("v-loop").textContent = fmtHz(m.loop_hz) + " Hz";
    el("v-loop-avg").textContent = fmtHz(avg("loop_hz")) + " Hz";
    el("v-fps").textContent = fmtHz(m.fps) + " fps";
    el("v-dt").textContent = finite(m.dt_ms) ? m.dt_ms.toFixed(0) + " ms" : "--";
    el("v-frames").textContent = fmtInt(m.frames);
    el("v-hits").textContent = fmtInt(m.line_hits);
    el("v-empty").textContent = fmtInt(m.empty_frames);
    el("v-dir").textContent = !finite(m.direction) || m.direction === 0 ? "--" : (m.direction < 0 ? "TRÁI" : "PHẢI");
    el("v-conf").textContent = finite(m.confidence) ? m.confidence.toFixed(2) : "--";
    el("v-p").textContent = fmt(m.p);
    el("v-i").textContent = fmt(m.i);
    el("v-d").textContent = fmt(m.d);
    el("v-kp").textContent = finite(m.kp) ? m.kp.toFixed(2) : "--";
    el("v-ki").textContent = finite(m.ki) ? m.ki.toFixed(2) : "--";
    el("v-kd").textContent = finite(m.kd) ? m.kd.toFixed(2) : "--";
    el("v-base").textContent = finite(m.base_throttle) ? m.base_throttle.toFixed(3) : "--";
    el("v-uptime").textContent = fmtUptime(m.uptime_s);

    var pill = el("status-pill"), txt = "--", cls = "pill-idle";
    if (m.status === "line_ok"){ txt = "LINE OK"; cls = "pill-ok"; }
    else if (m.status === "sharp_turn"){ txt = "CUA " + (m.direction < 0 ? "TRÁI" : "PHẢI"); cls = "pill-turn"; }
    else if (m.status === "line_lost"){ txt = "LINE LOST"; cls = "pill-lost"; }
    pill.textContent = txt;
    pill.className = "pill " + cls;
  }

  function drawChart(cv, series, ymin, ymax){
    var dpr = window.devicePixelRatio || 1;
    var W = cv.clientWidth, H = cv.clientHeight;
    if (!W || !H || !hist.length || !last) return;
    var pw = Math.round(W * dpr), ph = Math.round(H * dpr);
    if (cv.width !== pw || cv.height !== ph){ cv.width = pw; cv.height = ph; }
    var ctx = cv.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = "#0d172e";
    ctx.fillRect(0, 0, W, H);

    var tEnd = last.ts, tStart = tEnd - WINDOW;
    function ypx(v){ return H - 4 - ((v - ymin) / (ymax - ymin)) * (H - 8); }
    function xpx(t){ return ((t - tStart) / WINDOW) * W; }

    ctx.font = "10px monospace";
    for (var g = Math.ceil(ymin * 2) / 2; g <= ymax; g += 0.5){
      var gy = ypx(g);
      ctx.strokeStyle = g === 0 ? "#39455f" : "#1c2740";
      ctx.lineWidth = g === 0 ? 1.5 : 1;
      ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(W, gy); ctx.stroke();
      ctx.fillStyle = "#51608a";
      ctx.fillText(String(g), 4, gy - 3);
    }

    for (var s = 0; s < series.length; s++){
      var ser = series[s];
      ctx.strokeStyle = ser.color;
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      var pen = false;
      for (var k = 0; k < hist.length; k++){
        var p = hist[k];
        if (p.ts < tStart) continue;
        var v = p[ser.key];
        if (!finite(v)){ pen = false; continue; }
        var x = xpx(p.ts), y = ypx(v);
        if (!pen){ ctx.moveTo(x, y); pen = true; }
        else { ctx.lineTo(x, y); }
      }
      ctx.stroke();
    }

    var lx = xpx(tEnd);
    ctx.strokeStyle = "#39455f";
    ctx.beginPath(); ctx.moveTo(lx, 0); ctx.lineTo(lx, H); ctx.stroke();
    ctx.fillStyle = "#51608a";
    ctx.fillText(WINDOW + "s", W - 26, H - 6);
  }

  var CTRL = [
    {key: "error", color: "#eab308"},
    {key: "steering", color: "#38bdf8"},
    {key: "throttle", color: "#22c55e"}
  ];
  var PID = [
    {key: "p", color: "#f87171"},
    {key: "i", color: "#fb923c"},
    {key: "d", color: "#c084fc"}
  ];

  function loop(){
    drawChart(el("chart-control"), CTRL, -1.0, 1.0);
    drawChart(el("chart-pid"), PID, -1.5, 1.5);
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);

  async function poll(){
    try{
      var r = await fetch("/metrics", {cache: "no-store"});
      if (!r.ok) throw new Error("HTTP " + r.status);
      var m = await r.json();
      if (!m || typeof m.ts !== "number") throw new Error("bad payload");
      last = m;
      lastOk = Date.now();
      hist.push(m);
      if (hist.length > MAX_HIST) hist.shift();
      renderValues(m);
    }catch(e){ /* chờ lần poll kế tiếp */ }
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