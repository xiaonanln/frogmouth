# frogmouth

> Named after the tawny frogmouth — an Australian nocturnal bird that sits motionless
> for hours with enormous eyes, indistinguishable from a branch, then strikes without warning.

A garden sentry that **looks before it acts**: a camera identifies an animal, a turret
turns towards it, and a jet of water sends it away.

Targets are small animals generally — possums, brush turkeys, cats, birds, rabbits.
Which ones matter depends on where you live; the mechanism is the same.

---

## This is not another motion-activated sprinkler

Existing motion sprinklers trigger on **PIR** (passive infrared). A PIR knows only that
*something warm moved*. It cannot tell a possum from a cat, from a delivery driver, from
sunlit foliage swaying in the wind.

The ratings tell the story. On Amazon AU this product category sits at **2.2 – 3.9 stars**,
and the negative reviews are overwhelmingly about false triggers: soaked pets, soaked
people, water wasted all night on a moving shadow.

**frogmouth demotes the PIR from decision-maker to wake-up call. Vision decides.**

| | Existing products | frogmouth |
|---|---|---|
| What decides to fire | PIR | **Vision model** |
| Spraying people and pets | common complaint | hard rule against it |
| Aiming | fixed arc | **aimed at the target** |
| Record of what happened | none | full event log |

---

## Status

**Design stage.** Hardware is not yet assembled. Code comes after calibration has been
measured on the real rig — see [Why calibration is measured, not configured](#calibration-is-measured-not-configured).

An early V0 skeleton was written and then removed: writing code before the hardware and
calibration approach were settled was the wrong order. It remains in git history.

---

## Architecture

```
Camera (fixed, does not rotate)
     │ RTSP
     ▼
Host: detection + decision
     │ angle + spray_ms
     ▼
   ESP32
     ├── servo → horizontal pan
     └── relay → 12V normally-closed solenoid valve
```

Direction and water are fully decoupled. The host sends two numbers — an angle and a
duration. The firmware executes them and enforces safety; it makes no decisions.

**Build order:** get `mouse click → angle → spray` working first, then replace the mouse
with detected coordinates. Mechanics and AI stay decoupled, and the riskiest part is
proven first.

---

## The fixed-camera constraint

The camera does not move, so **its field of view is the entire sensed area**. Therefore:

> **The turret's sweep must equal the camera's horizontal field of view.**

| | Consequence |
|---|---|
| Sweep **>** FOV | The extra angle can never produce a detection — **phantom coverage** |
| Sweep **<** FOV | Targets visible at the frame edges **cannot be reached** |

### Parallax: mount the camera against the turret

Calibration assumes the camera and turret share an axis. With offset `d` and target
distance `L`, the pointing error is roughly `atan(d/L)`:

| Offset | 1 m | 3 m | 5 m |
|---|---|---|---|
| 20 cm | 11° ⚠️ | 3.8° | 2.3° |
| 50 cm | 27° ❌ | 9.5° ⚠️ | 5.7° |

**Keep it under 20 cm, ideally directly above the axis of rotation.**

### Calibration is measured, not configured

Quoted fields of view are optimistic, lenses distort, and — most importantly — a
datasheet cannot know how crookedly you mounted things or where your servo's mechanical
zero actually points.

Measure it instead: click a target in frame, nudge the angle until the water hits it,
record `(pixel_x, true_angle)`. Repeat 3–5 times and solve for the mapping.

Pixel offset is proportional to `tan(θ)`, so the mapping is
`θ = atan(x_norm · tan(hfov/2))` — **not** linear interpolation. A linear map
systematically under-shoots targets in the middle of the frame.

---

## Hardware

| Part | Model | Price (AUD) |
|---|---|---|
| **Camera** | Reolink RLC-520A PoE 5MP | **$99.99** |
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
will twist the servo back. (A proper water rotary union costs $50–200 — skip it for V0;
a flexible tail is fine over ±60°.)

### Four mistakes that cost a rebuild

**1. The valve must be 12V DC, not 24V AC.** Most irrigation valves sold in hardware
stores are 24V AC — standard for sprinkler controllers, and not drivable from an ESP32
and a MOSFET.

**2. BSP threads, not NPT.** Australian garden fittings are BSP. The wrong thread means
the whole batch is useless.

**3. You need a flyback diode.** A solenoid is an inductor; the reverse spike when it
switches off will destroy a MOSFET and can take the microcontroller with it. This is the
most common way this kind of project dies overnight. Opto-isolated relay modules
normally include the protection.

**4. Never power the servo from the ESP32's regulator.** A 35 kg servo's stall current
will brown out the board. Use a separate 6–7.4V supply and a common ground.

### Do not use a solar camera

Solar and battery cameras sleep to save power and only wake on their own PIR. That means
no continuous stream — which puts the PIR back in charge of what gets seen, and the PIR
is the thing this project exists to replace. **Wired power and continuous RTSP.**

850 nm IR (faint visible red glow) vs 940 nm (invisible, 30–50% less sensitive, pricier):
**start with 850 nm.** Whether the glow deters the animals is an empirical question you
can answer in the first week. Don't pay double for a problem you haven't observed.

---

## Safety

Two independent layers, both defaulting to *water off*. See [SAFETY.md](SAFETY.md).

| Layer | Responsibilities |
|---|---|
| Firmware | angle limits, max spray duration, **watchdog that closes the valve if the host goes quiet**, valve closed on boot |
| Host | cooldown between shots, hourly cap, valve closed on every exit path |

**The error cost is asymmetric.** Missing an animal costs you some fruit. Hitting a
person is a different category of problem. The detector needs an explicit
*never fire at anything human-shaped* rule — a confidence threshold is not enough.

---

## The open question: habituation

Reviews of existing motion sprinklers repeat one complaint: **the animals stop caring
after a couple of weeks.**

Two mechanisms, with very different implications:

| Mechanism | What the animal learns | Fixed by aiming + randomisation? |
|---|---|---|
| Pattern learning | where the blind spots are, which angle the water can't reach, that walking slowly doesn't trigger it | ✅ yes |
| Harmlessness | getting wet is annoying, but **nothing bad actually happens** | ❌ no |

Water differs from scarecrows and ultrasonic devices in a way that matters: it imposes a
real cost every single time, rather than a one-off startle that fades. Wildlife
authorities generally rank motion-activated sprinklers as the most effective deterrent
for exactly this reason.

And the dominant complaint in the reviews is **false triggering**, not indifference —
which is why frogmouth targets false triggering first. Habituation is a lifetime metric,
not the core thesis.

### The six-week experiment

The metric that matters is not detection accuracy:

```
1. Flight latency     seconds from spray to the animal leaving
2. Approach distance   how close it got before being sprayed
3. Return interval     how long until it comes back
```

Habituation shows up as: leaving more slowly, approaching more closely, returning sooner.

**A/B:** alternate weeks of fixed versus randomised response, and find out whether
randomisation actually helps. No manufacturer has published an answer to this.

---

## Roadmap

- [ ] Buy the hardware
- [ ] Mount the camera and **record several nights first** — infrared footage is both the
      training data and the first video material
- [ ] V0: mouse click → angle → spray
- [ ] Measure calibration on the real rig
- [ ] Detection model + the *never fire at humans* rule
- [ ] Six-week habituation experiment

**Record before modelling.** The main targets are nocturnal, and separating a possum from
a cat in infrared — no colour, similar size — is much harder than separating a person
from a dog. Every choice about models and cameras is guesswork until real night footage
exists.

---

## License

MIT — see [LICENSE](LICENSE). This is a hobby project provided as-is; you are responsible
for what you build from it.
