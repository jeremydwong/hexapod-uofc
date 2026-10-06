"""Map the reachable horizontal region (sway x surge) at each height, without moving the platform.

At each heave, the search goes outward from (0, 0) along --directions evenly spaced
directions in the sway/surge plane, and binary-searches the furthest reachable radius.
That outline is the reachable area at that height (it assumes the region is star-shaped
around home, which a constant-orientation hexapod workspace normally is). Rotations
are always zero.

Hardware probe: every command is sent PAUSED with the FullMatch strategy, which
rejects any pose the inverse kinematics cannot reach (the same check that rejects the
parked heave of -165.65 mm). Nothing moves. The last command is a paused pose near
park (heave -165.0 mm), the pose test_from_park.py starts from. Afterwards the
controller may report "paused" rather than "parked".

--synthetic instead uses the schematic geometry from report.py with leg strokes fitted
to the tech-sheet heave range. It is NOT the PS-6TL-350 and exists only to exercise
the report; its output is labelled synthetic.

Run: uv run hexapod-envelope --report                       M10 imitator (default serial)
     uv run hexapod-envelope --serial <S/N> --report        platform controller
     uv run hexapod-envelope --synthetic --report           no device, schematic test data
(ForceSeatPM closed for the device runs.)
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import time

import numpy as np

from uofc_hexa import vendor

SEARCH_MM = 400.0  # beyond any single-axis excursion in the tech sheet
PARK_SAFE_HEAVE_MM = -165.0
HEAVE_LIMITS_MM = (-165.8, 189.1)  # tech sheet, used only by the synthetic model


def directions(count):
    """Angles in degrees; 0 = +sway (right), 90 = +surge (front). Count is a multiple of 4."""
    return np.arange(count) * 360.0 / count


def radial_limit(reachable, heave, angle_deg, resolution):
    """Furthest reachable radius (mm) from (0, 0) along angle_deg at this heave."""
    u = np.array([np.cos(np.deg2rad(angle_deg)), np.sin(np.deg2rad(angle_deg))])
    lo, hi = 0.0, SEARCH_MM  # lo accepted, hi rejected
    while hi - lo > resolution:
        mid = (lo + hi) / 2
        sway, surge = u * mid
        lo, hi = (mid, hi) if reachable(sway, surge, heave) else (lo, mid)
    return lo


def outline_stats(radius, angles_deg):
    """Extents and enclosed area of the outline polygon."""
    a = np.deg2rad(angles_deg)
    x, y = radius * np.cos(a), radius * np.sin(a)  # sway, surge
    area = 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
    n = len(angles_deg)
    return {"surge_max": float(radius[n // 4]), "surge_min": float(-radius[3 * n // 4]),
            "sway_max": float(radius[0]), "sway_min": float(-radius[n // 2]),
            "area_cm2": float(area / 100.0)}


def synthetic_reachable():
    """Leg-length check on the schematic report.py geometry (NOT the PS-6TL-350)."""
    from uofc_hexa.hexapod.report import BASE_Z, NEUTRAL_H, joints
    base, top = joints()
    lift = BASE_Z + NEUTRAL_H

    def lengths(sway, surge, heave):
        offset = np.array([surge, -sway, heave]) / 1000.0  # same axes as the report animation
        return np.linalg.norm(top + offset + [0, 0, lift] - base, axis=1)

    l_min = lengths(0, 0, HEAVE_LIMITS_MM[0]).min()
    l_max = lengths(0, 0, HEAVE_LIMITS_MM[1]).max()
    def reachable(sway, surge, heave):
        legs = lengths(sway, surge, heave)
        return bool(np.all((legs >= l_min - 1e-9) & (legs <= l_max + 1e-9)))
    return reachable


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--library", default=vendor.default_library(),
                        help=f"ForceSeatDI native library (default: ${vendor.LIBRARY_ENV})")
    parser.add_argument("--serial", help="USB controller S/N (default: the M10 imitator)")
    parser.add_argument("--synthetic", action="store_true",
                        help="schematic test geometry instead of a device (NOT the PS-6TL-350)")
    parser.add_argument("--heave-step", type=float, default=10.0, help="mm between heights")
    parser.add_argument("--directions", type=int, default=72, help="directions per height (multiple of 4)")
    parser.add_argument("--resolution", type=float, default=1.0, help="mm, binary search stop")
    parser.add_argument("--output", type=Path,
                        help="JSON path (default: output/envelope.json, or output/envelope_synthetic.json)")
    parser.add_argument("--report", action="store_true",
                        help="also build surge-range-of-motion.html (or _synthetic.html) next to the JSON")
    args = parser.parse_args()
    if args.output is None:
        args.output = Path("output") / ("envelope_synthetic.json" if args.synthetic else "envelope.json")
    if args.directions % 4:
        parser.error("--directions must be a multiple of 4, so the pure surge and sway axes are included")

    device = None
    if args.synthetic:
        reachable = synthetic_reachable()
        source = "synthetic: schematic geometry, NOT the PS-6TL-350"
    else:
        if not args.library:
            parser.error(f"--library or ${vendor.LIBRARY_ENV} is required for a device probe")
        from uofc_hexa.hexapod import level_move as lm
        serial = args.serial or lm.M10_SERIAL
        device = lm.Device(args.library, None, serial, 0, 2000, 0, SEARCH_MM)
        source = f"measured: paused FullMatch probe, controller S/N {serial}"

        def reachable(sway, surge, heave):
            try:
                device.send(np.array([sway, surge, heave]), pause=True)  # paused: nothing moves
                return True
            except RuntimeError:
                return False

    angles = directions(args.directions)
    heights = []
    start = time.monotonic()
    try:
        print(f"{source}\nheave   surge_min  surge_max  sway_min  sway_max   area_cm2")
        for heave in np.arange(-160.0, 190.0, args.heave_step):
            if not reachable(0.0, 0.0, heave):
                print(f"{heave:6.0f}   not reachable at (0, 0)")
                continue
            radius = np.array([radial_limit(reachable, heave, a, args.resolution) for a in angles])
            stats = outline_stats(radius, angles)
            heights.append({"heave": float(heave), "radius": [round(float(r), 2) for r in radius], **stats})
            print(f"{heave:6.0f}   {stats['surge_min']:9.1f}  {stats['surge_max']:9.1f}  "
                  f"{stats['sway_min']:8.1f}  {stats['sway_max']:8.1f}  {stats['area_cm2']:9.0f}")
        if device:
            reachable(0.0, 0.0, PARK_SAFE_HEAVE_MM)  # leave a harmless paused setpoint near park
    finally:
        if device:
            device.close()

    result = {"source": source, "synthetic": args.synthetic, "date": datetime.now().isoformat(timespec="seconds"),
              "resolution_mm": args.resolution, "directions_deg": [float(a) for a in angles],
              "probe_seconds": round(time.monotonic() - start, 1), "heights": heights}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=1), encoding="utf-8")
    if heights:
        best = max(heights, key=lambda h: h["surge_max"] - h["surge_min"])
        print(f"\nWidest surge range: {best['surge_max'] - best['surge_min']:.1f} mm at heave "
              f"{best['heave']:+.0f} mm ({best['surge_min']:+.1f} to {best['surge_max']:+.1f})")
    print(f"Saved {args.output}")
    if args.report and heights:
        from uofc_hexa.hexapod.envelope_report import build
        build(args.output)
    elif heights:
        print(f"Report: uv run hexapod-envelope-report --input {args.output}")


if __name__ == "__main__":
    main()
