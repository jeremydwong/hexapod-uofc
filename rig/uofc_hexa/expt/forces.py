"""Forces and centre of pressure from the two Bertec plates, computed on the host from ai1..ai12.

The Speedgoat app still has placeholder calibration, so its cop_x / cop_y / fz_total are not
usable; the state packet does carry the tared amplifier volts (ai1..ai12), and this turns them
into loads and CoP for the live view and the 3D scene.

Channel map: AI 1-6 = RIGHT plate, AI 7-12 = LEFT plate, each [Fx, Fy, Fz, Mx, My, Mz]
(order ASSUMED, Fy confirmed by a push). Gains are the lab's values at the amplifiers' ±5 V
output, the same for both plates, applied as a diagonal calibration: load = GAINS * volts.

Geometry (lab): 200 x 200 mm plates, 50 mm gap, centred on the platform's top frame, so the
plate centres are at x = +125 mm (right) and -125 mm (left), y = 0. Frame: x = right, y = front, mm.
Per plate CoP: x = -My/Fz, y = Mx/Fz (origin assumed at the surface centre, dz = 0), plus the
plate centre; only when Fz > MIN_FZ_N. Combined CoP = Fz-weighted mean of the loaded plates.

SIGNS ARE UNVERIFIED: a Bertec plate may report Fz < 0 for a downward load. FZ_SIGN multiplies
Fz before the threshold and the CoP; flip it to -1.0 once a press on a plate shows the sign.
The moment signs are taken as given and are unverified too (check with an off-centre press).
"""
from __future__ import annotations

import numpy as np

GAINS = np.array([500, 500, 1000, 150, 100, 75])  # per V: N for Fx Fy Fz, N·m for Mx My Mz (lab values)
FZ_SIGN = 1.0      # UNVERIFIED: set to -1.0 if a downward press reads negative
MIN_FZ_N = 20.0    # below this a plate counts as unloaded (no CoP)
PLATE_SIDE_MM = 200.0
PLATE_CENTERS_MM = np.array([[125.0, 0.0], [-125.0, 0.0]])  # 0 = right, 1 = left
PLATE_NAMES = ("right", "left")
AI_FIELDS = [f"ai{i}" for i in range(1, 13)]


def from_state(s) -> np.ndarray:
    """ai1..ai12 (V, tared) from a packet.State as a (12,) array."""
    return np.array([getattr(s, f) for f in AI_FIELDS], dtype=float)


def plate_loads(ai12) -> np.ndarray:
    """(..., 12) volts -> (..., 2, 6) loads [Fx Fy Fz Mx My Mz] per plate, N / N·m; Fz has FZ_SIGN applied."""
    v = np.asarray(ai12, dtype=float)
    loads = v.reshape(v.shape[:-1] + (2, 6)) * GAINS
    loads[..., 2] *= FZ_SIGN
    return loads


def plate_cops(loads):
    """(..., 2, 6) loads -> (CoP (..., 2, 2) mm with NaN where unloaded, loaded mask (..., 2))."""
    fz = loads[..., 2]
    loaded = fz > MIN_FZ_N
    safe = np.where(loaded, fz, 1.0)
    # moment signs as given, UNVERIFIED; N·m / N = m -> mm
    local = np.stack([-loads[..., 4] / safe, loads[..., 3] / safe], axis=-1) * 1000.0
    cop = local + PLATE_CENTERS_MM
    cop[~loaded] = np.nan
    return cop, loaded


def combined_many(ai):
    """(n, 12) volts -> (total Fz (n,) N, combined CoP (n, 2) mm, NaN where no plate is loaded)."""
    loads = plate_loads(ai)
    cop, loaded = plate_cops(loads)
    fz = loads[..., 2]
    w = np.where(loaded, fz, 0.0)
    wsum = w.sum(axis=-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        c = (np.nan_to_num(cop) * w[..., None]).sum(axis=-2) / wsum[..., None]
    c[wsum <= 0] = np.nan
    return fz.sum(axis=-1), c


def combined(ai12) -> tuple[float, np.ndarray | None]:
    """(total Fz N, combined CoP (2,) mm or None if neither plate is loaded)."""
    fz, c = combined_many(np.asarray(ai12, dtype=float)[None])
    return float(fz[0]), (None if np.isnan(c[0, 0]) else c[0])


def plates_for_scene(ai12) -> list[dict]:
    """[right, left]: {"force_N": (3,) Fx Fy Fz, "cop_mm": (2,) or None, "loaded": bool}."""
    loads = plate_loads(ai12)
    cop, loaded = plate_cops(loads)
    return [{"force_N": loads[k, :3].copy(), "cop_mm": cop[k].copy() if loaded[k] else None,
             "loaded": bool(loaded[k])} for k in range(2)]
