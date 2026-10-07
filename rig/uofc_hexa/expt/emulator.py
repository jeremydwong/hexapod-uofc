"""Stand-in for the Speedgoat: runs the FSM mirror at 1 kHz on synthetic CoP and sends state packets.

The synthetic participant is NOT a balance model; it only exercises the FSM and the host:
  - quiet-stance sway: Ornstein-Uhlenbeck noise per axis (--sway-sd mm, 0.8 s time constant)
  - perturbation response: the CoP shifts against the platform move, proportional to how far
    the platform is from where it settled (gain --gain), and recovers over --recover-s.

Run: uv run hexapod-expt-emulator --trials rig/speedgoat/trials_example.csv
     uv run hexapod-live          (in another terminal)
"""
from __future__ import annotations

import argparse
import socket
import time

import numpy as np

from uofc_hexa.expt import packet
from uofc_hexa.expt.fsm import FsmExpt, load_trials, S_DONE

DT = 0.001


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--trials", default="rig/speedgoat/trials_example.csv")
    parser.add_argument("--host", default="127.0.0.1", help="where hexapod-live listens")
    parser.add_argument("--port", type=int, default=packet.DEFAULT_PORT)
    parser.add_argument("--sway-sd", type=float, default=2.0, help="quiet-stance CoP SD per axis (mm)")
    parser.add_argument("--gain", type=float, default=0.3, help="CoP shift per mm of platform displacement")
    parser.add_argument("--recover-s", type=float, default=1.5, help="CoP recovery time constant (s)")
    parser.add_argument("--start-after", type=float, default=2.0, help="seconds before Start goes high")
    parser.add_argument("--speed", type=float, default=1.0, help="time multiplier (2 = twice real time)")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    trials = load_trials(args.trials)
    fsm = FsmExpt(trials)
    rng = np.random.default_rng(args.seed)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    stance = np.array([0.0, 20.0])  # where this participant stands, mm (plate frame)
    sway, settled = np.zeros(2), np.zeros(2)
    tau_sway = 0.8
    seq, t, wall0 = 0, 0.0, time.perf_counter()
    print(f"Emulating {len(trials)} trials -> {args.host}:{args.port} at 1 kHz (synthetic CoP). Ctrl-C to stop.")
    done_at = None
    try:
        while True:
            target = (time.perf_counter() - wall0) * args.speed
            while t < target:
                # quiet stance sway (OU process), then the response to platform displacement
                sway += -sway * DT / tau_sway + args.sway_sd * np.sqrt(2 * DT / tau_sway) * rng.standard_normal(2)
                platform = fsm.sp_last[:2]  # [sway, surge]
                settled += (platform - settled) * DT / args.recover_s
                cop = stance + sway - args.gain * (platform - settled)
                out = fsm.step(t, start=t >= args.start_after, host_ok=True, cop_xy=cop, fz_total=700.0)
                out.update(magic=packet.MAGIC, version=packet.VERSION, seq=seq)
                sock.sendto(packet.pack(out), (args.host, args.port))
                if out["events"]:
                    names = [n for bit, n in packet.EVENTS.items() if int(out["events"]) & bit]
                    print(f"t={t:7.2f}s trial {out['trial']}: {', '.join(names)}")
                seq += 1
                t += DT
                if out["state"] == S_DONE and done_at is None:
                    done_at = t
                    print(f"t={t:7.2f}s all trials done; still sending (Ctrl-C to stop)")
            time.sleep(0.005)
    except KeyboardInterrupt:
        print(f"Stopped after {seq} packets")


if __name__ == "__main__":
    main()
