"""Build surge-range-of-motion.html from hexapod-envelope's JSON.

The page has a looping GIF that sweeps through the heights (top-down reachable region
plus a side view of surge range against height) and an interactive view: a vertical
height slider beside the reachable sway x surge region at that height, with the side
view marking the selected height. Self-contained: data, GIF and script are inline.

Run: uv run hexapod-envelope-report --input output/envelope.json
"""
from __future__ import annotations

import argparse
import base64
import html
import json
from pathlib import Path
import tempfile

import numpy as np


def outline(h, angles_deg):
    a = np.deg2rad(angles_deg)
    r = np.array(h["radius"])
    return r * np.cos(a), r * np.sin(a)  # sway, surge


def make_gif(data, extent):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation, PillowWriter

    hs = data["heights"]
    angles = data["directions_deg"]
    heave = np.array([h["heave"] for h in hs])
    smin = np.array([h["surge_min"] for h in hs])
    smax = np.array([h["surge_max"] for h in hs])
    widest = max(hs, key=lambda h: h["area_cm2"])
    wx, wy = outline(widest, angles)

    fig, (top, side) = plt.subplots(1, 2, figsize=(9, 4.4), gridspec_kw={"width_ratios": [1, 1.15]})
    fig.subplots_adjust(left=0.08, right=0.97, bottom=0.13, top=0.86, wspace=0.3)
    top.fill(np.r_[wx, wx[0]], np.r_[wy, wy[0]], color="#c9c4b8", alpha=0.35, lw=0, label="widest height")
    region = top.fill([0], [0], color="#2a6fdb", alpha=0.75, lw=0, label="reachable")[0]
    top.plot(0, 0, "+", color="#222", ms=10)
    surge_line, = top.plot([], [], color="#c0392b", lw=2.2, label="surge reach")
    top.set_xlim(-extent, extent); top.set_ylim(-extent, extent); top.set_aspect("equal")
    top.set_xlabel("sway (mm, + right)"); top.set_ylabel("surge (mm, + front)")
    top.grid(alpha=0.3); top.legend(loc="lower left", fontsize=7, frameon=False)

    side.fill_betweenx(heave, smin, smax, color="#2a6fdb", alpha=0.25, lw=0)
    side.plot(smin, heave, color="#2a6fdb", lw=1.5); side.plot(smax, heave, color="#2a6fdb", lw=1.5)
    side.axvline(0, color="#888", lw=0.8)
    cursor = side.axhline(heave[0], color="#c0392b", lw=2)
    side.set_xlim(-extent, extent); side.set_ylim(heave.min() - 10, heave.max() + 10)
    side.set_xlabel("surge (mm, + front)"); side.set_ylabel("heave (mm)"); side.grid(alpha=0.3)
    side.set_title("Surge range vs height", fontsize=10)
    title = fig.suptitle("", fontsize=11)

    order = list(range(len(hs))) + list(range(len(hs) - 2, 0, -1))  # up, then back down: seamless loop
    home = int(np.argmin(np.abs(heave)))
    order = order[home:] + order[:home]  # first frame (shown before the GIF plays) is home height

    def draw(i):
        h = hs[i]
        x, y = outline(h, angles)
        region.set_xy(np.c_[np.r_[x, x[0]], np.r_[y, y[0]]])
        surge_line.set_data([0, 0], [h["surge_min"], h["surge_max"]])
        cursor.set_ydata([h["heave"], h["heave"]])
        title.set_text(f"heave {h['heave']:+.0f} mm   surge {h['surge_min']:+.0f} to {h['surge_max']:+.0f} mm   "
                       f"area {h['area_cm2']:.0f} cm²")
        return region, surge_line, cursor, title

    anim = FuncAnimation(fig, lambda k: draw(order[k]), frames=len(order), blit=False)
    with tempfile.TemporaryDirectory() as folder:  # PillowWriter writes to a file path
        gif = Path(folder) / "sweep.gif"
        anim.save(gif, writer=PillowWriter(fps=6), dpi=80)
        encoded = base64.b64encode(gif.read_bytes()).decode()
    plt.close(fig)
    return encoded


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Surge Range of Motion</title>
<style>
:root{--bg:#fbfaf7;--fg:#1d1d1f;--muted:#6b6b70;--line:#dedbd3;--panel:#fff;--region:#2a6fdb;--ghost:#c9c4b8;--accent:#c0392b;--warn-bg:#fdecea}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#15171b;--fg:#e8e8ea;--muted:#9a9aa2;--line:#2e3138;--panel:#1c1f24;--region:#5b9bff;--ghost:#4a4740;--accent:#ff6b5b;--warn-bg:#3a1f1c}}
:root[data-theme="dark"]{--bg:#15171b;--fg:#e8e8ea;--muted:#9a9aa2;--line:#2e3138;--panel:#1c1f24;--region:#5b9bff;--ghost:#4a4740;--accent:#ff6b5b;--warn-bg:#3a1f1c}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1060px;margin:0 auto;padding:20px 16px 48px}
h1{margin:0 0 4px;font-size:1.6rem} h2{margin:32px 0 8px;font-size:1.15rem}
.muted{color:var(--muted)} code{font-size:.9em}
.warn{background:var(--warn-bg);border-left:4px solid var(--accent);padding:10px 14px;border-radius:6px;margin:14px 0}
.gif{width:100%;max-width:900px;border-radius:8px;border:1px solid var(--line);background:#fff}
.explore{display:grid;grid-template-columns:auto minmax(0,1fr) minmax(0,1fr);gap:16px;align-items:stretch;
  background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px}
.slider{display:flex;flex-direction:column;align-items:center;gap:6px;font-size:.8rem;color:var(--muted)}
input[type=range]{writing-mode:vertical-lr;direction:rtl;height:360px;width:28px;accent-color:var(--accent);cursor:pointer}
svg{width:100%;height:auto;display:block;overflow:visible}
svg text{fill:var(--muted);font-size:11px}
.axis{stroke:var(--line);stroke-width:1} .grid{stroke:var(--line);stroke-width:.6;stroke-dasharray:3 4}
.readout{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin-top:12px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 12px}
.stat b{display:block;font-size:1.2rem;font-variant-numeric:tabular-nums}
.stat span{font-size:.78rem;color:var(--muted)}
table{border-collapse:collapse;font-variant-numeric:tabular-nums;font-size:.9rem}
th,td{padding:4px 12px 4px 0;border-bottom:1px solid var(--line);text-align:right} th{color:var(--muted);font-weight:600}
tr.sel td{color:var(--accent);font-weight:600}
.scroll{overflow-x:auto}
@media (max-width:760px){.explore{grid-template-columns:auto minmax(0,1fr)} .side{grid-column:1/-1}
  input[type=range]{height:260px}}
</style></head><body><main>
<h1>Surge range of motion</h1>
<p class="muted">PS-6TL-350 hexapod, level top frame. __SOURCE__ · __DATE__ · resolution __RES__ mm,
__NDIR__ directions per height. Surge + is front, sway + is right, heave + is up, all from home (0,0,0).</p>
__WARNING__
<p>How far the top frame can translate horizontally at each height, with all rotations at zero. The widest
surge range is <b>__BEST__</b>. Use the slider to pick a height; the side view shows where that height sits in
the full surge envelope.</p>

<h2>Explore by height</h2>
<div class="explore">
  <div class="slider"><span>higher</span>
    <input id="h" type="range" min="0" step="1" aria-label="Height (heave)">
    <span>lower</span></div>
  <div><svg id="top" role="img" aria-label="Reachable sway and surge region at the selected height"></svg></div>
  <div class="side"><svg id="side" role="img" aria-label="Surge range against height"></svg></div>
</div>
<div class="readout" id="readout"></div>

<h2>Sweep through all heights</h2>
<img class="gif" src="data:image/gif;base64,__GIF__" alt="Animation sweeping height up and down, showing the reachable region and surge range at each height">

<h2>Table</h2>
<div class="scroll"><table id="tbl"><thead><tr><th>heave (mm)</th><th>surge min</th><th>surge max</th>
<th>surge range</th><th>sway min</th><th>sway max</th><th>area (cm²)</th></tr></thead><tbody></tbody></table></div>

<h2>Method</h2>
<p class="muted">At each height the probe searches outward from (0,0) along each direction in the sway/surge plane and
records the furthest pose the ForceSeatDI inverse kinematics accepts with the strict FullMatch strategy. Every probe
command is sent paused, so the platform does not move. The outline assumes the region is star-shaped around home,
which a constant-orientation hexapod workspace normally is. These are kinematic limits only: speed, acceleration,
payload and controller software limits can be tighter, so keep a margin from the edge. Generated by
<code>uv run hexapod-envelope</code> and <code>uv run hexapod-envelope-report</code>.</p>
</main>
<script>
const D = __DATA__;
const H = D.heights, A = D.directions_deg.map(a => a * Math.PI / 180), E = __EXTENT__;
const NS = "http://www.w3.org/2000/svg";
const el = (tag, attrs, parent) => { const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]); parent && parent.appendChild(e); return e; };
const pts = h => h.radius.map((r, i) => [r * Math.cos(A[i]), r * Math.sin(A[i])]);
const widest = H.reduce((a, b) => b.area_cm2 > a.area_cm2 ? b : a);

// Top-down view: x = sway (right), y = surge (front, up the page).
const plan = document.getElementById("top"), P = 36, S = 340;
plan.setAttribute("viewBox", `${-P} ${-12} ${S + 2 * P} ${S + P + 12}`);
const tx = v => (v + E) / (2 * E) * S, ty = v => (E - v) / (2 * E) * S;
for (let v = -E; v <= E + 1e-9; v += E / 2) {
  el("line", {x1: tx(v), x2: tx(v), y1: 0, y2: S, class: "grid"}, plan);
  el("line", {y1: ty(v), y2: ty(v), x1: 0, x2: S, class: "grid"}, plan);
  el("text", {x: tx(v), y: S + 14, "text-anchor": "middle"}, plan).textContent = Math.round(v);
  el("text", {x: -6, y: ty(v) + 4, "text-anchor": "end"}, plan).textContent = Math.round(v);
}
el("text", {x: S / 2, y: S + 30, "text-anchor": "middle"}, plan).textContent = "sway (mm, + right)";
el("text", {x: S / 2, y: -2, "text-anchor": "middle"}, plan).textContent = "surge (mm, + front) ↑";
el("polygon", {points: pts(widest).map(([x, y]) => `${tx(x)},${ty(y)}`).join(" "),
  fill: "var(--ghost)", opacity: .45}, plan);
const region = el("polygon", {fill: "var(--region)", opacity: .78}, plan);
const reach = el("line", {stroke: "var(--accent)", "stroke-width": 3, x1: tx(0), x2: tx(0)}, plan);
el("path", {d: `M${tx(0) - 6},${ty(0)}h12M${tx(0)},${ty(0) - 6}v12`, stroke: "var(--fg)", "stroke-width": 1.5}, plan);

// Side view: x = surge, y = heave.
const side = document.getElementById("side"), W = 320, HT = 340;
side.setAttribute("viewBox", `${-44} ${-12} ${W + 56} ${HT + 46}`);
const hv = H.map(h => h.heave), hmin = Math.min(...hv) - 10, hmax = Math.max(...hv) + 10;
const sx = v => (v + E) / (2 * E) * W, sy = v => (hmax - v) / (hmax - hmin) * HT;
for (let v = -E; v <= E + 1e-9; v += E / 2) {
  el("line", {x1: sx(v), x2: sx(v), y1: 0, y2: HT, class: "grid"}, side);
  el("text", {x: sx(v), y: HT + 14, "text-anchor": "middle"}, side).textContent = Math.round(v);
}
for (let v = Math.ceil(hmin / 50) * 50; v <= hmax; v += 50) {
  el("line", {y1: sy(v), y2: sy(v), x1: 0, x2: W, class: "grid"}, side);
  el("text", {x: -6, y: sy(v) + 4, "text-anchor": "end"}, side).textContent = v;
}
el("text", {x: W / 2, y: HT + 30, "text-anchor": "middle"}, side).textContent = "surge (mm, + front)";
el("text", {x: -34, y: HT / 2, "text-anchor": "middle", transform: `rotate(-90 -34 ${HT / 2})`}, side).textContent = "heave (mm)";
const band = H.map(h => `${sx(h.surge_max)},${sy(h.heave)}`).concat(
  H.slice().reverse().map(h => `${sx(h.surge_min)},${sy(h.heave)}`)).join(" ");
el("polygon", {points: band, fill: "var(--region)", opacity: .28, stroke: "var(--region)", "stroke-width": 1.5}, side);
el("line", {x1: sx(0), x2: sx(0), y1: 0, y2: HT, class: "axis"}, side);
const cur = el("line", {x1: 0, x2: W, stroke: "var(--accent)", "stroke-width": 2.5}, side);
const curSpan = el("line", {stroke: "var(--accent)", "stroke-width": 6, "stroke-linecap": "round"}, side);
side.addEventListener("click", ev => {  // click the side view to jump to a height
  const r = side.getBoundingClientRect(), vb = side.viewBox.baseVal;
  const y = vb.y + (ev.clientY - r.top) / r.height * vb.height;
  const v = hmax - y / HT * (hmax - hmin);
  let best = 0; H.forEach((h, i) => { if (Math.abs(h.heave - v) < Math.abs(H[best].heave - v)) best = i; });
  slider.value = best; show(best);
});

// Table
const tbody = document.querySelector("#tbl tbody");
const rows = H.slice().reverse().map(h => {
  const tr = document.createElement("tr");
  [h.heave, h.surge_min, h.surge_max, h.surge_max - h.surge_min, h.sway_min, h.sway_max, h.area_cm2]
    .forEach((v, i) => { const td = document.createElement("td");
      td.textContent = i === 0 ? (v > 0 ? "+" : "") + v.toFixed(0) : v.toFixed(i === 6 ? 0 : 1); tr.appendChild(td); });
  tbody.appendChild(tr); return tr; }).reverse();

const readout = document.getElementById("readout");
const stat = (label, value) => `<div class="stat"><span>${label}</span><b>${value}</b></div>`;
const f = v => (v > 0 ? "+" : "") + v.toFixed(0);
function show(i) {
  const h = H[i];
  region.setAttribute("points", pts(h).map(([x, y]) => `${tx(x)},${ty(y)}`).join(" "));
  reach.setAttribute("y1", ty(h.surge_min)); reach.setAttribute("y2", ty(h.surge_max));
  cur.setAttribute("y1", sy(h.heave)); cur.setAttribute("y2", sy(h.heave));
  curSpan.setAttribute("x1", sx(h.surge_min)); curSpan.setAttribute("x2", sx(h.surge_max));
  curSpan.setAttribute("y1", sy(h.heave)); curSpan.setAttribute("y2", sy(h.heave));
  readout.innerHTML = stat("heave", f(h.heave) + " mm") + stat("surge reach", `${f(h.surge_min)} to ${f(h.surge_max)} mm`)
    + stat("surge range", (h.surge_max - h.surge_min).toFixed(0) + " mm")
    + stat("sway reach", `${f(h.sway_min)} to ${f(h.sway_max)} mm`) + stat("area", h.area_cm2.toFixed(0) + " cm²");
  rows.forEach((r, k) => r.classList.toggle("sel", k === i));
  slider.setAttribute("aria-valuetext", `heave ${f(h.heave)} millimetres`);
}
const slider = document.getElementById("h");
slider.max = H.length - 1;
slider.value = H.reduce((b, h, i) => Math.abs(h.heave) < Math.abs(H[b].heave) ? i : b, 0);  // start at home
slider.addEventListener("input", () => show(+slider.value));
show(+slider.value);
</script></body></html>
"""


def default_report_path(data, folder=Path("output")):
    return folder / "surge-range-of-motion.html"


def build(input_path, output_path=None):
    """Write the report for one envelope JSON; returns the output path."""
    data = json.loads(Path(input_path).read_text(encoding="utf-8"))
    hs = data["heights"]
    if not hs:
        raise ValueError(f"{input_path} has no reachable heights")
    output_path = Path(output_path) if output_path else default_report_path(data, Path(input_path).parent)
    extent = float(np.ceil(max(max(h["radius"]) for h in hs) / 50.0) * 50.0)
    best = max(hs, key=lambda h: h["surge_max"] - h["surge_min"])
    warning = ""
    page =(PAGE.replace("__SOURCE__", html.escape(data["source"]))
                .replace("__DATE__", html.escape(data["date"]))
                .replace("__RES__", f"{data['resolution_mm']:g}")
                .replace("__NDIR__", str(len(data["directions_deg"])))
                .replace("__WARNING__", warning)
                .replace("__BEST__", f"{best['surge_max'] - best['surge_min']:.0f} mm at heave "
                                     f"{best['heave']:+.0f} mm ({best['surge_min']:+.0f} to {best['surge_max']:+.0f})")
                .replace("__GIF__", make_gif(data, extent))
                .replace("__EXTENT__", f"{extent:g}")
                .replace("__DATA__", json.dumps(data, separators=(",", ":"))))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page, encoding="utf-8")
    print(f"Wrote {output_path} ({output_path.stat().st_size / 1e6:.1f} MB)")
    return output_path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=Path("output") / "envelope.json",
                        help="JSON from hexapod-envelope")
    parser.add_argument("--output", type=Path,
                        help="default: surge-range-of-motion.html next to the input")
    args = parser.parse_args()
    try:
        build(args.input, args.output)
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
