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
relay module (they normally include protection) or add the diode yourself.

Do not power a high-torque servo from the microcontroller's regulator.

## No warranty

This is a hobby project provided as-is. You are responsible for anything you
build from it. See LICENSE.
