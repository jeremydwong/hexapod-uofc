"""The Speedgoat -> host state packet: 21 little-endian doubles (rig/speedgoat/pack_state.m)."""
from __future__ import annotations

from dataclasses import dataclass
import struct

MAGIC = 1212504129.0  # 'HEXA'
VERSION = 1
FIELDS = ["magic", "version", "seq", "t", "state", "trial",
          "sp_sway", "sp_surge", "sp_heave", "cop_x", "cop_y", "cop_sd", "stable_s", "fz_total",
          "events", "t_state", "center_x", "center_y", "radius", "sd_thr", "stable_need"]
FORMAT = "<" + "d" * len(FIELDS)
SIZE = struct.calcsize(FORMAT)  # 168 bytes
DEFAULT_PORT = 25000  # outside Simulink Real-Time's reserved 1-1023 and 5500-5560

STATES = {0: "IDLE", 1: "HOMED", 2: "MOVETGT", 3: "WAIT_COP", 4: "RETURN", 5: "DONE", 9: "FAULT"}
EVENTS = {1: "perturbation start", 2: "arrived", 4: "return start", 8: "trial done", 16: "fault"}


@dataclass
class State:
    magic: float
    version: float
    seq: float
    t: float
    state: float
    trial: float
    sp_sway: float
    sp_surge: float
    sp_heave: float
    cop_x: float
    cop_y: float
    cop_sd: float
    stable_s: float
    fz_total: float
    events: float
    t_state: float
    center_x: float
    center_y: float
    radius: float
    sd_thr: float
    stable_need: float

    @property
    def state_name(self):
        return STATES.get(int(self.state), f"?{int(self.state)}")


def pack(values):
    return struct.pack(FORMAT, *[float(values[f]) for f in FIELDS])


def unpack(data):
    """Decode one packet; None if it is the wrong size, magic or version."""
    if len(data) != SIZE:
        return None
    s = State(*struct.unpack(FORMAT, data))
    if s.magic != MAGIC or int(s.version) != VERSION:
        return None
    return s
