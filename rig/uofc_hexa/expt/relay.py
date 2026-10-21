"""Host relay: forward the Speedgoat's setpoint (sp_sway, sp_surge, sp_heave) to the hexapod.

The Speedgoat cannot talk to the platform itself: the controller is only reachable through
the ForceSeatDI SDK, a Windows DLL, and the Speedgoat runs QNX. So the host forwards it:

  before Start   connect; paused FullMatch check of every protocol target (nothing moves on a
                 rejection); lift from park to home (0,0,0) at --lift-rate
  during run     every 10 ms: take the newest state packet's setpoint, slew-limit it, send it;
                 every 50 ms read the platform (state gate, ±bound, tilt). Stale stream
                 (> STALE_HOLD_S) holds the last command; > STALE_FAULT_S, a Speedgoat FAULT, a
                 failed send or a bad reading pauses the platform and faults the relay. A failed
                 READ (SDK error 2: readback dead, sends still work) is logged and streaming goes
                 on unmonitored; dead for tfp.READ_DEAD_S, the run stops after the current trial.
  after the run  stream from the last command down to the park height, then Park.
Loop stalls under tfp.STALL_ABORT_S (Windows hiccups) hold the last command and are counted;
the slew step uses at most 2 loop periods, so the command never jumps after one.

The Speedgoat stays the clock and the record of what was commanded; the relay adds what was
sent and what the SDK reported (relay rows, saved next to the state stream).
"""
from __future__ import annotations

import ctypes as ct
import sys
import threading
import time

import numpy as np

from uofc_hexa.expt.fsm import S_FAULT
from uofc_hexa.hexapod import level_move as lm
from uofc_hexa.hexapod import test_from_park as tfp

STALE_HOLD_S = 0.05  # no new state packet for this long: hold the last command
STALE_FAULT_S = 0.5  # ... for this long: pause the platform, fault
MAX_SLEW_MM_S = 600.0  # guard on the setpoint itself (protocol peak speeds are <= 500 mm/s)
FIELDS = ["t", "sg_t", "sg_state", "sp_sway", "sp_surge", "sp_heave", "cmd_sway", "cmd_surge", "cmd_heave",
          "act_sway", "act_surge", "act_heave", "roll", "pitch", "yaw", "dev_state", "read_err"]
# act_*/roll/pitch/yaw/dev_state: last good 20 Hz reading; read_err: SDK code of the latest read (0 = ok)


def protocol_waypoints(trials):
    """Each trial's target and the return home, as test_from_park waypoints (name, xyz mm)."""
    index = {1: lm.AXES["surge"], 2: lm.AXES["sway"]}  # protocol axis code -> [sway, surge, heave]
    waypoints = []
    for k, row in enumerate(trials, 1):
        target = np.zeros(3)
        target[index[int(row["axis"])]] = row["distance_mm"]
        waypoints += [(f"trial {k}", target), ("home", np.zeros(3))]
    return waypoints


class Relay(threading.Thread):
    """Lift on prepare(); run() streams the Speedgoat setpoint until stop; finish() lowers and parks."""

    def __init__(self, device, rx, trials, lift_rate=50.0, margin_mm=tfp.BOUND_MARGIN_MM,
                 tilt_limit_deg=lm.TILT_LIMIT_DEG):
        super().__init__(daemon=True)
        self.device, self.rx = device, rx
        self.waypoints = protocol_waypoints(trials)
        too_close = tfp.check_axis_limits(self.waypoints)
        if too_close:
            raise ValueError("protocol targets too close to the platform's limits: " + "; ".join(too_close))
        self.bound = max(np.max(np.abs(w)) for _, w in self.waypoints) + margin_mm
        self.lift_rate, self.tilt_limit = lift_rate, tilt_limit_deg
        self.stalls = []  # (time s, gap ms) of loop iterations over lm.DEADLINE_S
        self.ready = False  # homed and streaming: Start may be sent
        self.fault = None  # message, once the relay has paused the platform
        self.blind = None  # message, once readback has been dead READ_DEAD_S: stop after this trial
        self.running = True
        self.rows, self.log, self.states = [], [], []
        self.parked = None
        self.command = np.zeros(3)
        self.pose = None  # latest SDK report (xyz mm, rpy rad, state), for the live view's 3D panel
        self.clock0 = time.monotonic()

    def t(self):
        return time.monotonic() - self.clock0

    def prepare(self):
        """Path check (paused), then lift to home. Raises with nothing moved on a rejection."""
        d = self.device
        parked, _, _, state = tfp.lenient_read(d)
        print(f"Hexapod start: pose {np.round(parked, 2)} mm, state=0x{state:x}")
        parked[2] = max(parked[2], tfp.LOWEST_HEAVE_MM)
        self.parked = np.array([0.0, 0.0, tfp.LOWEST_HEAVE_MM])  # always end at the park height
        d.bound = self.bound
        rejected = tfp.precheck_path(d, self.waypoints)
        d.bound = tfp.LIFT_BOUND_MM
        if rejected:
            raise RuntimeError(f"{len(rejected)} protocol poses unreachable, nothing moved. First: "
                               + "; ".join(f"{n} at {p}" for n, p in rejected[:3]))
        print(f"Hexapod path check: all {len(self.waypoints)} targets reachable; bound ±{self.bound:g} mm")
        tfp.stream(d, parked, np.zeros(3), self.lift_rate, "lift", self.t, self.log, self.states)
        d.bound = self.bound
        self.command = np.zeros(3)

    def run(self):
        d, dt_nom = self.device, lm.DT
        begin = previous = time.monotonic()
        last_count, last_new = self.rx.received, begin
        actual, rpy, state = np.full(3, np.nan), np.full(3, np.nan), 0  # last good reading
        dead_since, read_err = None, 0
        try:
            self.ready = True
            k = 0
            while self.running:
                k += 1
                time.sleep(max(0.0, begin + k * dt_nom - time.monotonic()))
                now = time.monotonic()
                gap = now - previous
                if gap > tfp.STALL_ABORT_S:
                    raise RuntimeError(f"relay loop stalled {1000 * gap:.0f} ms")
                if gap > lm.DEADLINE_S:
                    self.stalls.append((self.t(), 1000 * gap))
                    print(f"relay: loop stalled {1000 * gap:.0f} ms; command held, continuing", file=sys.stderr)
                dt, previous = min(gap, 2 * dt_nom), now
                if k % tfp.READ_EVERY == 0:
                    xyz, r, st, err = tfp.soft_read(d, self.tilt_limit)
                    if st is not None:
                        state = st
                        if state & (lm.STATE_PAUSED | lm.STATE_PARK_MASK):
                            raise RuntimeError(f"hexapod paused or parked during the run; state=0x{state:x}")
                    if xyz is None:
                        if err != d.read_error:
                            print(f"relay: platform readback failed (SDK error {err}); streaming on "
                                  "unmonitored (pose, tilt and 3D view frozen)", file=sys.stderr)
                            d.read_error = err
                        dead_since = dead_since or now
                        if now - dead_since > tfp.READ_DEAD_S and not self.blind:
                            self.blind = f"platform readback dead {tfp.READ_DEAD_S:g} s (SDK error {err})"
                            print(f"relay: {self.blind}; stopping after the current trial", file=sys.stderr)
                    else:
                        actual, rpy, dead_since = xyz, r, None
                        self.pose = (actual, rpy, state)
                        if np.max(np.abs(actual)) > self.bound:
                            raise RuntimeError(f"reported pose {np.round(actual, 2)} outside ±{self.bound:g} mm")
                    read_err = err
                s = self.rx.last
                if self.rx.received != last_count:
                    last_count, last_new = self.rx.received, now
                age = now - last_new
                if age > STALE_FAULT_S:
                    raise RuntimeError(f"no state packets for {age:.2f} s")
                if s is not None and int(s.state) == S_FAULT:
                    raise RuntimeError("Speedgoat FAULT (host link lost)")
                sp = np.array([s.sp_sway, s.sp_surge, s.sp_heave]) if s is not None else self.command
                if not np.all(np.isfinite(sp)) or np.max(np.abs(sp)) > self.bound:
                    raise RuntimeError(f"Speedgoat setpoint {np.round(sp, 2)} outside ±{self.bound:g} mm")
                if age <= STALE_HOLD_S:
                    step = MAX_SLEW_MM_S * dt
                    self.command = self.command + np.clip(sp - self.command, -step, step)
                d.send(self.command)
                self.rows.append([self.t(), s.t if s else np.nan, s.state if s else np.nan, *sp,
                                  *self.command, *actual, *rpy, state, read_err])
        except BaseException as error:
            self.fault = str(error)
            print(f"RELAY FAULT: {error}; pausing the hexapod", file=sys.stderr)
            try:
                d.send(self.command, pause=True)
            except Exception as e:
                print(f"Pause request failed: {e} (use the E-stop)", file=sys.stderr)
        finally:
            self.ready = False

    def finish(self):
        """Stop streaming, lower to the parked pose and park. Skipped after a fault (platform paused)."""
        self.running = False
        if self.is_alive():
            self.join(timeout=2.0)
        if self.fault or self.parked is None:
            print("Hexapod left paused where it stopped; park it from ForceSeatPM once the area is clear")
            return
        d = self.device
        d.bound = tfp.LIFT_BOUND_MM
        tfp.stream(d, self.command, self.parked, self.lift_rate, "lower", self.t, self.log, self.states)
        d.send(self.parked, pause=True)
        park = d.lib.ForceSeatDI_Park
        park.restype, park.argtypes = ct.c_char, [ct.c_void_p, ct.c_uint8]
        ok = park(d.api, 0)  # FSDI_ParkMode_Normal
        print(f"Hexapod park request: {'ok' if ok == b'\x01' else 'FAILED'}")
