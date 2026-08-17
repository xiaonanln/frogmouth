# V0 design

**Goal of V0: the whole loop, working by itself.**

`camera sees an animal → host classifies it and computes the angle → turret turns → water fires`

V0 is finished when **the rig does that unaided, repeatably, for an hour, without ever
firing at a person and without the valve ever sticking open.**

---

## What V0 is graded on

**The path, link by link — not how well any link performs.**

```
frame arrives → detector emits a box → box becomes an angle → servo reaches it
              → valve opens → water lands there → the event is logged
```

Every arrow either carries the signal to the next stage or it does not. V0 asks only that
none of them is broken.

It does **not** ask whether the classifier is any good. Mistaking a cat for a possum, or
missing an animal entirely, is a model problem — solved with data and training, and solved
*after* there is a working path to drop a better model into. Grading V0 on accuracy would
mean tuning a model against a rig that has never fired end to end.

## What V0 does not chase

**Not reliability, not power, not weatherproofing, not uptime.** V0 runs for an hour with
someone standing next to it, on a day chosen for the purpose, and then gets carried back
inside. Anything whose payoff arrives after the first week belongs in
[beyond-v0.md](beyond-v0.md), not here.

What does stay in from the first day is the short list of things that cost **one line or one
wire**, and whose absence is not recoverable later: the fail-closed valve, the duration cap,
and the never-fire-at-humans check. The last is in because a detector looking for animals
emits `person` in the same forward pass — the check is `if person in frame: return`, at no
extra latency and no extra model. They are in because they are free, not because they are
prudent. How *reliably* the human check holds is a model-quality question like any other,
and V0 is not graded on it.

## Three stages, and every one of them is kept

The riskiest parts of this project are mechanical and geometric, not perceptual:

- Does the servo hold position against the hose's torque?
- Does the water land where the geometry says it should?
- Does the valve close every single time?

So the detector goes in **last**. Each stage below removes suspects before the next one adds
any, and none of them is scaffolding — all three survive into the finished tool.

### Stage 1 — move each thing by hand

Make the servo turn. Make the valve open. **Separately, one typed command at a time:** `nc`
into the turret and send `AIM 30`, then `SPRAY 500`.

This is why `AIM` and `SPRAY` exist in the protocol as commands in their own right rather
than only as steps inside `FIRE`. Nothing is aimed at anything and nothing is calibrated
yet — the only questions are whether the two actuators obey at all, and whether the valve
shuts when told to.

### Stage 2 — click to fire

A human is the detector. With a person clicking, a miss can only be aiming, calibration or
timing — the classifier is not yet a suspect.

This stage is also **how calibration is performed**: step 2 of the procedure below is
*click it in the frame*. So it stays in the tool permanently, and it stays the way any
future aiming problem gets separated from any future classification problem.

### Stage 3 — detect and fire

Swap the click for the detector. By this point everything underneath has been proven, so a
new failure points at the model.

## Scope

**In:** network link · servo pan with mechanical limits · valve open/close with a hard
duration cap · pixel → angle mapping · empirical calibration · click-to-fire UI over a
live frame · **animal detection** · **the never-fire-at-humans rule** · **autonomous
firing** · event log · safety (limits, cooldown, watchdog, fail-closed)

**Out:** tilt · night operation and IR · wireless, battery, solar

**Tilt is out because the nozzle is low**, not because aiming in elevation would be hard —
see the mechanics section. The two decisions are one decision and must not be separated.

Night is out of V0 even though the most interesting targets are nocturnal. That is a
deliberate ordering: daylight targets — brush turkeys, cats, birds — are enough to prove
the loop, and infrared brings its own perception problem that deserves its own attempt.

---

## Architecture

```
Camera (fixed, does not rotate)
     │ RTSP
     ▼
┌───────────── Host (indoor computer) ─────────────┐
│  frame ──► detector ──► never-fire-at-humans      │
│      └───► UI: click to fire (calibration)        │
│                    │                              │
│            calibration: pixel_x → angle           │
│                    │                              │
│            controller (limits, cooldown, rate cap)│
│                    │                              │
│            event log (JSONL)                      │
└────────────────────┼──────────────────────────────┘
                     │ network, ASCII
       ┌─────────────▼──────────────┐
       │      Turret controller      │
       │      (Raspberry Pi)         │
       │  · clamp angle              │
       │  · cap spray duration       │
       │  · watchdog → close valve   │
       │  · valve closed on boot     │
       └───┬────────────────────┬────┘
           │                    │
        servo            relay ──► 12V NC valve
```

The host decides *what*. The turret controller decides *whether it is safe* and does it.
Neither duplicates the other's job — the host sends exactly two numbers, an angle and a
duration.

**Why a Raspberry Pi for V0:** because there is one on the shelf. V0's bar is one hour of
clicking with someone standing there, and a Pi drives a servo and a relay perfectly well.
The reasons a microcontroller eventually wins this slot — boot window, no OS to hang, an SD
card that survives power cuts, 85°C instead of 70°C, microamps in sleep for a battery
version — are all *unattended, outdoor, long-run* reasons. They are recorded in
[beyond-v0.md](beyond-v0.md) and none of them apply to a demo.

**The one thing the Pi costs in V0:** Linux is not a real-time system, so a servo driven by
software PWM twitches whenever the machine is busy. That reads as a mechanical fault — which
is expensive on a rig whose headline risk *is* mechanical, and you can lose an evening to the
bearing before suspecting the pulse train. Drive the servo from a **hardware PWM pin**
(GPIO 12, 13, 18 or 19) or through **`pigpio`**, which generates pulses by DMA rather than
from userspace. A PCA9685 breakout is the fallback if neither is convenient. Choose before
building, not after the first twitch.

The rest of this document says **firmware** for the turret side. On a Pi it is a service
rather than firmware, but the job is unchanged: execute and enforce, never decide.

**Build order:** get the mouse-click path working before swapping in detected
coordinates, so the riskiest part is proven first.

---

## Wire protocol

Line-based ASCII over TCP. Deliberately human-readable: when the rig misbehaves you can
`nc` into it and drive it by hand, with no tooling.

A dropped connection is normal on a network in a way it is not on a cable, which makes the
watchdog load-bearing rather than decorative: **silence closes the valve**, and the host
reconnecting is an ordinary event rather than an error.

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

**`<ms>` is relay-closed time, not water-out time.** A solenoid lags in both directions —
for a comparable valve, ≤0.15 s to open and ≤0.3 s to close — so the water is late to start
and later to stop. Three consequences:

- The commanded number and the delivered volume are not proportional at short durations,
  so the habituation experiment must randomise over *measured* shots, not over `<ms>`.
- The turn-then-spray rule needs its mirror: **wait out the closing lag before turning
  away**, or the tail of the shot paints the arc that `FIRE` ordering exists to prevent.
- The lag is not wasted water. A part-open valve throttles pressure at a fixed nozzle, so the
  jet is short while the valve is still opening and reaches full range once it is — **every
  shot sweeps near to far on its own**, and back again as it closes. A short command is a
  short-range shot rather than a failed one, which makes duration a crude range knob that
  costs nothing. How far the jet actually reaches mid-transient is unmeasured; see below.

The lag is a property of the valve that was bought, so it is measured on arrival like
everything else, and the firmware's settle and post-spray waits are set from that.

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

### Camera placement: put it where it sees well

**The camera and the turret do not have to share an axis.** Calibration is a measured map
from image position to turret angle, and that map absorbs whatever fixed geometry it is
handed. Mount the camera where the view is good — high, looking down, away from the
foliage — and let the fit deal with it.

Two things follow, and both are about the *fit* rather than the mounting.

**Calibrate over an area, not a line.** With the camera on the turret's axis, bearing depends
on `pixel_x` alone and three or four points across the frame are enough. Off-axis, the right
angle depends on how far away the target is as well, which the image encodes as `pixel_y` —
so the calibration points have to spread across the ground in **both** directions, not along
one line, and there need to be more of them. Same procedure as below, more targets.

**The map assumes the animal is standing on the ground.** That is how `pixel_y` becomes
distance. A possum on a fence, a bird on a branch, a cat on a wall — anything above the
ground plane reads as further away than it is, and the shot goes wide. Co-axial mounting is
the one arrangement immune to this, since bearing then contains no distance term at all.

For reference, if the camera does end up off-axis by `d` with the target at `L`, an
*uncorrected* map is wrong by about `atan(d/L)`:

| Horizontal offset | 1 m | 3 m | 5 m |
|---|---|---|---|
| 20 cm | 11° | 3.8° | 2.3° |
| 50 cm | 27° | 9.5° | 5.7° |

That is the size of what calibration is being asked to absorb — worst close in, which is also
where the animal is when it matters.

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
| **Servo** | DFRobot 35 kg·cm waterproof 180° IP54 | **$36.55** |
| Servo horn | aluminium 25T round disc | $3.47 |
| **Impact sprinkler** | metal, ground-standing — bearing, swivel, base and nozzle in one | **~$30** |
| **Swivel joint** | pressure-washer swivel — the driven joint in arrangements B and C | **~$30** |
| Swivel adapters | M22 ↔ 3/4" BSP | ~$10 |
| Coupling clamp | U-bolt plus aluminium flat bar — **size it after measuring the head** | ~$5 |
| Linkage | RC pushrod with **ball links** at both ends | ~$10 |
| **Solenoid valve** | SparkFun ROB-10456 — 12V DC, normally closed, 3/4" BSP, 330 mA | **$22.55** |
| **Relay module** | 5V 2-channel **opto-isolated** (Core CE05114) | **$5.70** |
| Turret controller | Raspberry Pi — 3.3V GPIO, 5V on header pins 2 and 4 | already owned |
| Servo supply | 6–7.4V, 3A+ BEC | ~$20 |
| 12V supply | for the valve; 1A is ample at 330 mA | ~$15 |
| Flyback diode | 1N4004 or 1N4007, **across the solenoid** | ~$0.50 |
| Pull-up resistor | 10 kΩ, on the relay input | ~$0.30 |
| Bench indicator | 12V panel lamp, or an LED with a 1 kΩ series resistor | ~$2 |
| Jumper wires | female-to-female, Pi header to relay board | ~$5 |
| Hose fittings | 3/4" BSP, tap to valve | ~$15 |
| Flexible tail | short reinforced hose, valve to rotating head | ~$10 |
| Thread tape | PTFE, for every BSP joint | ~$2 |
| **Box** | plastic tub or toolbox with a lid, plus grommets | ~$25 |
| | | **~$345** |

Uncosted: whatever holds the servo alongside the sprinkler, and the camera wherever it sees
best. Timber and screws are a legitimate answer for V0.

This buys the parts for all three arrangements below. If none of them can be coupled, the
build-it-yourself stack costs another $46 — lazy susan bearing $31, adjustable nozzle $15 —
plus making a base.

The last three cost almost nothing and are each load-bearing: without the diode the valve's
switch-off spike goes looking for the microcontroller, without the pull-up the valve opens
while the Pi boots, and without the indicator there is no way to prove the valve closes
before committing water to the question.

### Shopping list, grouped by where you get it

Ordered so that each group can be bought without waiting on the others, and so that the two
parts that must be *exactly* right arrive first.

**Core Electronics — online, ships same day before 2PM.** The parts with no acceptable
substitute:

- [ROB-10456](https://core-electronics.com.au/12v-solenoid-valve-3-4.html) — the valve.
  12V DC and 3/4" BSP are both non-negotiable; see the four mistakes below
- [CE05114](https://core-electronics.com.au/5v-2-channel-relay-module-10a.html) — the relay.
  The 2-channel board specifically, because the cheaper 1-channel one is **not** opto-isolated
- Servo and horn, if you are consolidating orders

**Camera — Reolink direct or any reseller.** RLC-520A, camera only. It ships with **no power
supply of any kind** — no adapter, no injector — because it assumes a PoE switch, which we
have. Order it first: longest lead time, and nothing can be aimed until it is up.

**Jaycar (Hornsby) or Little Bird — walk in.** Diode, 10 kΩ resistor, 12V indicator lamp,
female-to-female jumper wires, and the 12V supply. Buy the diodes in a strip; they cost cents
and the first one always ends up somewhere else.

**RC Hobbyland (Castle Hill) or Ultimate Hobbies (Parramatta) — walk in.** The 6–7.4V BEC, and
the pushrod with ball links. Both are RC-hobby stock rather than electronics stock, which is why
those shops are on the list at all.

**Bunnings, second trip — after the sprinkler is in hand and measured.** The U-bolt and
aluminium flat bar for the coupling. Sized by the head's diameter, so it cannot be bought blind.

**Bunnings — walk in.** The metal impact sprinkler, 3/4" BSP hose fittings, a short flexible hose for the tail,
PTFE thread tape, the box and its grommets, and whatever timber and fasteners the base is
made of. **Do not buy a
solenoid valve here** — the irrigation aisle is 24V AC.

**Online, no hurry.** The pressure-washer swivel and its M22-to-BSP adapters — search
"pressure washer swivel joint", not "rotary union", which returns industrial parts at ten
times the price. A lazy susan bearing only if all three arrangements fail.

**Already owned:** the Raspberry Pi, the laptop that runs the host, and a network for them to
find each other on.

Local matters more than price for everything above the bearing. The bottleneck is getting the
rig standing, and a fortnight of international shipping on a critical part is a fortnight of
not measuring anything.

### Network

The camera is **Ethernet-only — no WiFi** — and ships with no power supply at all, so it
needs a port that also feeds it. A PoE switch does both:

```
indoor router ══ mesh backhaul ══ outdoor mesh node
                                        │
                                  PoE+ switch ─┬── camera   (power + data, one cable)
                                               └── Pi       (wired)
laptop (host) ── indoor network
```

**PoE+ is 802.3at and covers the camera's 802.3af**, so any PoE+ switch works and no injector
or 12V adapter is needed. One cable to the camera instead of two.

**The Pi goes on the wire too**, since the ports are there. The control link then stops
competing with video for the same radio, which costs nothing to arrange and is one less thing
that can look like a bug.

**Pull the substream, not the 5MP main stream.** Detection does not need full resolution, and
the video still crosses the wireless backhaul to reach the host. The substream is roughly a
megabit; the main stream is not. Fetch the main stream only when looking closely at something.

A mesh link drops occasionally by nature. That is not a special case here — silence closing
the valve is what the watchdog is for, and reconnecting is an ordinary event.

A desktop switch is not weatherproof. For V0 it gets carried out, plugged in, and carried
back, which is the whole V0 posture; finding it a permanent home is
[beyond-v0](beyond-v0.md) work. If no PoE switch were available, the camera's own 12V input
is the fallback — kept off the valve's rail, since the solenoid puts switching noise there
and a camera that glitches only while spraying is a miserable thing to diagnose.

### The box

Everything electrical except the camera lives in one box. Cables leave it to reach the three
things that cannot be inside it.

| | |
|---|---|
| **Inside** | Pi · relay module · PoE switch · 12V supply · 6–7.4V BEC · a powerboard for the plug-packs |
| **Leaving it** | Ethernet to the camera · three wires to the servo · two wires to the valve · one mains lead |

**What this box is not: weatherproof.** It is a carrying case. The rig goes out for an hour
on a chosen afternoon and comes back inside, so a plastic tub with a lid is the right answer
and a sealed enclosure with a gasket and cable glands is [beyond-v0](beyond-v0.md) work.
Putting the powerboard inside is what turns four plug-packs into one mains lead, which is the
difference between a box you carry and a box you rebuild every time.

**What it still has to get right**, because both of these bite inside the first hour:

- **Strain relief on every cable that leaves it.** A box that gets carried has its cables
  pulled, and a wire lifted off the relay's screw terminal mid-session is either a valve that
  stops answering or a short across the supply. Anything counts — a grommet and a knot behind
  it, a cable tie to an internal anchor — as long as the pull lands on the box and not on a
  terminal.
- **Nothing spliced into mains.** Plug-packs into a powerboard, one lead out. There is water
  and a garden on the other side of the wall; [SAFETY.md](../SAFETY.md) covers the RCD.

### Mechanics

Three paths, each doing exactly one job, and none of them doing another's:

```
load   nozzle ─ rotating top ─ turntable bearing ─ fixed base
drive                          25T horn ─ 35 kg servo ─ fixed base
water  nozzle ─ swivel ON THE ROTATION AXIS ─ fixed supply hose
```

**Do not let the servo output shaft carry the sprinkler's weight or the hose's pull.**
The lazy susan bearing takes the load; the servo drives through a horn or linkage.

**The hose does not rotate.** A swivel joint on the axis lets the head turn while the supply
hose stays still, which deletes the headline mechanical risk of this project rather than
asking the servo to overcome it. A garden hose is stiff, and a stiff hose twisting the turret
back is the difference between water landing where it was aimed and water landing where the
hose decided.

Two things make or break it:

- **The swivel goes on the axis of rotation.** Off-axis it is just a lever arm in a new place.
- **The swivel seals, it does not carry.** The bearing takes the weight. Same rule as the
  servo shaft, for the same reason.

#### Buy the rotating joint rather than building it

Three arrangements do this, and they are cheap enough that the sensible move is to buy the
parts for all of them — about $70 — and settle it in an afternoon with the things in hand.
The document's own rule applies: the bottleneck is hardware and measurement, not analysis.

**A — impact sprinkler alone, ~$30.** A metal impact sprinkler already *is* a rotating water
head: swivel built in and concentric from the factory, bearing sized for the job, heavy base
that stands on the ground where the nozzle wants to be, and the longest-throwing nozzle in the
garden aisle since throwing far is the point of the type. The conversion is *stop it turning
itself, then drive it* — remove the sprung impact arm, remove the arc-reversing trip, back off
the friction screw, and clamp a driven lever to the rotating body.

**B — swivel plus a nozzle, ~$55.** A pressure-washer swivel is a sealed bearing and a rotary
seal in one part, with nothing to defeat. But its axis has to stand vertical, so the water
comes out facing up and needs an elbow to turn it — two more joints to leak, a cantilever
hanging off a small bearing, and a base still to build.

**C — swivel carrying a sprinkler head, ~$70.** The combination, and probably the best of the
three, for one reason worth stating plainly: **it moves the driven joint onto a part designed
to turn freely, and demotes the sprinkler to something that only has to be locked. Locking is
far easier than driving.** A grub screw or a hose clamp stops the head rotating on its own
bearing; finding somewhere to clamp a *loaded* lever that will not slip is the hard part of A.
The servo then drives the sprinkler body, which has far more to grip than the swivel does, and
the heavy base and riser stay still underneath — weight on the side that does not move.

```
C:   sprinkler head (own rotation locked)      inlet down, nozzle out
       └ swivel, rotating half                 ← servo lever clamps here or just above
         swivel, fixed half                    axis VERTICAL, so the head sweeps horizontally
           └ riser ─ heavy base (stationary)
```

The swivel's axis stands **vertical**, which is what makes the head sweep in the horizontal
plane. An impact sprinkler head is already *inlet down, nozzle out*, so the ninety degrees the
water has to turn is built into it — that turn is exactly what B has to add an elbow for.

A vertical axis also means **gravity produces no torque to fight.** A heavy or lopsided head
loads the bearing sideways but exerts no moment about a vertical axis, so the servo is only
ever working against seal friction and jet reaction — never against weight.

Its one hard requirement: **lock the head's own rotation.** Leave it free and there are two
rotary joints in series, the servo commands one, and the resulting angle is undetermined. The
impact arm still comes off in every arrangement — against a locked head it just hammers away
wasting energy and making noise.

##### What to buy for the coupling, and what to search for

Two parts, from two different kinds of shop.

**The clamp on the head.** A **U-bolt** around the body with an **aluminium flat bar** across
its nuts is about $5 at a hardware store, needs no drilling, is adjustable, and the flat bar
*is* the lever. Search terms: `U-bolt`, `pipe saddle clamp`, `conduit saddle`, `aluminium flat
bar`. The tidier answer is a `split shaft collar` or `clamping shaft collar` from a bearing
supplier — less play, $10–20, and only if a size matches. `exhaust clamp` at an auto shop is
the same idea heavier.

**The rod to the servo.** Buy this from an RC hobby shop, not a hardware shop: search
`pushrod`, `ball link`, `ball joint linkage`, `clevis`, `linkage stopper`. A wire bent into a
hole is where slop comes from; **ball links at both ends are the cheap fix for it.** $5–10, and
it is the same trip as the BEC.

**Order the sprinkler first and measure it.** U-bolts and collars are sized by bore, and
whether the head is 20 mm or 35 mm across is not knowable from here. This is deliberately a
second trip.

##### The coupling is a backlash problem, not a strength problem

Whatever grips the rotating part, the torque it carries is small — seal friction plus whatever
reaction the nozzle leaves, with gravity contributing nothing about a vertical axis. So the
clamp does not need to be fierce.

What it must not have is **play**, because play turns a commanded angle into an approximate one.
The scale is unforgiving: at a 30 mm crank radius one degree is 0.52 mm of travel, at 40 mm it is
0.70 mm. Two mediocre joints and a flexible bracket spend the entire 1–2° budget on their own.
Two consequences:

- **Use the largest crank radius that fits.** 35–40 mm rather than 20 mm. It does nothing for
  angular error but it divides every *linear* error — joint clearance, bracket flex, clamp creep.
- **Prefer a shape that cannot slip over a grip that must not slip.** A flat, a hex or a boss to
  drive against beats friction on a smooth cylinder. Where only a cylinder is available, use a
  two-piece clamp with a thin rubber or fibre friction liner and an anti-rotation tab bearing
  against an existing feature. **Never drill into a pressurised part of the head.**

##### Which drive, and the one number that decides it

Three ways to get rotation from an offset servo axis to the head, and they rank differently for
V0 than they do on merit:

| | Kinematics | For a rig built this morning |
|---|---|---|
| **Parallelogram pushrod** | exact 1:1, but passes servo lash through undivided | **build this** |
| Timing belt, e.g. 20T→30T | constant ratio *and* reduction — strictly better on paper | the upgrade path |
| Pull–pull cable | also constant ratio; drum can surround the water axis | skip |

The parallelogram: **equal crank lengths, and a ball-to-ball pushrod equal to the measured
axis-to-axis spacing.** The four links then form a parallelogram, the cranks stay parallel, and
the angle transfers exactly — no lookup table, no varying ratio, and the change-point that would
jam it sits out near ±90°, far outside ±40°. Unequal cranks give a ratio that varies across the
sweep and are not worth choosing.

But 1:1 has a real cost, and it is the term this document previously ignored: **the servo's own
gearbox lash, around 0.5° on this class of servo, arrives at the head undivided.** A 1.5:1
reduction would cut it to 0.33°. So a belt is genuinely better — by 0.17°.

That number is the decision. A split pulley clamped onto a brass casting by hand, slightly
eccentric or slightly loose, loses far more than 0.17°. The belt only pays if its driven pulley
is truly concentric, rigidly held, and aligned with the servo pulley without side-loading the
head — none of which a same-morning build can promise. **Build the parallelogram; keep the belt
as the upgrade once the geometry is known and something can be machined.**

Two cheap wins that cost no parts:

- **Always approach a target from the same direction** — command a couple of degrees past it and
  come back. Backlash is hysteresis, so a consistent approach direction removes most of its
  effect for free. Worth doing whichever drive is fitted.
- **Keep the servo off its mechanical endpoints**, roughly 30–150° of its range.

And check the actual servo's backlash figure rather than assuming 0.5° — it is published for
some 35 kg·cm units and not for others.

##### Coaxial drive: right idea, wrong fitting

There is a fourth arrangement, and the reasoning that dismissed it was wrong. *Water occupies
the rotation axis* is only true of a **straight-through** joint. Put an **elbow** on the swivel
and the water turns outward before it reaches the top — so the axis above the bend is empty, and
a servo on a bracket over the top can drive the joint **directly, on-axis, 1:1, with no linkage
at all.** No ball links, no crank radius, no four-bar geometry.

It is genuinely attractive, and with an off-the-shelf angled tap connector it is still a trap.
The freed axis lands on the **outside of a curved brass casting** — no flat, no boss, nothing
manufactured to attach to. And the rule against drilling into a pressurised part applies exactly
there. Every quick fix is bad: a bonded disc has almost no bond area and loads it in peel;
brazing cooks the O-ring; filing a flat removes wall. A split saddle bridging over the elbow does
respect the pressure boundary, but then it is a custom fixture whose shaft has to be centred over
an axis nothing externally defines — and being assembled 1–2 mm off-axis is the likely failure,
long before anything bursts.

The deeper point is that **fewer parts is not the same as easier**:

> The parallelogram tolerates considerable axis-placement error without side-loading the swivel.
> Direct coaxial mounting has fewer parts, but each part must be located substantially more
> accurately. It does not remove error; it trades one set for another.

**The variant that does work is a tee instead of an elbow.**

```
fixed riser → straight live swivel → short rotating nipple → brass TEE
                                                              ├─ side branch → nozzle
                                                              └─ top port → threaded plug
                                                                             └─ shaft → coupling → servo
```

The tee's top port is a **manufactured, pressure-rated thread**, and its plug is a separate
replaceable part rather than a casting wall. Clamp a bored hub around a brass hex plug, or use a
reducing bush with a male shaft adapter, or machine the plug's *external* head with the plug out
of the system and refit it with sealant. Cross-bolt only through solid material above the sealing
thread. Never into the wet cavity.

Two conditions gate it:

- **The swivel must be a live swivel.** The whole tee downstream of it has to rotate while
  pressurised without loosening a threaded joint. A tap adaptor whose "swivel" only lets its nut
  turn during installation will not do this.
- **The breakaway torque has to be low enough** — measure it, below. Coaxial drive is exposed
  directly to seal stiction with no reduction to soften it.

If both hold, use a **zero-backlash Oldham** coupling (not a rubber spider — a soft spider winds
up torsionally and stores energy until it breaks away, which *is* stick-slip), on a vertically
adjustable bracket. Target parallel offset under 0.25–0.5 mm and angular error under 0.5°: the
coupling absorbs the residue after alignment, it is not a substitute for aligning.

##### Measure the breakaway torque before designing around the swivel

Cheap, decisive, and it needs no build. Pressurise the fitting exactly as intended, clamp a
temporary **100 mm lever** to the rotating part, and pull tangentially with a **fishing or
luggage scale**. At that radius, `T = F × 0.1`, so newtons read directly as tenths of a N·m:

| Pull | Torque |
|---|---|
| 1 N | 0.10 N·m |
| 3 N | 0.30 N·m |
| 5 N | 0.50 N·m |

The servo's 35 kgf·cm is about **3.4 N·m**, so raw torque is never the question. What matters is
staying well under **0.2–0.3 N·m** breakaway, leaving margin for control, nozzle reaction and
bracket flex. Record five things: force to start moving, force while moving, whether breakaway
differs by direction, whether it returns to the same marked angle from both approaches, and
whether friction climbs at 500 kPa.

**The gap between starting and running force matters more than either number.** Starts at 7 N and
runs at 2 N means stick-slip and direct drive is out. Starts at 2 N and runs at 1.5 N means
coaxial drive is plausible.

##### What the drive can defer, and what it cannot

Legitimately postponed to the six-week experiment: corrosion, UV, weather sealing, cable creep,
belt tooth wear, bearing fatigue, lubricant washout, thermal cycling, fasteners loosening over
many cycles.

**Not deferrable, because they bite in the first hour:** head play measured with water both off
and on · nozzle reaction when the valve opens · the clamp neither entering the water path nor
obstructing rotation · not deforming the rotary joint · side-load and the stiction it causes ·
supply voltage sag while the servo moves · physical or software stops that keep the mechanism
away from a toggle position · repeatability checked from *both* approach directions.

*(The drive ranking, the 0.17° figure and the defer split came out of a design discussion with
GPT-5; it conceded the parallelogram point and supplied the servo-lash term this document had
missed.)*

Whichever wins, four things decide it and none can be answered from here:

- Is there anywhere to clamp — a flat, a boss, wall thick enough to grip?
- Does everything turn freely by hand once the arm and trip are out?
- Can the friction screw be backed off, and does its friction help hold or fight the servo?
- **Does the head creep once the water is on?** Any nozzle not pointing exactly through the
  axis leaves a reaction torque. This is the one that needs water to answer.
- **Can the servo still turn it once the water is on?** Line pressure pushes the swivel's two
  halves apart — around 4 kg at mains pressure through a 10 mm bore — and that force lands on
  the seal, so friction rises with pressure. Free by hand when dry says nothing about driven
  under pressure, and testing dry first is the natural mistake.

Residual torque is not zero in any arrangement — line pressure loads the seal and seals have friction
— so *holds position against torque* stays on the definition of done. It just stops being a
question about a garden hose and becomes a question about a bearing.

#### Mount the nozzle low. This is what removes the tilt axis.

A jet leaving near ground level at a few degrees of rise stays inside the height band a
small animal occupies — roughly 0 to 40 cm — for most of its flight. Anything standing along
that bearing gets hit somewhere, at a wide range of distances, without the range ever being
aimed at. **Bearing is the only quantity that has to be right.**

Mount the same nozzle at chest height and that stops being true: a downward stream crosses
animal height at exactly one distance, and hitting anything then requires elevation as well.
Tilt would be back, and with it a second servo, a second calibration and a second axis of
error.

So elevation is **set once and bolted**, not controlled — a few degrees up, adjusted during
calibration until the useful band covers the ground you care about. The band has ends: very
close in, the stream has barely risen; far out, it has already landed. Neither end needs
aiming, both need knowing, and both come out of the flow measurement rather than a
calculation.

##### Varying the nozzle opening is not a range control

It looks like one — open wide for near, narrow for far — and it fails three ways. (Throttling
*upstream* is a different matter and happens for free every time the valve opens; that is in
the protocol section.)

**The physics runs backwards.** Exit velocity comes from pressure, not from aperture; the
aperture sets flow. A wide opening flows more, drops more pressure in the hose, and arrives
at the tip *slower*. Narrowing it throws water **further**, which is why squeezing a hose end
makes it squirt across the yard. And the relationship is not just inverted but cliffed: past
some point the stream breaks into spray and the range collapses.

**It costs an actuator on the rotating head** — a servo to turn the nozzle collar, plus its
own calibration. That is precisely the cost that mounting the nozzle low was chosen to avoid,
reintroduced on the one part already fighting hose torque.

**It answers a question the geometry already answered.** A low jet covers a long band of
distances *simultaneously*. Sweeping near-to-far is only worth anything if the instantaneous
band is shorter than the ground being defended, and whether it is comes out of the flow
measurement, not out of a calculation.

If the band does measure short, the cheap fixes come first and none of them is a mechanism:
adjust the nozzle it already has (including trying a vertical fan, trading impact for
coverage), adjust the bolted elevation, shorten or widen the supply hose to lose less
pressure, or move the rig.

### Four mistakes that cost a rebuild

**1. The valve must be 12V DC, not 24V AC.** Most irrigation valves sold in hardware
stores are 24V AC — a decades-old standard, because a bare transformer produces it with no
electronics at all. Pick one up without checking and you get the default, which is wrong.

A relay *could* switch 24V AC — contacts do not care, and AC is gentler on them than DC.
The reasons for DC are the other ones: a 12V DC rail can also feed the 5V and 6–7.4V rails,
where 24V AC is a dead end only the valve can use; a DC valve can be verified with nothing
but a battery touched to its leads, before any electronics exist; and it leaves the option
of dropping the relay for a MOSFET later. (A MOSFET genuinely cannot switch AC — it
conducts one way and its body diode conducts the other — so choosing AC would close that
door permanently.)

**2. BSP threads, not NPT — and 3/4", because that is what an Australian outdoor tap is.**
The wrong thread means the whole batch is useless. Watch for 1/2" NPS in particular: same
14 TPI as BSP but a 60° flank instead of 55°, so it threads in, feels seated, and then
weeps under pressure. Look for the flank angle stated explicitly.

**3. You need a flyback diode.** A solenoid is an inductor; the reverse spike when it
switches off will destroy a MOSFET and can take the microcontroller with it. This is the
most common way this kind of project dies overnight. Opto-isolated relay modules normally
include the protection.

**4. Never power the servo from the controller's own supply.** A 35 kg servo's stall
current will brown out the board. Separate 6–7.4V supply, common ground.

### Wiring the valve

Three different voltages meet at the relay, and confusing them is how this goes wrong:

| Circuit | Volts | What is on it |
|---|---|---|
| Signal | 3.3V | the Pi's GPIO |
| Coil | 5V | the relay's electromagnet |
| Contact | 12V | the solenoid valve |

The "5V" in a relay module's name describes the **coil only**. What it can switch is the
separate contact rating — 10A @ 28VDC here, against a 330 mA load.

**The opto-isolated module is not optional, and spike isolation is only half the reason.**
On these boards the trigger is **active-LOW**, and on a non-isolated module one pin feeds
both the coil and the input, so the two requirements collide:

- the input must sit at **3.3V**, or the controller's logic high cannot fully switch it off
- the coil needs its full **5V**, or the relay pulls in weakly

A 5V coil driven at 3.3V is below its pull-in spec — it works on a warm bench and not
dependably anywhere else, and a contact that closes weakly can weld shut, which is a valve
stuck open. Vendor tutorials wire it that way; do not copy them.

Removing the module's VCC/JD-VCC jumper separates the two rails and both requirements are
met at once. That is the reason to buy the isolated board.

**Then:**

- Solenoid through the relay's **NO** contact — de-energised relay, no water. Note the
  naming collision: the *valve* is normally closed and the *relay* has an NC terminal, and
  they are unrelated. Wiring to the relay's NC inverts everything, so the valve opens
  whenever the controller is off.
- **10k pull-up on the input.** GPIO is an input for the whole of boot — around thirty
  seconds on a Pi — and active-LOW plus a floating pin means the relay energises. The
  pull-up is what holds the valve closed across that window, so it is not optional.
- **A flyback diode across the solenoid.** The diode on a relay module protects the
  module's own coil, not your load, and the solenoid is the larger inductor.
- Verify with a multimeter across the contact through a full power cycle, before the LED
  goes on the bench, let alone water.

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

V0 fires by itself, so **never fire at humans** is in from the first autonomous shot, not
deferred. It lives in the host controller, above the detector and independent of it: if
anything human-shaped is anywhere in frame, no shot is issued, whatever the animal
classifier thinks. A rule, not a threshold — see [SAFETY.md](../SAFETY.md).

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

## Verified on the real rig, dry

**No mock device.** The bottleneck on this project is hardware and measurement, and a
simulated serial peer proves only that the host agrees with a fiction someone wrote. It
would pass happily while the servo stalls, the relay chatters, or the board browns out.

What replaces it is a **dry bench**: the real Pi, the real servo, and an indicator in
place of the solenoid on the relay's 12V circuit — either a 12V panel lamp, or an LED with
a series resistor sized for 12V (about 1 kΩ gives ~10 mA). Not a bare LED: across 12V it
draws whatever the supply will give and dies in the first shot, which is a poor way to
learn that the valve stayed open. Everything else behaves as it will in the garden except
that nothing gets wet, so the two most expensive silent errors are visible before a hose is
connected:

| Error | How it shows on the dry bench |
|---|---|
| Calibration wrong — *"it aims left but sprays right"* | servo turns to the wrong angle for a known click |
| Safety wrong — *the valve stays open* | indicator stays lit past the duration cap, after `STOP`, or when the host is killed mid-spray |

**Connect water only after the indicator has behaved for a full session**, including a host
kill mid-spray and a power cut. A lamp that stays on is a bug; a valve that stays open is a
flooded garden and a lesson about normally-closed valves you did not need to pay for.

Geometry and the calibration solve stay ordinary unit-tested functions — pixel in, angle
out, no device of any kind involved. That is arithmetic rather than simulation, and it
costs nothing to check.

## Measure on arrival

Rule 4 applies to the valve as much as to the lens. Three numbers are not on any datasheet
that covers this rig, and all three can stop V0 dead:

| Measure | How | Why it blocks V0 |
|---|---|---|
| **Flow at the real tap** | bucket and stopwatch, valve wide open | Decides whether the jet reaches at all. The published "~3 L/min" is quoted at the 3 PSI *minimum*, not at mains |
| **Does it open at your pressure** | listen for the click with the tap on | It is pilot-operated, so it needs pressure to open. A comparable system quotes ~25 PSI as the practical floor — well under mains, but a rainwater tank will not do it |
| **Open and close lag** | stopwatch on the indicator vs the water | Sets the settle waits, per the protocol section |
| **How the jet sweeps while the valve opens** | film one shot in slow motion on a phone | A part-open valve throttles a fixed nozzle, so each shot sweeps near→far unaided. This says how much near-field coverage comes free, and therefore whether short commands are usefully short-range shots |

Also check the hose-to-valve joint under full pressure before leaving it unattended for
even an hour. That connection is the reported leak point on comparable hardware, and here
it sits on a moving flexible tail rather than fixed plumbing.

## Definition of done

- [ ] `PING` round-trips over the real link
- [ ] `AIM` turns the servo and `SPRAY` opens the valve, typed by hand, one at a time
- [ ] Dry bench passes a full session on the indicator before water is connected
- [ ] Servo reaches both mechanical limits and holds against the swivel's seal friction
- [ ] Supply hose does not move when the turret does
- [ ] Valve opens and closes; **never observed stuck open**
- [ ] Watchdog closes the valve when the host is killed mid-spray
- [ ] Calibration solved from measured points; water lands within a jet-width of a clicked
      target across the frame
- [ ] One hour of clicking with no missed close and no drift
- [ ] Detector runs on the live stream and produces angles the turret acts on
- [ ] The whole path closes unaided at least once: an animal walks in, water arrives at it,
      the event appears in the log — nobody touching anything
- [ ] Events logged and readable

Only then: night, infrared, and the six-week experiment.
