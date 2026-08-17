# Safety

frogmouth aims a stream of water at animals, autonomously, unattended.
Read this before building one.

## Non-negotiable design rules

**1. The valve must be normally-closed.**
No power = no water. Every failure mode — power loss, crashed host, dead
firmware, cut cable — must end with the water off. Never use a normally-open
valve.

**2. Never spray people.**
A confidence threshold is not enough. Implement an explicit rule: if anything
human-shaped is detected anywhere in frame, do not fire. The cost is
asymmetric — missing an animal costs you some fruit; hitting a person, a
child, or a delivery driver is a different category of problem.

**3. Two independent layers of shutoff.**
- Firmware: angle limits, maximum spray duration, watchdog that closes the
  valve if the host goes silent, valve closed on boot.
- Host: cooldown between shots, hourly rate cap, valve closed on every exit
  path including crashes.

**4. Know where the water lands.**
Aim away from footpaths, neighbouring property, electrical outlets, and
anything that must not get wet. Water travels further than you expect.

## Legal

In many jurisdictions wildlife is protected and may not be harmed or trapped.
Deterrence with water is generally permitted where lethal or injurious methods
are not — but **check your local rules before deploying.** This project is for
non-injurious deterrence only.

A camera pointed at your garden may also capture neighbouring property or a
public footpath. Check local privacy law and aim accordingly.

## Electrical

Solenoid valves are inductive. Switching one without a flyback diode will
destroy your MOSFET and possibly your microcontroller. Use an opto-isolated
relay module and **add a diode across the solenoid yourself** — the diode on a
relay module protects that module's own coil, not the load you attached to it.

Do not power a high-torque servo from the microcontroller's regulator.

Mains, water and outdoors in the same place: use an **RCD-protected outlet**.

Two wiring mistakes open the valve when nothing asked it to, and both defeat
rule 1 while looking correct:

- The relay has an **NC** terminal and the valve is **normally closed**. These
  are unrelated. Wire the valve through the relay's **NO** contact; using NC
  inverts everything, and water flows whenever the controller is off.
- These relay modules trigger on a **low** input, and a microcontroller pin is
  high-impedance while it boots. Without a pull-up the valve opens during
  start-up. Pull the input high and keep off the strapping pins.

Confirm both with a multimeter across the contact, through a full power cycle,
before water is anywhere near the rig. Wiring detail is in
[docs/v0-design.md](docs/v0-design.md).

## No warranty

This is a hobby project provided as-is. You are responsible for anything you
build from it. See LICENSE.
