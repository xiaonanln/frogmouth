# Beyond V0

V0 is an attended demo: one hour, someone standing there, a day chosen for good weather.
Almost nothing here bites under those conditions, which is exactly why none of it belongs
in V0 — adding it would delay the demo, and the demo is the whole point of V0.

What follows bites when the rig is **outdoors, unattended, overnight, for six weeks** —
the conditions of the habituation experiment. Each item is listed with the condition that
triggers it, so it is obvious when it stops being optional.

Most of this comes from [FarmBot's own documentation](https://express.farm.bot). They have
been selling an outdoor water-plus-electronics machine for years and publish what fails.
Reading their troubleshooting pages is cheaper than reproducing their failures.

## Enclosure

**Triggers: the first night it is left outside.**

A sealed box with a **gasket** and a **cable gland for every entry** — not a plastic box
with holes drilled in it. FarmBot ships exactly this (box, lid, gasket, latches, glands).

The current bill of materials has an ESP32, a relay module and two supplies with nowhere to
live. That is fine on a bench and not fine in a garden.

## Fuse

**Triggers: unattended operation.**

There is no fuse anywhere in the bill of materials. Outdoors, over weeks, insulation chafes
and water finds things; a 1A+ supply into a short is a fire. FarmBot ships one pre-inserted.

## A physical cut-off

**Triggers: the first night nobody is watching.**

`SAFETY.md` promises two independent layers of shutoff — but both are software, and both
are gone together if the firmware hangs. FarmBot's third layer is a red button that
**unpowers** the peripherals outright.

A switch that physically breaks the valve supply is fail-closed by construction rather than
by correctness. It is the only layer that does not assume a working semiconductor, which
matters because both relays and MOSFETs tend to fail *closed*.

While a human is present, the tap and the plug are that button. That stops being true at
3am.

## Keep the valve out of the sun

**Triggers: the first hot afternoon.**

FarmBot rates its solenoid valve and pressure regulator as failing **above 60°C** — a
temperature a dark plastic body in direct Sydney summer sun reaches easily. Their cheapest
mitigation is the obvious one: put it in shade.

Related, for the battery version rather than now: a Raspberry Pi is rated 0–70°C and is the
most heat-fragile part of their machine. Moving computation outdoors imports that limit.

## Shielded serial

**Triggers: a long permanent cable run.**

FarmBot's camera cable specifies a *shielded* USB cable "or there will be EMI issues". The
host-to-ESP32 link is USB serial and will eventually be a long outdoor run. A short bench
cable is fine; the permanent installation is where this appears.

## Drain before a freeze

**Triggers: winter, and barely in Sydney.**

Water left in a valve cracks it when it freezes. Low priority here, listed so it is not
rediscovered.

## Pressure: where we cannot copy them

FarmBot recommends an upstream regulator at 45 PSI because high pressure makes their
connections leak and blows tubing off barbs.

**We cannot take that advice** — pressure is range, and a regulator would throw away the
reach the whole device depends on. What does transfer is the *failure location*: the joint
between garden hose and solenoid is where leaks appear, and ours is worse than theirs,
because it sits on a rotating flexible tail rather than fixed plumbing. Check it under full
pressure before any unattended run.

## A limitation worth naming

FarmBot detects stalled motion and stops. We cannot: a hobby servo returns no position, so
firmware has no way to know the hose has twisted the turret back. It is a consequence of
the servo choice, not something firmware can be written around.

For now this is why V0 is attended. If it matters later, it costs a current sensor or a
servo with feedback.

## What the design already gets right

Every moving axis on FarmBot needs a cable carrier to manage cables that flex. The turret
puts the servo on the fixed base and rotates only the sprinkler and its hose — **no
electrical cable moves at all.** That is a real advantage and worth not losing to a later
"improvement".
