# Waypoints_Simulink: park → home → surge/sway waypoints → park, in Simulink

Same motion as `examples/LevelMove_Python/test_from_park.py`, but built from
the vendor's ForceSeatDI Simulink blocks so it fits the lab's existing
Simulink setup. The motion logic is plain `.m` text; the `.slx` is generated
by a script and is not committed.

**Status: written without MATLAB and untested in Simulink.** The schedule
logic was checked with a Python transcription (continuous, ≤ 10 mm/s,
matches the timeline of the 2026-09-29 M10 run); the model build and the
block wiring have not been run. Try it on the M10 first.

## Files

| File | Role |
| --- | --- |
| `waypoints_params.m` | The sequence and the safety limits. Edit this. |
| `waypoint_schedule.m` | Pure function: setpoint at time t (smoothstep moves, rests). |
| `waypoint_setpoint_block.m` | Body of the MATLAB Function block: read pose, latch start, follow the schedule, stop sending on a fault. |
| `build_waypoints_model.m` | Generates `Waypoints_FSDI.slx` from the vendor library blocks. |
| `run_waypoints.m` | Builds if needed, runs, plots command vs reported, saves a `.mat`. |

## Model

```
Digital Clock ─► Setpoint (MATLAB Function) ─► ForceSeatDI_PosPhy
                   ▲                       └─► ForceSeatDI_Refresh
ForceSeatDI_Sway/Surge/Heave/Roll/Pitch/Yaw ┘   (reported pose)
```

Fixed 10 ms step, Simulation Pacing on (as in the vendor example), stop time
from the schedule (~134 s for the default sequence). The vendor library's
`initialize()` connects to the platform at start and its `terminate()` parks
it when the simulation stops.

## Run

1. Close ForceSeatPM. Only one program can hold the device.
2. Copy `ForceSeatDI64.dll` into this folder.
3. Platform (or M10) parked; E-stop in reach.
4. In MATLAB: `cd examples/Waypoints_Simulink`, `run_waypoints`.

## Safety behaviour, and why it is needed

The vendor `SetPosPhy` sends `maxSpeed = 65535` (no limit) and never pauses,
so whatever reaches its inputs is executed as fast as the controller can.
That is also what happens with the lab's sliders: a fast drag is a full-speed
move. Here the Setpoint block is the only speed limit:

- First 0.5 s: only refresh and read the pose, send nothing.
- Refuses to move (fault) unless the reported heave is below −100 mm
  (parked), and if the pose reads all zeros (no data yet).
- Starts the schedule from the measured pose (heave clamped to −165.0 mm).
- Stops sending for good if reported and commanded differ by more than
  20 mm on any axis, or any rotation exceeds 0.5°. The controller then holds
  the last setpoint; stop the simulation and `terminate()` parks it.

The vendor blocks ignore SDK return values, so failed sends are silent here.
Use the Python scripts when you need error codes and state bits.

## Things to check on first run

- Port order of `ForceSeatDI_PosPhy`: assumed to follow `SetPosPhy`'s
  argument order (yaw, pitch, roll, heave, sway, surge, strategy, enable).
  Open the block and compare with the wiring before powering a real platform.
- `strategy` and `enable` are sent as `int32`. If Simulink reports a type
  mismatch on those ports, insert Data Type Conversion blocks.
- The model reads `P` from the base workspace; `run_waypoints.m` sets it.
