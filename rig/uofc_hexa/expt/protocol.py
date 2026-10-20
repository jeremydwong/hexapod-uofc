"""Experiment protocols: JSON on the host, sent to the Speedgoat as a trial table at run time.

A protocol is a name, defaults, and a list of trials; each trial overrides the defaults:

    {
      "name": "demo_surge",
      "defaults": {"random_s": 3, "peak_speed_mm_s": 100, "thresh_seconds_cop_stable": 1,
                   "cop_radius_mm": 30, "cop_sd_mm": 5, "max_wait_s": 6},
      "trials": [{"axis": "surge", "distance_mm": 50}, {"axis": "surge", "distance_mm": -50}]
    }

axis is "surge" (+ front) or "sway" (+ right), or 1 / 2 as in the CSV. Every trial is a move
out from home and a return to home (fsm_expt.m). The keys are fsm.COLUMNS.

Run: uv run hexapod-expt-protocol demo --out experiments/demo_surge.json
     uv run hexapod-expt-protocol show experiments/demo_surge.json
     uv run hexapod-expt-protocol csv experiments/demo_surge.json --out trials.csv   (for test_fsm_expt.m)
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from uofc_hexa.expt import command
from uofc_hexa.expt.fsm import COLUMNS

AXES = {"surge": 1, "sway": 2, 1: 1, 2: 2}


def load(path):
    """Read a protocol JSON; returns (name, list of trial dicts with every column as float)."""
    spec = json.loads(Path(path).read_text())
    defaults = spec.get("defaults", {})
    trials = []
    for i, t in enumerate(spec["trials"], 1):
        row = {**defaults, **t}
        row.setdefault("max_wait_s", 0.0)
        if row.get("axis") not in AXES:
            raise ValueError(f"trial {i}: axis must be surge or sway, not {row.get('axis')!r}")
        row["axis"] = AXES[row["axis"]]
        missing = [c for c in COLUMNS if c not in row]
        if missing:
            raise ValueError(f"trial {i}: missing {', '.join(missing)}")
        row = {c: float(row[c]) for c in COLUMNS}
        if not command.row_ok(row):
            raise ValueError(f"trial {i}: outside the safe limits or invalid: {row}")
        trials.append(row)
    if not 1 <= len(trials) <= command.N_MAX:
        raise ValueError(f"need 1..{command.N_MAX} trials, have {len(trials)}")
    return spec.get("name", Path(path).stem), trials


def demo(n_pairs=3, distance_mm=50.0, peak_speed_mm_s=100.0, seed=0):
    """A few surges forward and back, each returning home, with a jittered wait at home."""
    rng = np.random.default_rng(seed)
    trials = []
    for _ in range(n_pairs):
        for sign in (1, -1):
            trials.append({"axis": "surge", "distance_mm": sign * distance_mm,
                           "random_s": round(float(rng.uniform(2.0, 4.0)), 2)})
    return {
        "name": "demo_surge",
        "description": f"{n_pairs} pairs of +/-{distance_mm:g} mm surges at {peak_speed_mm_s:g} mm/s peak, "
                       "each followed by a return to home. max_wait_s returns after 6 s even if "
                       "the CoP never settles (uncalibrated plates, nobody standing).",
        "defaults": {"peak_speed_mm_s": peak_speed_mm_s, "thresh_seconds_cop_stable": 1.0,
                     "cop_radius_mm": 30.0, "cop_sd_mm": 5.0, "max_wait_s": 6.0},
        "trials": trials,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("demo", help="write the demo surge protocol")
    p.add_argument("--out", default="experiments/demo_surge.json")
    p.add_argument("--pairs", type=int, default=3)
    p.add_argument("--distance", type=float, default=50.0, help="mm")
    p.add_argument("--speed", type=float, default=100.0, help="peak mm/s")
    p = sub.add_parser("show", help="validate a protocol and print its trial table")
    p.add_argument("protocol")
    p = sub.add_parser("csv", help="write a protocol as a trial CSV (load_trials.m, hexapod-expt-emulator)")
    p.add_argument("protocol")
    p.add_argument("--out", required=True)
    args = parser.parse_args()

    if args.cmd == "demo":
        spec = demo(args.pairs, args.distance, args.speed)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(spec, indent=2) + "\n")
        name, trials = load(args.out)  # validates
        print(f"Wrote {args.out}: {len(trials)} trials")
    elif args.cmd == "show":
        name, trials = load(args.protocol)
        print(f"{name}: {len(trials)} trials, checksum {command.table_sum(trials):.6g}")
        print("  #  " + "  ".join(f"{c:>12}" for c in COLUMNS))
        for k, t in enumerate(trials, 1):
            print(f"{k:3d}  " + "  ".join(f"{t[c]:12g}" for c in COLUMNS))
    else:
        name, trials = load(args.protocol)
        with open(args.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["trial"] + COLUMNS)
            w.writeheader()
            for k, t in enumerate(trials, 1):
                w.writerow({"trial": k, **{c: f"{t[c]:g}" for c in COLUMNS}})
        print(f"Wrote {args.out}: {len(trials)} trials")


if __name__ == "__main__":
    main()
