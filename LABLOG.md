# Lab log

Newest entry first. What was done, what is known, what to try next.

## 2026-10-20: Speedgoat app live, first platform motion, USB link drops pose reads

### Done

- **Speedgoat `expt_rt` built and running** on TargetPC1 (192.168.7.5), R2025b. Fixes needed on the
  way: UDP blocks live in `slrealtimeiplib`; receive width is `rcvWidth`; UDP Send has a Length
  input (double, 312); both UDP blocks need `useHostTargetConn` (the 10.10.10.x default fails at
  start); the IO324 Analog input has **one output port per channel**, so a Mux builds the 12-wide
  vector (before, only AI 1 reached the CoP block). Host gets 1000 packets/s, 0 lost.
- **Host firewall:** the Speedgoat cable is a Public network and uv's python.exe had inbound
  Block rules (from a cancelled prompt). Disabled them; added an allow rule for UDP 25000 from
  192.168.7.5 only.
- **Tare + gate:** load cells zeroed over the first 2 s after app start (plates must be empty);
  perturbation waits for a centred CoP; below `P.noise_floor_N` (empty plates) both CoP gates
  pass. Zero check with amplifiers on: all 12 channels within ±0.9 mV, SD ~0.2 mV.
- **Channel map:** the professor's ReadForcePlates.slx (identical to `simulink/`) reads only AI 3;
  its unsaved Aug 31 autosave (the version last built) reads AI 1-12 as two scopes of 6. No
  volts-to-force mapping anywhere on the PC (`ReadForcePlatescal.mat` is the code generator's
  empty parameter file). A y-push moved AI 2 and AI 8, so assumed order Fx Fy Fz Mx My Mz holds
  for Fy; **AI 1-6 = right plate, AI 7-12 = left**. `C` still `eye(6)`.
- **Real platform over USB:** connects with `--serial any` (S/N 3a0034-001551-303338-353336;
  enumerates as ForceSeatMP1, like the M10). Parked = state 0x52, heave -165.65 mm.
- **First motion under our software:** `hexapod-park-test --run-byte 0 --serial any --sequence
  "surge:+10,home"`: lift, +10.00 mm, home all clean (10.0 ms loops). **Run byte 0 = run on the
  PS-6TL-350.** The lower then aborted on one 212 ms loop stall (paused at heave -32.5 mm);
  lowered and parked by hand-run script.
- **Live view:** `hexapod-live --pose` adds a 3D platform panel (SDK pose read-only, Speedgoat
  setpoint as a ghost, RGB right/front/up triad; footprint and heights from the tech sheet, top
  size estimated, legs schematic). Analog legend labelled R/L Fx..Mz.
- **Protocols:** `experiments/demo_one.json` (+50 mm at 100 mm/s) and `demo_fast.json` (+100 mm at
  500 mm/s = 74% of the 680 mm/s maximum; 0.375 s, 0.42 G). Dry runs on the Speedgoat (platform
  untouched) match the plan exactly.
- **Relay / one-liner:** `uv run hexapod-expt-run --hexapod --protocol experiments/demo_fast.json`
  (defaults: serial any, run byte 0, maxSpeed 65535, tilt abort 1.0 deg, DLL found under
  ~/Documents/MotionSystems). Loop stalls under 0.5 s are held and logged; lowers to the park
  height at the end.

### Problem: pose/actuator reads fail with SDK error 2

The fast run aborted 8 s into the lift (heave -164.75 mm, paused) after three ~200 ms stalls:
`GetActuatorsPosLog failed; SDK error 2`. Afterwards every `GetTopTablePosPhy` and
`GetActuatorsPosLog` fails with error 2 in any new connection; `GetPlatformInfo` still works and
reports no module error. A USB replug clears it. Tests after the replug:

- Reads only, 30 s at 100 Hz: 9000 calls, max 1.7 ms, no failures.
- Paused sends at the parked pose (no motion): state 0x52 -> 0x11, then reads fail with error 2
  again, until the next replug.

**Likely cause:** the Windows services **MotionSystems Com64** and **MotionSystems AppWatcher64**
(ForceSeatPM's background services) are running and probably share the USB device with our
ForceSeatDI connection. Closing the ForceSeatPM window and tray icon does not stop them. The
controller is not on Ethernet (10.1.1.75 unreachable); the Speedgoat only talks to the host.

### Next

1. Admin PowerShell: `Stop-Service -DisplayName "MotionSystems Com64", "MotionSystems AppWatcher64"`,
   then replug the USB. Rerun the paused-send timing test (no motion). If there are no stalls and no
   error 2, the services were the cause; set them to Manual startup on this PC.
2. Then the 75% run: `uv run hexapod-expt-run --hexapod --protocol experiments/demo_fast.json`
   (area clear, E-stop in hand; lift starts at once, the surge on Start).
3. If error 2 persists with the services stopped: USB directly into the PC, USB selective suspend
   off; ask Motion Systems what `GetRecentErrorCode` 2 means (DLL 2.177); try Ethernet.
4. Force calibration: full scale at ±5 V is [500 500 1000 N, 150 100 75 N·m] per plate, so
   `C = diag([100 100 200 30 20 15])` per volt. Check the Fz sign with a press first (a negative Fz
   would read as empty plates and trigger the override). Rebuild with the plates empty (re-tare).
5. Verify the rest of the channel order (Fz, moments) by pressing on each plate; set
   `P.noise_floor_N` from the empty-plate Fz noise once `C` is real.

## 2026-10-08: transient tilt during fast moves, and what the force plates can tell us

- **The 0.5° tilt guard** (`TILT_LIMIT_DEG` in `level_move.py`, used by `hexapod-park-test`)
  is an abort threshold on the SDK-reported roll/pitch/yaw; we always command zero rotation.
  On the M10, smooth 300 mm moves in 0.7–1.0 s reported 0.18–0.44° and a 0.5 s move 0.46°,
  so fast runs on the robot may trip it mid-move. To do: a `--tilt-limit` option (default
  0.5°) so fast runs can raise it deliberately and report the peak.
- **Cause:** the six actuator servos lag their targets by different amounts during fast
  moves, so the top frame twists in transit. The reported tilt is forward kinematics of
  the measured actuator positions, not a measurement of the frame.
- **Ways to reduce it, in order:** gentler profiles (longer, or higher-order S-curves); try
  the controller's acceleration profiles on the robot (the M10 ignores them); iterative
  learning control: repeat a profile, record the reported tilt, feed back the opposite
  roll/pitch/yaw (lag-shifted) as feedforward until it converges, learnt with a
  representative load. Not recommended: real-time tilt feedback, or per-actuator commands
  via `SendActuatorsPosLog` (needs confidential geometry, bypasses the vendor checks).
- **Force plates cannot separate tilt from acceleration** (tilt shows as shear W·θ, about
  6 N for 0.5° on 700 N; a 0.15 g acceleration shows as about 105 N in the same channels).
  They are fine for static tilt with an inert load, not mid-move or with a person on them.
- **Plate inertial artefact:** the plates' own top mass produces forces during
  accelerations even when unloaded, so force and CoP during perturbations contain an
  artefact. Correct by subtracting unloaded recordings of each profile, or with an
  accelerometer. Together with true onset timing and frame tilt, this argues for a small
  IMU (gyro + accelerometer) on the top frame, logged on the Speedgoat. Raise with Ryan
  and Tyler: what transient tilt is acceptable for the paradigm?

## 2026-10-07: where we are, and the Ethernet checklist for tomorrow

### Done

- **Reachability measured on the M10 imitator** (`hexapod-envelope`, paused probe,
  nothing moves; 70 heights in 3 s). At home height surge reaches −306.2 / +272.7 mm and
  sway ±265.6 mm: matches the tech sheet to 0.5 mm, so the probe measures the real
  PS-6TL-350 kinematics. Widest surge: 638 mm at heave −30 (−336 / +302).
- **30 cm surge answer:** at home height centre the stroke, −167 → +133 mm (139 mm spare
  each end). It fits with ≥ 25 mm spare from heave −80 to +90. Spec-limited minimum time
  0.55 s; 0.83 s with our S-curve; first fast try ~1.2 s (`--rate 470 --max-speed 65535`).
- **Imitator speed tests** (`hexapod-dynamics`, refuses any controller except the M10):
  the M10 ignores `maxSpeed` and `accelerationProfile`, steps 300 mm in 0.37 s (~1.5 m/s,
  faster than the real platform can), tilts ~1° during instant steps. Windows sender
  stalls of 65–130 ms show up as lurches in fast streamed moves.
- **Report:** `uv run hexapod-reachability-report` → `output/reachability/hexapod-reachability.html`
  (3D M10 reach, mm height slider, side view, speed section, API table).
  The measurements behind it are committed in `rig/data/reachability/` (imitator sweep,
  speed tests; CSV gzipped), so the report rebuilds on any machine without the M10. Fresh
  measurements in `output/reachability/` take precedence.
- **Experiment FSM:** `rig/speedgoat/` (fsm_expt, cop_from_plates, pack_state, trial CSV,
  desktop test, wiring README) and host tools `hexapod-live` (live UDP plot) and
  `hexapod-expt-emulator`. Python mirror tested end to end (1–2 kHz, no lost packets).
  MATLAB files not yet run (no MATLAB on the dev laptop).
- **Robot connection:** USB with `--serial any` failed (ConnectToUsbDevice, error 3).
  ForceSeatPM shows the controller at **10.1.1.75**. Host "Ethernet" adapter is
  192.168.7.2/24 (probably the Speedgoat link) and we added 10.1.1.10/24 to it. Ping to
  10.1.1.75 fails and `--ip 10.1.1.75` has **not** connected yet. Ethernet 2 and 3 are
  unplugged.

### Tomorrow at the lab: get the controller connection working

Prep: `git pull`, `uv sync`, `$env:FORCESEATDI_LIBRARY = "...\ForceSeatDI64.dll"` (the file,
not its folder). Administrator PowerShell. Write down every result below.

1. **Trace the cables.** Which PC port goes to the Speedgoat, which to the hexapod
   cabinet (or a switch)? Is there also a USB cable from the cabinet to the PC?
2. **How does ForceSeatPM connect?** With ForceSeatPM open and showing the platform
   connected:
   ```powershell
   arp -a | Select-String "10.1.1.75"
   Find-NetRoute -RemoteIPAddress 10.1.1.75 | Select-Object InterfaceAlias, IPAddress
   Get-NetTCPConnection -OwningProcess (Get-Process ForceSeatPM).Id -ErrorAction SilentlyContinue | Format-Table RemoteAddress, RemotePort, State
   Get-NetUDPEndpoint -OwningProcess (Get-Process ForceSeatPM).Id -ErrorAction SilentlyContinue | Format-Table LocalAddress, LocalPort
   Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match 'VID_0483' }
   ```
   Also screenshot ForceSeatPM → Tools and Diagnostic → Devices (USB or network?).
   - 10.1.1.75 in `arp` with a real MAC → ForceSeatPM uses Ethernet; go to step 3.
   - Not in `arp` but a `VID_0483` device present → ForceSeatPM uses USB; close
     ForceSeatPM (tray icon too) and try `--serial any` (step 5).
3. **Give the controller its own port (recommended).** If the cabinet cable is on the
   Speedgoat's port or a switch, move it to Ethernet 2, then:
   ```powershell
   Remove-NetIPAddress -InterfaceAlias "Ethernet" -IPAddress 10.1.1.10 -Confirm:$false
   New-NetIPAddress -InterfaceAlias "Ethernet 2" -IPAddress 10.1.1.10 -PrefixLength 24
   ```
4. **Firewall.** ForceSeatPM gets through because its installer added firewall rules;
   uv's Python has none, and the new network is probably classed "Public".
   ```powershell
   Get-NetConnectionProfile | Format-Table InterfaceAlias, NetworkCategory
   Get-NetFirewallApplicationFilter | Where-Object Program -like "*ForceSeat*" | Format-List Program
   $py = (uv run python -c "import sys; print(sys._base_executable)")
   New-NetFirewallRule -DisplayName "ForceSeatDI (uv python)" -Direction Inbound -Program $py -Action Allow -Profile Any
   ```
   If that is not enough, a one-minute test with the Public profile firewall off tells
   us whether the firewall is the cause at all (turn it straight back on; check this is
   allowed on the lab PC):
   ```powershell
   Set-NetFirewallProfile -Profile Public -Enabled False   # test only
   # run step 5
   Set-NetFirewallProfile -Profile Public -Enabled True
   ```
5. **Connect (ForceSeatPM fully closed).** Nothing moves past the path check unless it
   connects; this run is +10 mm surge only.
   ```powershell
   uv run hexapod-park-test --hardware --run-byte 0 --ip 10.1.1.75 --sequence "surge:+10,home" --output output/first
   uv run hexapod-park-test --hardware --run-byte 0 --serial any --sequence "surge:+10,home" --output output/first
   ```
   Record the last line: `Connected to controller S/N ...`, or the exact
   `... failed; SDK error N`. Different error numbers mean different problems.
6. **Speedgoat address while we are at it:** `Test-Connection 192.168.7.5 -Count 2`, and in
   MATLAB `tg = slrealtime; tg.TargetSettings`.

### Once connected

1. Note the controller serial and the working transport (`--ip` or `--serial`) in README.
2. Robot reach, no motion: `uv run hexapod-envelope --ip 10.1.1.75 --heave-step 5 --output output/reachability/robot.json`,
   then `uv run hexapod-reachability-report`: the robot appears as a third 3D view.
3. Slow motion check: `hexapod-park-test` default ±250 mm sequence at 10 mm/s, area clear,
   E-stop in hand. Then the 300 mm stroke at increasing `--rate` (100 → 235 → 340 → 470),
   checking each `hexapod-report` for lag, overshoot and lurches.
4. Undo the firewall test if used; remove the 10.1.1.10 address from whichever adapter
   does not need it.

### Open items

- Force-plate make, channel order and calibration (for `cop_from_plates.m`).
- Host heartbeat into the Speedgoat (`host_ok`), and the host relay that forwards the FSM
  setpoint to the hexapod and sends back the reported pose.
- The vendor Simulink blocks never call a connect function: check whether they can reach
  an Ethernet controller at all before relying on them.
