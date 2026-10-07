"""How fast can a 300 mm surge go? Step and fast-move tests, M10 MOTION IMITATOR ONLY.

Sends instant 300 mm setpoint jumps and fast smooth moves, and logs the reported pose as
fast as the SDK can be polled. On the imitator this shows the motion the controller
model generates by itself (its ramps and speed limits) for each acceleration profile and
maxSpeed setting. On a real platform these commands would be violent, so the script
refuses to run unless the connected controller reports the M10's serial.

Sequence: lift from park (10 mm/s) -> slow move to the stroke start -> tests -> home ->
lower -> park. Writes output/reachability/dynamics.csv (every sample) and
dynamics.json (per-test metrics).

Run: uv run hexapod-dynamics     (ForceSeatPM closed, M10 on USB)
"""
from __future__ import annotations

import argparse
import ctypes as ct
import csv
import json
from pathlib import Path
import time

import numpy as np

from uofc_hexa import vendor
from uofc_hexa.hexapod import level_move as lm
from uofc_hexa.hexapod import test_from_park as tp

STROKE = (-166.7, 133.3)  # 300 mm centred in the measured home-height surge range (-306.2 / +272.7)
PROFILES = {"auto": 0, "rapid": 1, "balanced": 2, "smoothest": 3}
SPEEDS = [4000, 16000, 32767, 65535]  # FSDI maxSpeed, logical units (65535 = no limit)
SMOOTH_TIMES_S = [1.0, 0.7, 0.5]
HOLD_S = 3.0
IMITATOR_TILT_LIMIT_DEG = 20.0  # instant steps tilt the top frame in transit; log it, don't abort


def connected_serial(device):
    sn = ct.create_string_buffer(28)
    device.lib.ForceSeatDI_GetSerialNumber(device.api, sn)
    return sn.value.decode(errors="replace").replace("-", "").lower()


class Recorder:
    """Polls the pose as fast as possible while re-sending the current target every 10 ms."""

    def __init__(self, device):
        self.device, self.rows, self.t0 = device, [], time.perf_counter()

    def run(self, test, target_fn, duration):
        start = time.perf_counter()
        last_send = -1.0
        while (now := time.perf_counter()) - start < duration:
            t = now - start
            command = target_fn(t)
            if now - last_send >= 0.01:
                self.device.send(command)
                last_send = now
            xyz, rpy, act, state = tp.lenient_read(self.device, IMITATOR_TILT_LIMIT_DEG)
            self.rows.append([now - self.t0, test, t, *command, *xyz, *np.rad2deg(rpy), state])
        return command


def _smooth(x, n):
    return np.convolve(x, np.ones(n) / n, "same")


def metrics(rows, test, start, target):
    """Rise time, settle time, overshoot, peak speed/acceleration, tilt for one surge move.

    Robust to the SDK's occasional glitch samples and to Windows loop stalls: positions are
    median-filtered (5 samples), resampled to 1 ms, differentiated, then averaged over 21 ms
    (velocity) and 41 ms (acceleration).
    """
    sel = [row for row in rows if row[1] == test]
    t = np.array([row[2] for row in sel], dtype=float)
    raw = np.array([row[7] for row in sel], dtype=float)
    windows = np.lib.stride_tricks.sliding_window_view(np.pad(raw, 2, mode="edge"), 5)
    surge = np.median(windows, axis=1)
    grid = np.arange(0, t[-1], 0.001)
    s = np.interp(grid, t, surge)
    v = _smooth(np.gradient(s, 0.001), 21)
    a = _smooth(np.gradient(v, 0.001), 41)
    inner = slice(30, -30)  # ignore smoothing edge effects
    stroke = target - start
    progress = (s - start) / stroke
    def first(cond):
        idx = np.flatnonzero(cond)
        return float(grid[idx[0]]) if len(idx) else None
    t10, t90 = first(progress >= 0.1), first(progress >= 0.9)
    outside = np.flatnonzero(np.abs(s - target) > 1.0)
    settle = 0.0 if not len(outside) else (float(grid[outside[-1] + 1]) if outside[-1] + 1 < len(grid) else None)
    gaps = np.diff(t)
    return {"test": test, "start_mm": start, "target_mm": target,
            "samples": int(len(t)), "median_sample_ms": float(np.median(gaps) * 1000),
            "longest_gap_ms": float(gaps.max() * 1000),
            "rise_10_90_s": (t90 - t10) if t10 is not None and t90 is not None else None,
            "settle_1mm_s": settle,
            "overshoot_mm": float(max(0.0, np.max((s - target) * np.sign(stroke)))),
            "peak_speed_mm_s": float(np.max(np.abs(v[inner]))),
            "peak_accel_g": float(np.max(np.abs(a[inner])) / 9810.0),
            "peak_tilt_deg": float(np.max(np.abs([[row[9], row[10], row[11]] for row in sel]))),
            "peak_heave_dev_mm": float(np.max(np.abs([row[8] for row in sel]))),
            "final_error_mm": float(s[-1] - target)}


def reanalyze(folder):
    """Recompute dynamics.json metrics from dynamics.csv (no hardware)."""
    rows = []
    with (folder / "dynamics.csv").open() as stream:
        reader = csv.reader(stream)
        next(reader)
        for r in reader:
            rows.append([float(r[0]), r[1], *map(float, r[2:12]), int(r[12])])
    info = json.loads((folder / "dynamics.json").read_text(encoding="utf-8"))
    for test in info["tests"]:
        test.update(metrics(rows, test["test"], test["start_mm"], test["target_mm"]))
    (folder / "dynamics.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    for test in info["tests"]:
        print(f"{test['test']:24s} settle {test['settle_1mm_s']:.3f} s  rise {test['rise_10_90_s']:.3f} s  "
              f"{test['peak_speed_mm_s']:6.0f} mm/s  {test['peak_accel_g']:.2f} g  tilt {test['peak_tilt_deg']:.2f} deg  "
              f"gap {test['longest_gap_ms']:.0f} ms")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--library", default=vendor.default_library(), required=not vendor.default_library(),
                        help=f"ForceSeatDI native library (default: ${vendor.LIBRARY_ENV})")
    parser.add_argument("--run-byte", type=int, choices=[0, 1], default=0)
    parser.add_argument("--output", type=Path, default=Path("output") / "reachability")
    parser.add_argument("--reanalyze", action="store_true", help="recompute metrics from the saved CSV only")
    args = parser.parse_args()
    if args.reanalyze:
        return reanalyze(args.output)

    device = lm.Device(args.library, None, lm.M10_SERIAL, args.run_byte, 65535, 0, 400.0)
    sn = connected_serial(device)
    if sn != lm.M10_SERIAL.replace("-", "").lower():
        device.close()
        raise SystemExit(f"Refusing: connected controller {sn} is not the M10 imitator. "
                         "These tests send instant 300 mm steps.")
    print(f"M10 imitator {sn}: running step and fast-move tests")
    rec, rows_states, summary = Recorder(device), [], []
    t0 = lambda: time.perf_counter() - rec.t0
    try:
        parked, _, _, _ = tp.lenient_read(device)  # start from wherever it is (normally park)
        parked[2] = max(parked[2], tp.LOWEST_HEAVE_MM)
        park_pose = np.array([0.0, 0.0, tp.LOWEST_HEAVE_MM])
        device.bound = tp.LIFT_BOUND_MM
        device.speed = 2000
        tp.stream(device, parked, np.zeros(3), 10.0, "lift", t0, [], rows_states)
        device.bound = 400.0
        start, end = np.array([0, STROKE[0], 0.0]), np.array([0, STROKE[1], 0.0])
        tp.stream(device, np.zeros(3), start, 50.0, "to stroke start", t0, [], rows_states)
        device.speed = 65535

        for name, code in PROFILES.items():  # instant steps, controller ramps only
            device.accel_profile = code
            for label, a, b in [("fwd", start, end), ("back", end, start)]:
                test = f"step {name} {label}"
                rec.run(test, lambda t, b=b: b, HOLD_S)
                summary.append({"kind": "step", "profile": name, "max_speed": 65535,
                                **metrics(rec.rows, test, a[1], b[1])})
                print(f"{test}: {summary[-1]['peak_speed_mm_s']:.0f} mm/s, {summary[-1]['peak_accel_g']:.2f} g")

        device.accel_profile = PROFILES["auto"]
        for speed in SPEEDS[:-1]:  # maxSpeed scale (65535 already covered by 'auto' above)
            device.speed = speed
            for label, a, b in [("fwd", start, end), ("back", end, start)]:
                test = f"maxspeed {speed} {label}"
                rec.run(test, lambda t, b=b: b, HOLD_S + 2)
                summary.append({"kind": "maxspeed", "profile": "auto", "max_speed": speed,
                                **metrics(rec.rows, test, a[1], b[1])})
                print(f"{test}: {summary[-1]['peak_speed_mm_s']:.0f} mm/s")
        device.speed = 65535

        for duration in SMOOTH_TIMES_S:  # streamed smoothstep, like hexapod-park-test at high --rate
            for label, a, b in [("fwd", start, end), ("back", end, start)]:
                test = f"smooth {duration:g}s {label}"
                rec.run(test, lambda t, a=a, b=b, d=duration: a + (b - a) * lm.smoothstep(t / d), duration + 2)
                summary.append({"kind": "smooth", "profile": "auto", "max_speed": 65535, "duration_s": duration,
                                "commanded_peak_mm_s": 1.875 * 300 / duration,
                                **metrics(rec.rows, test, a[1], b[1])})
                print(f"{test}: {summary[-1]['peak_speed_mm_s']:.0f} mm/s (commanded peak "
                      f"{1.875 * 300 / duration:.0f})")

        device.speed = 2000
        tp.stream(device, start, np.zeros(3), 50.0, "home", t0, [], rows_states)
        device.bound = tp.LIFT_BOUND_MM
        tp.stream(device, np.zeros(3), park_pose, 10.0, "lower", t0, [], rows_states)
        device.send(park_pose, pause=True)
        park = device.lib.ForceSeatDI_Park
        park.restype, park.argtypes = ct.c_char, [ct.c_void_p, ct.c_uint8]
        park(device.api, 0)
    finally:
        device.close()
        args.output.mkdir(parents=True, exist_ok=True)
        with (args.output / "dynamics.csv").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["time_s", "test", "test_time_s", "cmd_sway_mm", "cmd_surge_mm", "cmd_heave_mm",
                             "sway_mm", "surge_mm", "heave_mm", "roll_deg", "pitch_deg", "yaw_deg", "state"])
            writer.writerows(rec.rows)
        (args.output / "dynamics.json").write_text(json.dumps(
            {"device": "M10 motion imitator", "stroke_mm": STROKE, "tests": summary}, indent=1), encoding="utf-8")
        print(f"Saved {args.output / 'dynamics.csv'} and dynamics.json ({len(rec.rows)} samples)")


if __name__ == "__main__":
    main()
