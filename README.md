# Repo layout

| Path | Whose | Contents |
| --- | --- | --- |
| `rig/` | ours | Everything we write. `rig/uofc_hexa/`: the Python package (`uofc_hexa.hexapod`: `level_move`, `test_from_park`, `report`; `uofc_hexa.vendor`: finds the SDK bindings). `rig/hexapod_simulink/`: the same waypoint sequence on the vendor Simulink blocks. The Option E code (PLAN.md) goes here too. |
| `code/`, `examples/`, `plugins/`, `readme.txt` | Motion Systems | ForceSeatDI SDK as shipped: the API headers and bindings (`code/`), vendor examples, Simulink/Unity/Unreal plugins. Kept unmodified, so a newer SDK can be copied over it. |
| `docs/` | Motion Systems PDFs, our index | Unmodified vendor manuals and the PS-6TL-350 tech sheet; `docs/README.md` and `sources.json` are our notes on them (sources, revisions, hashes, useful pages). |

The vendor DLL/.so files are not in the repo; copy them from the SDK
(`ForceSeatDI64.dll` on Windows, `ForceSeatDI64.LinuxPC.so` on Linux).

Progress and the next lab steps: LABLOG.md.

License: proprietary, all rights reserved (see LICENSE). The MotionSystems
SDK and manuals are excluded and remain under MotionSystems' own terms.

## Running our Python tools

One uv project at the repo root (`pyproject.toml`, `uv.lock`). Install name
`uofc-hexa`, import name `uofc_hexa` (source in `rig/uofc_hexa/`).
`uofc_hexa/vendor.py` finds the vendor's Python bindings: in this repo it
reads them from `code/`; an installed wheel carries its own copy of the two
binding files. The native DLL/.so is never bundled.

```
git clone git@github.com:jeremydwong/hexapod-uofc.git && cd hexapod-uofc
uv sync                                   # exact versions from uv.lock
$env:FORCESEATDI_LIBRARY = "C:\path\to\ForceSeatDI64.dll"   # PowerShell; or pass --library each time
uv run hexapod-park-test --hardware --run-byte 0 --output output/sequence
uv run hexapod-report --output output/sequence
uv run hexapod-move --help                # single-axis level move
uv run hexapod-envelope --report          # reachable sway x surge area per height (paused probe, no motion)
uv run hexapod-envelope --synthetic --report   # same report from schematic test geometry, no device
```

`hexapod-envelope` writes `output/envelope.json` and, with `--report`,
`output/surge-range-of-motion.html`. Synthetic runs write
`envelope_synthetic.json` / `surge-range-of-motion_synthetic.html` and are
watermarked, so they cannot be mistaken for measured limits.

The commands work from any folder inside the repo; `--output` (default
`output`) is relative to where you run them, and `/output/` at the repo root
is gitignored.

From another repo: `uv add --editable ../hexapod-uofc` (checkout on the same
machine; edits show up immediately) or
`uv add "uofc-hexa @ git+ssh://git@github.com/jeremydwong/hexapod-uofc.git"`
(installs a copy; pin a tag or commit with `@<ref>`). Then
`from uofc_hexa.hexapod import level_move`.

Close ForceSeatPM (and any
Simulink model using the ForceSeatDI blocks) first: only one program can
hold the device. `--serial` defaults to the M10 imitator; pass the platform
controller's serial (or use `hexapod-move --ip`) for the real platform.

# Architecture notes (Jeremy, 2026-09-23)

## Proposed wiring and communication (per Ryan/Tyler emails below)

```
                    ┌───────────────────────────┐
                    │  Python GUI (any PC)       │  experiment config: trial list,
                    │  "master"                  │  randomization, profiles, channel toggles
                    └─────────────┬─────────────┘
                                  │ TCP/UDP or Simulink Real-Time API (config + start/stop)
                                  ▼
 force plates ──12 AI──►┌───────────────────────────┐
 EMG ─────────── AI ───►│  Speedgoat (real-time)     │  1 kHz fixed step, hard deadlines
 platform sync ─ AI ───►│  - sample all AI channels  │
                        │  - CoP position/velocity   │
 EVS stimulator ◄─ AO ──│  - trigger logic + jitter  │
                        │  - AO stimulator waveform  │
                        │  - log per-trial data      │
                        └─────────────┬─────────────┘
                                      │ UDP packet: "perturb: axis, profile, amplitude, t0"
                                      ▼
                        ┌───────────────────────────┐
                        │  Hexapod host (Linux/Win)   │  any ForceSeatDI binding: C/C++,
                        │  "slave"                    │  Python, C#, or the Simulink blocks
                        │  - receive UDP command       │  (Simulink blocks: Windows only)
                        │  - generate pose trajectory  │
                        │  - SendTopTablePosPhy @10 ms │
                        └─────────────┬─────────────┘
                                      │ USB or Ethernet — ForceSeatDI64.dll / ForceSeatDI64.so
                                      ▼
                        ┌───────────────────────────┐
                        │  PS-6TL-350 controller      │  inverse kinematics, ramps,
                        │  (in the platform)          │  actuator servo loops
                        └─────────────┬─────────────┘
                                      │ 6 actuators
                                      ▼
                                  top frame  ──►  participant on force plates
```

The hexapod cannot hang off the Speedgoat directly: ForceSeatDI ships only
for Windows x64 (`ForceSeatDI64.dll`), Linux x64 (`ForceSeatDI64.LinuxPC.so`;
the C loader expects it renamed to `./ForceSeatDI64.so`) and Raspberry Pi
(`ForceSeatDI64.RSPi_4_*.so`). That is the only reason the hexapod host exists
in the chain. The host does not have to be Windows or Simulink: the same API
is callable from C/C++, Python (rig/uofc_hexa) or C#, and only the
vendor's Simulink blocks are Windows-only. "Host" here means the machine that
drives the hexapod; if a Speedgoat is used, the separate Simulink Real-Time
development computer that builds and deploys models to it is Windows, but it
does not need to be in the real-time path.

## Trigger-to-motion latency, Option A as proposed (estimates, nothing measured yet)

This is for the chain drawn above with a Windows host running Simulink. See
Option E below for the tighter Linux design.

| Hop | Typical | Jitter | Basis |
| --- | --- | --- | --- |
| CoP condition met → Speedgoat detects | ≤1 ms | ~0 | one 1 kHz step |
| Speedgoat → host, UDP on a direct LAN cable | 0.1–1 ms | <1 ms | normal for a dedicated link |
| Host Simulink picks up the packet | 0–10 ms | ~10 ms | depends on model step; vendor examples run at 10 ms |
| Windows scheduling on top of that | 1–5 ms | up to 15 ms | not real-time; worst case when the OS is busy |
| SDK call → controller receives command | 1–2 ms USB, ~1 ms Ethernet | ~1 ms | USB HID polling interval |
| Controller ramp → first measurable motion | 10–30 ms | small, deterministic | acceleration profile; 0.66 g max means ~17 ms to 1 mm |
| **Total trigger → motion** | **~20–50 ms** | **~10–20 ms** | dominated by the host PC hops |

Consequences:

1. The Speedgoat will not know when the platform actually moved. It must
   record a ground-truth onset signal: an accelerometer on the top frame, or a
   digital sync line, sampled as one more channel. Relaying the SDK's
   reported pose back over UDP is second best (it carries the same jitter).
2. The command itself should be stamped with a Speedgoat timestamp so the
   per-trial file can record intended vs actual onset.
3. The host step size should be as small as the vendor library tolerates
   (10 ms is proven by their own examples; 5 ms is used in their Python demo).
4. Measured 2026-09-29 on this Windows laptop (Python 100 Hz loop, M10 over
   USB): mean period 10.2 ms, but a 110–156 ms stall every 5–15 s, and all
   gaps quantised to the 15.6 ms Windows timer tick. The platform held its
   last setpoint through each stall. Windows is fine for testing, not for
   time-locked perturbation onset.

## Do we need Speedgoat at all?

Not strictly. What the experiment actually needs is (a) deterministic
sampling of ~14+ analog inputs and one analog output, (b) a trigger decision
inside a few ms, (c) time-locked per-trial recording, and (d) hexapod
commands. Two ways to get that:

**Option A, as proposed: Speedgoat + Windows Simulink host.** Two computers, one UDP
hop, Simulink everywhere. Pros: hard real-time I/O with vendor-supported DAQ
modules; the lab's own staff can maintain Simulink models after the contract;
if the lab already owns the Speedgoat and I/O modules this costs nothing
extra. Cons: the extra hop and the Windows host add ~10–20 ms jitter to
perturbation onset; two machines to configure; MATLAB/Simulink Real-Time
licences.

**Option B: one Linux PC in C (or Python + C).** ForceSeatDI ships a Linux
x64 build, so a single box with a PREEMPT_RT kernel and a DAQ card (e.g. NI,
MCC, or a Comedi-supported board) could sample the plates, compute CoP,
decide to trigger, and call SendTopTablePosPhy in the same process. Pros:
removes the UDP hop and the Windows jitter entirely; one machine; no
MATLAB licence in the loop; we already have working DI code. Cons: someone
writes and maintains a real-time C application and DAQ driver integration;
the lab loses the Simulink workflow they asked for; DAQ vendor Linux driver
support varies; the vendor notes ForceSeatDI on Linux wants root for USB
(connecting over Ethernet avoids that).

**Option C: Windows host does everything, no Speedgoat.** A Windows DAQ
card sampled from the same process that drives the hexapod. Simplest, but
Windows cannot guarantee sample timing, so EMG/force-plate recordings would
have jitter in the ms range and the trigger loop is at the mercy of the
scheduler. Acceptable for pilot work, not for the time-locked recordings
Ryan describes.

**Option D: Speedgoat speaks the controller's Ethernet protocol directly.**
The controller accepts network connections (ConnectToNetworkDevice), so in
principle the Speedgoat could send packets itself and the hexapod host would
disappear along with its jitter. Blockers: the protocol is proprietary and
undocumented, and the DI library does more than framing. The Linux readme
says the library computes the work envelope on the PC, so inverse
kinematics and reachability checking almost certainly live in the DLL, not
the controller. Going this route means hand-rolling IK (needs NDA joint
geometry), envelope checks, keepalive/timeout semantics, handshake and
licence checks, and tracking protocol changes across firmware versions.
Firmware-side safeties (actuator stops, servo limits, thermal, E-stop, park)
would remain. Worth one question to the vendor ("is the network protocol
available under NDA for a real-time target?"); do not plan around it.

**Option E (proposed, tightest): Linux RT is the controller; Speedgoat is
only I/O and the logger.** The decision loop moves off the Speedgoat onto a
PREEMPT_RT Linux box, which commands the hexapod directly and reports the
hexapod's state back to the Speedgoat so the log carries it.

```
                  ┌────────────────────────┐
                  │  Python GUI (any PC)    │  config, trial list, start/stop
                  └───────────┬────────────┘  (TCP, not in the real-time path)
                              ▼
┌──────────────────────┐  UDP 1 kHz, NIC 1   ┌─────────────────────────────┐
│ Speedgoat: I/O+logger │ ──────────────────► │ Linux PREEMPT_RT "brain"      │
│ - sample force/EMG AI │  sample idx + force │ - CoP position/velocity       │
│   on its own clock    │                     │ - trigger state machine       │
│ - AO: EVS waveform    │ ◄────────────────── │   (conditions, jitter,        │
│   generated locally   │  echo sample idx,   │    randomisation, catch)      │
│ - logs everything,    │  events, commanded  │ - profile generator           │
│   one master clock    │  + SDK-reported     │ - ForceSeatDI64.so            │
│ - AI: accelerometer   │  pose, stim on/off  └──────────────┬──────────────┘
│   on top frame        │                                    │ Ethernet, NIC 2
└──────────▲───────────┘                                    ▼  (no root needed)
           │ accelerometer (ground-truth onset)   ┌─────────────────────────┐
           └──────────────────────────────────────│ PS-6TL-350 controller    │
                                                  └─────────────────────────┘
```

Loop design:

1. **The Speedgoat clocks the loop.** It sends one small UDP packet per
   1 kHz step: sample index plus the 12 force-plate channels (EMG is only
   logged, not streamed). The Linux control thread blocks on that socket, so
   its loop is paced by Speedgoat samples, not a second clock. If packets stop
   for more than a few ms, a watchdog holds the platform and pauses.
2. **The Linux control thread** (SCHED_FIFO, pinned to an isolated core)
   computes CoP and its velocity, runs the trigger state machine and profile
   generator, and writes the latest setpoint to shared memory. It never calls
   the SDK itself, so a slow SDK call cannot delay the decision.
3. **The Linux hexapod thread** (second isolated core) sends setpoints with
   `SendTopTablePosPhy` at the fastest rate the controller accepts (10 ms is
   proven, 5 ms is in vendor demos; measure 1–2 ms). On a trigger it is woken
   immediately (eventfd), so the first command goes out within about a
   millisecond instead of waiting for the next tick. It reads back the SDK
   pose and platform state each cycle.
4. **Everything is reported back to the Speedgoat.** Each Linux → Speedgoat
   packet echoes the sample index it is responding to and carries events
   (trigger fired, profile id, catch trial), the commanded and SDK-reported
   pose, and the platform state bits. The Speedgoat logs these next to its
   analog data on one clock, so every trial file has samples, decision,
   command and reported motion aligned. The top-frame accelerometer on a
   Speedgoat AI channel gives the true onset, independent of every software
   hop.
5. **The EVS stimulator waveform is generated on the Speedgoat**
   (deterministic AO). Linux only sends start/stop and a seed, so the
   stimulus stays sample-exact.

Linux RT setup: mainline kernel ≥ 6.12 with `PREEMPT_RT` (in mainline
since 6.12); `isolcpus`/`nohz_full`/`rcu_nocbs` for the two real-time cores;
`mlockall`; `SCHED_FIFO`; performance CPU governor and `cpu_dma_latency` = 0
(no deep C-states); two NICs on direct cables (Speedgoat, hexapod) with their
interrupts pinned to the real-time cores; busy-polling receive on the
Speedgoat socket. Written in C++; the Python GUI talks to it over TCP and is
never in the loop.

Trigger-to-motion budget for Option E (estimates, to be measured):

| Hop | Typical | Jitter |
| --- | --- | --- |
| CoP condition in the samples → Speedgoat sends packet | ≤1 ms | ~0 |
| UDP to Linux, direct cable, busy poll | 0.05–0.2 ms | <0.1 ms |
| CoP + decision on Linux | <0.05 ms | ~0 |
| Wake hexapod thread + SDK call → controller (Ethernet) | ~1 ms | ~1 ms |
| Controller ramp → first measurable motion | 10–30 ms | small |
| **Total** | **~12–33 ms** | **~1–2 ms** |

Compared with Option A, jitter drops from ~10–20 ms to ~1–2 ms. What is left
is the platform itself: the controller's ramp dominates the latency, and how
often it accepts a new setpoint sets the jitter floor. Neither can be tuned
from our side, so measure them first. With the M10 on hand, still before the
platform: SDK call duration distribution over Ethernet and USB on Linux, and
the fastest setpoint rate the controller accepts. On the platform: trigger →
accelerometer onset over a few hundred trials.

Note that Option E is Option B with the Speedgoat as the DAQ. If the lab
later drops the Speedgoat, a hardware-timed DAQ card on the Linux box
replaces it and the control code does not change.

Recommendation: Option E if the lab keeps the Speedgoat, Option B if it does
not. The file-by-file build plan for Option E is in PLAN.md. Either way the real-time logic is plain C++ in git, the Simulink side is
a thin I/O-and-logging model, and the lab keeps its MATLAB data files.
Before committing, still ask (1) whether the Speedgoat and its I/O modules
are already bought, and (2) who maintains the system after the contract. If
the maintainers only work in Simulink, Option A with the onset-sync channel
(point 1 of the latency notes) is the fallback. The hexapod-side work in
rig/uofc_hexa and the API notes carry over to all of these.

## Hardware on hand

PS-6TL-350 platform (rating label, photo in hexapodserial.jpg):

| Field | Value |
| --- | --- |
| Model / revision | PS-6TL-350, Rev 1.4.2 |
| Serial number | 249B-B66E0BF594 |
| Manufacture date | 2024-10-28 |

M10 Motion Imitator:

| Field | Value |
| --- | --- |
| USB ID / name | `0483:A110`, enumerates as `ForceSeatMP1` |
| Controller S/N (ForceSeatPM Devices window; also reported by USB and ForceSeatDI) | 5f0051-000150-344335-353720 |

Read-only SDK probe on 2026-09-24 (ForceSeatDI64.dll, USB): connection OK, no
module errors, referenced, not paused, soft-parked (state `0x52`), heave
-165.65 mm, and `GetLicenseStatus` false. The ForceSeatDI license lives on the
device and is activated once through ForceSeatPM: Tools and Diagnostic →
Devices → Quick Codes, then power-cycle and check Features shows FSDI
(docs/ForceSeatDI-manual.pdf, section 2).

2026-09-29: after entering the M10 quick codes below, `GetLicenseStatus`
returns true. Park-to-park surge and sway tests ran on the M10
(`uv run hexapod-park-test`, `hexapod-report`). ForceSeatPM must be
closed while the SDK is connected; it holds the USB device and the connect
call fails.

---

# SOP: Tyler 2026-09-15 13:30
Hi Jeremy,

Yes, and we'd like to have a library of standardized blocks for position control (displacement, ramp up and down time, etc.) and velocity control. I would like step, linear and sigmoidal profiles, all configurable from the GUI. 

I'd also like the flexibility to randomize different perturbation conditions within the overall experiment - fully randomized, pseudo/block randomized, and catch trials. Finally, some random component on the perturbation timing once they've met the CoP position and velocity conditions to apply the perturbation. I think the human in the loop approach will be important for managing response variability. 

Last, I would like configurable analog recordings - a list of accessible channels with a toggle button to record or not. 

In the long run, I would also like some visual stimuli that we can integrate, but let's get the platform going. 

# SOP: Ryan 2026-09-15 12:30

Hi Jeremy,

Yes, those items would be the first things to tackle here. A GUI (Python likely) that can be used to configure experiments, and some basic perturbations to start makes good sense. 

The way we think the controller should be setup is essentially Speedgoat realtime performing I/O (sampling the 12 force plate channels, EMG channels, etc, and outputting stimulator waveforms), calculating CoP, and triggering perturbations. Speedgoat will communicate via UDP to the host computer’s Simulink program which is receiving UDP commands and running the Motion Systems blocks. The Motion Systems blocks output and control the hexapod hardware. The Python GUI would essentially be used to configure/control the Speedgoat realtime level (master) and the host computer just does what it’s told (slave). I think this makes sense, and GPT agrees that this architecture will work for our purposes.

For example, the user configures an experiment on the Python GUI to run 10 surge perturbations, which are triggered after some fixed delay (plus some timing jitter), only when the CoP is near the centre of the plates and CoP velocity has fallen below some threshold (i.e., it triggers only when the participant is standing straight and relatively still). All analog input channels would be sampled around the time of triggering each perturbation and stored in separate data files/matlab data structures for each perturbation (like Kinarm). During some subset of perturbations, we can output a white noise signal that will drive an EVS stimulator to mess with vestibular sensory reliability. This is essentially all the functionality we’d need to have in place. 

Happy to discuss details further, but I think this gives you a good idea of what we’d be after. Time and money permitting we could look at other functionality such as implementing marker less motion capture with this setup, which is time-locked to the analog input recordings. Just a thought - there may be other things we think of later that we can extend the contract for.

Cheers,

Ryan


# Communication with Motion Systems

Hello.

    Regarding of the 3D models and signing NDA, please contact our Sales team trough the PRODUCT ENQUIRY form, following the link : https://qubicsystem.com/contact/

    Our software does not support MacOS, ForceSaetPM runs on Windows only. ForceSeatDI supports Windows and Linux (x64 + Raspberry), but it offers no simulation calculations.

    Could you, please elaborate what exactly you need from us exactly as your last sentence is not exactly unclear to us ?

Regards

## Activation codes and cabinet identifiers

Transcribed from `~/Downloads/code1.png` and `~/Downloads/code2.png`
(email thread “Platform arrived!”), 2026-09-24. Wrapped lines in the screenshots
are joined below; copy each code as one uninterrupted string.

The email labels the first code **SDK MI** (ForceSeatMI) and the second
**Motion Theater**. It does not explicitly label either as a ForceSeatPM
activation code. The cabinet license is recorded separately with its original
label. These have been transcribed, not tested for activation.

### M10 quick codes (serial 5F0051-000150-344335-353720)

Sent by Motion Systems by email for the M10 Motion Imitator. They were
entered via ForceSeatPM Quick Codes, and the M10 was reported working on
2026-09-29. Copy each code as one uninterrupted string.

SDK MI:

```text
c0e8d75cfa98016e37b73eaa41e83bc05dd0693b6e79fd6e528bbb5303fcbfc2590974fb6e2f00fb4f817556c39908c0eb3b5c5946fd27c90632ef83873a69f1aafd8fabc2a6d930f8283267dfdd1853cf6d5ceb0e02ef5c5de4a9d0ada62206201406d0b0df47e8
```

SDK DI:

```text
638ce3ae8ab9fa619fa0fa89264db9ecd4c6831c4f019840d58e4192
```

Motion Theater:

```text
689d51ca6d64085dbb864418b6b4e6af7fc2f54be678f8d09db0f4809c2a2303618e5493d10a6dd1615c9eb0faef4b58213f03aa5a3b263ca19f074bc6a98d3f2fcf7b04cbf8406acbb26e80346670e26af2d727d07871b55da35562d55be8f582bc3291b456cb32
```

### Power cabinet

- Serial number: `24A7-C7CE73286A`
- License number: `3A0034-001551-303338-353336`

### M10 delivery note

The second screenshot says an M10 had been purchased but was missing from the
crate. Motion Systems replied that it should have been included and would be
shipped immediately. This confirms the purchase and promised shipment, not
subsequent delivery or a local installation.

### OLD DOES NOT WORK SDK MI activation code

```text
7dc8b6297f1bafe6f83cd4e0b6290154cba6db65f7b9eaeed58e4192
```

### OLD DOES NOT WORK Motion Theater activation code

```text
8e7f37a60268692f663a33f467b81e8125e0df977b045beeb792ceac3126802d5b6c7eaf6c16ce8f598060a1c230c35125fd712e313bffe06c28bb8be52ba7ad0566413255e167990c68062d1f28a89e909edbf2219d08cfcdace6bcb07117c5a257d8496d43f96f
```
