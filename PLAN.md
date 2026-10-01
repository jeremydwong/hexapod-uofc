# Option E build plan: Linux RT brain, Speedgoat as I/O and logger

Architecture and timing rationale: README.md, "Option E". This file is the
work list. Phases are in order; each ends with something runnable and a
measured result. Paths are relative to the repo root.

```
Speedgoat (I/O + logger) ──UDP 1 kHz──► Linux RT brain (C++) ──Ethernet──► PS-6TL-350
        ▲  ◄──UDP 1 kHz: events, poses, state, stim cmd──┘        ▲
        └─ accelerometer on top frame (true onset) ───────────────┘
Python GUI ──TCP JSON (config, start/stop)──► Linux RT brain
```

## Unknowns to settle first (each one blocks a phase)

| Question | Blocks | Ask |
| --- | --- | --- |
| Speedgoat model and I/O modules (AI/AO/DI channel counts, ranges, driver block names) | 5 | Ryan |
| Force plates: make/model, 12-channel mapping, calibration matrix, plate origin offsets | 4, 5 | Ryan |
| EMG: system, channel count, analog output range, required sample rate (≥ 2 kHz?) | 5 | Tyler |
| EVS stimulator: input range, bandwidth, safety limits on the drive signal | 5 | Tyler |
| Accelerometer for top-frame onset (model, range, mounting) | 7 | buy |
| Lab PC: desktop or laptop, CPU, number of NICs (need 2: Speedgoat + hexapod) | 2 | Ryan |
| PS-6TL-350 controller Ethernet: enabled, IP address | 2, 7 | Motion Systems |
| Controller setpoint rate (hint: 4 ms / 250 Hz in the MI manual) | 1 measures it; email confirms | Motion Systems |

## Phase 1: SDK timing baseline (Windows now, M10 over USB)

Goal: real numbers for SDK call cost and the controller's setpoint rate.

- [ ] `tools/sdk_timing/sdk_timing.py`: reuses `examples/LevelMove_Python/level_move.Device` and the lift/park helpers from `test_from_park.py`.
  - holds home and adds a ±1 mm, 0.5 Hz surge sine, so every setpoint differs
  - sweeps send periods 10, 4, 2, 1 ms (60 s each)
  - per cycle: `perf_counter_ns` timestamps, duration of each SDK call, sent setpoint, `requiredMotorPosition` (what the controller accepted), `actualMotorPosition`, reported pose
  - every 1 s: `GetPerformanceCounters` (vendor per-call µs, including send stages 1–3)
  - Windows: `timeBeginPeriod(1)`, `REALTIME_PRIORITY_CLASS`, one pinned core, `gc.disable()` during the loop
  - Linux (phase 2): same script, `SCHED_FIFO`, `mlockall`, pinned core
- [ ] Setpoint-rate estimate: the rate at which `requiredMotorPosition` changes, compared with the send rate. If it saturates near 250 Hz, that is the controller's cycle.
- [ ] `tools/sdk_timing/timing_report.py`: histograms of loop period, per-call durations and time-to-acceptance, per period; mirrors `examples/LevelMove_Python/report.py`.

Outputs (in `output/timing/`, gitignored):
- `<host>_<os>_<period>ms.csv` (one row per cycle)
- `<host>_<os>_perfcounters.csv`
- `summary.json` (percentiles p50/p99/p99.9/max per period)
- `timing_report.html`

Done when the report shows SDK call p99 and the saturating setpoint rate on Windows.

## Phase 2: Linux RT machine (second SSD in the lab PC)

- [ ] `rig/linux/SETUP.md`: install steps. Debian 13 with `linux-image-rt-amd64`, or Ubuntu 24.04 with the real-time kernel; Omarchy with an RT kernel if preferred. Pin the kernel version for the duration of a study.
- [ ] `rig/linux/kernel-cmdline.txt`: `isolcpus=2,3 nohz_full=2,3 rcu_nocbs=2,3 irqaffinity=0,1` (adjust to core count).
- [ ] `rig/linux/rt-tune.sh`: performance governor; hold `/dev/cpu_dma_latency` at 0; pin the two NICs' IRQs to cores 2/3; disable irqbalance; set up the NICs (static IPs, no power saving).
- [ ] `rig/linux/99-forceseat.rules`: udev rule for the M10 / controller USB (`0483:A110`) so the brain need not run as root. Untested assumption: the vendor says root is needed to detach the kernel driver. Fall back to root or use Ethernet.
- [ ] `rig/linux/cyclictest.sh`: 1 h `cyclictest` on the isolated cores under `stress-ng` load; writes a histogram and plot.
- [ ] Re-run phase 1 on Linux against the M10.

Outputs: `output/linux/cyclictest_<date>.txt`, `.png`; phase-1 CSVs for Linux.

Done when cyclictest max < ~100 µs and the Linux SDK timing is recorded next to Windows.

## Phase 3: Wire protocol (single source of truth)

- [ ] `rig/protocol/packets.h`: packed C structs, little-endian, `magic` + `version` fields.
  - `SampleFrame` (Speedgoat → Linux, every 1 ms): `sample_idx u32`, `sg_time_us u64`, `force[12] f32` (volts), `din u16`, `flags u16`
  - `ControlFrame` (Linux → Speedgoat, one reply per SampleFrame): `echo_sample_idx u32`, `seq u32`, `trial_id u16`, `profile_id u16`, `events u32` (bits: trigger_fired, profile_start, profile_end, catch_trial, abort, watchdog), `cmd_pose[6] f32`, `sdk_pose[6] f32`, `platform_state u32`, `stim_enable u8`, `stim_seed u32`, `stim_amp f32`, `rx_to_tx_ns u32`
- [ ] `rig/protocol/packets.py`: `struct` formats mirroring the header, plus a size and layout test against the C header.
- [ ] `rig/protocol/PROTOCOL.md`: byte layout tables, units and signs (sway + right, surge + front), timeout rules. The Speedgoat pack/unpack blocks are built from these tables.

Done when a round-trip test passes in C++ and Python with identical bytes.

## Phase 4: Linux brain (C++20, CMake)

`rig/brain/`:
- [ ] `CMakeLists.txt`: builds `brain`, unit tests; links `code/ForceSeatDI_Loader.c` (loads `ForceSeatDI64.so`).
- [ ] `src/main.cpp`: parse args; `mlockall`; start threads with `SCHED_FIFO` and core affinity; clean shutdown pauses the hexapod, then parks it.
- [ ] `src/rt.{h,cpp}`: helpers for thread priority/affinity, monotonic ns clock, `eventfd` wakeups.
- [ ] `src/udp_link.{h,cpp}`: Speedgoat socket on NIC 1; busy-poll receive; validates magic/version/sequence; watchdog (no SampleFrame for N ms → hold, pause, flag).
- [ ] `src/cop.{h,cpp}`: calibration matrix × volts → forces/moments per plate; combined CoP; CoP velocity (filtered difference); config from `config/plates.json`.
- [ ] `src/trigger.{h,cpp}`: state machine WAIT_READY → IN_WINDOW (CoP within radius, speed below threshold, for a dwell time) → JITTER (random delay) → FIRE → PROFILE → COOLDOWN; catch trials run the same states but fire nothing; seeded RNG, seed logged.
- [ ] `src/schedule.{h,cpp}`: trial list from the experiment config: fully random, block/pseudo-random, catch-trial ratio.
- [ ] `src/profiles.{h,cpp}`: position profiles (step, linear, sigmoid/smoothstep: displacement, ramp-up/ramp-down time, hold) and velocity profiles; per-axis; bounded by workspace and rate limits.
- [ ] `src/hexapod.{h,cpp}`: ForceSeatDI wrapper; command thread on core 3, woken by `eventfd` on a trigger, otherwise ticking at the measured controller period; lift-from-park / lower-to-park (logic from `test_from_park.py`, including the −165.0 mm start); bound and tilt checks; reads SDK pose/state each cycle into shared state.
- [ ] `src/control_loop.{h,cpp}`: core 2; one iteration per SampleFrame: CoP → trigger → profile setpoint → publish setpoint → build and send ControlFrame.
- [ ] `src/config_server.{h,cpp}`: TCP JSON on the management NIC (load experiment, start, stop, status); never touches the RT threads directly (lock-free queue).
- [ ] `src/debug_log.{h,cpp}`: lock-free ring buffer → binary file for debugging; the authoritative log is the Speedgoat's.
- [ ] `config/experiment.example.json`, `config/plates.example.json`.
- [ ] `tests/`: profiles (shape, limits), trigger (synthetic CoP traces), cop (known loads), protocol round trip.
- [ ] `tools/sg_emulator.py`: acts as the Speedgoat. Sends SampleFrames at 1 kHz from synthetic sway or a recorded CSV; receives and logs ControlFrames. Lets the brain be developed and tested against the M10 without a Speedgoat.

Outputs: `output/brain/<session>/debug.bin`, `session.json` (config, seeds, versions); `sg_emulator` writes `control_frames.csv`.

Done when the brain + `sg_emulator` + M10 run a 20-trial randomized session with catch trials and correct event bits.

## Phase 5: Speedgoat I/O-and-logger model

This is the "dummy shell" model: no experiment logic, only I/O, UDP and logging.

`rig/speedgoat/`:
- [ ] `rig_io.slx`, the model:
  - **Solver:** fixed-step discrete. Base rate 0.5 ms (2 kHz) if EMG needs it; UDP send/receive at 1 ms (multi-rate, rate transitions explicit).
  - **Inputs:** analog input driver blocks for the lab's I/O module: 12 force channels, N EMG channels, 1–3 accelerometer channels, any digital sync inputs. Scale to volts.
  - **Sample counter:** free-running counter → `sample_idx`; target time → `sg_time_us`.
  - **Send:** pack SampleFrame (MATLAB Function `pack_sample_frame.m`, or Byte Pack) → Simulink Real-Time UDP Send block to Linux IP:port. Force channels only; EMG is logged, not sent.
  - **Receive:** Simulink Real-Time UDP Receive block → `unpack_control_frame.m` → bus of ControlFrame fields plus `rx_valid` and `frames_missed`. If no frame arrives, hold the last value and count misses.
  - **Stimulator:** `stim_noise.m` (MATLAB Function with persistent LCG state, reseeded when `stim_seed` changes) × `stim_amp` × `stim_enable` → hard clamp to the stimulator's safe range → analog output block.
  - **Optional:** digital output pulse on `trigger_fired` for external sync (mocap).
  - **Logging:** target file logging of all analog inputs, the whole ControlFrame bus, `sample_idx`, `rx_valid`, `frames_missed`, the stim output.
- [ ] Keep all logic in `.m` files so git diffs mean something; the `.slx` is only wiring:
  - `rig_io_params.m`: IPs, ports, rates, channel maps, scaling, stim limits
  - `pack_sample_frame.m`, `unpack_control_frame.m`: byte layouts from `rig/protocol/PROTOCOL.md`
  - `stim_noise.m`
- [ ] `build_and_deploy.m`: `slbuild`, connect `slrealtime` target, load, start; prints the target and model version.
- [ ] `export_trials.m`: pulls the target log; splits by `trial_id` / `profile_start` into one `.mat` per trial (Kinarm-style struct: analog, events, commanded + reported pose, stim, config); writes a session `.mat` index.
- [ ] `rig/speedgoat/README.md`: required toolboxes, MATLAB version, I/O module, network setup.
- [ ] `.gitattributes`: `*.slx binary`, `*.mat binary`, `*.mldatx binary`; `.gitignore`: `slprj/`, `*.slxc`, `*_slrealtime_rtw/`, `*.mldatx` logs.

Outputs:
- on the target: the log file per run
- after `export_trials.m`: `data/<subject>/<session>/trial_###.mat` + `session.mat`

Done when Linux sees SampleFrames at 1 kHz with no sequence gaps for 10 min, and the Speedgoat log shows every ControlFrame with `rx_valid`.

## Phase 6: GUI (Python)

`rig/gui/`:
- [ ] `gui.py` (PySide6):
  - experiment editor: perturbation blocks (axis, profile type, amplitude, ramp times), randomization mode, catch-trial ratio, CoP window and thresholds, timing jitter range, stim on a subset of trials
  - channel list with record toggles; the Speedgoat logs everything and the toggles select what `export_trials.m` keeps
  - start/stop, live status (trial n/N, platform state, missed frames)
- [ ] `experiment_schema.py`: one schema (pydantic) for the JSON that the brain and the GUI share.
- [ ] `client.py`: TCP client for `config_server`.

Outputs: `experiments/<name>.json` (versioned in git).

## Phase 7: Integration and acceptance

- [ ] Brain + Speedgoat + M10: full session; check event alignment in the exported `.mat`.
- [ ] Platform + accelerometer: ≥ 300 triggers; latency = accelerometer onset − trigger sample, all on the Speedgoat clock.
- [ ] `rig/analysis/latency_report.py`: onset detection, latency histogram, jitter percentiles; compare with the README budget (~12–33 ms, ~1–2 ms jitter).
- [ ] `rig/analysis/session_report.py`: per-session HTML (trials, CoP at trigger, profiles, meshcat replay reusing `examples/LevelMove_Python/report.py`).
- [ ] Update README Option E with measured numbers.

Outputs: `output/latency/latency_report.html`, `output/sessions/<session>/report.html`.
