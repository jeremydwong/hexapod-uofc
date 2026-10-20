"""The Speedgoat -> host state packet: 39 little-endian doubles (rig/speedgoat/pack_state.m)."""
from __future__ import annotations

from dataclasses import make_dataclass
import struct

MAGIC = 1212504129.0  # 'HEXA'
VERSION = 2
FIELDS = ["magic", "version", "seq", "t", "state", "trial",
          "sp_sway", "sp_surge", "sp_heave", "cop_x", "cop_y", "cop_sd", "stable_s", "fz_total",
          "events", "t_state", "center_x", "center_y", "radius", "sd_thr", "stable_need",
          "n_trials", "n_loaded", "table_sum", "host_ok", "cmd_seq", "n_rejected"] + [f"ai{i}" for i in range(1, 13)]
FORMAT = "<" + "d" * len(FIELDS)
SIZE = struct.calcsize(FORMAT)  # 312 bytes
DEFAULT_PORT = 25000  # outside Simulink Real-Time's reserved 1-1023 and 5500-5560

STATES = {0: "IDLE", 1: "HOMED", 2: "MOVETGT", 3: "WAIT_COP", 4: "RETURN", 5: "DONE", 9: "FAULT"}
EVENTS = {1: "perturbation start", 2: "arrived", 4: "return start", 8: "trial done", 16: "fault"}


State = make_dataclass("State", [(f, float) for f in FIELDS])
State.state_name = property(lambda self: STATES.get(int(self.state), f"?{int(self.state)}"))


def pack(values):
    """Encode a dict of field values; missing fields are sent as 0."""
    return struct.pack(FORMAT, *[float(values.get(f, 0.0)) for f in FIELDS])


def unpack(data):
    """Decode one packet; None if it is the wrong size, magic or version."""
    if len(data) != SIZE:
        return None
    s = State(*struct.unpack(FORMAT, data))
    if s.magic != MAGIC or int(s.version) != VERSION:
        return None
    return s
