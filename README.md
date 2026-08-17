# frogmouth

> Named after the tawny frogmouth — an Australian nocturnal bird that sits motionless
> for hours with enormous eyes, indistinguishable from a branch, then strikes without warning.

A garden sentry that **looks before it acts**: a camera identifies an animal, a turret
turns towards it, and a jet of water sends it away.

Targets are small animals generally — possums, brush turkeys, cats, birds, rabbits.

## Why not just another motion sprinkler

Motion sprinklers trigger on **PIR**, which only knows that *something warm moved*. It
cannot tell a possum from a cat, from a delivery driver, from sunlit leaves in the wind.

The ratings say the rest: on Amazon AU the category sits at **2.2 – 3.9 stars**, and the
complaints are overwhelmingly false triggers — soaked pets, soaked people, water running
all night at a moving shadow.

**frogmouth demotes the PIR to a wake-up call. Vision decides.**

| | Motion sprinklers | frogmouth |
|---|---|---|
| What decides to fire | PIR | **vision model** |
| Spraying people and pets | common complaint | hard rule against it |
| Aiming | fixed arc | **aimed at the target** |
| Record of what happened | none | full event log |

## Status

**Design stage — no implementation yet.** The bottleneck here is hardware and
measurement, not code: calibration has to be measured on the real rig, and the main
targets are nocturnal, so the first real task is pointing a camera at the garden and
recording nights.

## Documentation

| | |
|---|---|
| [docs/v0-design.md](docs/v0-design.md) | V0 scope, protocol, geometry, calibration, hardware, definition of done |
| [docs/beyond-v0.md](docs/beyond-v0.md) | What outdoor unattended operation adds, and when each part of it starts to matter |
| [SAFETY.md](SAFETY.md) | **Read before building one.** Fail-closed valve, never fire at humans, legal notes |
| [CLAUDE.md](CLAUDE.md) | Project rules and build order |

Roughly **A$285** of parts — full list in the V0 design doc.

## The open question

Reviews of existing sprinklers repeat one complaint: animals stop caring after a couple
of weeks. Water differs from scarecrows and ultrasonics in that it imposes a real cost
every time rather than a startle that fades — but nobody has published data.

Six weeks in a garden, measuring flight latency, approach distance and return interval,
with randomised and fixed response on alternating weeks, would answer it.
See [docs/v0-design.md](docs/v0-design.md).

## License

MIT — see [LICENSE](LICENSE). A hobby project, provided as-is; you are responsible for
what you build from it.
