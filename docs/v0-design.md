# V0 design

**Goal of V0: prove the mechanics, and nothing else.**

`mouse click in a video frame → turret turns → water fires at that point`

No detection model, no autonomy, no night operation. A human is the detector. If this
does not work reliably, nothing built on top of it will.

V0 is finished when: **someone can click a spot in the frame and the water lands there,
repeatably, for an hour, without the valve ever sticking open.**

---

## Why a human is the detector first

The riskiest parts of this project are mechanical and geometric, not perceptual:

- Does the servo actually hold position against the hose's torque?
- Does the water land where the geometry says it should?
- Does the valve close every single time?

A detection model would obscure all of these — a miss could be bad aiming, bad
calibration, bad timing, or bad classification, and you would not know which. Removing
the model removes three of the four.

---

## Scope

**In**

- Serial link between host and ESP32
- Servo pan, mechanically limited
- Solenoid valve open/close with a hard duration cap
- Pixel → angle mapping (pinhole)
- Empirical calibration procedure
- Click-to-fire UI over a live camera frame
- Event log
- Safety: limits, cooldown, watchdog, fail-closed

**Out**

- Detection, tracking, classification
- Tilt (pan only)
- Night operation and IR
- Wireless, battery, solar
- Any autonomous firing

---

## Component layout

```
┌───────────── Host (indoor computer) ─────────────┐
│                                                   │
│  camera (RTSP) ──► frame ──► UI: click to fire     │
│                                  │                 │
│                          calibration               │
│                          pixel_x → angle           │
│                                  │                 │
│                          controller                │
│                    (limits, cooldown, rate cap)    │
│                                  │                 │
│                          event log (JSONL)         │
└──────────────────────────────────┼─────────────────┘
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
duplicates the other's job.

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

The camera is fixed. Its field of view is the entire sensed area, so **turret sweep must
equal camera FOV** — larger is coverage that can never produce a detection, smaller means
visible targets that cannot be reached.

Pixel offset is proportional to `tan θ`, so:

```
x_norm = (x_px − W/2) / (W/2)
θ      = centre + sign · degrees( atan( x_norm · tan( hfov/2 ) ) )
```

**Not linear interpolation.** At 70° FOV the difference at half-frame is ~1.8°, and it
grows with wider lenses. Linear mapping under-shoots everything between the centre and
the edge.

`sign` handles a servo that turns opposite to the image.

### Calibration procedure

Do not trust the datasheet. It cannot know how crookedly the rig is mounted or where the
servo's mechanical zero actually is.

1. Place a visible target in the scene
2. Click it in the frame → note `pixel_x`
3. Nudge the angle until the water hits it → note `true_angle`
4. Repeat at 3–5 positions spread across the frame
5. Solve for `centre`, `hfov` and `sign` by least squares

For fixed `hfov` and `sign`, the best `centre` is just the mean residual — so the search
is one-dimensional over `hfov` plus two cases of `sign`. Exact, fast, no dependencies.

**Store the result in a config file.** Recalibrate whenever the rig is physically moved.

---

## Safety

Two independent layers, both defaulting to *water off*. Full rationale in `SAFETY.md`.

| Layer | Guarantees |
|---|---|
| **Firmware** | angle clamped to mechanical limits · spray duration capped · **watchdog closes the valve if the host goes quiet** · valve closed on boot · non-blocking valve timing so a stuck loop cannot hold it open |
| **Host** | minimum cooldown between shots · hourly shot cap · `STOP` on every exit path including exceptions |

The valve is **normally closed**: no power, no water. A cut cable, a dead board, a
crashed host and a pulled plug all end the same way.

V0 fires only on a human click, so the *never fire at humans* rule is not yet needed —
but the controller is where it will live, and nothing in V0 should make that awkward.

---

## Event log

JSONL, one file per night, flushed and `fsync`ed on every write. A power cut at 3am must
not lose the evening.

Even in V0 — where a human aims — the log records `fire` events with angle, duration,
source and target pixel. That establishes the schema and the discipline before the
experiment that depends on it.

```json
{"ts":…, "iso":…, "session":…, "event":"fire",
 "angle_deg":67.5, "spray_ms":1500, "source":"click", "target_x_px":812}
```

Later events — `detection`, `flee`, with the three experimental metrics — extend the same
file. The schema grows; it does not change shape.

---

## Testable without hardware

Every part above except the servo and the valve can be exercised with a mock device that
accepts the same protocol and simulates servo travel time. Geometry and safety logic are
pure functions and pure state machines — both deserve tests, and both are where a silent
error is most expensive:

- Calibration wrong → *"it aims left but sprays right"*
- Safety wrong → *the valve stays open*

---

## Definition of done

- [ ] `PING` round-trips over real serial
- [ ] Servo reaches both mechanical limits and holds against hose torque
- [ ] Valve opens and closes; **never observed stuck open**
- [ ] Watchdog closes the valve when the host is killed mid-spray
- [ ] Calibration solved from measured points; water lands within a jet-width of a
      clicked target across the frame
- [ ] One hour of clicking with no missed close and no drift
- [ ] Events logged and readable

Only then: point the camera at the garden overnight and start collecting IR footage.
