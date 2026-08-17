# V0 design

**Goal of V0: prove the mechanics, and nothing else.**

`mouse click in a video frame → turret turns → water fires at that point`

No detection model, no autonomy, no night operation. A human is the detector. If this
does not work reliably, nothing built on top of it will.

V0 is finished when **someone can click a spot in the frame and the water lands there,
repeatably, for an hour, without the valve ever sticking open.**

---

## Why a human is the detector first

The riskiest parts of this project are mechanical and geometric, not perceptual:

- Does the servo hold position against the hose's torque?
- Does the water land where the geometry says it should?
- Does the valve close every single time?

A detection model would obscure all of these — a miss could be bad aiming, bad
calibration, bad timing, or bad classification, and you would not know which. Removing
the model removes three of the four.

## Scope

**In:** serial link · servo pan with mechanical limits · valve open/close with a hard
duration cap · pixel → angle mapping · empirical calibration · click-to-fire UI over a
live frame · event log · safety (limits, cooldown, watchdog, fail-closed)

**Out:** detection, tracking, classification · tilt · night operation and IR · wireless,
battery, solar · any autonomous firing

---

## Architecture

```
Camera (fixed, does not rotate)
     │ RTSP
     ▼
┌───────────── Host (indoor computer) ─────────────┐
│  frame ──► UI: click to fire                      │
│                    │                              │
│            calibration: pixel_x → angle           │
│                    │                              │
│            controller (limits, cooldown, rate cap)│
│                    │                              │
│            event log (JSONL)                      │
└────────────────────┼──────────────────────────────┘
                     │ serial, ASCII
       ┌─────────────▼──────────────┐
       │           ESP32             │
       │  · clamp angle              │
       │  · cap spray duration       │
       │  · watchdog → close valve   │
       │  · valve closed on boot     │
       └───┬────────────────────┬────┘
           │                    │
        servo            relay ──► 12V NC valve
```

The host decides *what*. The firmware decides *whether it is safe* and does it. Neither
duplicates the other's job — the host sends exactly two numbers, an angle and a duration.

**Build order:** get the mouse-click path working before swapping in detected
coordinates, so the riskiest part is proven first.

---

## Wire protocol

Line-based ASCII over USB serial, 115200 baud. Deliberately human-readable: when the rig
misbehaves you can open a serial terminal and drive it by hand, with no tooling.

| Host → device | Device → host |
|---|---|
| `PING` | `PONG <fw_version>` |
| `AIM <angle>` | `OK AIM <angle>` |
| `SPRAY <ms>` | `OK SPRAY <ms>` |
| `FIRE <angle> <ms>` | `OK FIRE <angle> <ms>` |
| `STOP` | `OK STOP` |
| `STATUS` | `STATUS angle=<f> spraying=<0\|1> uptime_ms=<i>` |
| — | `ERR <reason>` |

`FIRE` turns first, waits for the servo to settle, then opens the valve. The order is not
negotiable: spraying while turning paints an arc across whatever is in between.

---

## Geometry

The camera is fixed, so **its field of view is the entire sensed area**. Therefore:

> **Turret sweep must equal camera FOV.**

| | Consequence |
|---|---|
| Sweep **>** FOV | Angles that can never produce a detection — **phantom coverage** |
| Sweep **<** FOV | Targets visible at the frame edges **cannot be reached** |

The RLC-520A is 80° horizontal, so the sweep is fixed: **±40° about the centre line.**

80° is a datasheet figure, and the next section is about why those are not trusted. Size
the *mechanics* with it — bracket travel, hose slack, where the servo's centre has to sit
— and nothing else. Two separate limits come out of the build, and conflating them is a
safety bug:

| Limit | Lives in | Comes from |
|---|---|---|
| **Mechanical** | firmware | the physical stops — measured bracket travel and hose slack |
| **Reachable image** | host | `centre ± hfov/2`, from calibration |

The firmware clamp is a property of the rig, not of the camera, so calibration must never
feed it. A crooked mount can calibrate to `centre = 10°, hfov = 80°` — reachable −30°..50°,
which on one side is past where the bracket lets the servo go. Deriving the firmware limit
from that would let a host aiming at something genuinely in frame drive the servo into its
own stop. The firmware clamps to the stops, the host declines to aim outside the frame,
and neither number is computed from the other.

Pixel offset is proportional to `tan θ`, so:

```
x_norm = (x_px − W/2) / (W/2)
θ      = centre + sign · degrees( atan( x_norm · tan( hfov/2 ) ) )
```

**Not linear interpolation.** At 70° FOV the difference at half-frame is ~1.8°, and it
grows with wider lenses. A linear map systematically under-shoots everything between the
centre and the edge. `sign` handles a servo that turns opposite to the image.

### Parallax: mount the camera against the turret

Calibration assumes camera and turret share an axis. With offset `d` and target distance
`L`, the pointing error is roughly `atan(d/L)`:

| Offset | 1 m | 3 m | 5 m |
|---|---|---|---|
| 20 cm | 11° ⚠️ | 3.8° | 2.3° |
| 50 cm | 27° ❌ | 9.5° ⚠️ | 5.7° |

**Keep it under 20 cm, ideally directly above the axis of rotation.**

### Calibration is measured, not configured

Quoted fields of view are optimistic, lenses distort, and — most importantly — a
datasheet cannot know how crookedly you mounted things or where the servo's mechanical
zero actually points.

1. Place a visible target in the scene
2. Click it in the frame → note `pixel_x`
3. Nudge the angle until the water hits it → note `true_angle`
4. Repeat at 3–5 positions spread across the frame
5. Solve for `centre`, `hfov` and `sign` by least squares

For fixed `hfov` and `sign` the best `centre` is just the mean residual, so the search is
one-dimensional over `hfov` plus two cases of `sign`. Exact, fast, no dependencies.

Store the result in a config file. Recalibrate whenever the rig is physically moved.

---

## Hardware

| Part | Model | Price (AUD) |
|---|---|---|
| **Camera** | Reolink RLC-520A PoE 5MP — 80° H FOV, 850 nm IR to 30 m | **$99.99** |
| PoE injector | any | ~$25 |
| **Servo** | DFRobot 35 kg·cm waterproof 180° IP54 | **$36.55** |
| Servo horn | aluminium 25T round disc | $3.47 |
| **Bearing** | heavy-duty aluminium lazy susan | **$31** |
| **Solenoid valve** | 12V DC, normally closed, 3/4" BSP | ~$25–40 |
| Relay module | 12V, opto-isolated | ~$10 |
| ESP32 | any dev board | ~$15 |
| Servo supply | 6–7.4V, 3A+ BEC | ~$20 |
| 12V supply | for the valve | ~$15 |
| Nozzle | adjustable, set to jet | ~$15 |
| | | **~$300** |

Sydney suppliers: Core Electronics · Little Bird (Hornsby) · Jaycar (Hornsby) ·
RC Hobbyland (Castle Hill) · Ultimate Hobbies (Parramatta)

### Mechanics

```
sprinkler → rotating top → turntable bearing → 25T horn → 35 kg servo → fixed base
                              ↑ carries load                ↑ supplies torque only
```

**Do not let the servo output shaft carry the sprinkler's weight or the hose's pull.**
The lazy susan bearing takes the load; the servo drives through a horn or linkage.

Water path: fixed hose → **short flexible hose** → rotating head. A stiff garden hose
will twist the servo back. A proper water rotary union costs $50–200 — skip it for V0; a
flexible tail is fine over ±60°, comfortably more than the ±40° the camera's FOV asks for.

### Four mistakes that cost a rebuild

**1. The valve must be 12V DC, not 24V AC.** Most irrigation valves sold in hardware
stores are 24V AC — standard for sprinkler controllers, and not drivable from an ESP32
and a MOSFET.

**2. BSP threads, not NPT.** Australian garden fittings are BSP. The wrong thread means
the whole batch is useless.

**3. You need a flyback diode.** A solenoid is an inductor; the reverse spike when it
switches off will destroy a MOSFET and can take the microcontroller with it. This is the
most common way this kind of project dies overnight. Opto-isolated relay modules normally
include the protection.

**4. Never power the servo from the ESP32's regulator.** A 35 kg servo's stall current
will brown out the board. Separate 6–7.4V supply, common ground.

### Do not use a solar camera

Solar and battery cameras sleep to save power and only wake on their own PIR. That means
no continuous stream — which puts the PIR back in charge of what gets seen, and the PIR
is the thing this project exists to replace. **Wired power and continuous RTSP.**

The RLC-520A settles the IR question by having it built in: **850 nm, 30 m range.** The
alternative, 940 nm, is invisible to the eye but 30–50% less sensitive and dearer, and it
would mean a separate illuminator.

850 nm glows faintly red. Whether that glow itself deters the animals is an empirical
question the first week of recording answers — and if it does, that is the point to add a
940 nm illuminator, not before. Don't pay double for a problem you haven't observed.

---

## Safety

Two independent layers, both defaulting to *water off*. Full rationale in
[SAFETY.md](../SAFETY.md).

| Layer | Guarantees |
|---|---|
| **Firmware** | angle clamped to mechanical limits · spray duration capped · **watchdog closes the valve if the host goes quiet** · valve closed on boot · non-blocking valve timing, so a stuck loop cannot hold it open |
| **Host** | minimum cooldown between shots · hourly shot cap · `STOP` on every exit path including exceptions |

The valve is **normally closed**: no power, no water. A cut cable, a dead board, a crashed
host and a pulled plug all end the same way.

V0 fires only on a human click, so the *never fire at humans* rule is not yet needed — but
the controller is where it will live, and nothing in V0 should make that awkward.

---

## Event log

JSONL, one file per night, flushed and `fsync`ed on every write. A power cut at 3am must
not lose the evening.

Even in V0 — where a human aims — every shot is recorded. That establishes the schema and
the discipline before the experiment that depends on it.

```json
{"ts":…, "iso":…, "session":…, "event":"fire",
 "angle_deg":67.5, "spray_ms":1500, "source":"click", "target_x_px":812}
```

### What the log is actually for

The six-week habituation experiment rests on three numbers — detection accuracy is not
among them:

```
flight latency     seconds from spray to the animal leaving
approach distance  how close it got before being sprayed
return interval    how long until it comes back
```

Habituation shows up as: leaving more slowly, approaching more closely, returning sooner.
Alternate weeks of fixed versus randomised response to find out whether randomisation
helps at all.

Later events — `detection`, `flee` — extend the same file. The schema grows; it does not
change shape.

---

## Testable without hardware

Everything above except the servo and the valve can be exercised against a mock device
that speaks the same protocol and simulates servo travel time. Geometry and safety logic
are pure functions and pure state machines — both deserve tests, and both are where a
silent error is most expensive:

- Calibration wrong → *"it aims left but sprays right"*
- Safety wrong → *the valve stays open*

## Definition of done

- [ ] `PING` round-trips over real serial
- [ ] Servo reaches both mechanical limits and holds against hose torque
- [ ] Valve opens and closes; **never observed stuck open**
- [ ] Watchdog closes the valve when the host is killed mid-spray
- [ ] Calibration solved from measured points; water lands within a jet-width of a clicked
      target across the frame
- [ ] One hour of clicking with no missed close and no drift
- [ ] Events logged and readable

Only then: point the camera at the garden overnight and start collecting IR footage.
