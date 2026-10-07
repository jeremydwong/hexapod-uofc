# Speedgoat experiment model: FSM_EXPT, CoP and state stream

The Speedgoat (Simulink Real-Time, QNX) is the I/O box and master clock, and runs the
trial state machine at 1 kHz. It streams its state to the host over UDP; the host plots
it (`uv run hexapod-live`) and, next, relays the setpoint to the hexapod through
ForceSeatDI.

**Status: written without MATLAB; not yet run in Simulink.** The same logic, as a Python
mirror (`rig/uofc_hexa/expt/fsm.py`), passes the full-run, stop and host-loss tests and
drives the live viewer through the emulator at 1 kHz with no lost packets. Run
`test_fsm_expt.m` first: it checks the MATLAB version the same way, without Simulink.

## Files

| File | Role |
| --- | --- |
| `fsm_expt.m` | MATLAB Function block: the trial state machine and open-loop perturbation setpoints |
| `cop_from_plates.m` | MATLAB Function block: two plates' 12 analog inputs -> combined CoP and total Fz |
| `pack_state.m` | MATLAB Function block: the 21-double state packet |
| `expt_params.m` | Parameters (`P`): trial table, CoP filter, force-plate calibration placeholders |
| `load_trials.m` | Reads the trial CSV, checks every target against the measured safe limits |
| `trials_example.csv` | Example trial list |
| `test_fsm_expt.m` | Desktop test of `fsm_expt.m` on synthetic CoP (no Simulink) |

## States

```
IDLE --Start--> HOMED --random_s elapsed--> MOVETGT --arrived--> WAIT_COP
  ^               ^                                               | CoP within cop_radius_mm of centre,
  |               '------------- next trial <---- RETURN <--------'  SD < cop_sd_mm, for thresh_seconds_cop_stable
  '-- Start = 0 (after returning home)            '-- last trial --> DONE
host_ok = 0 in HOMED/MOVETGT/WAIT_COP/RETURN --> FAULT (setpoint frozen)
```

Moves are open-loop smoothsteps: duration = 1.875 × distance / peak speed (minimum 0.2 s),
the same profile as `hexapod-park-test`. Heave stays 0: the host lifts the platform to home
before Start and parks it afterwards. The CoP centre is the running-mean CoP at the moment
Start goes high (`P.cop_center_auto`), or `P.cop_center_mm`.

## Wiring the model (fixed-step discrete, 0.001 s)

```
Digital Clock (0.001) ------------------------------------------> fsm_expt  t
Constant "start" (tunable; set 1 to run) ------------------------> fsm_expt  start
Constant 1 (until the host heartbeat exists) --------------------> fsm_expt  host_ok
Analog Input (12 ch: plates) --> cop_from_plates --cop_xy, fz---> fsm_expt  cop_xy, fz_total
Counter Free-Running ------------------------------------------> pack_state seq
fsm_expt outputs + cop + t -----------------------------------> pack_state --> Byte Packing (double)
                                                                    --> UDP Send (host IP, port 25000)
everything above ----------------------------------------------> File Log (the authoritative record)
```

- Block parameter `P` in all three MATLAB Function blocks: run `P = expt_params('trials.csv');`
  before building. `P` is a struct with fixed-size arrays (trial table padded to 500 rows).
- UDP Send: *Local IP address* = "Use host-target connection" works; Speedgoat recommends a
  dedicated port for real-time UDP if your target has one. Remote IP = host (e.g.
  192.168.7.2), remote port 25000. Avoid ports 1-1023 and 5500-5560 (reserved).
- Byte Packing: all inputs double, little-endian; the host decodes 21 doubles (168 bytes).
  Layout: `pack_state.m` and `rig/uofc_hexa/expt/packet.py`.
- Windows will ask whether Python may receive on the network the first time `hexapod-live`
  runs; allow it, or add a firewall rule for UDP 25000.

## Before the first real run

1. **Force plates.** Fill in `P.plate(k).C`, `.channels`, `.origin_mm`, `.dz_mm` for the lab's
   plates (make/model, amplifier gains, channel order). Check signs by standing on each
   corner and watching `hexapod-live`.
2. **Host heartbeat.** Replace the `host_ok` constant with a UDP Receive from the host
   (packet counter that must keep changing) so a crashed host freezes the FSM.
3. **Setpoint relay.** The host program that forwards `sp` to the hexapod (ForceSeatDI,
   `SendTopTablePosPhy`) and sends the reported pose back for logging is the next piece.
