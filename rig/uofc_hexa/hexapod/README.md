# ForceSeatDI level move example

`level_move.py` uses ctypes and the supplied code/ForceSeatDI_Structs.py to call
the installed native ForceSeatDI library over Ethernet or USB. It defaults to
surge; sway and heave are also supported. Twist is not implemented here.

The Python program streams a smooth move from the reported start pose to home
(0,0,0), holds, then a move of --amount mm (default 15) along --axis, then
holds. It is open loop: Python only generates setpoints at
100 Hz and logs what the SDK reports back. All rotational commands are zero.
The platform controller operates the actuators. Position feedback comes from
the SDK; there is no external tilt measurement and no Python-side correction.

Setpoints change at no more than --rate mm/s (default 5); move durations
scale with distance so large moves stay slow. --bound (default 50 mm, hard
cap 150 mm) aborts the run if any reported or commanded translation exceeds
it. The tech sheet lists single-axis surge travel of -306/+273 mm, so raise
--bound deliberately once small moves are verified. After the run the script prints
tracking metrics (max error, settle time to within 0.2 mm) and shows a plot of
reference, command and reported pose, reported rotations, and the six logical
actuator positions. These metrics are informational and never abort a run.
Nothing here has been tested on hardware.

An installed ForceSeatDI library, device address, and explicit --hardware flag
are required. Run `uv run hexapod-move --help` from anywhere in the repo for arguments; `--library` defaults to `$FORCESEATDI_LIBRARY`. Supply either --ip or --serial and a
verified --run-byte (0 or 1): the supplied header and examples disagree about
the pause flag. --max-speed is an SDK logical value, not mm/s. --accel-profile selects the
controller's ramp shape (auto, rapid, balanced, smoothest); the API has no
numeric acceleration limit. All settings are printed before any motion.

The device must already be referenced, unpaused, unparked, and within the
--bound / 0.5 degree limits of neutral. The script moves it to (0,0,0)
itself but does not run the controller's reference (homing) run. It requests a pause on completion or an error.

A successful run saves trajectory.csv and trajectory.png with timestamps,
reference/command positions, SDK-reported position and rotation, and actuator
positions. Pass --no-plot to skip the window. It also writes command.csv and actual.csv
in the vendor's semicolon pose format (see PrecisePos_CSV_CPP_Win/motion), so
either the sent or the reported trajectory can be replayed by the vendor's CSV
player unmodified. The log runs at the same nominal 10 ms, and is interpolated onto
an exact grid to remove timing jitter. No simulated data or actuator
force estimates are generated. No hardware run has been performed here.
