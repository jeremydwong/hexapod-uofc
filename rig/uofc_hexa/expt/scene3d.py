"""Live 3D view of the PS-6TL-350 in the browser: platform pose, Speedgoat setpoint, force plates, GRF.

Replaces the matplotlib 3D panel of live_view.py (re-projected in Python every frame, hundreds of
ms behind). Our own tiny viewer rather than meshcat: meshcat sends one WebSocket message per
object per update (~10 per frame), and at 60 Hz that per-message cost dropped the page to 35 fps
(measured headless, 2026-10-21; 60 fps with the scene idle). Here each frame is ONE message with
everything in it; the page keeps only the newest frame and applies it on requestAnimationFrame, so
a slow page drops frames instead of building a backlog (no growing delay).

  python side   a tornado server on its own thread: GET / (page), /web/* (vendored three.js r128 +
                OrbitControls, MIT), /ws. A producer thread calls source() at rate_hz and pushes
                the frame to every client; a client still sending the previous frame is skipped.
  page          builds the geometry once from the constants below; per frame sets the top-frame
                matrix, the 6 legs, the setpoint ghost, plate colours and GRF arrows; HUD text.

Scene frame: x = right (+sway), y = front (+surge), z = up, metres, floor at z = 0.
Dimensions from docs/PS-6TL-350-tech-sheet.pdf p.2; top size estimated; legs schematic (real joint
positions are confidential).

Run the self-test: uv run python -m uofc_hexa.expt.scene3d
"""
from __future__ import annotations

from collections import deque
import json
from pathlib import Path
import threading
import time
import webbrowser

import numpy as np

FOOT_X, FOOT_Y = 1.726, 1.660      # base footprint (m), tech sheet
TOP_Z0 = 0.790 + 0.1658            # top surface at heave 0: 0.790 m parked at heave -165.8 mm
TOP_SIDE = 1.0                     # square top frame side (m): ESTIMATE, not on the tech sheet
TOP_T = 0.03                       # top frame slab thickness (m)
BASE_T = 0.02
TILT_GAIN = 10.0                   # real tilts are < 1 deg: drawn rotation is exaggerated (positions are not)
GHOST_SIDE = 1.06
PLATE_SIDE, PLATE_T, PLATE_X = 0.20, 0.02, 0.125   # 200 mm plates, 50 mm gap: centres x = +0.125 (RIGHT,
                                                   # idx 0), -0.125 (LEFT, idx 1), y = 0
ARROW_M_PER_N = 0.001              # 1000 N -> 1 m
ARROW_MAX_M = 1.5
GRF_SIGN = 1.0                     # flip to -1 to draw the reaction instead of the force as given
# Plate / arrow colours per plate (0 = right, 1 = left): idle tint, loaded, arrow.
PLATE_COLORS = ((0xf5b7b1, 0xc0392b, 0xff3b30), (0xaed6f1, 0x2471a3, 0x0a84ff))
CAM_TARGET = (0.0, 0.0, 0.75)      # orbit point (m)
CAM_OFFSET = (1.7, -2.4, 1.3)      # camera from the target: behind-right, above (world x, y, z)
TRIAD_L = 0.3
DEFAULT_PORT = 7070
WEB = Path(__file__).resolve().parent / "web"

# schematic legs: base joints r 0.62 m at z 0.12; top joints r 0.42 m, 0.10 m below the top surface
BASE_R, BASE_JZ, TOP_R, TOP_JZ = 0.62, 0.12, 0.42, -0.10


def _joints():
    """(base, top) joint positions, leg j = base[j] -> top[j]; base in world, top in the top frame."""
    base, top = [], []
    for k in range(3):
        c = 90 + 120 * k
        for s in (-1, 1):
            a = np.radians(c + 12 * s)
            base.append([BASE_R * np.cos(a), BASE_R * np.sin(a), BASE_JZ])
        for s in (-1, 1):
            a = np.radians(c + 48 * s)
            top.append([TOP_R * np.cos(a), TOP_R * np.sin(a), TOP_JZ])
    return np.array(base), np.array(top)


def _trans(p):
    T = np.eye(4)
    T[:3, 3] = p
    return T


def _rot(axis, a):
    c, s = np.cos(a), np.sin(a)
    i, j = {"x": (1, 2), "y": (2, 0), "z": (0, 1)}[axis]
    R = np.eye(4)
    R[i, i], R[i, j], R[j, i], R[j, j] = c, -s, s, c
    return R


def top_transform(xyz_mm, rpy_rad):
    """World transform of the top frame (origin = centre of the top surface).

    R = Rz(yaw) Rx(pitch) Ry(roll): roll about y (front), pitch about x (right), yaw about z.
    Signs vs the SDK are unverified. Rotation drawn x TILT_GAIN.
    """
    sway, surge, heave = np.asarray(xyz_mm, float) / 1000.
    roll, pitch, yaw = TILT_GAIN * np.asarray(rpy_rad, float)
    return _trans([sway, surge, TOP_Z0 + heave]) @ _rot("z", yaw) @ _rot("x", pitch) @ _rot("y", roll)


def frame(pose, sp_mm, plates):
    """One frame as a small JSON-able dict (everything the page needs)."""
    xyz, rpy, state = pose if pose is not None else ((0, 0, 0), (0, 0, 0), None)
    T = top_transform(xyz, rpy)
    f = {"T": np.round(T.T.ravel(), 5).tolist(),          # column-major, as three.js Matrix4.fromArray
         "pose": None if pose is None else [round(float(v), 2) for v in xyz] + [round(float(np.degrees(v)), 3) for v in rpy],
         "state": None if state is None else int(state),
         "sp": None if sp_mm is None else [round(float(v), 2) for v in sp_mm], "plates": []}
    for i in range(2):
        pl = plates[i] if plates is not None and i < len(plates) else None
        if not pl:
            f["plates"].append(None)
            continue
        F = None if pl.get("force_N") is None else [round(float(v) * GRF_SIGN, 1) for v in pl["force_N"]]
        cop = None if pl.get("cop_mm") is None else [round(float(v), 1) for v in pl["cop_mm"]]
        f["plates"].append({"loaded": bool(pl.get("loaded")), "F": F, "cop": cop})
    return f


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Hexapod live</title>
<style>html,body{margin:0;height:100%;overflow:hidden;background:#1d2733;font:13px/1.35 monospace;color:#e8eef5}
#hud{position:absolute;left:10px;top:8px;white-space:pre;background:rgba(0,0,0,.45);padding:6px 9px;border-radius:4px}
#key{position:absolute;right:10px;top:8px;white-space:pre;background:rgba(0,0,0,.45);padding:6px 9px;border-radius:4px}</style>
</head><body><div id="hud">connecting...</div><div id="key"></div>
<script src="/web/three.min.js"></script><script src="/web/OrbitControls.js"></script>
<script>
const G = __GEOMETRY__;
const scene = new THREE.Scene(); scene.background = new THREE.Color(0x1d2733);
const camera = new THREE.PerspectiveCamera(45, innerWidth / innerHeight, 0.05, 50); camera.up.set(0, 0, 1);
camera.position.set(G.cam_target[0] + G.cam_offset[0], G.cam_target[1] + G.cam_offset[1], G.cam_target[2] + G.cam_offset[2]);
const renderer = new THREE.WebGLRenderer({antialias: true}); renderer.setPixelRatio(devicePixelRatio);
renderer.setSize(innerWidth, innerHeight); document.body.appendChild(renderer.domElement);
const controls = new THREE.OrbitControls(camera, renderer.domElement); controls.target.set(...G.cam_target); controls.update();
addEventListener('resize', () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });
scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 0.9)); const sun = new THREE.DirectionalLight(0xffffff, 0.6); sun.position.set(2, -3, 4); scene.add(sun);
const grid = new THREE.GridHelper(6, 24, 0x5a6a7a, 0x34404c); grid.rotation.x = Math.PI / 2; scene.add(grid);
const M = c => new THREE.MeshLambertMaterial({color: c});
const box = (sx, sy, sz, c) => new THREE.Mesh(new THREE.BoxGeometry(sx, sy, sz), M(c));
const base = box(G.foot[0], G.foot[1], G.base_t, 0x2b2e33); base.position.z = G.base_t / 2; scene.add(base);
function triad(parent, at, z, L) { [[L, .015, .015, 0xff2020, [L / 2, 0, 0]], [.015, L, .015, 0x20c020, [0, L / 2, 0]], [.015, .015, L, 0x3060ff, [0, 0, L / 2]]]
  .forEach(([a, b, c, col, o]) => { const m = box(a, b, c, col); m.position.set(at[0] + o[0], at[1] + o[1], z + o[2]); parent.add(m); }); }
triad(scene, [-G.foot[0] / 2, -G.foot[1] / 2], G.base_t + .005, G.triad_l);
const sph = new THREE.SphereGeometry(0.03, 12, 8), jm = M(0x6f737a);
G.base_j.forEach(p => { const s = new THREE.Mesh(sph, jm); s.position.set(...p); scene.add(s); });
const topG = new THREE.Group(); topG.matrixAutoUpdate = false; scene.add(topG);
const slab = box(G.top_side, G.top_side, G.top_t, 0xd9a441); slab.position.z = -G.top_t / 2; topG.add(slab);
G.top_j.forEach(p => { const s = new THREE.Mesh(sph, jm); s.position.set(...p); topG.add(s); });
triad(topG, [0, 0], G.plate_t + .005, G.triad_l);
const legGeo = new THREE.CylinderGeometry(0.02, 0.02, 1, 10); legGeo.rotateX(Math.PI / 2); // unit length along z
const legs = G.base_j.map(() => { const m = new THREE.Mesh(legGeo, M(0xc9ccd1)); scene.add(m); return m; });
const plates = [], arrows = [];
for (let i = 0; i < 2; i++) {
  const m = box(G.plate_side, G.plate_side, G.plate_t, G.colors[i][0]); m.position.set(i == 0 ? G.plate_x : -G.plate_x, 0, G.plate_t / 2); topG.add(m); plates.push(m);
  const a = new THREE.Group(), am = M(G.colors[i][2]);
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.014, 0.014, 1, 12), am); shaft.rotation.x = Math.PI / 2; a.add(shaft);
  const head = new THREE.Mesh(new THREE.ConeGeometry(0.035, 0.08, 16), am); head.rotation.x = Math.PI / 2; a.add(head);
  a.userData = {shaft, head}; a.visible = false; topG.add(a); arrows.push(a);
}
const ghost = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(G.ghost_side, G.ghost_side, 0.006)), new THREE.LineBasicMaterial({color: 0x2ecc71}));
ghost.visible = false; scene.add(ghost);
document.getElementById('key').textContent = 'red = right (+sway)\\ngreen = front (+surge)\\nblue = up\\nplates: R red, L blue\\nrotation drawn x' + G.tilt_gain + '\\ntop size est., legs schematic';
const hud = document.getElementById('hud');
let latest = null, nMsg = 0, nFrame = 0, tStat = performance.now(), fps = 0, mps = 0, lastT = 0;
const v0 = new THREE.Vector3(), v1 = new THREE.Vector3(), mT = new THREE.Matrix4(), dir = new THREE.Vector3(), zAxis = new THREE.Vector3(0, 0, 1);
function connect() {
  const ws = new WebSocket('ws://' + location.host + '/ws');
  ws.onmessage = e => { latest = JSON.parse(e.data); nMsg++; };
  ws.onclose = () => { hud.textContent = 'disconnected: retrying...'; setTimeout(connect, 1000); };
}
connect();
function apply(f) {
  mT.fromArray(f.T); topG.matrix.copy(mT); topG.matrixWorldNeedsUpdate = true;
  for (let j = 0; j < 6; j++) {
    v0.set(...G.base_j[j]); v1.set(...G.top_j[j]).applyMatrix4(mT);
    const L = v0.distanceTo(v1), m = legs[j]; m.position.copy(v0).add(v1).multiplyScalar(.5); m.scale.set(1, 1, L); m.lookAt(v1);
  }
  if (f.sp) { ghost.visible = true; ghost.position.set(f.sp[0] / 1000, f.sp[1] / 1000, G.top_z0 + f.sp[2] / 1000 + .003); } else ghost.visible = false;
  const lines = [];
  for (let i = 0; i < 2; i++) {
    const p = f.plates ? f.plates[i] : null, a = arrows[i];
    plates[i].material.color.setHex(G.colors[i][p && p.loaded ? 1 : 0]);
    const F = p && p.F, n = F ? Math.hypot(F[0], F[1], F[2]) : 0;
    if (p && p.loaded && p.cop && n > 1e-3) {
      a.visible = true; a.position.set(p.cop[0] / 1000, p.cop[1] / 1000, G.plate_t);
      const L = Math.max(Math.min(n * G.arrow_m_per_n, G.arrow_max), 0.09), sl = L - 0.08;
      a.quaternion.setFromUnitVectors(zAxis, dir.set(F[0] / n, F[1] / n, F[2] / n));
      a.userData.shaft.scale.set(1, sl, 1); a.userData.shaft.position.z = sl / 2; a.userData.head.position.z = sl + 0.04;
    } else a.visible = false;
    lines.push((i == 0 ? 'R' : 'L') + ' ' + (F ? 'F ' + F.map(v => v.toFixed(0).padStart(6)).join('') + ' N' : 'no force data') + (p && p.cop ? '  CoP ' + p.cop.map(v => v.toFixed(0).padStart(5)).join('') + ' mm' : ''));
  }
  const ps = f.pose ? 'sway ' + f.pose[0].toFixed(1) + '  surge ' + f.pose[1].toFixed(1) + '  heave ' + f.pose[2].toFixed(1) + ' mm\\nroll ' + f.pose[3].toFixed(2) + '  pitch ' + f.pose[4].toFixed(2) + '  yaw ' + f.pose[5].toFixed(2) + ' deg'
    + '  state 0x' + (f.state || 0).toString(16) + ((f.state & 0xE0) ? ' PARKED' : '') + ((f.state & 1) ? ' PAUSED' : '') : 'no pose (drawing home)';
  const sp = f.sp ? '\\nsetpoint ' + f.sp.map(v => v.toFixed(1)).join(', ') + ' mm' : '';
  hud.textContent = ps + sp + '\\n' + lines.join('\\n') + '\\n' + fps.toFixed(0) + ' fps, ' + mps.toFixed(0) + ' frames/s in';
}
function loop(t) {
  requestAnimationFrame(loop); nFrame++;
  if (t - tStat > 1000) { fps = nFrame * 1000 / (t - tStat); mps = nMsg * 1000 / (t - tStat); nFrame = 0; nMsg = 0; tStat = t; }
  if (latest) { apply(latest); latest = null; }
  controls.update(); renderer.render(scene, camera);
}
requestAnimationFrame(loop);
</script></body></html>"""


def _geometry():
    base, top = _joints()
    return {"foot": [FOOT_X, FOOT_Y], "base_t": BASE_T, "top_side": TOP_SIDE, "top_t": TOP_T, "top_z0": TOP_Z0,
            "plate_side": PLATE_SIDE, "plate_t": PLATE_T, "plate_x": PLATE_X, "ghost_side": GHOST_SIDE,
            "base_j": base.round(4).tolist(), "top_j": top.round(4).tolist(), "colors": PLATE_COLORS,
            "arrow_m_per_n": ARROW_M_PER_N, "arrow_max": ARROW_MAX_M, "triad_l": TRIAD_L, "tilt_gain": TILT_GAIN,
            "cam_target": CAM_TARGET, "cam_offset": CAM_OFFSET}


class LiveScene:
    """Live 3D view of the PS-6TL-350, force plates and ground reaction forces (browser, 1 message/frame)."""

    def __init__(self, source, rate_hz=60.0, open_browser=True, port=DEFAULT_PORT):
        import tornado.ioloop
        import tornado.web
        import tornado.websocket
        self.source, self.period = source, 1.0 / rate_hz
        self.update_times = deque(maxlen=2000)  # seconds per update() call (frame build + hand-off)
        self.clients, self._pending = set(), set()
        self._thread, self._stop = None, threading.Event()
        page = PAGE.replace("__GEOMETRY__", json.dumps(_geometry()))
        scene = self

        class Page(tornado.web.RequestHandler):
            def get(self):
                self.set_header("Cache-Control", "no-store")
                self.write(page)

        class Socket(tornado.websocket.WebSocketHandler):
            def open(self):
                self.set_nodelay(True)
                scene.clients.add(self)

            def on_close(self):
                scene.clients.discard(self)
                scene._pending.discard(self)

        class NoIcon(tornado.web.RequestHandler):
            def get(self):
                self.set_status(204)

        import logging
        logging.getLogger("tornado.access").setLevel(logging.ERROR)  # no per-request lines in the terminal
        app = tornado.web.Application([(r"/", Page), (r"/ws", Socket), (r"/favicon.ico", NoIcon),
                                       (r"/web/(.*)", tornado.web.StaticFileHandler, {"path": str(WEB)})])
        ready = threading.Event()

        def serve():
            import asyncio
            asyncio.set_event_loop(asyncio.new_event_loop())
            self.loop = tornado.ioloop.IOLoop.current()
            for p in range(port, port + 20):  # first free port
                try:
                    self.server = app.listen(p, address="127.0.0.1")
                    self.port = p
                    break
                except OSError:
                    continue
            ready.set()
            self.loop.start()

        self._server_thread = threading.Thread(target=serve, daemon=True)
        self._server_thread.start()
        ready.wait(5)
        self.url = f"http://127.0.0.1:{self.port}/"
        print(f"3D view: {self.url}")
        if open_browser:
            webbrowser.open(self.url)

    def _send(self, msg):
        """On the server loop: write to each client not still busy with the previous frame."""
        for c in list(self.clients):
            if c in self._pending:
                continue  # slow client: drop this frame rather than queue it
            try:
                fut = c.write_message(msg)
            except Exception:
                self.clients.discard(c)
                continue
            self._pending.add(c)
            fut.add_done_callback(lambda _, c=c: self._pending.discard(c))

    def update(self, pose, sp_mm, plates):
        """Build one frame and hand it to the server loop (non-blocking). Any argument may be None."""
        t0 = time.perf_counter()
        msg = json.dumps(frame(pose, sp_mm, plates), separators=(",", ":"))
        if self.clients:
            self.loop.add_callback(self._send, msg)
        self.update_times.append(time.perf_counter() - t0)

    def _run(self):
        warned = False
        nxt = time.perf_counter()
        while not self._stop.is_set():
            try:
                self.update(*self.source())
            except Exception as e:
                if not warned:
                    print(f"3D view: {type(e).__name__}: {e} (continuing)")
                    warned = True
            nxt += self.period
            delay = nxt - time.perf_counter()
            if delay < 0:
                nxt = time.perf_counter()  # behind: skip, don't catch up
            else:
                self._stop.wait(delay)

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)

    def close(self):
        self.stop()
        self.loop.add_callback(self.server.stop)
        self.loop.add_callback(self.loop.stop)


if __name__ == "__main__":
    t0 = time.time()

    def synthetic():
        t = time.time() - t0
        pose = (np.array([0.0, 100 * np.sin(np.pi * t), 0.0]), np.radians([0.3 * np.sin(np.pi * t), 0, 0]), 0x10)
        sp = [0.0, 100 * np.sin(np.pi * (t + 0.1)), 0.0]
        plates = [{"force_N": [20 * np.sin(t), 0, 350.0], "cop_mm": [125 + 30 * np.sin(1.3 * t), 30 * np.cos(t)], "loaded": True},
                  {"force_N": [0, 15 * np.cos(t), 330.0], "cop_mm": [-125 + 20 * np.cos(t), -25 * np.sin(1.7 * t)], "loaded": True}]
        return pose, sp, plates

    s = LiveScene(synthetic, rate_hz=60, open_browser=False).start()
    time.sleep(10)
    s.close()
    u = np.array(s.update_times) * 1000
    print(f"{len(u)} updates; update() mean {u.mean():.3f} ms, max {u.max():.2f} ms")
