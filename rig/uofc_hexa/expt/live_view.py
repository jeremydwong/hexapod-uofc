"""Live view of the Speedgoat state stream: CoP, platform setpoint, variability and FSM state.

Listens for rig/speedgoat/pack_state.m packets on UDP (default port 25000) and redraws
about 20 times a second. Top-down CoP with the trial's "near centre" circle and the running
SD; top-down platform setpoint; and the last --window seconds of state, setpoint, CoP and
SD against threshold with the stability timer.

Run: uv run hexapod-live                      (Windows may ask to allow Python through the firewall)
     uv run hexapod-live --snapshot out.png --seconds 20    (no window: save one frame)
"""
from __future__ import annotations

import argparse
from collections import deque
import socket
import threading
import time

import numpy as np

from uofc_hexa.expt import packet

STATE_COLORS = {0: "#9e9e9e", 1: "#2e86c1", 2: "#e67e22", 3: "#8e44ad", 4: "#16a085", 5: "#2c3e50", 9: "#c0392b"}
ROW = {code: i for i, code in enumerate(STATE_COLORS)}  # evenly spaced rows in the state plot


class Receiver(threading.Thread):
    def __init__(self, port, window_s):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", port))
        self.sock.settimeout(0.2)
        self.buf = deque(maxlen=int(window_s * 1000 * 1.2))
        self.lock = threading.Lock()
        self.received = self.bad = self.lost = 0
        self.last_seq = None
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
            self.last_seq = s.seq
            with self.lock:
                self.buf.append(np.array([getattr(s, f) for f in packet.FIELDS]))
            self.received += 1
            self._count += 1
            now = time.perf_counter()
            if now - self._t >= 1.0:
                self.rate, self._count, self._t = self._count / (now - self._t), 0, now

    def snapshot(self):
        with self.lock:
            return np.array(self.buf) if self.buf else None


def build_figure():
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(14, 8))
    gs = fig.add_gridspec(4, 3, width_ratios=[1, 1, 1.6], height_ratios=[0.8, 1, 1, 1], hspace=0.45, wspace=0.3)
    ax = {"cop": fig.add_subplot(gs[:, 0]), "plat": fig.add_subplot(gs[:, 1]), "state": fig.add_subplot(gs[0, 2])}
    ax["sp"] = fig.add_subplot(gs[1, 2], sharex=ax["state"])
    ax["copt"] = fig.add_subplot(gs[2, 2], sharex=ax["state"])
    ax["sd"] = fig.add_subplot(gs[3, 2], sharex=ax["state"])
    a = ax["cop"]
    a.set_title("Centre of pressure (plate frame)"); a.set_xlabel("x (mm, + right)"); a.set_ylabel("y (mm, + front)")
    a.set_aspect("equal"); a.grid(alpha=.3)
    a = ax["plat"]
    a.set_title("Platform setpoint (top view)"); a.set_xlabel("sway (mm, + right)"); a.set_ylabel("surge (mm, + front)")
    a.set_aspect("equal"); a.grid(alpha=.3); a.set_xlim(-300, 300); a.set_ylim(-320, 290)
    a.add_patch(__import__("matplotlib").patches.Rectangle((-266, -306), 532, 579, fill=False, ls="--", color="#999"))
    a.text(-262, 262, "single-axis limits at home", fontsize=7, color="#999")
    ax["state"].set_yticks(list(ROW.values())); ax["state"].set_yticklabels([packet.STATES[k] for k in ROW], fontsize=7)
    ax["state"].set_ylim(-0.5, len(ROW) - 0.5); ax["state"].set_title("FSM state", fontsize=9)
    ax["sp"].set_ylabel("setpoint (mm)"); ax["copt"].set_ylabel("CoP − centre (mm)")
    ax["sd"].set_ylabel("CoP SD (mm)"); ax["sd"].set_xlabel("time (s)")
    for k in ("state", "sp", "copt", "sd"):
        ax[k].grid(alpha=.3)
    lines = {
        "cop_trail": ax["cop"].plot([], [], lw=.8, color="#2e86c1", alpha=.6)[0],
        "cop_now": ax["cop"].plot([], [], "o", color="#c0392b", ms=7)[0],
        "center": ax["cop"].plot([], [], "+", color="k", ms=12, mew=2)[0],
        "plat_trail": ax["plat"].plot([], [], lw=1, color="#e67e22", alpha=.6)[0],
        "plat_now": ax["plat"].plot([], [], "s", color="#e67e22", ms=9)[0],
        "state": ax["state"].plot([], [], drawstyle="steps-post", color="#333")[0],
        "sp_surge": ax["sp"].plot([], [], label="surge")[0], "sp_sway": ax["sp"].plot([], [], label="sway")[0],
        "cop_dx": ax["copt"].plot([], [], label="x")[0], "cop_dy": ax["copt"].plot([], [], label="y")[0],
        "sd": ax["sd"].plot([], [], label="SD", color="#8e44ad")[0],
        "sd_thr": ax["sd"].plot([], [], "--", color="#8e44ad", alpha=.6, label="SD threshold")[0],
        "stable": ax["sd"].plot([], [], color="#16a085", label="stable time (s)")[0],
    }
    import matplotlib.patches as mp
    circles = {"radius": mp.Circle((0, 0), 1, fill=False, color="#16a085", lw=1.5, ls="--"),
               "sd": mp.Circle((0, 0), 1, fill=True, color="#8e44ad", alpha=.15)}
    for c in circles.values():
        ax["cop"].add_patch(c)
    for k in ("sp", "copt", "sd"):
        ax[k].legend(loc="upper left", fontsize=7, ncol=3)
    title = fig.suptitle("waiting for packets...", fontsize=12)
    return fig, ax, lines, circles, title


def update(rx, fig, ax, lines, circles, title, window_s, trail_s=5.0):
    d = rx.snapshot()
    if d is None or len(d) < 2:
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
    lines["plat_trail"].set_data(d[trail, col["sp_sway"]], d[trail, col["sp_surge"]])
    lines["plat_now"].set_data([L("sp_sway")], [L("sp_surge")])
    lines["state"].set_data(ts, [ROW.get(int(v), 0) for v in G("state")])
    lines["state"].set_color(STATE_COLORS.get(int(L("state")), "#333"))
    lines["sp_surge"].set_data(ts, G("sp_surge")); lines["sp_sway"].set_data(ts, G("sp_sway"))
    lines["cop_dx"].set_data(ts, G("cop_x") - G("center_x")); lines["cop_dy"].set_data(ts, G("cop_y") - G("center_y"))
    lines["sd"].set_data(ts, G("cop_sd")); lines["sd_thr"].set_data(ts, G("sd_thr")); lines["stable"].set_data(ts, G("stable_s"))
    for k in ("sp", "copt", "sd"):
        ax[k].relim(); ax[k].autoscale_view(scalex=False)
    ax["state"].set_xlim(t[-1] - window_s, t[-1] + 0.2)
    state = int(L("state"))
    title.set_text(f"t {L('t'):7.1f} s   trial {int(L('trial'))}   {packet.STATES.get(state, state)} "
                   f"({L('t_state'):.1f} s)   stable {L('stable_s'):.1f}/{L('stable_need'):.1f} s   "
                   f"CoP SD {L('cop_sd'):.1f}/{L('sd_thr'):.1f} mm   |   {rx.rate:.0f} pkt/s, lost {rx.lost}, bad {rx.bad}")
    title.set_color(STATE_COLORS.get(state, "#333"))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=packet.DEFAULT_PORT)
    parser.add_argument("--window", type=float, default=20.0, help="seconds of history in the time plots")
    parser.add_argument("--snapshot", help="save one frame to this PNG after --seconds, no window")
    parser.add_argument("--seconds", type=float, default=10.0)
    args = parser.parse_args()
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
        update(rx, fig, ax, lines, circles, title, args.window)
        fig.savefig(args.snapshot, dpi=90)
        print(f"Saved {args.snapshot}: {rx.received} packets, {rx.lost} lost, {rx.bad} bad")
        rx.stop = True
        return
    anim = FuncAnimation(fig, lambda _: update(rx, fig, ax, lines, circles, title, args.window),
                         interval=50, cache_frame_data=False)
    plt.show()
    rx.stop = True
    del anim


if __name__ == "__main__":
    main()
