"""Connect -> open-loop move to home (0,0,0) -> open-loop move along one axis, always level. Log and plot.

Run: uv run hexapod-move --help  (from anywhere in the repo)
Requires --hardware and explicit SDK connection arguments. No simulation mode.
"""
from __future__ import annotations

import argparse
import csv
import ctypes as ct
from pathlib import Path
import sys
import time

import numpy as np

from uofc_hexa import vendor

DT = 0.01  # 100 Hz setpoint/log loop, same as the vendor CSV player; not a real-time actuator servo
AXES = {"sway": 0, "surge": 1, "heave": 2}
SETTLE_MM = 0.2  # reporting threshold only; never aborts the run
TILT_LIMIT_DEG = 0.5  # abort if reported rotation exceeds this while commanding level
DEADLINE_S = 0.2  # abort if one loop iteration takes longer than this
# Single-axis excursions from docs/PS-6TL-350-tech-sheet.pdf p.2: surge -306/+273, sway ±265, heave -166/+189 mm.
# Hard cap on --bound keeps every axis inside its own single-axis excursion with margin.
MAX_BOUND_MM = 150.0
ACCEL_PROFILES = {"auto": 0, "rapid": 1, "balanced": 2, "smoothest": 3}  # FSDI_AccelerationProfile
VENDOR_INTERVAL_MS = 10  # examples/PrecisePos_CSV_CPP_Win/main.cpp: INTERVAL_MS = 10
M10_SERIAL = "5f0051-000150-344335-353720"  # Controller S/N of our M10 imitator (README.md); default USB target

# FSDI_State bits (code/ForceSeatDI_Structs.h)
STATE_PAUSED, STATE_OFFLINE, STATE_REF_RUN_DONE, STATE_PARK_MASK = 1 << 0, 1 << 2, 1 << 4, 0xE0


def sized(cls):
    value = cls()
    value.structSize = ct.sizeof(cls)
    return value


class Device:
    """Minimal typed binding; reuses packed structures from code/, no copied ABI."""

    def __init__(self, library, ip, serial, run_byte, speed, accel_profile, bound):
        self.bound, self.accel_profile = bound, accel_profile
        s = vendor.structs()
        self.s, self.run_byte, self.speed = s, bytes([run_byte]), speed
        self.lib = ct.CDLL(str(Path(library).resolve()))
        self.api = None
        specs = {
            "Create": (ct.c_void_p, []), "Delete": (None, [ct.c_void_p]),
            "ConnectToUsbDevice": (ct.c_char, [ct.c_void_p, ct.c_wchar_p, ct.c_wchar_p]),
            "ConnectToNetworkDevice": (ct.c_char, [ct.c_void_p, ct.c_char_p]),
            "TestConnection": (ct.c_char, [ct.c_void_p, ct.POINTER(ct.c_char)]),
            "GetLicenseStatus": (ct.c_char, [ct.c_void_p, ct.POINTER(ct.c_char)]),
            "GetRecentErrorCode": (ct.c_int32, [ct.c_void_p]),
            "GetSerialNumber": (ct.c_char, [ct.c_void_p, ct.c_char_p]),
        }
        for name, cls in [("GetPlatformInfo", s.FSDI_PlatformInfo),
                          ("GetTopTablePosPhy", s.FSDI_ActualTopTablePositionPhysical),
                          ("GetActuatorsPosLog", s.FSDI_ActualActuatorsPositionLogical),
                          ("SendTopTablePosPhy", s.FSDI_TopTablePositionPhysical)]:
            specs[name] = (ct.c_char, [ct.c_void_p, ct.POINTER(cls)])
        for name, (result, args) in specs.items():
            fn = getattr(self.lib, "ForceSeatDI_" + name)
            fn.restype, fn.argtypes = result, args
        try:
            self.api = self.lib.ForceSeatDI_Create()
            if not self.api:
                raise RuntimeError("ForceSeatDI_Create returned a null handle")
            if ip:
                self.call("ConnectToNetworkDevice", ip.encode("ascii"))
            else:
                # NULL name, as in the vendor's PrecisePos_CPP_Win; NULL serial = any attached device.
                wanted = None if serial in (None, "", "any") else serial
                if self.lib.ForceSeatDI_ConnectToUsbDevice(self.api, None, wanted) != b"\x01":
                    error = self.lib.ForceSeatDI_GetRecentErrorCode(self.api)
                    raise RuntimeError(
                        f"ConnectToUsbDevice failed for serial {wanted or 'any'} (SDK error {error}). "
                        "Check: ForceSeatPM fully closed (including the tray icon); the controller is "
                        "connected to this PC by USB; the serial is right (try --serial any). "
                        "If the controller is on Ethernet, use --ip instead.")
            sn = ct.create_string_buffer(28)  # FSDI_SerialNumberStringLength
            if self.lib.ForceSeatDI_GetSerialNumber(self.api, sn) == b"\x01":
                print(f"Connected to controller S/N {sn.value.decode(errors='replace')}")
            for name in ["TestConnection", "GetLicenseStatus"]:
                flag = ct.c_char(b"\x00")
                self.call(name, ct.byref(flag))
                if flag.value != b"\x01":
                    raise RuntimeError(name + " returned a false status")
        except BaseException:
            self.close()
            raise

    def call(self, name, *args):
        result = getattr(self.lib, "ForceSeatDI_" + name)(self.api, *args)
        if result != b"\x01":
            error = self.lib.ForceSeatDI_GetRecentErrorCode(self.api)
            raise RuntimeError(f"{name} failed; SDK error {error}")

    def read(self):
        """Return (xyz mm, rpy rad, six logical actuator positions) or raise on unsafe state."""
        info = sized(self.s.FSDI_PlatformInfo)
        self.call("GetPlatformInfo", ct.byref(info))
        if info.moduleErrorCode:
            raise RuntimeError(f"Module {info.moduleErrorIndex}: error {info.moduleErrorCode}")
        pose = sized(self.s.FSDI_ActualTopTablePositionPhysical)
        self.call("GetTopTablePosPhy", ct.byref(pose))
        act = sized(self.s.FSDI_ActualActuatorsPositionLogical)
        self.call("GetActuatorsPosLog", ct.byref(act))
        for state in [info.state, pose.state, act.state]:
            if state & (STATE_PAUSED | STATE_OFFLINE | STATE_PARK_MASK) or not state & STATE_REF_RUN_DONE:
                raise RuntimeError(f"Device must be referenced, unpaused and unparked; state=0x{state:x}")
        xyz = np.array([pose.sway, pose.surge, pose.heave], dtype=float)
        rpy = np.array([pose.roll, pose.pitch, pose.yaw], dtype=float)
        actuators = np.array(list(act.actualMotorPosition), dtype=float)
        if not np.all(np.isfinite(np.r_[xyz, rpy])):
            raise RuntimeError("Nonfinite pose feedback")
        # Runtime safety envelope: abort if the reported pose ever leaves it.
        if np.max(np.abs(xyz)) > self.bound or np.max(np.abs(rpy)) > np.deg2rad(TILT_LIMIT_DEG):
            raise RuntimeError(f"Pose outside ±{self.bound} mm / ±{TILT_LIMIT_DEG}° monitoring bounds")
        return xyz, rpy, actuators

    def send(self, xyz, pause=False):
        xyz = np.asarray(xyz)
        if not np.all(np.isfinite(xyz)) or np.max(np.abs(xyz)) > self.bound:
            raise ValueError(f"Command exceeds ±{self.bound} mm bound")
        p = sized(self.s.FSDI_TopTablePositionPhysical)
        p.sway, p.surge, p.heave = map(float, xyz)
        p.roll = p.pitch = p.yaw = 0.0
        p.pause = bytes([1 - self.run_byte[0]]) if pause else self.run_byte
        p.maxSpeed = self.speed  # SDK logical scale, NOT mm/s
        p.strategy = 0  # FullMatch: reject an unreachable pose
        p.accelerationProfile = self.accel_profile  # one of FSDI_AccelerationProfile
        self.call("SendTopTablePosPhy", ct.byref(p))

    def close(self):
        if self.api:
            self.lib.ForceSeatDI_Delete(self.api)
            self.api = None


def smoothstep(u):
    u = min(max(u, 0.), 1.)
    return 10*u**3 - 15*u**4 + 6*u**5


def run_motion(device, axis="surge", amount=15.0, rate=5.0, hold=3.0):
    """Open loop: smooth move to home (0,0,0), hold 2 s, move `amount` mm along `axis`, hold.

    Each move's duration is chosen so the smoothstep setpoint never exceeds `rate` mm/s
    (smoothstep peak speed is 1.875x the mean). Firmware closes its own servo loop.
    Python only streams setpoints and logs what the SDK reports back.
    Returns (rows, {phase: (start_s, move_end_s)}).
    """
    home, target = np.zeros(3), np.zeros(3)
    target[AXES[axis]] = amount
    initial, _, _ = device.read()
    print(f"Start pose (sway, surge, heave): {np.round(initial, 2)} mm")
    t_home = max(3., 2 * np.max(np.abs(initial)) / rate)
    t_move = max(3., 2 * abs(amount) / rate)
    home_start, move_start = 0., t_home + 2.
    duration = move_start + t_move + hold
    schedule = {"home": (home_start, home_start + t_home), "move": (move_start, move_start + t_move)}
    print(f"Timeline: home {t_home:.1f}s, hold 2s, move {t_move:.1f}s, hold {hold:.1f}s  (total {duration:.1f}s)")
    rows = []
    previous_command = initial.copy()
    previous_time = start_time = time.monotonic()
    try:
        for k in range(int(duration / DT) + 1):
            time.sleep(max(0, start_time + k * DT - time.monotonic()))
            now = time.monotonic()
            t, dt = now - start_time, now - previous_time if k else DT
            previous_time = now
            if dt > DEADLINE_S:
                raise RuntimeError(f"Control deadline missed by >{DEADLINE_S * 1000:.0f} ms")
            actual, rpy, actuators = device.read()
            if t < move_start:
                reference, phase = initial + (home - initial) * smoothstep(t / t_home), "home"
            else:
                reference, phase = home + (target - home) * smoothstep((t - move_start) / t_move), "move"
            # Per-axis setpoint slew limit; all rotations stay identically zero.
            command = previous_command + np.clip(reference - previous_command, -rate*dt, rate*dt)
            device.send(command)
            previous_command = command.copy()
            rows.append([t, phase, *reference, *actual, *command, *rpy, *actuators])
        return rows, schedule
    finally:
        # Request a pause at the most recent command, even on Ctrl-C/error.
        # This is best effort; communication loss requires the physical E-stop.
        try:
            device.send(previous_command, pause=True)
        except Exception as error:
            print(f"Pause request failed: {error}", file=sys.stderr)


def summarize(rows, schedule, axis):
    """Print open-loop tracking metrics. Informational only; nothing here aborts a run."""
    dts = np.diff([r[0] for r in rows]) * 1000
    print(f"\nLoop period: mean {dts.mean():.1f} ms, max {dts.max():.1f} ms (nominal {DT * 1000:.0f} ms)")
    t = np.array([r[0] for r in rows])
    phase = np.array([r[1] for r in rows])
    ref = np.array([r[2:5] for r in rows])[:, AXES[axis]]
    act = np.array([r[5:8] for r in rows])[:, AXES[axis]]
    rpy = np.rad2deg(np.array([r[11:14] for r in rows]))
    print(f"\nTracking summary ({axis}):")
    print(f"  max |reference - actual|: {np.max(np.abs(ref - act)):.2f} mm")
    print(f"  max |roll, pitch, yaw|:   {np.max(np.abs(rpy)):.3f} deg")
    for name, mask, target in [("home", phase == "home", 0.), ("move", phase == "move", ref[-1])]:
        move_end = schedule[name][1]
        inside = np.abs(act[mask] - target) < SETTLE_MM
        tm = t[mask]
        if inside.any() and inside[-1]:
            trailing = int(np.argmin(inside[::-1])) if not inside.all() else len(inside)
            first = tm[len(tm) - trailing]
            print(f"  {name:4s}: within {SETTLE_MM} mm from t={first:.2f}s ({first - move_end:+.2f}s after move end), "
                  f"final error {act[mask][-1] - target:+.2f} mm")
        else:
            print(f"  {name:4s}: never settled within {SETTLE_MM} mm; final error {act[mask][-1] - target:+.2f} mm")


def plot(rows, axis, path):
    import matplotlib.pyplot as plt
    t = np.array([r[0] for r in rows])
    ref, act = np.array([r[2:5] for r in rows]), np.array([r[5:8] for r in rows])
    cmd = np.array([r[8:11] for r in rows])
    rpy = np.rad2deg(np.array([r[11:14] for r in rows]))
    actuators = np.array([r[14:20] for r in rows])
    fig, ax = plt.subplots(3, 1, sharex=True, figsize=(9, 9))
    i = AXES[axis]
    ax[0].plot(t, ref[:, i], "--", label=f"reference {axis}")
    ax[0].plot(t, cmd[:, i], ":", label=f"command {axis}")
    ax[0].plot(t, act[:, i], label=f"actual {axis}")
    for j, name in enumerate(AXES):
        if j != i:
            ax[0].plot(t, act[:, j], alpha=.5, label=f"actual {name}")
    ax[0].set_ylabel("mm"); ax[0].legend(loc="best"); ax[0].set_title("Translation (SDK-reported vs commanded)")
    for j, name in enumerate(["roll", "pitch", "yaw"]):
        ax[1].plot(t, rpy[:, j], label=name)
    ax[1].set_ylabel("deg"); ax[1].legend(loc="best"); ax[1].set_title("Rotation (commanded zero)")
    for j in range(6):
        ax[2].plot(t, actuators[:, j], label=f"actuator {j + 1}")
    ax[2].set_ylabel("logical (0-65535)"); ax[2].set_xlabel("s"); ax[2].legend(loc="best", ncol=3)
    ax[2].set_title("Actuator positions")
    fig.tight_layout()
    fig.savefig(path)
    plt.show()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--axis", choices=list(AXES), default="surge")
    parser.add_argument("--amount", type=float, default=15.0,
                        help="mm to move along --axis from home (0,0,0); |amount| must be < --bound")
    parser.add_argument("--bound", type=float, default=50.0,
                        help=f"abort if any reported or commanded translation exceeds this (mm, max {MAX_BOUND_MM:g})")
    parser.add_argument("--rate", type=float, default=5.0, help="max setpoint speed in mm/s")
    parser.add_argument("--hardware", action="store_true", help="required: explicitly enable SDK device operation")
    parser.add_argument("--library", default=vendor.default_library(), required=not vendor.default_library(),
                        help=f"ForceSeatDI native library (default: ${vendor.LIBRARY_ENV})")
    transport = parser.add_mutually_exclusive_group()
    transport.add_argument("--ip")
    transport.add_argument("--serial", help=f"USB controller S/N (default: M10 imitator {M10_SERIAL})")
    parser.add_argument("--run-byte", type=int, choices=[0, 1], required=True)
    parser.add_argument("--max-speed", type=int, default=2000,
                        help="FSDI maxSpeed field, logical units 1-65535 (65535 = no limit); NOT mm/s")
    parser.add_argument("--accel-profile", choices=list(ACCEL_PROFILES), default="auto",
                        help="FSDI accelerationProfile: shape of the controller's start/stop ramps")
    parser.add_argument("--hold", type=float, default=3.0, help="seconds to hold at the target after the move")
    parser.add_argument("--no-plot", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("output"),
                        help="output folder, relative to where you run the command")
    args = parser.parse_args()
    if not args.hardware:
        parser.error("--hardware is required; there is no simulation mode")
    if not args.ip and args.serial is None:
        args.serial = M10_SERIAL
    if not (args.ip or args.serial):
        parser.error("provide a nonempty device IP or USB serial")
    if not 1 <= args.max_speed <= 65535:
        parser.error("--max-speed must be in [1, 65535]")
    if not 0 < args.bound <= MAX_BOUND_MM:
        parser.error(f"--bound must be in (0, {MAX_BOUND_MM:g}] mm")
    if not 0 < abs(args.amount) < args.bound:
        parser.error("--amount must be nonzero and smaller than --bound")
    if args.rate <= 0:
        parser.error("--rate must be positive")
    print("Run settings:")
    for label, value in [("transport", f"ip {args.ip}" if args.ip else f"usb serial {args.serial}"),
                         ("library", args.library),
                         ("axis / amount", f"{args.axis} {args.amount:+g} mm from home (0,0,0)"),
                         ("setpoint rate", f"{args.rate:g} mm/s"),
                         ("abort bound", f"±{args.bound:g} mm translation, ±{TILT_LIMIT_DEG:g}° rotation"),
                         ("maxSpeed", f"{args.max_speed} (logical, 65535 = unlimited)"),
                         ("accel profile", f"{args.accel_profile} ({ACCEL_PROFILES[args.accel_profile]})"),
                         ("strategy", "FullMatch (0): unreachable pose fails the send"),
                         ("run byte", f"{args.run_byte} (pause byte sent while moving)"),
                         ("loop period", f"{DT * 1000:g} ms; abort if any iteration exceeds {DEADLINE_S * 1000:g} ms"),
                         ("state gate", "every read requires: reference run done, not paused, not offline, no park, no module error"),
                         ("on exit", "send pause at last command (best effort; E-stop is the real stop)"),
                         ("settle report", f"{SETTLE_MM:g} mm threshold, informational only")]:
        print(f"  {label:14s} {value}")
    device = Device(args.library, args.ip, args.serial or "", args.run_byte, args.max_speed,
                    ACCEL_PROFILES[args.accel_profile], args.bound)
    try:
        rows, schedule = run_motion(device, axis=args.axis, amount=args.amount, rate=args.rate, hold=args.hold)
    finally:
        device.close()
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / "trajectory.csv"
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["time_s", "phase"] +
                        [f"{kind}_{axis}_mm" for kind in ["reference", "actual", "command"]
                         for axis in ["sway", "surge", "heave"]] +
                        [f"actual_{axis}_rad" for axis in ["roll", "pitch", "yaw"]] +
                        [f"actuator_{i + 1}_logical" for i in range(6)])
        writer.writerows(rows)
    print(f"SDK device trajectory: {path}")
    # Also emit vendor-format pose files matching examples/PrecisePos_CSV_CPP_Win/motion/*.csv exactly:
    # semicolon-separated, header "Time (ms);Roll (rad);Pitch (rad);Yaw (rad);Sway (mm);Surge (mm);Heave (mm)",
    # one row every 10 ms (the vendor player hardcodes INTERVAL_MS = 10). The log runs at the same nominal
    # rate, but real timestamps jitter, so it is linearly interpolated onto an exact grid. command.csv is what we sent (replayable); actual.csv is what the SDK reported.
    t_log = np.array([r[0] for r in rows])
    t_grid = np.arange(0., t_log[-1] + 1e-9, VENDOR_INTERVAL_MS / 1000.)
    for name, pose_cols, rot_cols in [("command", slice(8, 11), None), ("actual", slice(5, 8), slice(11, 14))]:
        pose = np.array([r[pose_cols] for r in rows], dtype=float)
        rot = np.array([r[rot_cols] for r in rows], dtype=float) if rot_cols else np.zeros_like(pose)
        resampled = [np.interp(t_grid, t_log, col) for col in np.c_[rot, pose].T]
        vendor_path = args.output / f"{name}.csv"
        with vendor_path.open("w", newline="") as stream:
            writer = csv.writer(stream, delimiter=";")
            writer.writerow(["Time (ms)", "Roll (rad)", "Pitch (rad)", "Yaw (rad)", "Sway (mm)", "Surge (mm)", "Heave (mm)"])
            for i, t in enumerate(t_grid):
                writer.writerow([f"{t * 1000:.1f}", *(f"{c[i]:.6g}" for c in resampled)])
        print(f"Vendor-format pose file ({VENDOR_INTERVAL_MS} ms grid): {vendor_path}")
    summarize(rows, schedule, args.axis)
    if not args.no_plot:
        plot(rows, args.axis, args.output / "trajectory.png")


if __name__ == "__main__":
    main()
