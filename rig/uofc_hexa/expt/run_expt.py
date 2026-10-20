"""Run an experiment on the Speedgoat from the host: send the protocol, start it, live-plot, record.

Sequence:
  1. (--start-target) run MATLAB in batch to load and start expt_rt on the Speedgoat; or have
     it running already (start_expt_rt.m, or set it as the target's startup app).
  2. Wait for the Speedgoat's state stream (UDP --port, 1 kHz).
  3. Send the protocol's trial table with the 100 Hz heartbeat (UDP --target:--cmd-port), until
     the Speedgoat echoes every row and the same checksum. Rejected rows stop here.
  4. Start (button, or --auto-start). The Speedgoat runs the trials on its own clock: wait at
     home, move out, wait for the CoP to settle (or max_wait_s), return home, next trial.
  5. At DONE, or on Stop, Start goes to 0. On exit the heartbeat keeps going until the
     Speedgoat is idle, so it does not fault mid-move; then the stream is saved to --out.

The setpoint is NOT sent to the hexapod yet: this only drives and watches the Speedgoat.

Run: uv run hexapod-expt-run --protocol experiments/demo_surge.json
     uv run hexapod-expt-emulator & uv run hexapod-expt-run --target 127.0.0.1 --auto-start   (no Speedgoat)
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import socket
import subprocess
import threading
import time

import numpy as np

from uofc_hexa.expt import command, packet, protocol
from uofc_hexa.expt.fsm import S_DONE, S_FAULT, S_IDLE
from uofc_hexa.expt.live_view import Receiver, build_figure, update

SPEEDGOAT_DIR = Path(__file__).resolve().parents[2] / "speedgoat"


class Commander(threading.Thread):
    """Heartbeat + start flag + trial rows (round robin while stopped), at --rate Hz."""

    def __init__(self, target, port, trials, rate_hz):
        super().__init__(daemon=True)
        self.addr, self.trials, self.period = (target, port), trials, 1.0 / rate_hz
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.start_flag = False
        self.running = True
        self.sent = 0

    def run(self):
        seq, row, next_t = 0, 0, time.perf_counter()
        while self.running:
            if self.start_flag:
                data = command.pack(seq, True, len(self.trials))
            else:
                data = command.pack(seq, False, len(self.trials), row + 1, self.trials[row])
                row = (row + 1) % len(self.trials)
            try:
                self.sock.sendto(data, self.addr)
                self.sent += 1
            except OSError:  # network down or unreachable: keep trying, host_ok will show it
                pass
            seq += 1
            next_t += self.period
            time.sleep(max(0.0, next_t - time.perf_counter()))


class Session:
    """Host-side steps, polled from the plot timer (or the headless loop)."""

    def __init__(self, rx, cmd, trials, auto_start, exit_when_done):
        self.rx, self.cmd, self.trials = rx, cmd, trials
        self.expected = command.table_sum(trials)
        self.auto_start, self.exit_when_done = auto_start, exit_when_done
        self.started = self.finished = False
        self.done_at = None
        self.status = "waiting for the Speedgoat"

    def loaded(self, s):
        return (int(s.n_trials) == len(self.trials) and int(s.n_loaded) == len(self.trials)
                and int(s.n_rejected) == 0 and command.sums_match(s.table_sum, self.expected))

    def start(self):
        s = self.rx.last
        if s is not None and self.loaded(s) and int(s.state) in (S_IDLE, S_DONE):
            self.cmd.start_flag, self.started, self.done_at = True, True, None
            print("Start sent")

    def stop(self):
        if self.cmd.start_flag:
            self.cmd.start_flag = False
            print("Stop sent: the Speedgoat finishes the current trial's return, then idles")

    def poll(self):
        s = self.rx.last
        if s is None:
            self.status = (f"no state packets on UDP {self.rx.sock.getsockname()[1]}"
                           + (f" ({self.rx.bad} bad: old model version?)" if self.rx.bad else ""))
            return
        st = int(s.state)
        if int(s.n_rejected):
            self.status = f"Speedgoat REJECTED {int(s.n_rejected)} rows (limits): fix the protocol"
        elif not self.loaded(s):
            self.status = f"loading table {int(s.n_loaded)}/{len(self.trials)}"
        elif st == S_FAULT:
            self.cmd.start_flag = False
            self.status = "FAULT (host link lost): stop and restart the app on the Speedgoat"
        elif not self.started:
            if self.auto_start:
                self.start()
            self.status = "table loaded: press Start"
        elif st == S_DONE or (st == S_IDLE and not self.cmd.start_flag):
            self.cmd.start_flag = False
            self.done_at = self.done_at or time.perf_counter()
            if self.status not in ("done", "stopped"):
                self.status = "done" if st == S_DONE else "stopped"
            if self.exit_when_done and time.perf_counter() - self.done_at > 2.0:
                self.finished = True
        else:
            self.status = "running"


def start_target(matlab):
    """Load and start expt_rt on the Speedgoat via MATLAB in batch mode (MATLAB exits, the app runs on)."""
    cmd = [matlab, "-batch", f"cd('{SPEEDGOAT_DIR.as_posix()}'); start_expt_rt"]
    print("Starting the Speedgoat app: " + " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode:
        raise SystemExit(f"MATLAB exited with {r.returncode}; start expt_rt by hand (start_expt_rt.m)")


def shutdown(rx, cmd, timeout_s=20.0):
    """Start = 0, keep the heartbeat until the Speedgoat is idle (or faulted), then stop sending."""
    cmd.start_flag = False
    t0 = time.perf_counter()
    while rx.last is not None and int(rx.last.state) not in (S_IDLE, S_DONE, S_FAULT):
        if time.perf_counter() - t0 > timeout_s:
            print("Speedgoat still not idle; stopping the heartbeat anyway (it will FAULT and hold)")
            break
        time.sleep(0.05)
    time.sleep(0.1)
    cmd.running = False


def save(rx, out_dir, name):
    with rx.lock:
        data = np.array(rx.record) if rx.record else np.zeros((0, len(packet.FIELDS)))
    out = Path(out_dir) / f"{name}_{datetime.now():%Y%m%d_%H%M%S}.npz"
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, data=data, fields=np.array(packet.FIELDS))
    print(f"Saved {len(data)} packets to {out} ({rx.lost} lost, {rx.bad} bad)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--protocol", default="experiments/demo_surge.json")
    parser.add_argument("--target", default="192.168.7.5", help="Speedgoat IP (127.0.0.1 for the emulator)")
    parser.add_argument("--cmd-port", type=int, default=command.DEFAULT_PORT)
    parser.add_argument("--port", type=int, default=packet.DEFAULT_PORT, help="state stream from the Speedgoat")
    parser.add_argument("--rate", type=float, default=100.0, help="command packets per second")
    parser.add_argument("--start-target", action="store_true", help="run MATLAB first to load and start expt_rt")
    parser.add_argument("--matlab", default="matlab", help="MATLAB executable for --start-target")
    parser.add_argument("--auto-start", action="store_true", help="start as soon as the table is loaded")
    parser.add_argument("--exit-when-done", action="store_true")
    parser.add_argument("--window", type=float, default=20.0, help="seconds of history in the time plots")
    parser.add_argument("--headless", metavar="PNG", help="no window: run, then save the last frame here")
    parser.add_argument("--timeout", type=float, default=600.0, help="headless: give up after this many s")
    parser.add_argument("--out", default="output/expt", help="where the recorded stream is saved")
    args = parser.parse_args()

    name, trials = protocol.load(args.protocol)
    print(f"{name}: {len(trials)} trials -> Speedgoat {args.target}:{args.cmd_port}, "
          f"state on UDP {args.port}, checksum {command.table_sum(trials):.6g}")
    if args.start_target:
        start_target(args.matlab)

    rx = Receiver(args.port, args.window, record=True)
    rx.start()
    cmd = Commander(args.target, args.cmd_port, trials, args.rate)
    cmd.start()
    session = Session(rx, cmd, trials, args.auto_start or bool(args.headless),
                      args.exit_when_done or bool(args.headless))
    last_status = None

    def tick():
        nonlocal last_status
        session.poll()
        if session.status != last_status:
            print(f"[{datetime.now():%H:%M:%S}] {session.status}")
            last_status = session.status

    import matplotlib
    if args.headless:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax, lines, circles, title = build_figure()
    try:
        if args.headless:
            t0 = time.perf_counter()
            while not session.finished and time.perf_counter() - t0 < args.timeout:
                tick()
                time.sleep(0.05)
            update(rx, fig, ax, lines, circles, title, args.window, status=session.status)
            fig.savefig(args.headless, dpi=90)
            print(f"Saved {args.headless}")
        else:
            from matplotlib.animation import FuncAnimation
            from matplotlib.widgets import Button
            b_start = Button(fig.add_axes([0.02, 0.02, 0.08, 0.045]), "Start", color="#d5f5e3")
            b_stop = Button(fig.add_axes([0.11, 0.02, 0.08, 0.045]), "Stop", color="#fadbd8")
            b_start.on_clicked(lambda _: session.start())
            b_stop.on_clicked(lambda _: session.stop())

            def frame(_):
                tick()
                update(rx, fig, ax, lines, circles, title, args.window, status=session.status)
                if session.finished:
                    plt.close(fig)

            anim = FuncAnimation(fig, frame, interval=50, cache_frame_data=False)
            plt.show()
            del anim
    except KeyboardInterrupt:
        pass
    finally:
        print("Shutting down: Start = 0, waiting for the Speedgoat to idle")
        shutdown(rx, cmd)
        rx.stop = True
        save(rx, args.out, name)


if __name__ == "__main__":
    main()
