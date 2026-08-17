# CLAUDE.md — frogmouth

Read `~/.claude/CLAUDE.md` first (global engineering principles). This file covers only
what is specific to **this** project; it does not repeat the global rules.

## What this is

A garden sentry that looks before it acts: camera identifies a small animal → turret
turns → aimed jet of water. Targets are **small animals generally** — possums, brush
turkeys, cats, birds, rabbits — not possums specifically.

**The design lives in this repository and nowhere else.** `docs/v0-design.md` holds the
V0 design, `SAFETY.md` the safety rules. Change the design there first, in a PR. No design
decision may live in a file outside this repository — a clone must carry the whole design.

(This is about design, not tooling. The pointer to `~/.claude/CLAUDE.md` above is a
personal working convention that applies across all of one author's projects; it holds no
frogmouth design decisions, and a contributor without it loses nothing about the design.)

## The thesis, which is easy to lose

**frogmouth solves false triggering, not habituation.**

Existing sprinklers fire on PIR, which cannot tell a possum from a cat from a delivery
driver from a moving shadow. That is why the category sits at 2.2–3.9 stars.

So: **PIR is a wake-up call. Vision decides.** Any design that demotes vision back to an
assistant has drifted from the reason this project exists.

Habituation is a lifetime metric measured by the six-week experiment. It is not the pitch.

## Hard rules

**1. Safety logic lives in exactly two places** — firmware and the host controller. Never
in UI code, detector code, or strategy code. See `SAFETY.md`.

**2. The valve is normally closed.** Every failure path — crash, disconnect, watchdog
timeout, process exit — must end with the water off.

**3. Never fire at anything human-shaped.** This is an explicit rule, not a confidence
threshold. The error cost is asymmetric: missing an animal costs fruit; hitting a person
is a different category of problem.

**4. Calibration is measured, never configured from a datasheet.** Quoted FOV is
optimistic, lenses distort, and a datasheet cannot know how crookedly the rig was
mounted or where the servo's mechanical zero really points. Measure
`(pixel_x, true_angle)` pairs and solve.

**5. Fixed camera ⇒ turret sweep must equal camera FOV.** Larger is phantom coverage
(angles that can never produce a detection); smaller means visible targets that cannot
be reached.

## Constraints that shape the code

- The host sends the turret controller exactly two numbers: **angle and spray duration**. All
  decisions are on the host; firmware executes and enforces safety only.
- Pixel → angle uses the **pinhole model**, `θ = atan(x_norm · tan(hfov/2))`. **Not**
  linear interpolation — a linear map systematically under-shoots mid-frame targets.
- Camera placement is free — calibration is a measured map from image position to angle and
  absorbs the geometry. Two consequences: off-axis, calibrate over an *area* rather than a
  line, and the map assumes the animal is **on the ground**, so climbers read as further away
  than they are. Co-axial mounting is the only arrangement without that assumption.
- **Pan only, and the nozzle is mounted low.** These are one decision: a jet leaving near the
  ground stays at small-animal height for most of its flight, so bearing is the only quantity
  that has to be right. Raise the nozzle and the tilt axis comes back.
- The detector must work on **bursts of frames and cold starts**, not a continuous
  stream with long-lived tracking state. A future battery version wakes from sleep with
  no history; if the logic depends on 30 seconds of tracking, it will need a rewrite.

## Build order — do not skip

```
1. Mount the camera and record several nights   ← IR samples: training data AND video material
2. Move the servo and the valve by hand         ← V0 stage 1
3. Click → angle → spray, and calibrate on it   ← V0 stage 2
4. Detection model + never-fire-at-humans rule  ← V0 stage 3, the loop closes
5. Six-week habituation experiment
```

**Record before modelling.** The main targets are nocturnal. Separating a possum from a
cat in infrared — no colour, similar size — is far harder than separating a person from
a dog. Model and camera choices are guesswork until real night footage exists.

**Keep mechanics and AI decoupled.** Get the mouse-click path working before swapping in
detected coordinates, so the riskiest part is proven first.

## On writing code

A V0 skeleton was once written before the hardware and calibration approach were settled.
That was the wrong order, and it was deleted (it remains in git history).

**The bottleneck on this project is hardware and measurement, not code.** Until the rig
exists and calibration has been measured, implementation is guesswork.

## The event log is experimental data

Not debug output. The six-week experiment rests on three numbers — detection accuracy is
not among them:

```
flight latency     seconds from spray to the animal leaving
approach distance  how close it got before being sprayed
return interval    how long until it comes back
```

Habituation shows up as: leaving more slowly, approaching more closely, returning sooner.

Flush and `fsync` on every write — a power cut at 3am must not lose the night.

## Conventions

- **This project is entirely in English** — code, comments, docs, commit messages, issues.
- **Every change goes through a PR.** Direct pushes to `main` are blocked by the
  `pre-push` hook and by branch protection.
- Enable the hook after cloning: `git config core.hooksPath .githooks`
- Squash merge.
- **While the project is still design-only, batch related changes into one PR.** Splitting
  a documentation pass into five PRs costs more review than it saves. One-PR-one-thing
  starts mattering once there is code to bisect.
