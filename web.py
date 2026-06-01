from flask import Flask, jsonify, render_template_string
from service import LocalizationService

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Snur - Sound Localization</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: system-ui, sans-serif; }

        .axis-card {
            background: #1f2937;
            border-radius: 10px;
            padding: 10px 8px;
            text-align: center;
        }
        .axis-label { font-size: 0.7rem; color: #6b7280; letter-spacing: 0.1em; text-transform: uppercase; }
        .axis-value { font-family: monospace; font-size: 1.6rem; font-weight: bold; }

        .mic-row {
            display: flex; justify-content: space-between; align-items: center;
            padding: 8px 10px; border-radius: 8px; margin-bottom: 6px;
            border: 2px solid transparent;
            transition: border-color 0.2s, background 0.2s;
        }
        .mic-row.hot { border-color: #ef4444; background: rgba(239,68,68,0.07); }
        .mic-label { color: #9ca3af; font-size: 0.9rem; }

        .graph-card {
            border: 2px solid #374151; border-radius: 10px;
            padding: 8px 10px; margin-bottom: 10px; background: #111827;
            transition: border-color 0.2s;
        }
        .graph-card.hot { border-color: #ef4444; }
        .graph-header {
            display: flex; justify-content: space-between;
            font-size: 0.8rem; color: #6b7280; margin-bottom: 5px;
        }
        .graph-header .pwr { font-family: monospace; }
        canvas { display: block; width: 100%; border-radius: 4px; }
        #iso-canvas { border-radius: 8px; background: #0f172a; }

        /* ── Velocity meter ── */
        .vel-card {
            background: #111827;
            border: 2px solid #374151;
            border-radius: 10px;
            padding: 10px 14px;
            flex: 1;
        }
        .vel-label { font-size: 0.7rem; color: #6b7280; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 2px; }
        .component-row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
        .component-bar-bg { flex: 1; height: 6px; background: #1f2937; border-radius: 3px; overflow: hidden; }
        .component-bar    { height: 100%; border-radius: 3px; transition: width 0.15s, background 0.15s; }
    </style>
</head>
<body class="bg-gray-950 text-white">
<div class="max-w-7xl mx-auto p-3">
    <h1 class="text-3xl font-bold text-center mb-3">🎤 Snur — Sound Localization</h1>

    <div style="display:flex; gap:20px; align-items:flex-start;">

        <!-- LEFT: position + mic powers -->
        <div style="min-width:300px; max-width:360px; flex-shrink:0;">

            <!-- Device position card -->
            <div class="bg-gray-900 rounded-2xl p-5 shadow-xl mb-4">
                <div class="text-gray-400 text-sm text-center mb-3">Device Position</div>

                <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; margin-bottom:14px;">
                    <div class="axis-card">
                        <div class="axis-label">X</div>
                        <div id="pos-x" class="axis-value text-emerald-400">0.00</div>
                        <div class="text-gray-600" style="font-size:0.65rem;">m</div>
                    </div>
                    <div class="axis-card">
                        <div class="axis-label">Y</div>
                        <div id="pos-y" class="axis-value text-sky-400">0.00</div>
                        <div class="text-gray-600" style="font-size:0.65rem;">m</div>
                    </div>
                    <div class="axis-card">
                        <div class="axis-label">Z</div>
                        <div id="pos-z" class="axis-value text-violet-400">0.00</div>
                        <div class="text-gray-600" style="font-size:0.65rem;">m</div>
                    </div>
                </div>

                <!-- Isometric 3D canvas -->
                <canvas id="iso-canvas" height="260" style="width:100%;"></canvas>
                <div class="text-gray-600 text-center mt-2" style="font-size:0.7rem;">
                    🟢 Microphone &nbsp;·&nbsp; 🟠 Device
                </div>
            </div>

            <!-- Error -->
            <div class="bg-gray-900 rounded-2xl p-4 shadow-xl mb-4" style="width:100%;">
                <div class="text-gray-400 text-sm">
                    Localization error: <span id="error" class="font-mono text-yellow-400">0.0000</span>
                </div>
            </div>

            <!-- Velocity (moved into left column) -->
            <div class="bg-gray-900 rounded-2xl p-4 shadow-xl mb-4">
                
<h2 class="text-base font-semibold mb-3 text-gray-300">Device Velocity</h2>
<div style="display:flex; gap:14px; align-items:center;">
    <div style="width:150px; text-align:center; flex-shrink:0;">
        <canvas id="gauge-canvas" height="80" style="width:100%;"></canvas>
    </div>

    <div style="width:120px; text-align:center; flex-shrink:0;">
        <div class="vel-label">Speed</div>
        <div>
            <span id="speed-val" class="font-mono font-bold text-emerald-400" style="font-size:1.5rem;">0.000</span>
        </div>
        <div class="text-gray-500 text-xs">m/s</div>
    </div>

    <div style="width:220px; flex-shrink:0;">
        <div class="vel-label">Vx</div>
        <div class="component-row">
            <span id="vx-val" class="font-mono text-sm text-gray-300" style="width:56px;text-align:right;">0.00</span>
            <div class="component-bar-bg"><div id="vx-bar" class="component-bar"></div></div>
        </div>

        <div class="vel-label mt-2">Vy</div>
        <div class="component-row">
            <span id="vy-val" class="font-mono text-sm text-gray-300" style="width:56px;text-align:right;">0.00</span>
            <div class="component-bar-bg"><div id="vy-bar" class="component-bar"></div></div>
        </div>

        <div class="vel-label mt-2">Vz</div>
        <div class="component-row">
            <span id="vz-val" class="font-mono text-sm text-gray-300" style="width:56px;text-align:right;">0.00</span>
            <div class="component-bar-bg"><div id="vz-bar" class="component-bar"></div></div>
        </div>
    </div>

    <div style="flex:1; min-width:0;">
        <div class="vel-label">Speed History</div>
        <canvas id="vel-canvas" height="90" style="width:100%;"></canvas>
    </div>
</div>
</div>

            <!-- Mic power rows -->
            <div class="bg-gray-900 rounded-2xl p-5 shadow-xl">
                <h2 class="text-base font-semibold mb-3 text-gray-300">Signal Power per Microphone</h2>
                <div id="powers-list"></div>
            </div>
        </div>

        <!-- RIGHT: signal graphs -->
        <div style="flex:1;">
            <div class="bg-gray-900 rounded-2xl p-5 shadow-xl">
                <h2 class="text-base font-semibold mb-4 text-gray-300">Signal Intensity Over Time</h2>
                <div id="graphs"></div>
            </div>
        </div>
    </div>

    <p class="text-center text-gray-600 text-sm mt-5">Updates every 200 ms</p>

    </div>

<script>
// ── Constants ────────────────────────────────────────────────────────────
const BUFFER_SIZE = 80;
let freqBands    = null;
let micPos3D     = null;
let searchBounds = null;
const buffers    = [];
let devicePos    = [0, 0, 0];

// ── Velocity state ───────────────────────────────────────────────────────
let prevPos      = null;
let prevTime     = null;
let smoothSpeed  = 0;          // EMA-smoothed speed
let smoothVx = 0, smoothVy = 0, smoothVz = 0;
const speedBuffer = [];        // rolling history for graph
const VEL_ALPHA   = 0.25;      // EMA smoothing factor (lower = smoother)

// ── Isometric 3D canvas ──────────────────────────────────────────────────
const C30 = Math.cos(Math.PI / 6);
const S30 = Math.sin(Math.PI / 6);

function isoProject(wx, wy, wz, cx, cy, scale) {
    return {
        x: cx + (wx - wz) * C30 * scale,
        y: cy + ((wx + wz) * S30 - wy) * scale
    };
}

function drawIso(canvas, mics, device, bounds) {
    const W = canvas.offsetWidth || 280;
    if (canvas.width !== W) canvas.width = W;
    const H   = canvas.height;
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, W, H);

    const [xmin,xmax,ymin,ymax,zmin,zmax] = bounds;
    const scale = Math.min(W * 0.26, 88);
    const cx = W * 0.5, cy = H * 0.63;

    function n(v, lo, hi) { return (v - lo) / (hi - lo); }
    function proj(wx, wy, wz) {
        return isoProject(n(wx,xmin,xmax), n(wy,ymin,ymax), n(wz,zmin,zmax), cx, cy, scale);
    }

    // Bounding box
    const corners = [
        [0,0,0],[1,0,0],[1,1,0],[0,1,0],
        [0,0,1],[1,0,1],[1,1,1],[0,1,1],
    ].map(([x,y,z]) => isoProject(x, y, z, cx, cy, scale));

    ctx.strokeStyle = '#1e3a5f'; ctx.lineWidth = 1;
    [[0,3],[3,2],[0,4],[3,7],[2,6]].forEach(([a,b]) => {
        ctx.beginPath(); ctx.moveTo(corners[a].x, corners[a].y);
        ctx.lineTo(corners[b].x, corners[b].y); ctx.stroke();
    });
    ctx.strokeStyle = '#1e4d8c'; ctx.lineWidth = 1.5;
    [[0,1],[1,2],[4,5],[5,6],[6,7],[4,7],[1,5],[2,6]].forEach(([a,b]) => {
        ctx.beginPath(); ctx.moveTo(corners[a].x, corners[a].y);
        ctx.lineTo(corners[b].x, corners[b].y); ctx.stroke();
    });

    // Axis labels
    ctx.font = '10px monospace';
    [['X','#4ade80',1.15,0,0],['Y','#38bdf8',0,1.15,0],['Z','#a78bfa',0,0,1.15]]
    .forEach(([label, color, lx, ly, lz]) => {
        const p = isoProject(lx, ly, lz, cx, cy, scale);
        ctx.fillStyle = color;
        ctx.fillText(label, p.x - 4, p.y + 4);
    });

    // Mic positions
    mics.forEach((m, i) => {
        const p = proj(m[0], m[1], m[2]);
        ctx.beginPath(); ctx.arc(p.x, p.y, 5, 0, Math.PI * 2);
        ctx.fillStyle = '#10b981'; ctx.fill();
        ctx.strokeStyle = '#065f46'; ctx.lineWidth = 1; ctx.stroke();
        ctx.fillStyle = '#6ee7b7'; ctx.font = '9px monospace';
        ctx.fillText('M' + (i + 1), p.x + 6, p.y - 4);
    });

    // Device shadow projections
    const dp      = proj(device[0], device[1], device[2]);
    const dpFloor = proj(device[0], ymin,      device[2]);
    const dpBack  = proj(xmin,      device[1], device[2]);
    const dpLeft  = proj(device[0], device[1], zmin);

    ctx.setLineDash([3, 3]); ctx.lineWidth = 1;
    ctx.strokeStyle = 'rgba(251,146,60,0.4)';
    [[dp, dpFloor],[dp, dpBack],[dp, dpLeft]].forEach(([a, b]) => {
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
    });
    ctx.setLineDash([]);

    // Device dot
    ctx.beginPath(); ctx.arc(dp.x, dp.y, 8, 0, Math.PI * 2);
    ctx.fillStyle = '#f97316'; ctx.fill();
    ctx.strokeStyle = '#fff7ed'; ctx.lineWidth = 1.5; ctx.stroke();
}

// ── Signal graph drawing ─────────────────────────────────────────────────
function drawGraph(canvas, buffer, hot) {
    const ctx = canvas.getContext('2d');
    const W   = canvas.offsetWidth || 300;
    const H   = canvas.height;
    if (canvas.width !== W) canvas.width = W;

    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, W, H);
    if (buffer.length < 2) return;

    const maxVal = Math.max(...buffer, 1e-7);
    const step   = W / (BUFFER_SIZE - 1);

    ctx.beginPath();
    ctx.moveTo(0, H);
    buffer.forEach((v, i) => ctx.lineTo(i * step, H - (v / maxVal) * (H - 8) - 4));
    for (let i = buffer.length; i < BUFFER_SIZE; i++) ctx.lineTo(i * step, H);
    ctx.closePath();
    ctx.fillStyle = hot ? 'rgba(239,68,68,0.12)' : 'rgba(16,185,129,0.08)';
    ctx.fill();

    ctx.beginPath();
    buffer.forEach((v, i) => {
        const x = i * step, y = H - (v / maxVal) * (H - 8) - 4;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.strokeStyle = hot ? '#ef4444' : '#10b981';
    ctx.lineWidth = 2; ctx.lineJoin = 'round'; ctx.stroke();
}

// ── Bootstrap ────────────────────────────────────────────────────────────
async function loadConfig() {
    const res  = await fetch('/api/config?_=' + Date.now());   // bust browser cache
    const data = await res.json();
    freqBands    = data.mic_freq_bands;
    micPos3D     = data.mic_positions;
    searchBounds = data.search_bounds;

    buffers.length = 0;   // clear any stale buffers before repopulating

    const list = document.getElementById('powers-list');
    list.innerHTML = '';
    freqBands.forEach((band, i) => {
        buffers.push([]);
        const row = document.createElement('div');
        row.id = 'mic-row-' + i;
        row.className = 'mic-row';
        row.innerHTML = `
            <span class="mic-label">Mic ${i + 1} &nbsp;(${band[0]}–${band[1]} Hz)</span>
            <span id="power-${i}" class="font-mono text-emerald-400 text-sm">0.0000</span>
        `;
        list.appendChild(row);
    });

    const graphs = document.getElementById('graphs');
    graphs.innerHTML = '';
    freqBands.forEach((band, i) => {
        const card = document.createElement('div');
        card.id = 'graph-card-' + i;
        card.className = 'graph-card';
        card.innerHTML = `
            <div class="graph-header">
                <span>Mic ${i + 1} &nbsp;·&nbsp; ${band[0]}–${band[1]} Hz</span>
                <span class="pwr" id="gpwr-${i}">0.0000</span>
            </div>
            <canvas id="canvas-${i}" height="70"></canvas>
        `;
        graphs.appendChild(card);
    });
}

// ── Velocity gauge (semicircle arc) ─────────────────────────────────────
function drawGauge(canvas, speed, maxSpeed) {
    const W   = canvas.offsetWidth || 200;
    if (canvas.width !== W) canvas.width = W;
    const H   = canvas.height;
    const ctx = canvas.getContext('2d');
    const cx  = W / 2, cy = H - 18;
    const r   = Math.min(cx - 6, cy - 6);

    ctx.fillStyle = '#111827';
    ctx.fillRect(0, 0, W, H);

    const startAngle = Math.PI;
    const endAngle   = 0;                       // left → right semicircle
    const frac       = Math.min(speed / maxSpeed, 1);

    // Background arc
    ctx.beginPath();
    ctx.arc(cx, cy, r, startAngle, endAngle);
    ctx.strokeStyle = '#1f2937';
    ctx.lineWidth   = 10;
    ctx.lineCap     = 'round';
    ctx.stroke();

    // Filled arc — colour shifts green → yellow → red with speed
    if (frac > 0) {
        const hue = Math.round((1 - frac) * 120);   // 120=green, 0=red
        ctx.beginPath();
        ctx.arc(cx, cy, r, startAngle, startAngle + frac * Math.PI);
        ctx.strokeStyle = `hsl(${hue},85%,52%)`;
        ctx.lineWidth   = 10;
        ctx.lineCap     = 'round';
        ctx.stroke();
    }

    // Tick marks
    ctx.lineWidth = 1.5;
    for (let t = 0; t <= 10; t++) {
        const a     = Math.PI + (t / 10) * Math.PI;
        const inner = t % 5 === 0 ? r - 18 : r - 12;
        ctx.strokeStyle = t % 5 === 0 ? '#6b7280' : '#374151';
        ctx.beginPath();
        ctx.moveTo(cx + Math.cos(a) * (r - 2), cy + Math.sin(a) * (r - 2));
        ctx.lineTo(cx + Math.cos(a) * inner,   cy + Math.sin(a) * inner);
        ctx.stroke();
    }

    // Max speed label
    ctx.fillStyle = '#4b5563';
    ctx.font = '9px monospace';
    ctx.textAlign = 'right';
    ctx.fillText(maxSpeed.toFixed(1), cx + r - 2, cy + 14);
    ctx.textAlign = 'left';
    ctx.fillText('0', cx - r + 2, cy + 14);
    ctx.textAlign = 'center';
}

// ── Speed history line graph ─────────────────────────────────────────────
function drawSpeedGraph(canvas, buffer) {
    const ctx = canvas.getContext('2d');
    const W   = canvas.offsetWidth || 300;
    const H   = canvas.height;
    if (canvas.width !== W) canvas.width = W;

    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, W, H);
    if (buffer.length < 2) return;

    const maxVal = Math.max(...buffer, 0.01);
    const step   = W / (BUFFER_SIZE - 1);

    // Filled area
    ctx.beginPath();
    ctx.moveTo(0, H);
    buffer.forEach((v, i) => ctx.lineTo(i * step, H - (v / maxVal) * (H - 6) - 3));
    for (let i = buffer.length; i < BUFFER_SIZE; i++) ctx.lineTo(i * step, H);
    ctx.closePath();
    ctx.fillStyle = 'rgba(251,146,60,0.12)';
    ctx.fill();

    // Line — colour by current speed fraction
    const frac = buffer[buffer.length - 1] / maxVal;
    const hue  = Math.round((1 - frac) * 120);
    ctx.beginPath();
    buffer.forEach((v, i) => {
        const x = i * step, y = H - (v / maxVal) * (H - 6) - 3;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.strokeStyle = `hsl(${hue},85%,52%)`;
    ctx.lineWidth = 2;
    ctx.lineJoin  = 'round';
    ctx.stroke();
}

// ── Component bar helper ─────────────────────────────────────────────────
function updateComponentBar(barId, valId, v, maxV) {
    const pct  = Math.min(Math.abs(v) / maxV * 100, 100);
    const hue  = v >= 0 ? 210 : 0;       // blue = positive, red = negative
    const bar  = document.getElementById(barId);
    const val  = document.getElementById(valId);
    if (bar) { bar.style.width = pct + '%'; bar.style.background = `hsl(${hue},75%,52%)`; }
    if (val) { val.textContent = v.toFixed(2); val.style.color = v >= 0 ? '#93c5fd' : '#fca5a5'; }
}

async function updateUI() {
    const res  = await fetch('/api/status');
    const data = await res.json();

    const [px, py, pz] = data.position;
    devicePos = data.position;
    document.getElementById('pos-x').textContent = px.toFixed(2);
    document.getElementById('pos-y').textContent = py.toFixed(2);
    document.getElementById('pos-z').textContent = pz.toFixed(2);
    document.getElementById('error').textContent  = data.error.toFixed(4);

    // ── Velocity calculation ─────────────────────────────────────────────
    const now = Date.now();
    if (prevPos && prevTime) {
        const dt = Math.max((now - prevTime) / 1000, 0.001);
        const rawVx = (px - prevPos[0]) / dt;
        const rawVy = (py - prevPos[1]) / dt;
        const rawVz = (pz - prevPos[2]) / dt;
        const rawSpeed = Math.sqrt(rawVx*rawVx + rawVy*rawVy + rawVz*rawVz);

        // Exponential moving average smoothing
        smoothVx    = VEL_ALPHA * rawVx    + (1 - VEL_ALPHA) * smoothVx;
        smoothVy    = VEL_ALPHA * rawVy    + (1 - VEL_ALPHA) * smoothVy;
        smoothVz    = VEL_ALPHA * rawVz    + (1 - VEL_ALPHA) * smoothVz;
        smoothSpeed = VEL_ALPHA * rawSpeed + (1 - VEL_ALPHA) * smoothSpeed;
    }
    prevPos  = [px, py, pz];
    prevTime = now;

    speedBuffer.push(smoothSpeed);
    if (speedBuffer.length > BUFFER_SIZE) speedBuffer.shift();

    // Max scale: peak of recent history, min 1 m/s
    const maxSpeed = Math.max(...speedBuffer, 1.0);

    // Gauge
    const gauge = document.getElementById('gauge-canvas');
    if (gauge) drawGauge(gauge, smoothSpeed, maxSpeed);

    // Speed value — colour matches gauge hue
    const speedEl = document.getElementById('speed-val');
    if (speedEl) {
        const frac = Math.min(smoothSpeed / maxSpeed, 1);
        const hue  = Math.round((1 - frac) * 120);
        speedEl.textContent  = smoothSpeed.toFixed(3);
        speedEl.style.color  = `hsl(${hue},85%,52%)`;
    }

    // Component bars
    const maxComp = Math.max(Math.abs(smoothVx), Math.abs(smoothVy), Math.abs(smoothVz), 0.01);
    updateComponentBar('vx-bar', 'vx-val', smoothVx, maxComp);
    updateComponentBar('vy-bar', 'vy-val', smoothVy, maxComp);
    updateComponentBar('vz-bar', 'vz-val', smoothVz, maxComp);

    // Speed history graph
    const velCv = document.getElementById('vel-canvas');
    if (velCv) drawSpeedGraph(velCv, speedBuffer);

    if (micPos3D && searchBounds) {
        drawIso(document.getElementById('iso-canvas'), micPos3D, devicePos, searchBounds);
    }

    if (!freqBands) return;
    const powers = data.powers;
    const avg    = powers.reduce((a, b) => a + b, 0) / powers.length;

    powers.forEach((p, i) => {
        const hot = p > avg;
        buffers[i].push(p);
        if (buffers[i].length > BUFFER_SIZE) buffers[i].shift();

        const row  = document.getElementById('mic-row-' + i);
        const pwrEl= document.getElementById('power-' + i);
        const card = document.getElementById('graph-card-' + i);
        const gpwr = document.getElementById('gpwr-' + i);
        const cv   = document.getElementById('canvas-' + i);

        if (row)   row.className   = 'mic-row'   + (hot ? ' hot' : '');
        if (card)  card.className  = 'graph-card' + (hot ? ' hot' : '');
        if (pwrEl) { pwrEl.textContent = p.toFixed(4); pwrEl.style.color = hot ? '#ef4444' : '#10b981'; }
        if (gpwr)  { gpwr.textContent  = p.toFixed(4); gpwr.style.color  = hot ? '#ef4444' : '#6b7280'; }
        if (cv)    drawGraph(cv, buffers[i], hot);
    });
}

loadConfig()
    .then(() => { setInterval(updateUI, 200); updateUI(); })
    .catch(e => console.error('Init error:', e));
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/status')
def status():
    return jsonify(service.get_latest())

@app.route('/api/config')
def config():
    return jsonify({
        "mic_freq_bands": service.config.mic_freq_bands,
        "channels":       service.config.channels,
        "mic_positions":  service.config.mic_positions,
        "search_bounds":  service.config.search_bounds,
    })

def start_web(service_instance: LocalizationService, host="0.0.0.0", port=8080):
    global service
    service = service_instance
    print(f"🌐 Web server starting on http://{host}:{port}")
    app.run(host=host, port=port, debug=False)
