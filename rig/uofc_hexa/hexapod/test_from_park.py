"""Park-to-park level sequence: lift from soft park to home, visit waypoints, lower back, park.

  lift    stream a smoothstep from the reported (parked) pose to (0,0,0) at --lift-rate mm/s
  check   before anything moves: every point of the planned test path (5 mm spacing) is sent
          PAUSED with FullMatch, which rejects poses the platform cannot reach. Any rejection
          stops the run while still parked.
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

from uofc_hexa import vendor
from uofc_hexa.hexapod import level_move as lm

LIFT_BOUND_MM = 170.0  # heave single excursion is -165.8 mm (tech sheet); lift/lower only
LOWEST_HEAVE_MM = -165.0  # FullMatch rejects the parked pose (-165.65 mm); -165.0 is accepted
STALL_S = 5.0  # abort lift if the platform has not moved 1 mm after this long
# Single-axis excursions from home, docs/PS-6TL-350-tech-sheet.pdf p.2 (sway, surge, heave).
AXIS_LIMITS_MM = {"sway": (-265.3, 265.3), "surge": (-306.0, 273.1), "heave": (-165.8, 189.1)}
EDGE_MARGIN_MM = 10.0  # waypoints must stay at least this far inside the tech-sheet limits
BOUND_MARGIN_MM = 15.0  # default --bound = largest waypoint + this
PRECHECK_STEP_MM = 5.0


def lenient_read(device, tilt_limit_deg=lm.TILT_LIMIT_DEG):
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
    limit = max(device.bound, LIFT_BOUND_MM)  # lift/lower: 170 mm; test phases: --bound
    if np.max(np.abs(xyz)) > limit or np.max(np.abs(rpy)) > np.deg2rad(tilt_limit_deg):
        raise RuntimeError(f"Pose outside ±{limit:g} mm / ±{tilt_limit_deg:g}° bounds")
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


def check_axis_limits(waypoints):
    """Names of waypoints closer than EDGE_MARGIN_MM to a tech-sheet single-axis limit."""
    bad = []
    for name, target in waypoints:
        for axis, (low, high) in AXIS_LIMITS_MM.items():
            value = target[lm.AXES[axis]]
            if not low + EDGE_MARGIN_MM <= value <= high - EDGE_MARGIN_MM:
                bad.append(f"{name} ({axis} {value:+g} mm; limit {low:g}/{high:+g}, margin {EDGE_MARGIN_MM:g})")
    return bad


def precheck_path(device, waypoints):
    """Send every point of the test path, PAUSED, before anything moves. Returns rejected poses.

    FullMatch makes the SDK reject unreachable poses, so a rejection here means the run would
    fail mid-motion. Ends with a paused setpoint at home; the lift then streams from the parked
    pose, so nothing jumps when motion starts.
    """
    rejected, last = [], np.zeros(3)
    for name, target in waypoints:
        steps = max(1, int(np.ceil(np.max(np.abs(target - last)) / PRECHECK_STEP_MM)))
        for u in np.linspace(0, 1, steps + 1):
            pose = last + (target - last) * u
            try:
                device.send(pose, pause=True)
            except RuntimeError:
                rejected.append((name, np.round(pose, 1)))
        last = target
    device.send(np.zeros(3), pause=True)
    return rejected


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
    parser.add_argument("--library", default=vendor.default_library(), required=not vendor.default_library(),
                        help=f"ForceSeatDI native library (default: ${vendor.LIBRARY_ENV})")
    transport = parser.add_mutually_exclusive_group()
    transport.add_argument("--serial", default=lm.M10_SERIAL,
                           help="USB controller S/N; 'any' = first attached device (default: the M10 imitator)")
    transport.add_argument("--ip", help="controller IP address, for a controller on Ethernet")
    parser.add_argument("--run-byte", type=int, choices=[0, 1], required=True)
    parser.add_argument("--sequence", default="surge:+250,surge:-250,home,sway:+250,home,sway:-250,home",
                        help="comma-separated waypoints, 'axis:mm' from home or 'home' (sway + is right, surge + is front)")
    parser.add_argument("--rest", type=float, default=3.0, help="seconds to rest at each waypoint")
    parser.add_argument("--rate", type=float, default=10.0, help="test setpoint rate, mm/s")
    parser.add_argument("--bound", type=float,
                        help=f"test-phase abort bound, mm (default: largest waypoint + {BOUND_MARGIN_MM:g})")
    parser.add_argument("--lift-rate", type=float, default=10.0, help="lift/lower setpoint rate, mm/s")
    parser.add_argument("--max-speed", type=int, default=2000)
    parser.add_argument("--hardware", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("output"),
                        help="output folder, relative to where you run the command")
    args = parser.parse_args()
    if not args.hardware:
        parser.error("--hardware is required")
    waypoints = parse_sequence(args.sequence)
    too_close = check_axis_limits(waypoints)
    if too_close:
        parser.error("waypoints too close to the platform's limits: " + "; ".join(too_close))
    largest = max(np.max(np.abs(target)) for _, target in waypoints)
    if args.bound is None:
        args.bound = largest + BOUND_MARGIN_MM
    if not largest < args.bound <= max(abs(v) for lim in AXIS_LIMITS_MM.values() for v in lim):
        parser.error("--bound must exceed every waypoint and stay within the tech-sheet limits")
    moves, last = 0.0, np.zeros(3)
    for _, target in waypoints:
        moves += max(3., 1.875 * np.max(np.abs(target - last)) / args.rate) + args.rest
        last = target
    lift = 2 * (max(3., 1.875 * abs(LOWEST_HEAVE_MM) / args.lift_rate) + 2)
    print("Sequence: lift -> " + " -> ".join(name for name, _ in waypoints) + " -> lower -> park")
    print(f"Test bound ±{args.bound:g} mm; estimated run time {(moves + lift) / 60:.1f} min")

    device = lm.Device(args.library, args.ip, args.serial, args.run_byte, args.max_speed, 0, LIFT_BOUND_MM)
    rows, states, clock0 = [], [], time.monotonic()
    t0 = lambda: time.monotonic() - clock0
    try:
        parked, _, _, state = lenient_read(device)
        print(f"Start: pose {np.round(parked, 2)} mm, state=0x{state:x}")
        parked[2] = max(parked[2], LOWEST_HEAVE_MM)
        device.bound = args.bound  # paused path check needs the full test range
        rejected = precheck_path(device, waypoints)
        device.bound = LIFT_BOUND_MM
        if rejected:
            raise RuntimeError(f"{len(rejected)} path points are unreachable, nothing moved. First: "
                               + "; ".join(f"{n} at {p}" for n, p in rejected[:3]))
        print("Path check: every point reachable (paused FullMatch probe)")
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
