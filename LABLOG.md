# Lab log

Newest entry first. What was done, what is known, what to try next.

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
