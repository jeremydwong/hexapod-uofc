# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.3"]
# ///
"""Park-to-park level sequence: lift from soft park to home, visit waypoints, lower back, park.

  lift    stream a smoothstep from the reported (parked) pose to (0,0,0) at --lift-rate mm/s
  test    for each --sequence waypoint: smoothstep there at --rate mm/s, rest --rest s.
          Strict gate: unparked, unpaused, reported and commanded translation within ±--bound mm.
  lower   stream back to the pose recorded at start
  park    ForceSeatDI_Park(Normal), then log state for a few seconds
All phases are logged into one trajectory.csv (same columns as level_move.py, one time base).
"""
from __future__ import annotations

import argparse
import csv
import ctypes as ct
from pathlib import Path
import sys
import time

import numpy as np

import level_move as lm

HERE = Path(__file__).resolve().parent
LIFT_BOUND_MM = 170.0  # heave single excursion is -165.8 mm (tech sheet); lift/lower only
LOWEST_HEAVE_MM = -165.0  # FullMatch rejects the parked pose (-165.65 mm); -165.0 is accepted
STALL_S = 5.0  # abort lift if the platform has not moved 1 mm after this long


def lenient_read(device):
    """Like Device.read but allows park/pause bits (lift starts parked); still aborts on errors and tilt."""
    s = device.s
    info = lm.sized(s.FSDI_PlatformInfo)
    device.call("GetPlatformInfo", ct.byref(info))
    if info.moduleErrorCode:
        raise RuntimeError(f"Module {info.moduleErrorIndex}: error {info.moduleErrorCode}")
    pose = lm.sized(s.FSDI_ActualTopTablePositionPhysical)
    device.call("GetTopTablePosPhy", ct.byref(pose))
    act = lm.sized(s.FSDI_ActualActuatorsPositionLogical)
    device.call("GetActuatorsPosLog", ct.byref(act))
    if info.state & lm.STATE_OFFLINE or not info.state & lm.STATE_REF_RUN_DONE:
        raise RuntimeError(f"Device offline or not referenced; state=0x{info.state:x}")
    xyz = np.array([pose.sway, pose.surge, pose.heave], dtype=float)
    rpy = np.array([pose.roll, pose.pitch, pose.yaw], dtype=float)
    if not np.all(np.isfinite(np.r_[xyz, rpy])):
        raise RuntimeError("Nonfinite pose feedback")
    if np.max(np.abs(xyz)) > LIFT_BOUND_MM or np.max(np.abs(rpy)) > np.deg2rad(lm.TILT_LIMIT_DEG):
        raise RuntimeError(f"Pose outside ±{LIFT_BOUND_MM} mm / ±{lm.TILT_LIMIT_DEG}° lift bounds")
    return xyz, rpy, np.array(list(act.actualMotorPosition), dtype=float), info.state


def parse_sequence(text):
    """'surge:+30,home,sway:-30' -> [(name, xyz target mm)]."""
    waypoints = []
    for item in text.split(","):
        item = item.strip()
        target = np.zeros(3)
        if item != "home":
            axis, amount = item.split(":")
            target[lm.AXES[axis]] = float(amount)
        waypoints.append((item.replace(":", " "), target))
    return waypoints


def stream(device, start, end, rate, phase, t0, rows, states, hold=2., bound=None):
    """Stream a smoothstep from start to end at <= rate mm/s, then hold. Returns last command.

    With bound set (test phases), also require unparked/unpaused and reported pose within ±bound mm.
    """
    duration = max(3., 1.875 * np.max(np.abs(end - start)) / rate)
    print(f"{phase}: {np.round(start, 2)} -> {np.round(end, 2)} mm over {duration:.1f} s")
    command, begin = start.copy(), time.monotonic()
    previous = begin
    try:
        for k in range(int((duration + hold) / lm.DT) + 1):
            time.sleep(max(0, begin + k * lm.DT - time.monotonic()))
            now = time.monotonic()
            if k and now - previous > lm.DEADLINE_S:
                raise RuntimeError("Control deadline missed")
            dt, previous, t = (now - previous if k else lm.DT), now, now - begin
            actual, rpy, actuators, state = lenient_read(device)
            if bound is not None:
                if state & (lm.STATE_PAUSED | lm.STATE_PARK_MASK):
                    raise RuntimeError(f"Device paused or parked during test; state=0x{state:x}")
                if np.max(np.abs(actual)) > bound:
                    raise RuntimeError(f"Reported pose {np.round(actual, 2)} outside ±{bound} mm test bound")
            reference = start + (end - start) * lm.smoothstep(t / duration)
            command = command + np.clip(reference - command, -rate * dt, rate * dt)
            device.send(command)
            rows.append([t0(), phase, *reference, *actual, *command, *rpy, *actuators])
            states.append((t0(), state))
            if phase == "lift" and t > STALL_S and np.max(np.abs(actual - start)) < 1.:
                raise RuntimeError(f"Platform did not leave park after {STALL_S:g} s; state=0x{state:x}")
        return command
    except BaseException:
        try:
            device.send(command, pause=True)
        except Exception as error:
            print(f"Pause request failed: {error}", file=sys.stderr)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", required=True)
    parser.add_argument("--serial", default=lm.M10_SERIAL)
    parser.add_argument("--run-byte", type=int, choices=[0, 1], required=True)
    parser.add_argument("--sequence", default="surge:+30,surge:-30,home,sway:+30,home,sway:-30,home",
                        help="comma-separated waypoints, 'axis:mm' from home or 'home' (sway + is right, surge + is front)")
    parser.add_argument("--rest", type=float, default=3.0, help="seconds to rest at each waypoint")
    parser.add_argument("--rate", type=float, default=10.0, help="test setpoint rate, mm/s")
    parser.add_argument("--bound", type=float, default=50.0, help="test-phase abort bound, mm (max 150)")
    parser.add_argument("--lift-rate", type=float, default=10.0, help="lift/lower setpoint rate, mm/s")
    parser.add_argument("--max-speed", type=int, default=2000)
    parser.add_argument("--hardware", action="store_true")
    parser.add_argument("--output", type=Path, default=HERE / "output")
    args = parser.parse_args()
    if not args.hardware:
        parser.error("--hardware is required")
    waypoints = parse_sequence(args.sequence)
    if not 0 < args.bound <= lm.MAX_BOUND_MM:
        parser.error(f"--bound must be in (0, {lm.MAX_BOUND_MM:g}]")
    if any(np.max(np.abs(target)) >= args.bound for _, target in waypoints):
        parser.error("every waypoint must be inside --bound")
    print("Sequence: lift -> " + " -> ".join(name for name, _ in waypoints) + " -> lower -> park")

    device = lm.Device(args.library, None, args.serial, args.run_byte, args.max_speed, 0, LIFT_BOUND_MM)
    rows, states, clock0 = [], [], time.monotonic()
    t0 = lambda: time.monotonic() - clock0
    try:
        parked, _, _, state = lenient_read(device)
        print(f"Start: pose {np.round(parked, 2)} mm, state=0x{state:x}")
        parked[2] = max(parked[2], LOWEST_HEAVE_MM)
        stream(device, parked, np.zeros(3), args.lift_rate, "lift", t0, rows, states)

        device.bound, last = args.bound, np.zeros(3)
        for name, target in waypoints:
            last = stream(device, last, target, args.rate, name, t0, rows, states, hold=args.rest, bound=args.bound)

        device.bound = LIFT_BOUND_MM
        stream(device, last, parked, args.lift_rate, "lower", t0, rows, states)
        device.send(parked, pause=True)
        park = device.lib.ForceSeatDI_Park
        park.restype, park.argtypes = ct.c_char, [ct.c_void_p, ct.c_uint8]
        ok = park(device.api, 0)  # FSDI_ParkMode_Normal
        print(f"Park request: {'ok' if ok == b'\x01' else 'FAILED'}")
        for _ in range(30):
            time.sleep(0.1)
            actual, rpy, actuators, state = lenient_read(device)
            rows.append([t0(), "park", *parked, *actual, *parked, *rpy, *actuators])
            states.append((t0(), state))
        print(f"End: pose {np.round(actual, 2)} mm, state=0x{state:x}")
    finally:
        device.close()
        if rows:
            args.output.mkdir(parents=True, exist_ok=True)
            with (args.output / "trajectory.csv").open("w", newline="") as stream_:
                writer = csv.writer(stream_)
                writer.writerow(["time_s", "phase"] +
                                [f"{kind}_{axis}_mm" for kind in ["reference", "actual", "command"]
                                 for axis in ["sway", "surge", "heave"]] +
                                [f"actual_{axis}_rad" for axis in ["roll", "pitch", "yaw"]] +
                                [f"actuator_{i + 1}_logical" for i in range(6)])
                writer.writerows(rows)
            with (args.output / "states.csv").open("w", newline="") as stream_:
                csv.writer(stream_).writerows([["time_s", "state_hex"]] + [[t, f"0x{s:x}"] for t, s in states])
            print(f"Logged {len(rows)} rows to {args.output / 'trajectory.csv'}")


if __name__ == "__main__":
    main()
