"""Build hexapod-reachability.html: where can we do ~30 cm surges, and how fast?

Inputs (output/reachability/ by default):
  imitator.json   hexapod-envelope against the M10 motion imitator (paused probe)
  schematic.json  hexapod-envelope --synthetic (our schematic geometry)
  robot.json      optional: hexapod-envelope against the real controller
  dynamics.json / dynamics.csv   hexapod-dynamics (M10 imitator only)

Run: uv run hexapod-reachability-report
"""
from __future__ import annotations

import argparse
import base64
import csv
import html
import io
import json
from pathlib import Path

import numpy as np

STROKE_MM = 300.0
MARGIN_MM = 25.0  # each end, for "300 mm fits comfortably"
SPEC = {"surge_v": 680.0, "surge_a_g": 0.66, "sway_v": 700.0, "sway_a_g": 0.5,
        "home_surge": (-306.0, 273.1), "home_sway": (-265.3, 265.3)}  # tech sheet p.2


def load(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def fits(h, need):
    return h["surge_max"] - h["surge_min"] >= need


def min_time(distance_mm, v_max, a_max_g):
    """Fastest move at the spec limits: bang-coast-bang, and the smoothstep (S-curve) we use."""
    a = a_max_g * 9810.0
    t_acc = v_max / a
    trapezoid = (2 * np.sqrt(distance_mm / a) if distance_mm < v_max * t_acc
                 else distance_mm / v_max + t_acc)
    smooth = max(1.875 * distance_mm / v_max, np.sqrt(5.7735 * distance_mm / a))
    return trapezoid, smooth


def png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    return base64.b64encode(buf.getvalue()).decode()


def dynamics_plots(csv_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = list(csv.DictReader(csv_path.open()))
    by = {}
    for r in rows:
        by.setdefault(r["test"], []).append(r)
    get = lambda name, col: np.array([float(r[col]) for r in by.get(name, [])])

    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    for name in [n for n in by if n.startswith("step") and n.endswith("fwd")] + \
                [n for n in by if n.startswith("maxspeed") and n.endswith("fwd")]:
        ax[0].plot(get(name, "test_time_s"), get(name, "surge_mm"), lw=1.2, alpha=.8, label=name.replace(" fwd", ""))
    ax[0].axhline(133.3, color="#888", ls=":", lw=1)
    ax[0].set_xlim(0, 0.6); ax[0].set_xlabel("time after the setpoint jump (s)"); ax[0].set_ylabel("reported surge (mm)")
    ax[0].set_title("Instant 300 mm step: every profile and maxSpeed is identical", fontsize=10)
    ax[0].legend(fontsize=7, ncol=2); ax[0].grid(alpha=.3)
    colors = {"1": "#2a6fdb", "0.7": "#e67e22", "0.5": "#c0392b"}
    for d, c in colors.items():
        name = f"smooth {d}s fwd"
        if name in by:
            ax[1].plot(get(name, "test_time_s"), get(name, "cmd_surge_mm"), ":", color=c, lw=1.5)
            ax[1].plot(get(name, "test_time_s"), get(name, "surge_mm"), color=c, lw=1.3, label=f"{d} s move")
    ax[1].set_xlim(0, 1.3); ax[1].set_xlabel("time (s)"); ax[1].set_ylabel("surge (mm)")
    ax[1].set_title("Streamed smooth 300 mm moves (dotted = command)", fontsize=10)
    ax[1].legend(fontsize=8); ax[1].grid(alpha=.3)
    fig.tight_layout()
    steps_png = png(fig)
    plt.close(fig)

    name = "smooth 1s back"
    fig, ax = plt.subplots(figsize=(11, 3.2))
    if name in by:
        t = get(name, "test_time_s")
        ax.plot(t, get(name, "cmd_surge_mm"), ":", lw=1.5, label="command")
        ax.plot(t, get(name, "surge_mm"), lw=1.3, label="reported")
        gaps = np.flatnonzero(np.diff(t) > 0.02)
        for g in gaps:
            ax.axvspan(t[g], t[g + 1], color="#c0392b", alpha=.18, lw=0)
            ax.annotate(f"{(t[g + 1] - t[g]) * 1000:.0f} ms Windows stall", (t[g + 1], get(name, "surge_mm")[g + 1]),
                        textcoords="offset points", xytext=(10, -14), fontsize=8, color="#c0392b")
    ax.set_xlim(0, 1.4); ax.set_xlabel("time (s)"); ax.set_ylabel("surge (mm)"); ax.grid(alpha=.3); ax.legend(fontsize=8)
    ax.set_title("A sender stall during a 1 s move: the command freezes, then jumps; the platform races to catch up",
                 fontsize=10)
    fig.tight_layout()
    stall_png = png(fig)
    plt.close(fig)
    return steps_png, stall_png


def slim(data, label, key):
    """Only what the page script needs."""
    return {"key": key, "label": label, "source": data["source"], "date": data["date"],
            "angles": data["directions_deg"],
            "heights": [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in h.items()}
                        for h in data["heights"]]}


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hexapod Reachability</title>
<style>
:root{--bg:#fbfaf7;--fg:#1d1d1f;--muted:#66666c;--line:#dedbd3;--panel:#fff;--soft:#f3f1ec;
 --imitator:#2a6fdb;--schematic:#8e6bd1;--robot:#16a085;--accent:#d35400;--ok:#1e8449;--bad:#b03a2e;--grid:#e6e3dc}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#14161a;--fg:#e8e8ea;--muted:#9a9aa2;
 --line:#2e3138;--panel:#1b1e23;--soft:#22262c;--imitator:#5b9bff;--schematic:#b493f0;--robot:#3fd0a8;
 --accent:#ff8c42;--ok:#52c47a;--bad:#ff6b5b;--grid:#2a2e35}}
:root[data-theme="dark"]{--bg:#14161a;--fg:#e8e8ea;--muted:#9a9aa2;--line:#2e3138;--panel:#1b1e23;--soft:#22262c;
 --imitator:#5b9bff;--schematic:#b493f0;--robot:#3fd0a8;--accent:#ff8c42;--ok:#52c47a;--bad:#ff6b5b;--grid:#2a2e35}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.75rem;margin:0 0 4px} h2{font-size:1.3rem;margin:44px 0 6px} h3{font-size:1.05rem;margin:24px 0 6px}
p{max-width:78ch} .muted{color:var(--muted)} code{font-size:.88em;background:var(--soft);padding:1px 5px;border-radius:4px}
.answer{background:var(--panel);border:1px solid var(--line);border-left:5px solid var(--accent);border-radius:10px;
 padding:14px 18px;margin:18px 0}
.answer ul{margin:6px 0 0;padding-left:20px} .answer li{margin:4px 0}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px;margin:12px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 14px}
.card b{display:block} .card span{color:var(--muted);font-size:.86rem}
.viewer{display:grid;grid-template-columns:76px minmax(0,1fr) minmax(0,1fr);gap:12px;background:var(--panel);
 border:1px solid var(--line);border-radius:12px;padding:12px}
.pane{position:relative;min-width:0} .pane h3{margin:0 0 6px;font-size:.95rem;display:flex;align-items:center;gap:8px}
.swatch{width:12px;height:12px;border-radius:3px;display:inline-block}
canvas.v3d{width:100%;aspect-ratio:1/1;display:block;background:var(--soft);border-radius:8px;touch-action:none;cursor:grab}
canvas.v3d:active{cursor:grabbing}
.toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 10px}
.toolbar button{font:inherit;font-size:.86rem;padding:5px 12px;border-radius:6px;border:1px solid var(--line);
 background:var(--panel);color:var(--fg);cursor:pointer} .toolbar button:hover{border-color:var(--accent)}
.toolbar label{font-size:.86rem;color:var(--muted);display:flex;gap:6px;align-items:center}
.hslider{position:relative;height:100%;min-height:300px;user-select:none;touch-action:none}
.hslider .track{position:absolute;left:46px;top:10px;bottom:10px;width:6px;border-radius:3px;background:var(--line)}
.hslider .fill{position:absolute;left:46px;width:6px;border-radius:3px;background:var(--accent);opacity:.35}
.hslider .thumb{position:absolute;left:38px;width:22px;height:22px;margin-top:-11px;border-radius:50%;background:var(--accent);
 border:3px solid var(--panel);box-shadow:0 1px 4px rgba(0,0,0,.35);cursor:grab}
.hslider .tick{position:absolute;right:36px;font-size:.72rem;color:var(--muted);transform:translateY(-50%);font-variant-numeric:tabular-nums}
.hslider .tick::after{content:"";position:absolute;right:-10px;top:50%;width:6px;border-top:1px solid var(--muted)}
.hslider .cap{position:absolute;left:0;right:0;text-align:center;font-size:.72rem;color:var(--muted)}
.hslider:focus-visible{outline:2px solid var(--accent);outline-offset:4px;border-radius:6px}
.readout{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:8px;margin-top:10px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 12px}
.stat span{display:block;font-size:.76rem;color:var(--muted)} .stat b{font-variant-numeric:tabular-nums;font-size:1.02rem}
.side{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px;margin-top:12px}
.side svg{width:100%;height:auto;display:block} .side text{fill:var(--muted);font-size:11px}
img.plot{width:100%;border-radius:8px;border:1px solid var(--line);background:#fff}
table{border-collapse:collapse;font-variant-numeric:tabular-nums;font-size:.86rem;width:100%}
th,td{padding:5px 10px 5px 0;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left} th{color:var(--muted);font-weight:600}
tr.sel td{color:var(--accent);font-weight:650}
.scroll{overflow-x:auto} .yes{color:var(--ok);font-weight:600} .no{color:var(--bad)}
.note{font-size:.88rem;color:var(--muted)}
dl.terms{display:grid;grid-template-columns:max-content 1fr;gap:6px 16px;margin:10px 0}
dl.terms dt{font-weight:650} dl.terms dd{margin:0}
@media (max-width:860px){.viewer{grid-template-columns:70px minmax(0,1fr)} .viewer .pane:last-child{grid-column:2}}
</style></head><body><main>
<h1>Hexapod reachability</h1>
<p class="muted">PS-6TL-350 · level top frame (roll = pitch = yaw = 0) · generated __DATE__. Surge + is front, sway +
is right, heave + is up; all distances in mm from home (0, 0, 0).</p>

<div class="answer"><b>The question: if we want large surges of about 30 cm, where can we do them, and how fast?</b>
<ul>
<li><b>Where.</b> __WHERE__</li>
<li><b>How fast.</b> __HOWFAST__</li>
<li><b>What is still unmeasured.</b> __PENDING__</li>
</ul></div>

<h3>Names, because they collide</h3>
<dl class="terms">
<dt>ForceSeatMI</dt><dd><b>M</b>otion <b>I</b>nterface: the vendor's high-level SDK. Sends telemetry or poses to
ForceSeatPM, which filters, interpolates (about 250 Hz) and drives the platform. Built for games.</dd>
<dt>ForceSeatDI</dt><dd><b>D</b>irect <b>I</b>nterface: the low-level SDK we use. Talks straight to the
controller; ForceSeatPM must be closed. Licensed per controller.</dd>
<dt>ForceSeatPM</dt><dd><b>P</b>latform <b>M</b>anager: the vendor's Windows app (sliders, diagnostics, licence codes).</dd>
<dt>M10 motion imitator</dt><dd>A small USB box from the vendor that pretends to be a PS-6TL-350 controller: same
kinematics and SDK, no motors. Not an API, despite sharing the letters "MI" with ForceSeatMI.</dd>
<dt>Schematic model</dt><dd>Our own illustrative geometry (the one in the meshcat animations), with leg strokes fitted
only to the tech-sheet heave range. Independent of the vendor. Shown here to see how far a guessed geometry is off.</dd>
</dl>

<h2>1 · Reachable space: imitator vs schematic model</h2>
<p>Each shape is the set of level poses the inverse kinematics accepts: at every height, the outline of how far the top
frame can translate in sway and surge. Drag to rotate, right-drag or shift-drag to pan, scroll to zoom. Move the height
slider to highlight one slice in both views. The orange line is the surge reach at that height; the green segment is
the 300 mm stroke, centred, when it fits.</p>
<div class="toolbar">
 <button data-view="iso">3D</button><button data-view="side">Side (surge × heave)</button>
 <button data-view="front">Front (sway × heave)</button><button data-view="top">Top (sway × surge)</button>
 <label><input type="checkbox" id="sync" checked> link the two views</label>
 <label><input type="checkbox" id="shell" checked> show all slices</label>
</div>
<div class="viewer" style="grid-template-columns:76px repeat(__NPANES__,minmax(0,1fr))">
 <div class="hslider" id="hs" role="slider" tabindex="0" aria-label="Height (heave, mm)"></div>
 __PANES__
</div>
<div class="readout" id="readout"></div>
<div class="side"><svg id="sideplot" role="img" aria-label="Surge reach against height for each source"></svg>
<p class="note">Surge reach against height (level frame). Shaded bands: where each source can reach. Green: heights where
a 300 mm stroke fits with at least __MARGIN__ mm to spare at both ends (imitator). Dots: tech-sheet single-axis
surge limits at home height. Click to choose a height.</p></div>
<h3>Comparison table</h3>
<div class="scroll"><table id="tbl"></table></div>
<p class="note">__AGREEMENT__</p>

<h2>2 · How fast: the imitator at full speed, and what the low-level API offers</h2>
__DYNAMICS__

<h3>What the low-level API (ForceSeatDI) lets us control</h3>
<table>
<tr><th>Call / field</th><th style="text-align:left">What it does</th><th style="text-align:left">Matters for fast surges because</th></tr>
<tr><td><code>SendTopTablePosPhy</code></td><td style="text-align:left;white-space:normal">Position setpoint: sway, surge, heave (mm), roll, pitch, yaw (rad)</td><td style="text-align:left;white-space:normal">The only way to command motion. There is no velocity, acceleration or trajectory command: speed comes from how fast we stream setpoints.</td></tr>
<tr><td><code>maxSpeed</code></td><td style="text-align:left;white-space:normal">Speed cap, unitless 0–65535 (65535 = none)</td><td style="text-align:left;white-space:normal">The imitator ignores it; untested on the robot. Our scripts send 2000 by default; use 65535 for fast moves.</td></tr>
<tr><td><code>accelerationProfile</code></td><td style="text-align:left;white-space:normal">auto, rapid, balanced, smoothest: shape of the controller's own ramps</td><td style="text-align:left;white-space:normal">The imitator ignores it. On the robot it should change how a setpoint jump is executed.</td></tr>
<tr><td><code>strategy</code></td><td style="text-align:left;white-space:normal">FullMatch (reject unreachable poses) or BestMatch (move to the nearest reachable one)</td><td style="text-align:left;white-space:normal">FullMatch is our safety net near the limits and what the reachability probe uses.</td></tr>
<tr><td><code>pause</code></td><td style="text-align:left;white-space:normal">Freeze or release motion</td><td style="text-align:left;white-space:normal">Every paused setpoint is checked but not executed: that is how the probe maps limits without moving.</td></tr>
<tr><td><code>SendTopTableMatrixPhy</code></td><td style="text-align:left;white-space:normal">Same as the pose call, as a 4×4 transform</td><td style="text-align:left;white-space:normal">No speed difference.</td></tr>
<tr><td><code>SendActuatorsPosLog</code></td><td style="text-align:left;white-space:normal">Six raw actuator setpoints, bypassing the library's kinematics and limit checks</td><td style="text-align:left;white-space:normal">Not faster (kinematics take microseconds) and loses the safety check. Avoid.</td></tr>
<tr><td><code>GetTopTablePosPhy</code>, <code>GetActuatorsPosLog</code>, <code>GetPlatformInfo</code></td><td style="text-align:left;white-space:normal">Reported pose, actuator positions and speeds, state bits, errors</td><td style="text-align:left;white-space:normal">Our only feedback. It is computed from actuator positions, not measured on the top frame; record an accelerometer for true onset.</td></tr>
<tr><td><code>GetPerformanceCounters</code></td><td style="text-align:left;white-space:normal">Microsecond timings of every SDK call</td><td style="text-align:left;white-space:normal">The tool for measuring send latency on the robot.</td></tr>
<tr><td><code>…2</code> variants + <code>FSDI_SFX</code></td><td style="text-align:left;white-space:normal">Small hardware-generated vibrations (≤100 Hz, ±0.12)</td><td style="text-align:left;white-space:normal">Rumble effects, not perturbations.</td></tr>
</table>
<p class="note">Not available at all: hardware-timed trajectories, timestamps on commands, a trigger or sync output, or a
documented setpoint rate. The vendor's MI manual streams positions every 4 ms (250 Hz), which suggests the controller
consumes setpoints at about that rate.</p>

<h2>3 · The robot itself</h2>
__ROBOT__

<h2>Method and caveats</h2>
<ul class="note">
<li>Reachability: at each height (5 mm steps), 72 directions in the sway/surge plane, binary search to 1 mm for the
furthest pose the vendor library accepts with FullMatch. Every probe command is paused; nothing moves. The outline
assumes the region is star-shaped around home. On the imitator the full probe takes about 3 s, because the check runs in
the vendor library on the PC.</li>
<li>Imitator speeds: reported pose polled every ~2 ms while the setpoint is re-sent every 10 ms; positions
median-filtered, then differentiated with 21 ms (speed) and 41 ms (acceleration) smoothing.</li>
<li>The imitator reproduces the PS-6TL-350's kinematics exactly (home-height limits match the tech sheet to 0.5 mm) but
not its dynamics: it ignores maxSpeed and the acceleration profile, and moves faster than the tech sheet allows.</li>
<li>Kinematic reach is not usable reach: payload, speed, controller software limits and safety margins all shrink it.
Keep 25 mm or more from the edge.</li>
</ul>
<p class="note">Generated by <code>uv run hexapod-reachability-report</code> from <code>hexapod-envelope</code> and
<code>hexapod-dynamics</code> outputs.</p>
</main>
<script>
const SETS = __SETS__;
const STROKE = __STROKE__, MARGIN = __MARGIN__, SPEC_HOME = __SPECHOME__;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const allH = SETS[0].heights.map(h => h.heave);
const HMIN = Math.min(...allH), HMAX = Math.max(...allH), HSTEP = allH[1] - allH[0];
const fmt = v => (v > 0 ? "+" : "") + Math.round(v);
const atHeight = (set, z) => set.heights.reduce((b, h) => Math.abs(h.heave - z) < Math.abs(b.heave - z) ? h : b);

// ---------- 3D viewer (orthographic, canvas 2D) ----------
const VIEWS = {iso: [-0.75, 0.42], side: [-Math.PI / 2, 0], front: [0, 0], top: [0, Math.PI / 2 - 1e-4]};
class Viewer {
  constructor(canvas, set, colorVar) {
    Object.assign(this, {canvas, set, colorVar, yaw: VIEWS.iso[0], pitch: VIEWS.iso[1], zoom: 1, panX: 0, panY: 0});
    this.rings = set.heights.map(h => h.radius.map((r, i) => {
      const a = set.angles[i] * Math.PI / 180; return [r * Math.cos(a), r * Math.sin(a), h.heave]; }));
    this.peers = [];
    let drag = null;
    canvas.addEventListener("pointerdown", e => { canvas.setPointerCapture(e.pointerId);
      drag = {x: e.clientX, y: e.clientY, pan: e.button === 2 || e.shiftKey}; });
    canvas.addEventListener("pointermove", e => { if (!drag) return;
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y; drag.x = e.clientX; drag.y = e.clientY;
      if (drag.pan) { this.panX += dx; this.panY += dy; }
      else { this.yaw -= dx * 0.01; this.pitch = Math.max(-1.55, Math.min(1.55, this.pitch + dy * 0.01)); }
      this.changed(); });
    canvas.addEventListener("pointerup", () => drag = null);
    canvas.addEventListener("contextmenu", e => e.preventDefault());
    canvas.addEventListener("wheel", e => { e.preventDefault();
      this.zoom = Math.max(0.4, Math.min(6, this.zoom * Math.exp(-e.deltaY * 0.0015))); this.changed(); }, {passive: false});
    canvas.addEventListener("dblclick", () => this.setView("iso"));
    new ResizeObserver(() => this.draw()).observe(canvas);
  }
  setView(name) { [this.yaw, this.pitch] = VIEWS[name]; this.zoom = 1; this.panX = this.panY = 0; this.changed(); }
  changed() { this.draw(); if (document.getElementById("sync").checked) for (const p of this.peers) {
    Object.assign(p, {yaw: this.yaw, pitch: this.pitch, zoom: this.zoom, panX: this.panX, panY: this.panY}); p.draw(); } }
  project([x, y, z]) {  // scene: x = sway (right), y = surge (front), z = heave (up)
    const cy = Math.cos(this.yaw), sy = Math.sin(this.yaw), cp = Math.cos(this.pitch), sp = Math.sin(this.pitch);
    const X = x * cy - y * sy, Y = x * sy + y * cy;            // rotate about vertical
    const sx = X, sz = z * cp + Y * sp, depth = Y * cp - z * sp; // tilt
    return [this.cx + this.panX + sx * this.k, this.cy0 + this.panY - (sz - this.zc * cp) * this.k, depth];
  }
  draw() {
    const c = this.canvas, dpr = window.devicePixelRatio || 1, w = c.clientWidth, h = c.clientHeight;
    if (!w) return;
    c.width = w * dpr; c.height = h * dpr;
    const g = c.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, h);
    this.cx = w / 2; this.cy0 = h / 2; this.zc = (HMIN + HMAX) / 2; this.k = this.zoom * w / 820;
    const col = css(this.colorVar), grid = css("--grid"), muted = css("--muted"), accent = css("--accent"), ok = css("--ok");
    const line = (pts, style, width, alpha = 1, close = false) => { g.globalAlpha = alpha; g.strokeStyle = style;
      g.lineWidth = width; g.beginPath(); pts.forEach((p, i) => { const [a, b] = this.project(p); i ? g.lineTo(a, b) : g.moveTo(a, b); });
      if (close) g.closePath(); g.stroke(); g.globalAlpha = 1; };
    // floor grid at the lowest height, axes through home
    for (let v = -300; v <= 300; v += 100) {
      line([[v, -350, HMIN], [v, 350, HMIN]], grid, 1); line([[-350, v, HMIN], [350, v, HMIN]], grid, 1); }
    line([[-350, 0, 0], [350, 0, 0]], muted, 1, .7); line([[0, -350, 0], [0, 350, 0]], muted, 1, .7);
    line([[0, 0, HMIN], [0, 0, HMAX + 20]], muted, 1, .7);
    g.fillStyle = muted; g.font = "11px system-ui";
    for (const [p, t] of [[[0, 370, 0], "surge +"], [[370, 0, 0], "sway +"], [[0, 0, HMAX + 35], "heave +"]]) {
      const [a, b] = this.project(p); g.fillText(t, a - 16, b); }
    // shell: every slice outline, plus meridians
    if (document.getElementById("shell").checked) {
      this.rings.forEach((ring, i) => line(ring, col, 1, i % 4 === 0 ? .35 : .14, true));
      for (let j = 0; j < this.set.angles.length; j += 6) line(this.rings.map(r => r[j]), col, 1, .22);
    }
    // highlighted slice
    const hz = atHeight(this.set, current), i = this.set.heights.indexOf(hz), ring = this.rings[i];
    g.globalAlpha = .38; g.fillStyle = col; g.beginPath();
    ring.forEach((p, k) => { const [a, b] = this.project(p); k ? g.lineTo(a, b) : g.moveTo(a, b); }); g.closePath(); g.fill();
    g.globalAlpha = 1; line(ring, col, 2.2, 1, true);
    line([[0, hz.surge_min, hz.heave], [0, hz.surge_max, hz.heave]], accent, 3);
    if (hz.surge_max - hz.surge_min >= STROKE) {
      const mid = (hz.surge_min + hz.surge_max) / 2;
      line([[0, mid - STROKE / 2, hz.heave], [0, mid + STROKE / 2, hz.heave]], ok, 6, .85); }
  }
}
const viewers = [];
SETS.forEach(set => { const canvas = document.getElementById("v-" + set.key);
  viewers.push(new Viewer(canvas, set, "--" + set.key)); });
viewers.forEach(v => v.peers = viewers.filter(o => o !== v));
document.querySelectorAll("[data-view]").forEach(b => b.addEventListener("click", () => viewers.forEach(v => v.setView(b.dataset.view))));
["sync", "shell"].forEach(id => document.getElementById(id).addEventListener("change", () => viewers.forEach(v => v.draw())));

// ---------- height slider in millimetres ----------
const hs = document.getElementById("hs");
hs.innerHTML = '<div class="cap" style="top:-14px">higher</div><div class="track"></div><div class="fill"></div>' +
  '<div class="thumb"></div><div class="cap" style="bottom:-16px">lower</div>';
const track = hs.querySelector(".track"), thumb = hs.querySelector(".thumb"), fill = hs.querySelector(".fill");
for (let v = Math.ceil(HMIN / 50) * 50; v <= HMAX; v += 50) {
  const t = document.createElement("div"); t.className = "tick"; t.dataset.v = v; t.textContent = fmt(v); hs.appendChild(t); }
let current = 0;
function layoutSlider() {
  const top = track.offsetTop, h = track.offsetHeight, y = v => top + (HMAX - v) / (HMAX - HMIN) * h;
  hs.querySelectorAll(".tick").forEach(t => t.style.top = y(+t.dataset.v) + "px");
  thumb.style.top = y(current) + "px";
  const y0 = y(0), y1 = y(current); fill.style.top = Math.min(y0, y1) + "px"; fill.style.height = Math.abs(y1 - y0) + "px";
}
function setHeight(v) {
  current = Math.max(HMIN, Math.min(HMAX, Math.round(v / HSTEP) * HSTEP));
  hs.setAttribute("aria-valuenow", current); hs.setAttribute("aria-valuetext", `heave ${fmt(current)} millimetres`);
  layoutSlider(); viewers.forEach(v => v.draw()); updateSide(); updateReadout(); updateTable();
}
const fromPointer = e => { const r = track.getBoundingClientRect();
  setHeight(HMAX - (e.clientY - r.top) / r.height * (HMAX - HMIN)); };
let sliding = false;
hs.addEventListener("pointerdown", e => { sliding = true; hs.setPointerCapture(e.pointerId); fromPointer(e); hs.focus(); });
hs.addEventListener("pointermove", e => sliding && fromPointer(e));
hs.addEventListener("pointerup", () => sliding = false);
hs.addEventListener("keydown", e => { const step = {ArrowUp: HSTEP, ArrowRight: HSTEP, ArrowDown: -HSTEP, ArrowLeft: -HSTEP,
  PageUp: 50, PageDown: -50}[e.key]; if (step) { e.preventDefault(); setHeight(current + step); }
  if (e.key === "Home") setHeight(HMIN); if (e.key === "End") setHeight(HMAX); });
hs.setAttribute("aria-valuemin", HMIN); hs.setAttribute("aria-valuemax", HMAX);
new ResizeObserver(layoutSlider).observe(hs);

// ---------- side plot: surge reach vs height, all sources ----------
const NS = "http://www.w3.org/2000/svg", svg = document.getElementById("sideplot");
const el = (t, a, p = svg) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); p.appendChild(e); return e; };
const W = 1000, H = 300, L = 54, B = 34, X0 = -360, X1 = 360;
svg.setAttribute("viewBox", `0 0 ${W} ${H + B + 10}`);
const sx = v => L + (v - X0) / (X1 - X0) * (W - L - 10), sy = v => 8 + (HMAX + 10 - v) / (HMAX - HMIN + 20) * H;
for (let v = -300; v <= 300; v += 100) { el("line", {x1: sx(v), x2: sx(v), y1: 8, y2: H + 8, stroke: "var(--grid)"});
  el("text", {x: sx(v), y: H + 24, "text-anchor": "middle"}).textContent = fmt(v); }
for (let v = Math.ceil(HMIN / 50) * 50; v <= HMAX; v += 50) { el("line", {x1: L, x2: W - 10, y1: sy(v), y2: sy(v), stroke: "var(--grid)"});
  el("text", {x: L - 8, y: sy(v) + 4, "text-anchor": "end"}).textContent = fmt(v); }
el("text", {x: (W + L) / 2, y: H + 40, "text-anchor": "middle"}).textContent = "surge (mm, + front)";
el("text", {x: 14, y: H / 2, transform: `rotate(-90 14 ${H / 2})`, "text-anchor": "middle"}).textContent = "heave (mm)";
const imitator = SETS.find(s => s.key === "imitator") || SETS[0];
imitator.heights.filter(h => h.surge_max - h.surge_min >= STROKE + 2 * MARGIN).forEach(h =>
  el("rect", {x: L, width: W - L - 10, y: sy(h.heave + HSTEP / 2), height: Math.abs(sy(h.heave) - sy(h.heave + HSTEP)),
    fill: "var(--ok)", opacity: .08}));
SETS.forEach((set, i) => {
  const pts = set.heights.map(h => `${sx(h.surge_max)},${sy(h.heave)}`).concat(
    set.heights.slice().reverse().map(h => `${sx(h.surge_min)},${sy(h.heave)}`)).join(" ");
  el("polygon", {points: pts, fill: `var(--${set.key})`, "fill-opacity": i ? .10 : .22, stroke: `var(--${set.key})`,
    "stroke-width": 1.6, "stroke-dasharray": i ? "6 4" : "none"}); });
el("line", {x1: sx(0), x2: sx(0), y1: 8, y2: H + 8, stroke: "var(--muted)", "stroke-width": .8});
SPEC_HOME.forEach(v => el("circle", {cx: sx(v), cy: sy(0), r: 4, fill: "var(--fg)"}));
const marker = el("line", {x1: L, x2: W - 10, stroke: "var(--accent)", "stroke-width": 2});
const legend = el("g", {});
SETS.forEach((set, i) => { el("rect", {x: L + 12 + i * 170, y: 14, width: 12, height: 12, fill: `var(--${set.key})`, rx: 2}, legend);
  el("text", {x: L + 30 + i * 170, y: 24}, legend).textContent = set.label; });
svg.addEventListener("click", e => { const r = svg.getBoundingClientRect();
  const y = (e.clientY - r.top) / r.height * (H + B + 10); setHeight(HMAX + 10 - (y - 8) / H * (HMAX - HMIN + 20)); });
function updateSide() { marker.setAttribute("y1", sy(current)); marker.setAttribute("y2", sy(current)); }

// ---------- readout and table ----------
function updateReadout() {
  const parts = [`<div class="stat"><span>height (heave)</span><b>${fmt(current)} mm</b></div>`];
  SETS.forEach(set => { const h = atHeight(set, current), range = h.surge_max - h.surge_min;
    const mid = (h.surge_min + h.surge_max) / 2, ok = range >= STROKE;
    parts.push(`<div class="stat"><span>${set.label}: surge reach</span><b>${fmt(h.surge_min)} to ${fmt(h.surge_max)} mm</b></div>`);
    parts.push(`<div class="stat"><span>${set.label}: 300 mm stroke</span><b class="${ok ? "yes" : "no"}">${ok
      ? `${fmt(mid - STROKE / 2)} → ${fmt(mid + STROKE / 2)} (±${Math.round((range - STROKE) / 2)} spare)` : "does not fit"}</b></div>`); });
  document.getElementById("readout").innerHTML = parts.join("");
}
const tbl = document.getElementById("tbl");
tbl.innerHTML = "<thead><tr><th>heave (mm)</th>" + SETS.map(s => `<th>${s.label} surge reach</th><th>range</th><th>300 mm?</th>`).join("") +
  "</tr></thead><tbody>" + imitator.heights.slice().reverse().filter(h => h.heave % 10 === 0).map(h => "<tr data-h=\"" + h.heave + "\"><td>" + fmt(h.heave) + "</td>" +
  SETS.map(s => { const x = atHeight(s, h.heave), r = x.surge_max - x.surge_min;
    return `<td>${fmt(x.surge_min)} to ${fmt(x.surge_max)}</td><td>${Math.round(r)}</td><td class="${r >= STROKE + 2 * MARGIN ? "yes" : r >= STROKE ? "" : "no"}">${
      r >= STROKE + 2 * MARGIN ? "yes" : r >= STROKE ? "tight" : "no"}</td>`; }).join("") + "</tr>").join("") + "</tbody>";
function updateTable() { tbl.querySelectorAll("tr[data-h]").forEach(r => r.classList.toggle("sel", +r.dataset.h === Math.round(current / 10) * 10)); }

setHeight(0);
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => viewers.forEach(v => v.draw()));
</script></body></html>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--folder", type=Path, default=Path("output") / "reachability")
    parser.add_argument("--output", type=Path, help="default: <folder>/hexapod-reachability.html")
    args = parser.parse_args()
    folder = args.folder
    imitator, schematic, robot = (load(folder / f) for f in ("imitator.json", "schematic.json", "robot.json"))
    if not imitator:
        parser.error(f"{folder / 'imitator.json'} missing: run uv run hexapod-envelope --heave-step 5 "
                     f"--output {folder / 'imitator.json'}")
    sets = [slim(imitator, "M10 imitator", "imitator")]
    if schematic:
        sets.append(slim(schematic, "Schematic model", "schematic"))
    if robot:
        sets.append(slim(robot, "Robot", "robot"))

    # ---- the answer ----
    hs = imitator["heights"]
    home = min(hs, key=lambda h: abs(h["heave"]))
    widest = max(hs, key=lambda h: h["surge_max"] - h["surge_min"])
    comfy = [h["heave"] for h in hs if fits(h, STROKE_MM + 2 * MARGIN_MM)]
    mid = (home["surge_min"] + home["surge_max"]) / 2
    where = (f"From the imitator (exact PS-6TL-350 kinematics): a level 300 mm surge fits with at least {MARGIN_MM:g} mm to "
             f"spare at both ends anywhere from heave {min(comfy):+.0f} to {max(comfy):+.0f} mm. At home height the surge "
             f"reach is {home['surge_min']:+.0f} to {home['surge_max']:+.0f} mm, so centre the stroke: "
             f"<b>{mid - 150:+.0f} → {mid + 150:+.0f} mm</b> (about {(home['surge_max'] - home['surge_min'] - 300) / 2:.0f} "
             f"mm spare each end). The most room is at heave {widest['heave']:+.0f} mm: {widest['surge_min']:+.0f} to "
             f"{widest['surge_max']:+.0f} mm ({widest['surge_max'] - widest['surge_min']:.0f} mm of travel). "
             f"Starting from home itself (0) only works forward up to {home['surge_max']:+.0f} or back to "
             f"{home['surge_min']:+.0f}, so pre-position for a full 30 cm.")
    trap, smooth = min_time(STROKE_MM, SPEC["surge_v"], SPEC["surge_a_g"])
    dyn = load(folder / "dynamics.json")
    step_settle = None
    if dyn:
        steps = [t for t in dyn["tests"] if t["kind"] in ("step", "maxspeed")]
        step_settle = float(np.median([t["settle_1mm_s"] for t in steps]))
    howfast = (f"By the tech sheet (surge ≤ {SPEC['surge_v']:.0f} mm/s, ≤ {SPEC['surge_a_g']} g), 300 mm cannot take less "
               f"than <b>{trap:.2f} s</b> (full acceleration, coast at top speed, full braking), or <b>{smooth:.2f} s</b> "
               f"with the smooth S-curve our scripts use. A sensible first fast 300 mm stroke is about 1.2 s "
               f"(470 mm/s peak, 0.12 g): <code>--rate 470 --max-speed 65535</code>; 1.0 s needs <code>--rate 565</code> "
               f"(83% of the speed limit).")
    if step_settle:
        howfast += (f" The imitator executes an instant 300 mm setpoint jump in {step_settle:.2f} s, faster than the "
                    f"tech sheet allows, and ignores maxSpeed and the acceleration profile: it confirms the commands work, "
                    f"not the robot's real speed.")
    pending = ("the robot's own reach (safe to measure: paused probe, nothing moves) and its real speed and ramps "
               "(must be measured by stepping up <code>--rate</code> on the robot). See section 3.") if not robot else \
              "the robot's real speed and ramps (step up <code>--rate</code> gradually on the robot)."

    # ---- agreement note ----
    agreement = ""
    if schematic:
        sw = max(schematic["heights"], key=lambda h: h["surge_max"] - h["surge_min"])
        agreement = (f"The schematic model is symmetric and too small: its widest surge range is "
                     f"{sw['surge_max'] - sw['surge_min']:.0f} mm (at {sw['heave']:+.0f} mm) against the imitator's "
                     f"{widest['surge_max'] - widest['surge_min']:.0f} mm, and it misses the real front/back asymmetry "
                     f"(the platform reaches about 30 mm further backward than forward). Use the imitator or the robot "
                     f"for planning; the schematic geometry is only good for animation.")

    # ---- dynamics section ----
    if dyn:
        steps_png, stall_png = dynamics_plots(folder / "dynamics.csv")
        rows = "".join(
            f"<tr><td>{t['test']}</td><td>{t['settle_1mm_s']:.3f}</td><td>{t['rise_10_90_s']:.3f}</td>"
            f"<td>{t['peak_speed_mm_s']:.0f}</td><td>{t['peak_accel_g']:.2f}</td><td>{t['peak_tilt_deg']:.2f}</td>"
            f"<td>{t['longest_gap_ms']:.0f}</td></tr>" for t in dyn["tests"])
        dynamics = f"""
<p>Run on the M10 imitator only (<code>uv run hexapod-dynamics</code> refuses any other controller): a 300 mm surge
stroke at home height, {dyn['stroke_mm'][0]:+.0f} ↔ {dyn['stroke_mm'][1]:+.0f} mm. First instant setpoint jumps with each
acceleration profile and maxSpeed setting, then smooth moves streamed from Python in 1.0, 0.7 and 0.5 s.</p>
<div class="cards">
<div class="card"><b>Instant step: {step_settle:.2f} s to within 1 mm</b><span>Same for all four acceleration profiles and
every maxSpeed: the imitator ignores both. About 1.5 m/s peak, over twice the tech sheet's 680 mm/s.</span></div>
<div class="card"><b>Tilts about 1° in transit</b><span>An instant jump moves the six actuators at different rates, so the
top frame is not level on the way. Smooth streamed moves tilt less than 0.5°.</span></div>
<div class="card"><b>Smooth moves track ~30 ms behind</b><span>The imitator follows streamed setpoints closely at every
speed tried, including 0.5 s (above the robot's speed limit). It does not enforce the tech-sheet limits.</span></div>
<div class="card"><b>Windows stalls show up as lurches</b><span>The Python sender froze for 65–130 ms several times;
each time the command jumped and the platform raced to catch up (below). On the robot this is a jolt. Real-time Linux
removes it.</span></div>
</div>
<img class="plot" src="data:image/png;base64,{steps_png}" alt="Step responses and smooth moves on the imitator">
<img class="plot" style="margin-top:10px" src="data:image/png;base64,{stall_png}" alt="A Windows stall during a 1 second move">
<h3>Per-test results (imitator)</h3>
<div class="scroll"><table><tr><th>test</th><th>settle to 1 mm (s)</th><th>rise 10–90% (s)</th><th>peak speed (mm/s)</th>
<th>peak accel (g)</th><th>peak tilt (°)</th><th>longest sender gap (ms)</th></tr>{rows}</table></div>
<p class="note">Peak speed and acceleration are inflated in tests where the sender stalled (gap ≫ 10 ms); settle and rise
times are robust. Spec limits for comparison: surge {SPEC['surge_v']:.0f} mm/s and {SPEC['surge_a_g']} g; sway
{SPEC['sway_v']:.0f} mm/s and {SPEC['sway_a_g']} g. Fastest possible 300 mm surge at those limits: {trap:.2f} s
(bang-coast-bang) or {smooth:.2f} s (S-curve).</p>"""
    else:
        dynamics = "<p>No imitator speed data yet: run <code>uv run hexapod-dynamics</code> with the M10 connected.</p>"

    robot_html = ("<p>Measured: see the third shape above.</p>" if robot else
                  """<p>Not measured yet. Two steps, in this order:</p>
<ol><li><b>Reach (safe, nothing moves):</b> ForceSeatPM closed, then
<code>uv run hexapod-envelope --ip 10.1.1.75 --heave-step 5 --output output/reachability/robot.json</code>, then rebuild
this report. Every probe command is paused; the platform does not move. It adds the robot as a third shape and confirms
the imitator's limits.</li>
<li><b>Speed (the platform moves):</b> do not use <code>hexapod-dynamics</code> on the robot. Step up the 300 mm stroke with
<code>hexapod-park-test --max-speed 65535</code> and <code>--rate</code> 100 → 235 → 340 → 470, checking each report for
lag, overshoot and lurches before going faster. Add a top-frame accelerometer for true onset times.</li></ol>""")

    page = (PAGE.replace("__DATE__", html.escape(imitator["date"][:10]))
                .replace("__WHERE__", where).replace("__HOWFAST__", howfast).replace("__PENDING__", pending)
                .replace("__PANES__", "".join(
                    f'<div class="pane"><h3><span class="swatch" style="background:var(--{s["key"]})"></span>{s["label"]}'
                    f'</h3><canvas class="v3d" id="v-{s["key"]}" aria-label="3D reachable space, {s["label"]}"></canvas></div>'
                    for s in sets))
                .replace("__NPANES__", str(len(sets)))
                .replace("__AGREEMENT__", agreement).replace("__DYNAMICS__", dynamics).replace("__ROBOT__", robot_html)
                .replace("__MARGIN__", f"{MARGIN_MM:g}")
                .replace("__SETS__", json.dumps(sets, separators=(",", ":")))
                .replace("__STROKE__", f"{STROKE_MM:g}")
                .replace("__SPECHOME__", json.dumps(list(SPEC["home_surge"]))))
    out = args.output or folder / "hexapod-reachability.html"
    out.write_text(page, encoding="utf-8")
    print(f"Wrote {out} ({out.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
