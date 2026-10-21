"""Live view of the Speedgoat state stream: CoP on the plates, plate forces, setpoint, variability, FSM state.

Listens for rig/speedgoat/pack_state.m packets on UDP (default port 25000) and redraws
about 20 times a second. Top-down CoP on the two force plates with the trial's "near centre"
circle and the running SD; the plate forces (N, NÂ·m) over the last --window seconds; and
state, setpoint, CoP and SD against threshold with the stability timer.
hexapod-expt-run uses the same figure, plus Start/Stop buttons.

Forces and CoP are computed on the host from the tared analog volts (forces.py): the
Speedgoat's own cop_x / cop_y / fz_total still use placeholder calibration. Its centre,
radius and SD come from its FSM and are drawn as sent.

With --pose (or --scene) a meshcat 3D view (scene3d.py, in the browser) shows the platform's
reported pose (read-only over ForceSeatDI; never sends a command) against the setpoint, with
the plate forces.

Run: uv run hexapod-live                      (Windows may ask to allow Python through the firewall)
     uv run hexapod-live --pose               (+ live platform pose in 3D; $FORCESEATDI_LIBRARY set)
     uv run hexapod-live --snapshot out.png --seconds 20    (no window: save one frame)
"""
from __future__ import annotations

import argparse
import socket
import threading
import time

import numpy as np

from uofc_hexa import vendor
from uofc_hexa.expt import forces, packet

STATE_COLORS = {0: "#9e9e9e", 1: "#2e86c1", 2: "#e67e22", 3: "#8e44ad", 4: "#16a085", 5: "#2c3e50", 9: "#c0392b"}
ROW = {code: i for i, code in enumerate(STATE_COLORS)}  # evenly spaced rows in the state plot
COL = {f: i for i, f in enumerate(packet.FIELDS)}
AI0 = COL["ai1"]  # ai1..ai12 are contiguous
PLATE_COLORS = {"Fz": "#2e86c1", "Fx": "#e74c3c", "Fy": "#27ae60", "Mx": "#e67e22", "My": "#8e44ad", "Mz": "#16a085"}
MAX_POINTS = 600       # per drawn line (the time axes are ~500 px wide)
AUTOSCALE_EVERY = 10   # frames between y relim/autoscale
# Fixed y ranges of the plate-force panels for one person standing (N, N·m). An axis widens to 1.1x
# the history window's extreme on the side the data exceed, and snaps back once that has scrolled out.
FORCE_YLIM = {"fz": (-50.0, 1200.0), "fxy": (-300.0, 300.0), "mom": (-150.0, 150.0)}


class Receiver(threading.Thread):
    """Receives state packets into a preallocated ring buffer (rows = packet.FIELDS)."""

    def __init__(self, port, window_s, record=False):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 << 20)  # ride out plot redraws at 1 kHz
        self.sock.bind(("0.0.0.0", port))
        self.sock.settimeout(0.2)
        self.ring = np.zeros((int(window_s * 1000 * 1.2), len(packet.FIELDS)))
        self.n = 0  # rows written in total; the newest is at (n - 1) % len(ring)
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
            row = np.frombuffer(data, dtype="<f8")
            with self.lock:
                self.ring[self.n % len(self.ring)] = row
                self.n += 1
                if self.record is not None:
                    self.record.append(row)
            self.received += 1
            self._count += 1
            now = time.perf_counter()
            if now - self._t >= 1.0:
                self.rate, self._count, self._t = self._count / (now - self._t), 0, now

    def snapshot(self, last=None):
        """Copy of the newest `last` rows (default: all buffered), oldest first; None if empty."""
        with self.lock:
            n, size = self.n, len(self.ring)
            m = min(n, size) if last is None else min(n, size, last)
            if m == 0:
                return None
            i = n % size
            if m <= i:
                return self.ring[i - m:i].copy()
            return np.concatenate([self.ring[size - (m - i):], self.ring[:i]])


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


def start_scene(rx, pose_src=None):
    """meshcat 3D view fed by the stream (+ pose_src.pose if given); None, with a warning, if unavailable."""
    try:
        from uofc_hexa.expt.scene3d import LiveScene
    except Exception as e:
        print(f"WARNING: no 3D scene (scene3d import failed: {e}); continuing without it")
        return None

    def source():
        pose = getattr(pose_src, "pose", None) if pose_src is not None else None
        s = rx.last
        if s is None:
            return pose, None, None
        return pose, [s.sp_sway, s.sp_surge, s.sp_heave], forces.plates_for_scene(forces.from_state(s))

    try:
        scene = LiveScene(source)
        scene.start()
    except Exception as e:
        print(f"WARNING: 3D scene failed to start ({e}); continuing without it")
        return None
    return scene


def stop_scene(scene):
    if scene is not None:
        try:
            scene.stop()
        except Exception as e:
            print(f"WARNING: 3D scene stop: {e}")


def _plate_outline(cx, half=forces.PLATE_SIDE_MM / 2):
    return [cx - half, cx + half, cx + half, cx - half, cx - half], [-half, -half, half, half, -half]


def build_figure():
    import matplotlib.patches as mp
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(17, 9.5))
    gs = fig.add_gridspec(5, 3, width_ratios=[1.2, 1.4, 1.6], height_ratios=[0.8, 1, 1, 1, 1], hspace=0.5, wspace=0.25,
                          bottom=0.1)
    ax = {"cop": fig.add_subplot(gs[:, 0]), "state": fig.add_subplot(gs[0, 2])}
    fgs = gs[:, 1].subgridspec(3, 1, hspace=0.35)
    ax["fz"] = fig.add_subplot(fgs[0], sharex=ax["state"])
    ax["fxy"] = fig.add_subplot(fgs[1], sharex=ax["state"])
    ax["mom"] = fig.add_subplot(fgs[2], sharex=ax["state"])
    ax["sp"] = fig.add_subplot(gs[1, 2], sharex=ax["state"])
    ax["copt"] = fig.add_subplot(gs[2, 2], sharex=ax["state"])
    ax["sd"] = fig.add_subplot(gs[3, 2], sharex=ax["state"])
    ax["stable"] = fig.add_subplot(gs[4, 2], sharex=ax["state"])

    a = ax["cop"]
    a.set_title("Centre of pressure on the plates (host)", fontsize=10)
    a.set_xlabel("x (mm, + right)"); a.set_ylabel("y (mm, + front)")
    a.set_aspect("equal"); a.grid(alpha=.3)
    for (cx, _), name in zip(forces.PLATE_CENTERS_MM, forces.PLATE_NAMES):
        a.plot(*_plate_outline(cx), color="#555", lw=1.2)
        a.text(cx, forces.PLATE_SIDE_MM / 2 + 8, name, ha="center", fontsize=8, color="#555")
    a.set_xlim(-240, 240); a.set_ylim(-160, 160)

    ax["state"].set_yticks(list(ROW.values())); ax["state"].set_yticklabels([packet.STATES[k] for k in ROW], fontsize=7)
    ax["state"].set_ylim(-0.5, len(ROW) - 0.5); ax["state"].set_title("FSM state", fontsize=9)
    ax["fz"].set_title("Plate forces: lab gains, channel order ASSUMED, signs UNVERIFIED (R solid, L dashed)",
                       fontsize=8)
    ax["fz"].set_ylabel("Fz (N)"); ax["fxy"].set_ylabel("Fx, Fy (N)"); ax["mom"].set_ylabel("moments (NÂ·m)")
    ax["mom"].set_xlabel("time (s, 0 = newest packet)")
    for k, lim in FORCE_YLIM.items():
        ax[k].set_ylim(*lim)
    ax["sp"].set_ylabel("setpoint (mm)"); ax["copt"].set_ylabel("CoP host (mm)")
    ax["sd"].set_ylabel("CoP SD (mm)\n(Speedgoat)", fontsize=8); ax["stable"].set_ylabel("stable time (s)")
    ax["stable"].set_xlabel("time (s, 0 = newest packet)")
    for k in ("state", "fz", "fxy", "mom", "sp", "copt", "sd", "stable"):
        ax[k].grid(alpha=.3)
        ax[k].tick_params(labelsize=7, labelbottom=k in ("mom", "stable"))

    P = lambda k, *a, **kw: ax[k].plot([], [], *a, **kw)[0]
    lines = {
        "cop_trail": P("cop", lw=.8, color="#2e86c1", alpha=.6),
        "cop_now": P("cop", "o", color="#c0392b", ms=7),
        "plate_cop": P("cop", "x", color="#555", ms=6, mew=1.5),
        "center": P("cop", "+", color="k", ms=12, mew=2),
        "state": P("state", drawstyle="steps-post", color="#333"),
        "fz_r": P("fz", lw=.9, color=PLATE_COLORS["Fz"], label="R Fz"),
        "fz_l": P("fz", lw=.9, color=PLATE_COLORS["Fz"], ls="--", label="L Fz"),
        "fz_sum": P("fz", lw=1.2, color="#333", label="R+L Fz"),
        "sp_surge": P("sp", label="surge"), "sp_sway": P("sp", label="sway"),
        "cop_x": P("copt", label="x"), "cop_y": P("copt", label="y"),
        "sd": P("sd", label="SD", color="#8e44ad"),
        "sd_thr": P("sd", "--", color="#8e44ad", alpha=.6, label="SD threshold"),
        "stable": P("stable", color="#16a085", label="stable"),
        "stable_need": P("stable", "--", color="#16a085", alpha=.6, label="needed"),
    }
    for side, k, ls in (("R", 0, "-"), ("L", 1, "--")):
        for c in ("Fx", "Fy"):
            lines[f"{c}{k}"] = P("fxy", lw=.8, ls=ls, color=PLATE_COLORS[c], label=f"{side} {c}")
        for c in ("Mx", "My", "Mz"):
            lines[f"{c}{k}"] = P("mom", lw=.8, ls=ls, color=PLATE_COLORS[c], label=f"{side} {c}")
    circles = {"radius": mp.Circle((0, 0), 1, fill=False, color="#16a085", lw=1.5, ls="--"),
               "sd": mp.Circle((0, 0), 1, fill=True, color="#8e44ad", alpha=.15)}
    for c in circles.values():
        ax["cop"].add_patch(c)
    for k in ("fz", "sp", "copt", "sd", "stable"):
        ax[k].legend(loc="upper left", fontsize=7, ncol=3)
    ax["fxy"].legend(loc="upper left", fontsize=7, ncol=4, handlelength=1.5)
    ax["mom"].legend(loc="upper left", fontsize=7, ncol=6, handlelength=1.5, columnspacing=0.8)
    title = fig.suptitle("waiting for packets...", fontsize=12)
    return fig, ax, lines, circles, title


def _autoscale_y(a):
    """Rescale y only when the data leave the limits or use under 40% of them, so a blitted view
    rarely needs a full redraw. True if the limits changed."""
    ys = [ln.get_ydata() for ln in a.get_lines() if len(ln.get_ydata())]
    if not ys:
        return False
    with np.errstate(all="ignore"):
        y = np.concatenate([np.asarray(v, dtype=float) for v in ys])
        lo, hi = np.nanmin(y), np.nanmax(y)
    if not np.isfinite(lo):
        return False
    c0, c1 = a.get_ylim()
    pad = max(0.15 * (hi - lo), 0.5)
    if lo >= c0 and hi <= c1 and hi - lo + 2 * pad >= 0.4 * (c1 - c0):
        return False
    a.set_ylim(lo - pad, hi + pad)
    return True


def _force_ylim(a, default):
    """Keep default limits unless the plotted window exceeds them; then 1.1x the extreme on that side.
    Widens only when data leave the current limits and resets only when they fit the default, so the
    limits (and the full redraw) change rarely. True if the limits changed."""
    ys = [ln.get_ydata() for ln in a.get_lines() if len(ln.get_ydata())]
    if not ys:
        return False
    with np.errstate(all="ignore"):
        y = np.concatenate([np.asarray(v, dtype=float) for v in ys])
        lo, hi = np.nanmin(y), np.nanmax(y)
    if not np.isfinite(lo):
        return False
    d0, d1 = default
    c0, c1 = a.get_ylim()
    if lo >= d0 and hi <= d1:
        new = (d0, d1)
    elif lo < c0 or hi > c1:
        new = (1.1 * lo if lo < d0 else d0, 1.1 * hi if hi > d1 else d1)
    else:
        new = (c0, c1)
    if new == (c0, c1):
        return False
    a.set_ylim(*new)
    return True


def update(rx, fig, ax, lines, circles, title, window_s, trail_s=5.0, status="", pose=None):
    """Set the artists from the newest window_s of the stream; True if the axes limits changed (so a
    blitted view needs a full redraw). Time axes are relative (0 = newest packet) so they stay fixed.
    pose is accepted for compatibility and ignored (the pose is shown in the 3D scene)."""
    frame = update.frames = getattr(update, "frames", -1) + 1
    full = False
    if ax["state"].get_xlim() != (-window_s, 0.2):
        ax["state"].set_xlim(-window_s, 0.2)
        full = True
    d = rx.snapshot(int(window_s * 1000 * 1.1))  # a little extra in case packets arrive faster than 1 kHz
    if d is None or len(d) < 2:
        title.set_text(f"waiting for packets on UDP {rx.sock.getsockname()[1]}...")
        return full
    t = d[:, COL["t"]]
    d = d[t >= t[-1] - window_s]
    t = d[:, COL["t"]]
    step = max(1, -(-len(d) // MAX_POINTS))
    ds = d[::-1][::step][::-1]  # decimate, keeping the newest sample
    ts = ds[:, COL["t"]] - t[-1]
    G = lambda f: ds[:, COL[f]]
    last = d[-1]
    L = lambda f: last[COL[f]]

    # forces from the tared volts (decimated rows only)
    loads = forces.plate_loads(ds[:, AI0:AI0 + 12])  # (n, 2, 6)
    lines["fz_r"].set_data(ts, loads[:, 0, 2]); lines["fz_l"].set_data(ts, loads[:, 1, 2])
    lines["fz_sum"].set_data(ts, loads[:, :, 2].sum(axis=1))
    for k in range(2):
        for j, c in enumerate(("Fx", "Fy", "Fz", "Mx", "My", "Mz")):
            if c != "Fz":
                lines[f"{c}{k}"].set_data(ts, loads[:, k, j])
    _, cop_ds = forces.combined_many(ds[:, AI0:AI0 + 12])
    lines["cop_x"].set_data(ts, cop_ds[:, 0]); lines["cop_y"].set_data(ts, cop_ds[:, 1])

    # CoP panel: trail of the last trail_s, combined CoP now, per-plate CoPs
    tr = d[t >= t[-1] - trail_s]
    tr = tr[::-1][::max(1, -(-len(tr) // MAX_POINTS))][::-1]
    _, cop_tr = forces.combined_many(tr[:, AI0:AI0 + 12])
    lines["cop_trail"].set_data(cop_tr[:, 0], cop_tr[:, 1])
    fz_now, cop_now = forces.combined(last[AI0:AI0 + 12])
    pc, _ = forces.plate_cops(forces.plate_loads(last[AI0:AI0 + 12]))
    lines["plate_cop"].set_data(pc[:, 0], pc[:, 1])
    lines["cop_now"].set_data(*(([cop_now[0]], [cop_now[1]]) if cop_now is not None else ([], [])))
    cx, cy = L("center_x"), L("center_y")
    lines["center"].set_data([cx], [cy])
    circles["radius"].center, circles["radius"].radius = (cx, cy), max(L("radius"), 0.1)
    if cop_now is not None:
        circles["sd"].set_visible(True)
        circles["sd"].center, circles["sd"].radius = tuple(cop_now), max(L("cop_sd"), 0.1)
    else:
        circles["sd"].set_visible(False)

    lines["state"].set_data(ts, [ROW.get(int(v), 0) for v in G("state")])
    lines["state"].set_color(STATE_COLORS.get(int(L("state")), "#333"))
    lines["sp_surge"].set_data(ts, G("sp_surge")); lines["sp_sway"].set_data(ts, G("sp_sway"))
    lines["sd"].set_data(ts, G("cop_sd")); lines["sd_thr"].set_data(ts, G("sd_thr"))
    lines["stable"].set_data(ts, G("stable_s")); lines["stable_need"].set_data(ts, G("stable_need"))
    for k, lim in FORCE_YLIM.items():
        full |= _force_ylim(ax[k], lim)
    if frame % AUTOSCALE_EVERY == 0:
        for k in ("sp", "copt", "sd", "stable"):
            full |= _autoscale_y(ax[k])
    state = int(L("state"))
    host = "host ok" if L("host_ok") else "NO HOST"
    cop_txt = f"CoP {cop_now[0]:+.0f},{cop_now[1]:+.0f} mm" if cop_now is not None else "CoP -- (unloaded)"
    title.set_text(f"t {L('t'):7.1f} s   trial {int(L('trial'))}/{int(L('n_trials'))}   {packet.STATES.get(state, state)} "
                   f"({L('t_state'):.1f} s)   stable {L('stable_s'):.1f}/{L('stable_need'):.1f} s   "
                   f"CoP SD {L('cop_sd'):.1f}/{L('sd_thr'):.1f} mm   Fz {fz_now:.0f} N (host)   {cop_txt}\n"
                   f"{host}   table {int(L('n_loaded'))}/{int(L('n_trials'))}   |   "
                   f"{rx.rate:.0f} pkt/s, lost {rx.lost}, bad {rx.bad}   {status}")
    title.set_color(STATE_COLORS.get(state, "#333"))
    return full


class Blitter:
    """Interactive redraws: the axes, ticks and legends are drawn once into a cached background, and
    each frame only restores it and redraws the moving artists; a full draw happens only when
    update() reports changed limits (or on resize). Not for savefig: animated artists are skipped there."""

    def __init__(self, fig, lines, circles, title):
        self.fig, self.canvas = fig, fig.canvas
        self.artists = [a for a in lines.values()] + list(circles.values()) + [title]
        for a in self.artists:
            a.set_animated(True)
        self.bg = None
        self.canvas.mpl_connect("draw_event", self._on_draw)

    def _on_draw(self, _event):
        self.bg = self.canvas.copy_from_bbox(self.fig.bbox)
        self._draw_animated()

    def _draw_animated(self):
        for a in self.artists:
            self.fig.draw_artist(a)

    def frame(self, full):
        import matplotlib.pyplot as plt
        if not plt.fignum_exists(self.fig.number):  # closed by step() (run finished)
            return
        if full or self.bg is None:
            self.canvas.draw()  # recaptures the background via draw_event
        else:
            self.canvas.restore_region(self.bg)
            self._draw_animated()
        self.canvas.blit(self.fig.bbox)
        self.canvas.flush_events()


def animate(fig, lines, circles, title, step, interval_ms=50):
    """Call step() (returns update()'s full-redraw flag) every interval_ms and blit. Keep the returned
    timer referenced while the window is open."""
    blitter = Blitter(fig, lines, circles, title)
    timer = fig.canvas.new_timer(interval=interval_ms)
    timer.add_callback(lambda: blitter.frame(step()))
    timer.start()
    return timer


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=packet.DEFAULT_PORT)
    parser.add_argument("--window", type=float, default=20.0, help="seconds of history in the time plots")
    parser.add_argument("--snapshot", help="save one frame to this PNG after --seconds, no window")
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--pose", action="store_true",
                        help="also read the platform's pose over the SDK, read-only, for the 3D scene")
    parser.add_argument("--scene", action=argparse.BooleanOptionalAction, default=None,
                        help="meshcat 3D scene in the browser (default: on with --pose)")
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

    rx = Receiver(args.port, args.window)
    rx.start()
    scene = start_scene(rx, pose) if (args.pose if args.scene is None else args.scene) else None
    fig, ax, lines, circles, title = build_figure()
    try:
        if args.snapshot:
            time.sleep(args.seconds)
            update(rx, fig, ax, lines, circles, title, args.window)
            fig.savefig(args.snapshot, dpi=90)
            print(f"Saved {args.snapshot}: {rx.received} packets, {rx.lost} lost, {rx.bad} bad")
            return
        timer = animate(fig, lines, circles, title, lambda: update(rx, fig, ax, lines, circles, title, args.window))
        plt.show()
        timer.stop()
    finally:
        rx.stop = True
        stop_scene(scene)
        if pose:
            pose.stop = True
            pose.join(timeout=2)


if __name__ == "__main__":
    main()
