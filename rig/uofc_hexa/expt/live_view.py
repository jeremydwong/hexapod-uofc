"""Live view of the Speedgoat state stream: CoP, platform setpoint, variability and FSM state.

Listens for rig/speedgoat/pack_state.m packets on UDP (default port 25000) and redraws
about 20 times a second. Top-down CoP with the trial's "near centre" circle and the running
SD; top-down platform setpoint; and the last --window seconds of state, setpoint, CoP and
SD against threshold with the stability timer, and the raw analog inputs (V).
hexapod-expt-run uses the same figure, plus Start/Stop buttons.

With --pose, a 3D panel also shows the platform's reported pose (read-only over ForceSeatDI;
never sends a command) against the Speedgoat setpoint, with a right/front/up axis triad.

Run: uv run hexapod-live                      (Windows may ask to allow Python through the firewall)
     uv run hexapod-live --pose               (+ live platform pose; $FORCESEATDI_LIBRARY set)
     uv run hexapod-live --snapshot out.png --seconds 20    (no window: save one frame)
"""
from __future__ import annotations

import argparse
from collections import deque
import socket
import threading
import time

import numpy as np

from uofc_hexa import vendor
from uofc_hexa.expt import packet

TILT_GAIN = 10.0  # real tilts are < 1 deg: drawn rotation is exaggerated by this much (numbers are true)
STATE_COLORS = {0: "#9e9e9e", 1: "#2e86c1", 2: "#e67e22", 3: "#8e44ad", 4: "#16a085", 5: "#2c3e50", 9: "#c0392b"}
ROW = {code: i for i, code in enumerate(STATE_COLORS)}  # evenly spaced rows in the state plot
# ASSUMED channel map (the professor's ReadForcePlates groups AI 1-6 and 7-12; Bertec amplifiers output
# Fx Fy Fz Mx My Mz in that order). Unverified: press on each plate and check. Same map as expt_params.m.
AI_NAMES = ["Fx", "Fy", "Fz", "Mx", "My", "Mz"]
AI_COLORS = ["#e74c3c", "#27ae60", "#2e86c1", "#e67e22", "#8e44ad", "#16a085"]


def ai_label(i):
    """AI channel 1-12 -> 'R Fx' ... 'L Mz' under the assumed map."""
    return f"{'R' if i <= 6 else 'L'} {AI_NAMES[(i - 1) % 6]} ({i})"


class Receiver(threading.Thread):
    def __init__(self, port, window_s, record=False):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 << 20)  # ride out plot redraws at 1 kHz
        self.sock.bind(("0.0.0.0", port))
        self.sock.settimeout(0.2)
        self.buf = deque(maxlen=int(window_s * 1000 * 1.2))
        self.lock = threading.Lock()
        self.received = self.bad = self.lost = 0
        self.last_seq = None
        self.last = None  # latest packet (packet.State)
        self.record = [] if record else None  # every packet, for saving after the run
        self.rate, self._count, self._t = 0.0, 0, time.perf_counter()
        self.stop = False

    def run(self):
        while not self.stop:
            try:
                data, _ = self.sock.recvfrom(4096)
            except socket.timeout:
                self.rate = 0.0 if time.perf_counter() - self._t > 1 else self.rate
                continue
            s = packet.unpack(data)
            if s is None:
                self.bad += 1
                continue
            if self.last_seq is not None and s.seq > self.last_seq + 1:
                self.lost += int(s.seq - self.last_seq - 1)
            self.last_seq, self.last = s.seq, s
            row = np.array([getattr(s, f) for f in packet.FIELDS])
            with self.lock:
                self.buf.append(row)
                if self.record is not None:
                    self.record.append(row)
            self.received += 1
            self._count += 1
            now = time.perf_counter()
            if now - self._t >= 1.0:
                self.rate, self._count, self._t = self._count / (now - self._t), 0, now

    def snapshot(self):
        with self.lock:
            return np.array(self.buf) if self.buf else None


class PoseReader(threading.Thread):
    """Read-only: polls the controller's reported pose over the SDK (never sends a command).

    .pose = (xyz mm [sway, surge, heave], rpy rad, state) or None; .error = message if it stopped.
    hexapod-expt-run --hexapod does not use this: its relay owns the connection and exposes .pose.
    """

    def __init__(self, library, ip=None, serial="any", rate_hz=30.0):
        super().__init__(daemon=True)
        self.library, self.ip, self.serial, self.period = library, ip, serial, 1.0 / rate_hz
        self.pose = self.error = None
        self.stop = False

    def run(self):
        import ctypes as ct
        from uofc_hexa.hexapod import level_move as lm
        try:
            d = lm.Device(self.library, self.ip, self.serial, 0, 2000, 0, 1000.0)  # connect + status checks only
        except Exception as e:
            self.error = f"pose: {e}"
            return
        try:
            info, pose = lm.sized(d.s.FSDI_PlatformInfo), lm.sized(d.s.FSDI_ActualTopTablePositionPhysical)
            while not self.stop:
                d.call("GetPlatformInfo", ct.byref(info))
                d.call("GetTopTablePosPhy", ct.byref(pose))
                self.pose = (np.array([pose.sway, pose.surge, pose.heave]),
                             np.array([pose.roll, pose.pitch, pose.yaw]), int(info.state))
                time.sleep(self.period)
        except Exception as e:
            self.error = f"pose: {e}"
        finally:
            d.close()


# --- 3D platform panel. Frame: x = +sway (right), y = +surge (front), z = up, metres, floor at z = 0.
# Real: footprint and heights from docs/PS-6TL-350-tech-sheet.pdf p.2 (width 1726 x length 1660 mm,
# height 790 mm at min heave = parked, 1145 mm at max). Estimated: the square top frame's size
# (not in the sheet; from the photo). Schematic: joint positions (confidential; CAD needs an NDA).
FOOT_W, FOOT_L = 1.726, 1.660  # sway x surge
TOP_Z_HOME = 0.790 + 0.1658    # top surface at heave 0 (min height + 165.8 mm heave down-travel)
TOP_SIDE = 1.0                 # ESTIMATE
BASE_JOINT_R, TOP_JOINT_R, JOINT_Z, TOP_DEPTH = 0.62, 0.42, 0.12, 0.10
AXIS_LEN = 0.35


def _joints():
    """Six base joints (world) and six top joints (top frame, under the surface), paired 120 deg apart."""
    base, top = [], []
    for k in range(3):
        for sign in (-1, 1):
            a = np.deg2rad(90 + 120 * k + sign * 12)
            b = np.deg2rad(90 + 120 * k + sign * 48)
            base.append([BASE_JOINT_R * np.cos(a), BASE_JOINT_R * np.sin(a), JOINT_Z])
            top.append([TOP_JOINT_R * np.cos(b), TOP_JOINT_R * np.sin(b), -TOP_DEPTH])
    return np.array(base), np.array(top)


def _rot(roll, pitch, yaw):
    """Roll about front (y), pitch about right (x), yaw about up (z). Signs vs the SDK not yet checked."""
    cr, sr, cp, sp, cy, sy = np.cos(roll), np.sin(roll), np.cos(pitch), np.sin(pitch), np.cos(yaw), np.sin(yaw)
    ry = np.array([[cr, 0, sr], [0, 1, 0], [-sr, 0, cr]])
    rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return rz @ rx @ ry


def _square(w, l):
    return np.array([[-w / 2, -l / 2, 0], [w / 2, -l / 2, 0], [w / 2, l / 2, 0], [-w / 2, l / 2, 0]])


def build_platform(a3):
    """Static footprint and base joints, plus the moving artists."""
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    base, _ = _joints()
    a3.add_collection3d(Poly3DCollection([_square(FOOT_W, FOOT_L)], color="#40444c", alpha=.3, edgecolor="#40444c"))
    a3.scatter(*base.T, color="#6f737a", s=25)
    art = {"plate": Poly3DCollection([_square(TOP_SIDE, TOP_SIDE)], color="#d9a441", alpha=.8, edgecolor="#8a6420"),
           "legs": [a3.plot([], [], [], color="#9aa0a8", lw=3)[0] for _ in range(6)],
           "joints": a3.plot([], [], [], "o", color="#6f737a", ms=4)[0],
           "axes": [a3.plot([], [], [], color=c, lw=3)[0] for c in ("#e02020", "#20b020", "#2050e0")],
           "labels": [a3.text(0, 0, 0, s, color=c, fontsize=8, fontweight="bold")
                      for s, c in (("right", "#e02020"), ("front", "#20b020"), ("up", "#2050e0"))],
           "ghost": a3.plot([], [], [], "--", color="#2ecc71", lw=1.5)[0],
           "text": a3.text2D(0.0, 0.9, "", transform=a3.transAxes, fontsize=8, family="monospace")}
    a3.add_collection3d(art["plate"])
    a3.set_xlim(-0.9, 0.9); a3.set_ylim(-0.9, 0.9); a3.set_zlim(0, 1.2); a3.set_box_aspect((1, 1, 0.67))
    a3.set_xlabel("sway (m, + right)", fontsize=7); a3.set_ylabel("surge (m, + front)", fontsize=7)
    a3.set_zlabel("height (m)", fontsize=7)
    a3.tick_params(labelsize=6); a3.view_init(elev=20, azim=-60)
    a3.set_title("PS-6TL-350: gold = SDK pose, green = setpoint\nfootprint + heights real; top size est.; legs "
                 f"schematic; rotation ×{TILT_GAIN:g}", fontsize=8)
    return art


def draw_platform(art, pose, sp_mm, error=None):
    """pose: (xyz mm [sway, surge, heave], rpy rad, state) or None; sp_mm: Speedgoat setpoint or None."""
    home = np.array([0, 0, TOP_Z_HOME])
    if sp_mm is not None:
        g = _square(TOP_SIDE + 0.06, TOP_SIDE + 0.06) + home + np.asarray(sp_mm) / 1000
        art["ghost"].set_data_3d(*np.r_[g, g[:1]].T)
    if pose is None:
        art["text"].set_text(error or "no pose source (hexapod-live --pose, or a --hexapod run)")
        return
    xyz, rpy, state = pose
    R = _rot(*(np.asarray(rpy) * TILT_GAIN))
    p = home + np.asarray(xyz) / 1000  # SDK [sway, surge, heave] mm is already right / front / up
    base, top = _joints()
    tops = top @ R.T + p
    art["plate"].set_verts([_square(TOP_SIDE, TOP_SIDE) @ R.T + p])
    for j, leg in enumerate(art["legs"]):
        leg.set_data_3d(*np.c_[base[j], tops[j]])
    art["joints"].set_data_3d(*tops.T)
    o = p + R @ [0, 0, 0.01]
    for k, (line, label) in enumerate(zip(art["axes"], art["labels"])):
        tip = o + R[:, k] * AXIS_LEN
        line.set_data_3d(*np.c_[o, tip])
        label.set_position_3d(o + R[:, k] * AXIS_LEN * 1.15)
    deg = np.rad2deg(rpy)
    flags = (" PARKED" if state & 0xE0 else "") + (" PAUSED" if state & 1 else "")
    art["text"].set_text(f"sway {xyz[0]:+7.1f} surge {xyz[1]:+7.1f} heave {xyz[2]:+7.1f} mm\n"
                         f"roll {deg[0]:+6.2f} pitch {deg[1]:+6.2f} yaw {deg[2]:+6.2f} deg  0x{state:02x}{flags}")


def build_figure():
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(17, 9.5))
    gs = fig.add_gridspec(5, 3, width_ratios=[0.9, 1.5, 1.6], height_ratios=[0.8, 1, 1, 1, 1], hspace=0.5, wspace=0.3,
                          bottom=0.1)
    ax = {"cop": fig.add_subplot(gs[:, 0]), "plat": fig.add_subplot(gs[:, 1], projection="3d"), "state": fig.add_subplot(gs[0, 2])}
    ax["sp"] = fig.add_subplot(gs[1, 2], sharex=ax["state"])
    ax["copt"] = fig.add_subplot(gs[2, 2], sharex=ax["state"])
    ax["sd"] = fig.add_subplot(gs[3, 2], sharex=ax["state"])
    ax["ai"] = fig.add_subplot(gs[4, 2], sharex=ax["state"])
    a = ax["cop"]
    a.set_title("Centre of pressure (plate frame)"); a.set_xlabel("x (mm, + right)"); a.set_ylabel("y (mm, + front)")
    a.set_aspect("equal"); a.grid(alpha=.3)
    ax["state"].set_yticks(list(ROW.values())); ax["state"].set_yticklabels([packet.STATES[k] for k in ROW], fontsize=7)
    ax["state"].set_ylim(-0.5, len(ROW) - 0.5); ax["state"].set_title("FSM state", fontsize=9)
    ax["sp"].set_ylabel("setpoint (mm)"); ax["copt"].set_ylabel("CoP − centre (mm)")
    ax["sd"].set_ylabel("CoP SD (mm)"); ax["ai"].set_ylabel("analog in (V, tared)"); ax["ai"].set_xlabel("time (s)")
    for k in ("state", "sp", "copt", "sd", "ai"):
        ax[k].grid(alpha=.3)
    lines = {
        "cop_trail": ax["cop"].plot([], [], lw=.8, color="#2e86c1", alpha=.6)[0],
        "cop_now": ax["cop"].plot([], [], "o", color="#c0392b", ms=7)[0],
        "center": ax["cop"].plot([], [], "+", color="k", ms=12, mew=2)[0],
        "platform": build_platform(ax["plat"]),
        "state": ax["state"].plot([], [], drawstyle="steps-post", color="#333")[0],
        "sp_surge": ax["sp"].plot([], [], label="surge")[0], "sp_sway": ax["sp"].plot([], [], label="sway")[0],
        "cop_dx": ax["copt"].plot([], [], label="x")[0], "cop_dy": ax["copt"].plot([], [], label="y")[0],
        "sd": ax["sd"].plot([], [], label="SD", color="#8e44ad")[0],
        "sd_thr": ax["sd"].plot([], [], "--", color="#8e44ad", alpha=.6, label="SD threshold")[0],
        "stable": ax["sd"].plot([], [], color="#16a085", label="stable time (s)")[0],
        **{f"ai{i}": ax["ai"].plot([], [], lw=.8, color=AI_COLORS[(i - 1) % 6], ls="-" if i <= 6 else "--",
                                   label=ai_label(i))[0] for i in range(1, 13)},
    }
    import matplotlib.patches as mp
    circles = {"radius": mp.Circle((0, 0), 1, fill=False, color="#16a085", lw=1.5, ls="--"),
               "sd": mp.Circle((0, 0), 1, fill=True, color="#8e44ad", alpha=.15)}
    for c in circles.values():
        ax["cop"].add_patch(c)
    for k in ("sp", "copt", "sd"):
        ax[k].legend(loc="upper left", fontsize=7, ncol=3)
    ax["ai"].legend(loc="upper left", fontsize=6, ncol=6, handlelength=1.5, columnspacing=0.8)
    ax["ai"].set_title("AI 1-6 right plate, AI 7-12 left (dashed); order ASSUMED Fx Fy Fz Mx My Mz (Fy seen on a push)",
                       fontsize=7)
    title = fig.suptitle("waiting for packets...", fontsize=12)
    return fig, ax, lines, circles, title


def update(rx, fig, ax, lines, circles, title, window_s, trail_s=5.0, status="", pose=None):
    """pose: anything with .pose (and optionally .error): a PoseReader, or the relay of a --hexapod run."""
    d = rx.snapshot()
    pose_now = getattr(pose, "pose", None) if pose is not None else None
    if d is None or len(d) < 2:
        draw_platform(lines["platform"], pose_now, None, getattr(pose, "error", None))
        title.set_text(f"waiting for packets on UDP {rx.sock.getsockname()[1]}...")
        return
    col = {f: i for i, f in enumerate(packet.FIELDS)}
    g = lambda f: d[:, col[f]]
    t = g("t")
    keep = t >= t[-1] - window_s
    d, t = d[keep], t[keep]
    step = max(1, len(t) // 3000)  # decimate for drawing
    ds, ts = d[::step], t[::step]
    G = lambda f: ds[:, col[f]]
    last = d[-1]
    L = lambda f: last[col[f]]
    trail = t >= t[-1] - trail_s
    cx, cy = L("center_x"), L("center_y")
    lines["cop_trail"].set_data(d[trail, col["cop_x"]], d[trail, col["cop_y"]])
    lines["cop_now"].set_data([L("cop_x")], [L("cop_y")])
    lines["center"].set_data([cx], [cy])
    circles["radius"].center, circles["radius"].radius = (cx, cy), L("radius")
    circles["sd"].center, circles["sd"].radius = (L("cop_x"), L("cop_y")), max(L("cop_sd"), 0.1)
    span = max(60.0, 1.3 * np.max(np.abs(np.c_[d[trail, col["cop_x"]] - cx, d[trail, col["cop_y"]] - cy])))
    ax["cop"].set_xlim(cx - span, cx + span); ax["cop"].set_ylim(cy - span, cy + span)
    draw_platform(lines["platform"], pose_now, [L("sp_sway"), L("sp_surge"), L("sp_heave")],
                  getattr(pose, "error", None))
    lines["state"].set_data(ts, [ROW.get(int(v), 0) for v in G("state")])
    lines["state"].set_color(STATE_COLORS.get(int(L("state")), "#333"))
    lines["sp_surge"].set_data(ts, G("sp_surge")); lines["sp_sway"].set_data(ts, G("sp_sway"))
    lines["cop_dx"].set_data(ts, G("cop_x") - G("center_x")); lines["cop_dy"].set_data(ts, G("cop_y") - G("center_y"))
    lines["sd"].set_data(ts, G("cop_sd")); lines["sd_thr"].set_data(ts, G("sd_thr")); lines["stable"].set_data(ts, G("stable_s"))
    for i in range(1, 13):
        lines[f"ai{i}"].set_data(ts, G(f"ai{i}"))
    for k in ("sp", "copt", "sd", "ai"):
        ax[k].relim(); ax[k].autoscale_view(scalex=False)
    ax["state"].set_xlim(t[-1] - window_s, t[-1] + 0.2)
    state = int(L("state"))
    host = "host ok" if L("host_ok") else "NO HOST"
    title.set_text(f"t {L('t'):7.1f} s   trial {int(L('trial'))}/{int(L('n_trials'))}   {packet.STATES.get(state, state)} "
                   f"({L('t_state'):.1f} s)   stable {L('stable_s'):.1f}/{L('stable_need'):.1f} s   "
                   f"CoP SD {L('cop_sd'):.1f}/{L('sd_thr'):.1f} mm   Fz {L('fz_total'):.0f} N\n"
                   f"{host}   table {int(L('n_loaded'))}/{int(L('n_trials'))}   |   "
                   f"{rx.rate:.0f} pkt/s, lost {rx.lost}, bad {rx.bad}   {status}")
    title.set_color(STATE_COLORS.get(state, "#333"))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=packet.DEFAULT_PORT)
    parser.add_argument("--window", type=float, default=20.0, help="seconds of history in the time plots")
    parser.add_argument("--snapshot", help="save one frame to this PNG after --seconds, no window")
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--pose", action="store_true",
                        help="also read the platform's pose over the SDK, read-only, for the 3D panel")
    parser.add_argument("--library", default=vendor.default_library(),
                        help=f"ForceSeatDI native library (default: ${vendor.LIBRARY_ENV})")
    parser.add_argument("--ip", help="controller IP, for a controller on Ethernet")
    parser.add_argument("--serial", default="any", help="USB controller S/N (default: any attached)")
    args = parser.parse_args()
    if args.pose and not args.library:
        parser.error(f"--pose needs --library or ${vendor.LIBRARY_ENV}")
    pose = None
    if args.pose:
        pose = PoseReader(args.library, args.ip, args.serial)
        pose.start()
    import matplotlib
    if args.snapshot:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    rx = Receiver(args.port, args.window)
    rx.start()
    fig, ax, lines, circles, title = build_figure()
    if args.snapshot:
        time.sleep(args.seconds)
        update(rx, fig, ax, lines, circles, title, args.window, pose=pose)
        fig.savefig(args.snapshot, dpi=90)
        print(f"Saved {args.snapshot}: {rx.received} packets, {rx.lost} lost, {rx.bad} bad")
        rx.stop = True
        if pose:
            pose.stop = True
            pose.join(timeout=2)
        return
    anim = FuncAnimation(fig, lambda _: update(rx, fig, ax, lines, circles, title, args.window, pose=pose),
                         interval=50, cache_frame_data=False)
    plt.show()
    rx.stop = True
    if pose:
        pose.stop = True
        pose.join(timeout=2)
    del anim


if __name__ == "__main__":
    main()
