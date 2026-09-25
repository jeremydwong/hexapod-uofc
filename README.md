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
                        │  Host PC (Windows)          │  Simulink, paced to wall clock
                        │  "slave"                    │  vendor ForceSeatDI blocks
                        │  - receive UDP command       │  (plugins/Matlab/Simulink)
                        │  - generate pose trajectory  │
                        │  - SendTopTablePosPhy @10 ms │
                        └─────────────┬─────────────┘
                                      │ USB (or Ethernet) — ForceSeatDI64.dll
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
for Windows/Linux x64 and Raspberry Pi, and the vendor states the Simulink
blocks are Windows-only. That is the only reason the host PC exists in the
chain.

## Trigger-to-motion latency (estimates, nothing measured yet)

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

## Do we need Speedgoat at all?

Not strictly. What the experiment actually needs is (a) deterministic
sampling of ~14+ analog inputs and one analog output, (b) a trigger decision
inside a few ms, (c) time-locked per-trial recording, and (d) hexapod
commands. Two ways to get that:

**Option A, as proposed: Speedgoat + Windows host.** Two computers, one UDP
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
support varies; the vendor notes ForceSeatDI on Linux wants root for USB.

**Option C: Windows host does everything, no Speedgoat.** A Windows DAQ
card sampled from the same process that drives the hexapod. Simplest, but
Windows cannot guarantee sample timing, so EMG/force-plate recordings would
have jitter in the ms range and the trigger loop is at the mercy of the
scheduler. Acceptable for pilot work, not for the time-locked recordings
Ryan describes.

**Option D: Speedgoat speaks the controller's Ethernet protocol directly.**
The controller accepts network connections (ConnectToNetworkDevice), so in
principle the Speedgoat could send packets itself and the Windows host would
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

Recommendation: ask the lab two questions before deciding. (1) Do they
already own the Speedgoat and its analog I/O modules? (2) Who maintains the
system after the contract, and do they work in Simulink? If both answers
point at Speedgoat, Option A is the right call and the onset-sync channel in
point 1 above fixes its main weakness. If they are buying hardware fresh and
are comfortable with a C codebase, Option B is cheaper and tighter. Either
way, the hexapod-side work in examples/LevelMove_Python and the API notes
carry over unchanged.

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

### SDK MI activation code

```text
7dc8b6297f1bafe6f83cd4e0b6290154cba6db65f7b9eaeed58e4192
```

### Motion Theater activation code

```text
8e7f37a60268692f663a33f467b81e8125e0df977b045beeb792ceac3126802d5b6c7eaf6c16ce8f598060a1c230c35125fd712e313bffe06c28bb8be52ba7ad0566413255e167990c68062d1f28a89e909edbf2219d08cfcdace6bcb07117c5a257d8496d43f96f
```

### Power cabinet

- Serial number: `24A7-C7CE73286A`
- License number: `3A0034-001551-303338-353336`

### M10 delivery note

The second screenshot says an M10 had been purchased but was missing from the
crate. Motion Systems replied that it should have been included and would be
shipped immediately. This confirms the purchase and promised shipment, not
subsequent delivery or a local installation.
