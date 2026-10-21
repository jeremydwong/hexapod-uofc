# Speedgoat experiment model: expt_rt (force channels, FSM, host link)

The Speedgoat (Simulink Real-Time, QNX) is the I/O box and master clock. It runs the trial
state machine at 1 kHz on the force-plate CoP, takes its trial table and Start from the host,
and streams its state back. The host program sends the protocol, starts the run and
live-plots it:

```
host (Windows)                                       Speedgoat (expt_rt, 1 kHz)
hexapod-expt-run --- UDP 25001, 100 Hz ---------->  host_rx: heartbeat, Start, trial rows
  protocol JSON      112 B: seq, start, row k            | table + start + host_ok
                                                         v
  live plot  <------ UDP 25000, 1 kHz ------------  fsm_expt <-- cop_from_plates <-- IO324 AI
  + .npz record      312 B: state, CoP, table echo,      |
                     12 analog volts                 pack_state --> UDP Send
                                                     file log (authoritative record)
```

**Status:** block functions tested in plain MATLAB (`test_host_rx.m`, `test_fsm_expt.m`),
byte layouts cross-checked against the Python side, host program tested end to end against
the emulator. `build_expt_rt.m` runs on R2025b and the model compiles (Update Diagram); not
yet built and run on the Speedgoat itself. The host relay to the hexapod (`--hexapod`) is
written but not yet run against a controller.

## Running the demo

On the lab PC (MATLAB R2025b with Simulink Real-Time, Speedgoat I/O libraries):

```matlab
cd rig/speedgoat
build_expt_rt        % once: generates expt_rt.slx; read the "Check in the block dialogs" list
start_expt_rt        % builds if needed, loads and starts it on the Speedgoat
```

Then in a terminal (Windows asks once to let Python through the firewall; allow it):

```powershell
uv run hexapod-expt-run --protocol experiments/demo_surge.json
```

It waits for the state stream, sends the table until the Speedgoat echoes every row with the
same checksum, then enables **Start**. `--auto-start` skips the button; `--start-target` runs
`start_expt_rt` through `matlab -batch` first. Closing the window sets Start = 0, keeps the
heartbeat until the Speedgoat is idle, and saves the stream to `output/expt/<name>_<time>.npz`.

**Plates empty when the app starts:** `cop_from_plates` zeroes the load cells over the first
`P.tare_s` (2 s) and the FSM ignores Start until then. The host plots the zeroed volts. To
re-zero without a restart (plates empty, idle): `retare_expt`.

**Calibration is tunable, no rebuild:** gains `C1`/`C2`, plate centres, `dz`, `min_fz_N` and
`noise_floor_N` live in `expt_cal.m`. `start_expt_rt` pushes them after every load; to change
them on the running app, edit `expt_cal.m` and run `apply_expt_cal`. They reach the model as
`CAL_*` Simulink.Parameters (`expt_tunables.m`, ExportedGlobal) read by Constant blocks, and
editing them never makes the build stale.

With `--hexapod --run-byte 0` (plus `--ip 10.1.1.75` for the platform on Ethernet; default is
the M10 imitator on USB) the host also drives the platform (`rig/uofc_hexa/expt/relay.py`):
before Start it checks every protocol target paused (FullMatch; nothing moves on a rejection)
and lifts from park to home; during the run it sends the Speedgoat's setpoint every 10 ms,
slew-limited, and pauses the platform on a stale stream (> 0.5 s), a Speedgoat FAULT, a pose
outside the bound or tilt limit, or any SDK error; after the run it lowers and parks. What it
sent and what the SDK reported are saved in the same `.npz` (`relay`, `relay_fields`).
The E-stop remains the real stop.

Without a Speedgoat: `uv run hexapod-expt-emulator` in one terminal (`--fz 0` for empty
plates), then `uv run hexapod-expt-run --target 127.0.0.1`.

## Protocols (why no file on the target)

A protocol is JSON on the host (`experiments/*.json`, format in `rig/uofc_hexa/expt/protocol.py`;
`uv run hexapod-expt-protocol demo` writes the demo). The host streams it to the target as
rows of the command packet, so there is no file on the QNX side and no rebuild per protocol:

- The table only changes while Start = 0, so it is frozen for a run.
- `host_rx.m` re-checks every row against the safe limits (`P.limits_mm`,
  `P.max_peak_speed_mm_s`); a bad row is not stored, is counted in `n_rejected`, and
  blocks Start.
- The checksum echo proves the target holds exactly the host's table before Start.
- The table and every row arrive in the target's file log, so the run is self-describing.

Alternatives considered: scp a file to the target (it accepts SSH) and read it in the model,
which needs custom file I/O code in the real-time app; or bake the table into the build,
which means a rebuild (minutes) for every protocol change.

## Files

| File | Role |
| --- | --- |
| `build_expt_rt.m` | Generates `expt_rt.slx` (IO324 blocks copied from `simulink/ReadForcePlates.slx`) |
| `start_expt_rt.m` | Build if stale, load and start on the target |
| `host_rx.m` | MATLAB Function block: command packet → Start, host_ok, trial table, echo |
| `fsm_expt.m` | MATLAB Function block: the trial state machine and open-loop setpoints |
| `cop_from_plates.m` | MATLAB Function block: tare, then analog inputs → combined CoP and total Fz |
| `pack_state.m` | MATLAB Function block: the 39-double state packet, as bytes |
| `expt_params.m` | Build-time parameters `P` (limits, CoP filter, AI channels, plate channels) and `net` |
| `expt_cal.m` | Tunable calibration: plate gains, centres, dz, `min_fz_N`, `noise_floor_N` (no rebuild) |
| `expt_tunables.m` | Creates the `CAL_*` Simulink.Parameters for the build |
| `apply_expt_cal.m` | Pushes `expt_cal.m` onto the loaded or running app |
| `retare_expt.m` | Re-zeroes the load cells on the running app (plates empty) |
| `load_trials.m` | Trial CSV → table matrix, for the desktop tests |
| `test_host_rx.m`, `test_fsm_expt.m` | Desktop tests (plain MATLAB, no Simulink) |

Python side (`rig/uofc_hexa/expt/`): `command.py` (command packet, `host_rx` mirror),
`packet.py` (state packet), `fsm.py` (FSM mirror), `protocol.py`, `run_expt.py`
(`hexapod-expt-run`), `relay.py` (setpoint → hexapod), `live_view.py` (`hexapod-live`), `emulator.py`. Keep each mirror in step
with its MATLAB block.

## States

```
IDLE --Start--> HOMED --random_s elapsed AND CoP centred--> MOVETGT --arrived--> WAIT_COP
  ^               ^                                               | CoP within cop_radius_mm of centre,
  |               '------------- next trial <---- RETURN <--------'  SD < cop_sd_mm, for thresh_seconds_cop_stable
  '-- Start = 0 (after returning home)            '-- last trial --> DONE      (or max_wait_s, if > 0)
host_ok = 0 in HOMED/MOVETGT/WAIT_COP/RETURN --> FAULT (setpoint frozen; restart the app)
```

Moves are open-loop smoothsteps: duration = 1.875 × distance / peak speed (minimum 0.2 s).
Heave stays 0. "CoP centred" (both gates) = total Fz at least `min_fz_N`, CoP within
`cop_radius_mm` of the centre, running SD below `cop_sd_mm`. **Empty-plate override:** with total
Fz below `noise_floor_N` both gates pass, so the protocol runs on an empty platform; loads
between the noise floor and `min_fz_N` (both in `expt_cal.m`; someone stepping on or off) wait. `max_wait_s` still
lets a loaded trial return if the CoP never settles.

## Before a real run

1. **Force-channel map.** `simulink/ReadForcePlates.slx` reads only AI 3 of the IO324-200k
   (±5.12 V, single-ended). Set `P.ai_channels` to the plates' 12 channels, and
   `P.plate_channels` rows to positions within that list. Fill in `C1`, `C2`, `origin_mm` and `dz_mm` in `expt_cal.m`, then
   check signs by standing on each corner while watching the analog and CoP panels.
2. **UDP blocks.** Check the dialog values `build_expt_rt` lists (ports 25001 in, 25000 out to
   192.168.7.2). Speedgoat recommends a dedicated real-time Ethernet port for UDP if the target
   has one; the host-target link works for a demo. Avoid ports 1–1023 and 5500–5560.
3. **Noise floor.** `noise_floor_N` in `expt_cal.m` (50 N) is a placeholder: set it from the zeroed, empty
   plates' Fz noise once `C` is real.
4. **Relay on hardware.** First on the M10 imitator, then the platform at a short protocol with
   the area clear and E-stop in hand. The relay runs on the host because the controller is only
   reachable through ForceSeatDI, a Windows DLL; the Speedgoat (QNX) cannot call it.
