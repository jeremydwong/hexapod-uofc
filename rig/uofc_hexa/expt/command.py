"""The host -> Speedgoat command packet, and a Python mirror of rig/speedgoat/host_rx.m.

14 little-endian doubles (112 bytes), sent at ~100 Hz:
  1 magic ('HOST')  2 version  3 seq (heartbeat)  4 start  5 n_trials  6 row (1-based, 0 = none)
  7-14 that row, in fsm.COLUMNS order
The host cycles through the trial rows while start = 0. The target stores each row that passes
the safe-limit checks and echoes n_loaded, n_rejected and table_sum in the state packet; the
host sends start = 1 only once that echo matches its own table.
"""
from __future__ import annotations

import math
import struct

from uofc_hexa.expt.fsm import COLUMNS, LIMITS_MM, ZERO_ROW

MAGIC = 1213157204.0  # 'HOST' as a big-endian uint32
VERSION = 1
FORMAT = "<14d"
SIZE = struct.calcsize(FORMAT)  # 112 bytes
DEFAULT_PORT = 25001  # the Speedgoat listens here
N_MAX = 500  # rows the target can hold (host_rx.m)
MAX_PEAK_SPEED_MM_S = 500.0  # P.max_peak_speed_mm_s in expt_params.m


def pack(seq, start, n_trials, row_index=0, row=None):
    values = [row[c] for c in COLUMNS] if row is not None else [0.0] * len(COLUMNS)
    return struct.pack(FORMAT, MAGIC, VERSION, seq, float(bool(start)), n_trials, row_index, *values)


def unpack(data):
    """Decode one packet to a dict; None if it is the wrong size, magic or version."""
    if len(data) != SIZE:
        return None
    v = struct.unpack(FORMAT, data)
    if v[0] != MAGIC or int(v[1]) != VERSION:
        return None
    return {"seq": v[2], "start": v[3] != 0, "n_trials": int(round(v[4])), "row_index": int(round(v[5])),
            "row": dict(zip(COLUMNS, v[6:]))}


def row_ok(row):
    """Same checks as row_ok in host_rx.m."""
    vals = [row[c] for c in COLUMNS]
    if not all(math.isfinite(v) for v in vals) or row["axis"] not in (1, 2):
        return False
    low, high = LIMITS_MM[int(row["axis"])]
    return (low <= row["distance_mm"] <= high and 0 < row["peak_speed_mm_s"] <= MAX_PEAK_SPEED_MM_S
            and row["random_s"] >= 0 and row["thresh_seconds_cop_stable"] > 0 and row["cop_radius_mm"] > 0
            and row["cop_sd_mm"] > 0 and row["max_wait_s"] >= 0)


def table_sum(trials):
    """Checksum of a table, as host_rx.m computes it: sum of TT(k, j) * (8k + j), 1-based."""
    total = 0.0
    for k, row in enumerate(trials, 1):
        for j, c in enumerate(COLUMNS, 1):
            total += row[c] * (8 * k + j)
    return total


def sums_match(a, b):
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


class HostRx:
    """Mirror of host_rx.m for the emulator. step() returns the same outputs, with the table as a list."""

    def __init__(self, host_timeout_s=0.5):
        self.timeout = host_timeout_s
        self.tbl = [None] * N_MAX
        self.bad = [False] * N_MAX
        self.n, self.last_seq, self.t_seen, self.start = 0, -1.0, -1e9, False
        self._out = None  # table-derived outputs, recomputed only when the table changes

    def step(self, t, cmd):
        if cmd is not None:
            if cmd["seq"] != self.last_seq:
                self.last_seq, self.t_seen = cmd["seq"], t
            self.start = cmd["start"]
            if not self.start:
                if cmd["n_trials"] != self.n and 0 <= cmd["n_trials"] <= N_MAX:
                    self.n = cmd["n_trials"]
                    self.tbl, self.bad = [None] * N_MAX, [False] * N_MAX
                    self._out = None
                r = cmd["row_index"]
                if 1 <= r <= self.n:
                    ok = row_ok(cmd["row"])
                    self.tbl[r - 1] = dict(cmd["row"]) if ok else None
                    self.bad[r - 1] = not ok
                    self._out = None
        if self._out is None:
            rows = [r if r is not None else ZERO_ROW for r in self.tbl[:self.n]]
            self._out = {"trials": rows, "n_trials": self.n, "table_sum": table_sum(rows),
                         "n_loaded": sum(r is not None for r in self.tbl[:self.n]),
                         "n_rejected": sum(self.bad[:self.n])}
        host_ok = t - self.t_seen < self.timeout
        loaded = self.n >= 1 and self._out["n_loaded"] == self.n
        return {**self._out, "start": self.start and loaded and host_ok, "host_ok": host_ok,
                "cmd_seq": self.last_seq}
