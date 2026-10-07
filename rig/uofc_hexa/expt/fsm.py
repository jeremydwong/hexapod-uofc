"""Python mirror of rig/speedgoat/fsm_expt.m (same states, thresholds and outputs).

Used by the emulator to test the host side without a Speedgoat, and as a readable
reference. Keep it in step with the MATLAB block: same order of operations.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np

S_IDLE, S_HOMED, S_MOVETGT, S_WAIT_COP, S_RETURN, S_DONE, S_FAULT = 0, 1, 2, 3, 4, 5, 9
# Measured safe single-axis targets at home height (M10 limits minus 25 mm), as in load_trials.m.
LIMITS_MM = {1: (-281.0, 248.0), 2: (-241.0, 241.0)}  # 1 surge, 2 sway


def load_trials(path):
    rows = list(csv.DictReader(Path(path).open()))
    trials = [{k: float(v) for k, v in r.items()} for r in rows]
    for i, t in enumerate(trials, 1):
        low, high = LIMITS_MM[int(t["axis"])]
        if not low <= t["distance_mm"] <= high:
            raise ValueError(f"trial {i}: {t['distance_mm']} mm on axis {int(t['axis'])} outside [{low}, {high}]")
    return trials


def smoothstep(u):
    u = min(max(u, 0.0), 1.0)
    return u ** 3 * (10 - 15 * u + 6 * u ** 2)


class FsmExpt:
    def __init__(self, trials, return_speed_mm_s=100.0, min_move_s=0.2, cop_tau_s=0.5, min_fz_n=200.0,
                 cop_center_auto=True, cop_center_mm=(0.0, 0.0)):
        self.trials, self.return_speed, self.min_move = trials, return_speed_mm_s, min_move_s
        self.tau, self.min_fz, self.auto, self.center0 = cop_tau_s, min_fz_n, cop_center_auto, np.array(cop_center_mm)
        self.st, self.tr, self.t_enter, self.last_t = S_IDLE, 1, None, None
        self.p0 = self.p1 = self.sp_last = np.zeros(3)
        self.move_T, self.stable = 1.0, 0.0
        self.m, self.v, self.ctr = np.zeros(2), np.zeros(2), self.center0.copy()

    def step(self, t, start, host_ok, cop_xy, fz_total):
        if self.t_enter is None:
            self.t_enter = self.last_t = t
        dt = max(t - self.last_t, 0.0)
        self.last_t = t
        events = 0
        cop_xy = np.asarray(cop_xy, dtype=float)
        valid = fz_total >= self.min_fz
        if valid:
            a = min(dt / self.tau, 1.0)
            d = cop_xy - self.m
            self.m = self.m + a * d
            self.v = (1 - a) * (self.v + a * d ** 2)
        cop_sd = math.sqrt(self.v.sum())
        n = len(self.trials)
        k = min(max(self.tr, 1), n) - 1
        T = self.trials[k]
        sp = self.sp_last.copy()

        if not host_ok and self.st in (S_HOMED, S_MOVETGT, S_WAIT_COP, S_RETURN):
            self.st, self.t_enter = S_FAULT, t
            events += 16

        if self.st == S_IDLE:
            sp = np.zeros(3)
            if start and host_ok:
                self.ctr = self.m.copy() if self.auto else self.center0.copy()
                self.tr, k = 1, 0
                T = self.trials[0]
                self.st, self.t_enter = S_HOMED, t
        elif self.st == S_HOMED:
            sp = np.zeros(3)
            if not start:
                self.st, self.t_enter = S_IDLE, t
            elif t - self.t_enter >= T["random_s"]:
                self.p0, self.p1 = np.zeros(3), np.zeros(3)
                self.p1[1 if int(T["axis"]) == 1 else 0] = T["distance_mm"]
                self.move_T = max(self.min_move, 1.875 * abs(T["distance_mm"]) / T["peak_speed_mm_s"])
                self.st, self.t_enter = S_MOVETGT, t
                events += 1
        elif self.st == S_MOVETGT:
            u = (t - self.t_enter) / self.move_T
            sp = self.p0 + (self.p1 - self.p0) * smoothstep(u)
            if u >= 1:
                sp, self.stable = self.p1.copy(), 0.0
                self.st, self.t_enter = S_WAIT_COP, t
                events += 2
        elif self.st == S_WAIT_COP:
            sp = self.p1.copy()
            near = math.hypot(*(cop_xy - self.ctr)) < T["cop_radius_mm"]
            self.stable = self.stable + dt if (valid and near and cop_sd < T["cop_sd_mm"]) else 0.0
            if self.stable >= T["thresh_seconds_cop_stable"] or not start:
                self.p0, self.p1 = self.p1.copy(), np.zeros(3)
                self.move_T = max(self.min_move, 1.875 * np.max(np.abs(self.p0)) / self.return_speed)
                self.st, self.t_enter = S_RETURN, t
                events += 4
        elif self.st == S_RETURN:
            u = (t - self.t_enter) / self.move_T
            sp = self.p0 + (self.p1 - self.p0) * smoothstep(u)
            if u >= 1:
                sp = np.zeros(3)
                events += 8
                self.tr += 1
                self.st = S_IDLE if not start else (S_DONE if self.tr > n else S_HOMED)
                self.t_enter = t
                k = min(self.tr, n) - 1
                T = self.trials[k]
        elif self.st == S_DONE:
            sp = np.zeros(3)
            if not start:
                self.st, self.t_enter = S_IDLE, t
        else:  # S_FAULT
            sp = self.sp_last.copy()

        self.sp_last = sp.copy()
        return {"t": t, "state": self.st, "trial": min(self.tr, n), "sp_sway": sp[0], "sp_surge": sp[1],
                "sp_heave": sp[2], "cop_x": cop_xy[0], "cop_y": cop_xy[1], "cop_sd": cop_sd,
                "stable_s": self.stable, "fz_total": fz_total, "events": events, "t_state": t - self.t_enter,
                "center_x": self.ctr[0], "center_y": self.ctr[1], "radius": T["cop_radius_mm"],
                "sd_thr": T["cop_sd_mm"], "stable_need": T["thresh_seconds_cop_stable"]}
