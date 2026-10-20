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
the emulator. `build_expt_rt.m` has **not** been run yet (needs Simulink Real-Time + the
Speedgoat libraries; it reports any UDP block parameter it could not set). The setpoint is
not yet relayed to the hexapod.

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

Without a Speedgoat: `uv run hexapod-expt-emulator` in one terminal, then
`uv run hexapod-expt-run --target 127.0.0.1`.

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
| `cop_from_plates.m` | MATLAB Function block: analog inputs → combined CoP and total Fz |
| `pack_state.m` | MATLAB Function block: the 39-double state packet, as bytes |
| `expt_params.m` | Parameters `P` (limits, CoP filter, AI channels, plate calibration) and `net` |
| `load_trials.m` | Trial CSV → table matrix, for the desktop tests |
| `test_host_rx.m`, `test_fsm_expt.m` | Desktop tests (plain MATLAB, no Simulink) |

Python side (`rig/uofc_hexa/expt/`): `command.py` (command packet, `host_rx` mirror),
`packet.py` (state packet), `fsm.py` (FSM mirror), `protocol.py`, `run_expt.py`
(`hexapod-expt-run`), `live_view.py` (`hexapod-live`), `emulator.py`. Keep each mirror in step
with its MATLAB block.

## States

```
IDLE --Start--> HOMED --random_s elapsed--> MOVETGT --arrived--> WAIT_COP
  ^               ^                                               | CoP within cop_radius_mm of centre,
  |               '------------- next trial <---- RETURN <--------'  SD < cop_sd_mm, for thresh_seconds_cop_stable
  '-- Start = 0 (after returning home)            '-- last trial --> DONE      (or max_wait_s, if > 0)
host_ok = 0 in HOMED/MOVETGT/WAIT_COP/RETURN --> FAULT (setpoint frozen; restart the app)
```

Moves are open-loop smoothsteps: duration = 1.875 × distance / peak speed (minimum 0.2 s).
Heave stays 0. `max_wait_s` lets a trial return even if the CoP never settles: the demo uses it
because uncalibrated plates (or nobody standing) never pass the `P.min_fz_N` check.

## Before a real run

1. **Force-channel map.** `simulink/ReadForcePlates.slx` reads only AI 3 of the IO324-200k
   (±5.12 V, single-ended). Set `P.ai_channels` to the plates' 12 channels, and
   `P.plate(k).channels` to positions within that list. Fill in `C`, `origin_mm` and `dz_mm`, then
   check signs by standing on each corner while watching the analog and CoP panels.
2. **UDP blocks.** Check the dialog values `build_expt_rt` lists (ports 25001 in, 25000 out to
   192.168.7.2). Speedgoat recommends a dedicated real-time Ethernet port for UDP if the target
   has one; the host-target link works for a demo. Avoid ports 1–1023 and 5500–5560.
3. **Setpoint relay.** Next piece: the host forwards `sp_sway`/`sp_surge` to the hexapod
   (ForceSeatDI) and returns the reported pose. The vendor FSDI Simulink blocks call a Windows
   DLL, so they cannot run in this QNX model; the relay belongs on the host.
