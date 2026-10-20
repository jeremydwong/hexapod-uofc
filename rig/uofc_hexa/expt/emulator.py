"""Stand-in for the Speedgoat's expt_rt model: host commands in, FSM at 1 kHz on synthetic CoP, state out.

Default: behaves like the real target. Listens for host commands (hexapod-expt-run) on
--cmd-port, loads the trial table they carry, starts when told, and streams state packets.
With --trials CSV it ignores the host and runs that table itself after --start-after s
(for hexapod-live on its own).

The synthetic participant is NOT a balance model; it only exercises the FSM and the host:
  - quiet-stance sway: Ornstein-Uhlenbeck noise per axis (--sway-sd mm, 0.8 s time constant)
  - perturbation response: the CoP shifts against the platform move, proportional to how far
    the platform is from where it settled (gain --gain), and recovers over --recover-s.
The analog inputs carry Fz-like volts on ch 3 and 9 and noise elsewhere.

Run: uv run hexapod-expt-emulator                         (then hexapod-expt-run --target 127.0.0.1)
     uv run hexapod-expt-emulator --trials rig/speedgoat/trials_example.csv   (then hexapod-live)
"""
from __future__ import annotations

import argparse
import socket
import time

import numpy as np

from uofc_hexa.expt import command, packet
from uofc_hexa.expt.fsm import FsmExpt, load_trials

DT = 0.001


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--trials", help="run this CSV without a host (old standalone mode)")
    parser.add_argument("--host", default="127.0.0.1", help="where the state packets go")
    parser.add_argument("--port", type=int, default=packet.DEFAULT_PORT)
    parser.add_argument("--cmd-port", type=int, default=command.DEFAULT_PORT, help="listen for host commands")
    parser.add_argument("--sway-sd", type=float, default=2.0, help="quiet-stance CoP SD per axis (mm)")
    parser.add_argument("--gain", type=float, default=0.3, help="CoP shift per mm of platform displacement")
    parser.add_argument("--recover-s", type=float, default=1.5, help="CoP recovery time constant (s)")
    parser.add_argument("--start-after", type=float, default=2.0, help="standalone: seconds before Start")
    parser.add_argument("--speed", type=float, default=1.0, help="time multiplier (2 = twice real time)")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    standalone = load_trials(args.trials) if args.trials else None
    fsm = FsmExpt(standalone or [])
    rx = command.HostRx()
    rng = np.random.default_rng(args.seed)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cmd_sock.bind(("0.0.0.0", args.cmd_port))
    cmd_sock.setblocking(False)
    stance = np.array([0.0, 20.0])  # where this participant stands, mm (plate frame)
    sway, settled = np.zeros(2), np.zeros(2)
    tau_sway = 0.8
    seq, t, wall0 = 0, 0.0, time.perf_counter()
    mode = f"standalone, {len(standalone)} trials" if standalone else f"waiting for host commands on UDP {args.cmd_port}"
    print(f"Emulating the Speedgoat ({mode}) -> {args.host}:{args.port} at 1 kHz. Ctrl-C to stop.")
    last_host = None
    try:
        while True:
            target = (time.perf_counter() - wall0) * args.speed
            while t < target:
                cmd = None
                try:  # like UDP Receive: at most one packet per step
                    cmd = command.unpack(cmd_sock.recv(4096))
                except BlockingIOError:
                    pass
                if standalone:
                    h = {"start": t >= args.start_after, "host_ok": True, "trials": None,
                         "n_trials": len(standalone), "n_loaded": len(standalone),
                         "table_sum": command.table_sum(standalone), "cmd_seq": 0, "n_rejected": 0}
                else:
                    h = rx.step(t, cmd)
                    if (h["host_ok"], h["n_loaded"], h["start"]) != last_host:
                        last_host = (h["host_ok"], h["n_loaded"], h["start"])
                        print(f"t={t:7.2f}s host_ok {int(h['host_ok'])}, table {h['n_loaded']}/{h['n_trials']} "
                              f"(rejected {h['n_rejected']}), start {int(h['start'])}")
                # quiet stance sway (OU process), then the response to platform displacement
                sway += -sway * DT / tau_sway + args.sway_sd * np.sqrt(2 * DT / tau_sway) * rng.standard_normal(2)
                platform = fsm.sp_last[:2]  # [sway, surge]
                settled += (platform - settled) * DT / args.recover_s
                cop = stance + sway - args.gain * (platform - settled)
                out = fsm.step(t, start=h["start"], host_ok=h["host_ok"], cop_xy=cop, fz_total=700.0,
                               trials=None if standalone or h["start"] else h["trials"])
                out.update({k: h[k] for k in ("n_trials", "n_loaded", "table_sum", "cmd_seq", "n_rejected")},
                           host_ok=float(h["host_ok"]), magic=packet.MAGIC, version=packet.VERSION, seq=seq)
                ai = 0.002 * rng.standard_normal(12)
                ai[2] += 0.35 + 0.002 * (cop[1] - stance[1])  # Fz-ish channels, as if plates were wired
                ai[8] += 0.35 - 0.002 * (cop[1] - stance[1])
                out.update({f"ai{i + 1}": v for i, v in enumerate(ai)})
                sock.sendto(packet.pack(out), (args.host, args.port))
                if out["events"]:
                    names = [n for bit, n in packet.EVENTS.items() if int(out["events"]) & bit]
                    print(f"t={t:7.2f}s trial {out['trial']}: {', '.join(names)}")
                seq += 1
                t += DT
            time.sleep(0.002)
    except KeyboardInterrupt:
        print(f"Stopped after {seq} packets")


if __name__ == "__main__":
    main()
