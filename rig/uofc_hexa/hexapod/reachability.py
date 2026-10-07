"""Is a level pose reachable? Answered from a saved reachability sweep, no device needed.

The sweep (hexapod-envelope; default: the M10 imitator sweep committed in
rig/data/reachability/imitator.json) stores, at each heave from -160 to +185 mm in 5 mm
steps, the furthest reachable distance from home in 72 directions of the sway/surge
plane, with roll = pitch = yaw = 0. For a query pose we take its direction and distance
from (0, 0) at that height, interpolate the limit linearly in direction (wrapping around)
and in heave, and compare.

Only level poses (no rotation). Heights outside the sweep count as unreachable: the real
limits are -165.8 / +189.1 mm, a few mm beyond the sweep.

Accuracy (2026-10-07, against the vendor library's own offline check, 60 000 random
poses): 99.9 % agreement. Right at the edge, interpolation can be up to ~11 mm optimistic,
all at heave -37 to -89 mm where the outline has a sharp corner. With a 10 mm margin there
were no false "reachable" answers, so the yes/no checks (reachable, grid, path_reachable)
default to margin_mm=10; pass 0 for the raw sweep. Range queries (surge_range, sway_range,
stroke) report the measured edges unless you pass a margin.

    from uofc_hexa.hexapod.reachability import Reachability
    r = Reachability.load()
    r.reachable(0, 250, 0)                      # sway, surge, heave in mm -> True (10 mm margin)
    r.reachable(sway, surge, heave, margin_mm=25)   # arrays broadcast like numpy
    r.margin(0, 250, 0)                         # mm to the edge (negative = outside)
    r.surge_range(-30)                          # (min, max) surge at that height
    r.stroke(0, length_mm=300)                  # centred 300 mm surge stroke, or None
    r.path_reachable([0, -167, 0], [0, 133, 0], margin_mm=10)
    ok = r.grid(sways, surges, heaves)          # boolean array over a meshgrid
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

DEFAULT_SWEEP = Path(__file__).resolve().parents[2] / "data" / "reachability" / "imitator.json"


class Reachability:
    def __init__(self, heights_mm, angles_deg, radius_mm, source=""):
        order = np.argsort(heights_mm)
        self.heights = np.asarray(heights_mm, dtype=float)[order]
        self.angles = np.asarray(angles_deg, dtype=float)
        self.radius = np.asarray(radius_mm, dtype=float)[order]  # (heights, directions)
        self.source = source
        if self.radius.shape != (len(self.heights), len(self.angles)):
            raise ValueError("radius must be heights x directions")
        self.step = 360.0 / len(self.angles)

    @classmethod
    def load(cls, path=DEFAULT_SWEEP):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls([h["heave"] for h in data["heights"]], data["directions_deg"],
                   [h["radius"] for h in data["heights"]], data.get("source", str(path)))

    def limit_radius(self, angle_deg, heave):
        """Furthest reachable distance (mm) from home along angle_deg (0 = +sway, 90 = +surge) at heave.

        NaN outside the swept heights.
        """
        angle = np.mod(np.asarray(angle_deg, dtype=float), 360.0)
        heave = np.asarray(heave, dtype=float)
        a = angle / self.step
        i0 = np.floor(a).astype(int) % len(self.angles)
        i1 = (i0 + 1) % len(self.angles)
        fa = a - np.floor(a)
        h = np.clip(heave, self.heights[0], self.heights[-1])
        j0 = np.clip(np.searchsorted(self.heights, h, side="right") - 1, 0, len(self.heights) - 2)
        j1 = j0 + 1
        fh = (h - self.heights[j0]) / (self.heights[j1] - self.heights[j0])
        r = lambda j, i: self.radius[j, i]
        at_j0 = r(j0, i0) * (1 - fa) + r(j0, i1) * fa
        at_j1 = r(j1, i0) * (1 - fa) + r(j1, i1) * fa
        out = at_j0 * (1 - fh) + at_j1 * fh
        return np.where((heave < self.heights[0]) | (heave > self.heights[-1]), np.nan, out)

    def margin(self, sway, surge, heave):
        """Distance (mm) from the pose to the edge of the reachable region, in its own direction.

        Positive = inside, negative = outside, -inf outside the swept heights.
        """
        sway, surge, heave = np.broadcast_arrays(*(np.asarray(v, dtype=float) for v in (sway, surge, heave)))
        dist = np.hypot(sway, surge)
        limit = self.limit_radius(np.degrees(np.arctan2(surge, sway)), heave)
        out = limit - dist
        return np.where(np.isnan(out), -np.inf, out)

    def reachable(self, sway, surge, heave, margin_mm=10.0):
        """True where the level pose is inside the sweep by at least margin_mm. Broadcasts."""
        result = self.margin(sway, surge, heave) >= margin_mm
        return bool(result) if np.ndim(result) == 0 else result

    def grid(self, sways, surges, heaves, margin_mm=10.0):
        """Boolean array over the meshgrid of the three axes, indexed [sway, surge, heave]."""
        s, u, h = np.meshgrid(sways, surges, heaves, indexing="ij")
        return self.reachable(s, u, h, margin_mm)

    def path_reachable(self, start, end, margin_mm=10.0, step_mm=5.0):
        """Check every point of a straight move. Returns (ok, first failing [sway, surge, heave] or None)."""
        start, end = np.asarray(start, dtype=float), np.asarray(end, dtype=float)
        n = max(1, int(np.ceil(np.max(np.abs(end - start)) / step_mm)))
        points = start + (end - start) * np.linspace(0, 1, n + 1)[:, None]
        ok = self.reachable(points[:, 0], points[:, 1], points[:, 2], margin_mm)
        bad = np.flatnonzero(~ok)
        return (True, None) if not len(bad) else (False, points[bad[0]])

    def surge_range(self, heave, margin_mm=0.0):
        """(most backward, most forward) reachable surge at this heave, sway 0."""
        return (-(self.limit_radius(270.0, heave) - margin_mm), self.limit_radius(90.0, heave) - margin_mm)

    def sway_range(self, heave, margin_mm=0.0):
        """(most left, most right) reachable sway at this heave, surge 0."""
        return (-(self.limit_radius(180.0, heave) - margin_mm), self.limit_radius(0.0, heave) - margin_mm)

    def stroke(self, heave, length_mm=300.0, axis="surge", margin_mm=0.0):
        """Centred (start, end) of a stroke along surge or sway at this heave, or None if it does not fit."""
        low, high = (self.surge_range if axis == "surge" else self.sway_range)(heave, margin_mm)
        if not np.isfinite(low) or high - low < length_mm:
            return None
        mid = (low + high) / 2
        return float(mid - length_mm / 2), float(mid + length_mm / 2)


def validate(library, samples=20000, seed=0, sweep=DEFAULT_SWEEP):
    """Compare predictions with the vendor library's own offline reach check (no device needed).

    Returns a dict of agreement figures. "unsafe" = predicted reachable but rejected by the library.
    """
    import ctypes as ct
    from uofc_hexa import vendor
    from uofc_hexa.hexapod import level_move as lm
    s = vendor.structs()
    lib = ct.CDLL(str(library))
    lib.ForceSeatDI_Create.restype = ct.c_void_p
    lib.ForceSeatDI_Delete.argtypes = [ct.c_void_p]
    send = lib.ForceSeatDI_SendTopTablePosPhy
    send.argtypes, send.restype = [ct.c_void_p, ct.POINTER(s.FSDI_TopTablePositionPhysical)], ct.c_char
    api = lib.ForceSeatDI_Create()
    model = Reachability.load(sweep)
    rng = np.random.default_rng(seed)
    pts = np.c_[rng.uniform(-350, 350, samples), rng.uniform(-350, 350, samples),
                rng.uniform(model.heights[0], model.heights[-1], samples)]

    def truth(p):
        pose = lm.sized(s.FSDI_TopTablePositionPhysical)
        pose.sway, pose.surge, pose.heave = map(float, p)
        pose.pause, pose.maxSpeed, pose.strategy = b"\x01", 2000, 0  # paused, FullMatch
        return send(api, ct.byref(pose)) == b"\x01"
    try:
        actual = np.array([truth(p) for p in pts])
    finally:
        lib.ForceSeatDI_Delete(api)
    margin = model.margin(pts[:, 0], pts[:, 1], pts[:, 2])
    predicted = margin >= 0
    unsafe = predicted & ~actual
    missed = ~predicted & actual
    return {"samples": samples, "agree": float(np.mean(predicted == actual)),
            "unsafe": int(unsafe.sum()), "missed": int(missed.sum()),
            "worst_unsafe_margin_mm": float(margin[unsafe].max()) if unsafe.any() else 0.0,
            "worst_missed_margin_mm": float(-margin[missed].min()) if missed.any() else 0.0}


if __name__ == "__main__":
    import argparse
    from uofc_hexa import vendor
    parser = argparse.ArgumentParser(description="Check the interpolated sweep against the vendor library (offline).")
    parser.add_argument("--library", default=vendor.default_library(), required=not vendor.default_library())
    parser.add_argument("--samples", type=int, default=20000)
    args = parser.parse_args()
    print(validate(args.library, args.samples))
