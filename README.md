# R vs B Train Game

A tabletop-diorama **Red-vs-Blue ICS hacking game** for SecKC / BSidesKC. A
self-driving transport truck must deliver to a power plant before the plant's
core process crosses a redline. **Blue** operates the plant and the truck;
**Red** starts with no control and must break in to cause chaos — run out the
clock, steal the truck off the map, or force a meltdown-lockout. An homage to
the cheesy hacker-vs-defender movie trope: a direct contest, a hard 20-minute
clock, and dramatic consequences (sirens, smoke out the stacks).

> ### ⚠️ Scope & safety
> This is a **vulnerable-by-design training range**, in the tradition of
> Metasploitable / DVWA / GRFICS. Everything here uses **known, documented bug
> classes and inherent protocol weaknesses** on a **network-isolated** tabletop —
> no novel exploits, no faithful clones of real safety-critical signalling, and
> no route to the internet or any real network. The planted HMI weaknesses are
> catalogued in [`docs/VULNS.md`](docs/VULNS.md), each with a defender's fix.

## How it works

The board is a model-railroad diorama: trains, crossings, switches, stoplights,
self-driving cars, a transport truck, and a power plant. Control software runs
across ESP32s, Raspberry Pis, and laptops, laid out as a real ICS network
(enterprise → DMZ → OT), so the skills map onto actual OT defense and attack.

- **Blue wins by default.** If nobody interferes, the truck docks and the plant
  stays safe. Every moment of danger is something Red actively caused.
- **The clock is a process, not a countdown.** The plant exposes a live core
  **pressure** that climbs on its own and is held down by cooling. Red killing
  cooling (or otherwise tampering) drives pressure to the redline. A truck
  delivery is Blue's primary win.
- **Blue defends live.** Blue can harden and *revert* Red's actions mid-round —
  but the range is offline, so only with tools already on the box (config/source
  edits, restarts, host firewall). No package installs.
- **Two Red entry tiers.** Tier 1 "blackbox" (fully outside, breach the edge
  first) and Tier 2 "attack van" (a staged foothold to jump off from).

Full design — topology, Purdue layering, the Modbus register map, effects, and
open questions — is in [`docs/DESIGN.md`](docs/DESIGN.md).

## Scoring mechanic

Scoring is **hybrid**: a live running score, not just win/lose, so a round is
always a contest even when Blue ultimately holds. Points are auto-detected from
game state (objective — no self-reporting), and Red's harassment milestones are
**edge-triggered**: awarded once per sustained streak, and re-armed if Blue
fixes the problem and Red breaks it again.

**Blue earns:**

| Award | Points | When |
|---|---|---|
| Plant-stable uptime | 1 / sec | every second the plant is sub-redline and the truck isn't stolen |
| Truck delivered | 500 | the truck docks (primary objective) |
| Clean round | 250 | delivered **with zero Red milestones** logged |

**Red earns:**

| Award | Points | When |
|---|---|---|
| Cooling sustained off | 150 | cooling pump held off ≥ 30 s (once per streak) |
| Warning silenced | 75 | the low-time alarm is *due* but forced off ≥ 15 s (once per streak) |
| Truck stolen off-map | 600 | truck driven off the edge (primary win) |
| Meltdown-lockout | 800 | core pressure crosses the redline (secondary win) |
| Timer expired | 600 | 20 min elapse with no delivery (primary win) |

These values are a **starting economy** (tunable in
[`rvb_score/scoring.py`](rvb_score/scoring.py)), not final. The key design
properties:

- **Harassment pays even when Blue wins.** Cutting cooling for a while still
  scores Red, and it denies Blue the clean-round bonus — so Blue is pushed to
  *fix fast*, not just survive.
- **The warning alarm is a contested signal, not just theater.** If the plant
  says the alarm should be sounding and Red has silenced it, Red scores — so
  Blue has to watch the alarm's integrity, not just the pressure.
- **Win conditions are the big payouts**, but a round's final score reflects the
  whole fight, not only who crossed the line.

Worked examples (from `scripts/demo_score.py`):

| Scenario | Outcome | Blue | Red |
|---|---|---|---|
| Nobody acts | Blue delivered (clean) | **1230** | 0 |
| Red cuts cooling, ignored | Meltdown | 431 | **950** |
| Red cuts cooling, Blue reverts at 5 min | Blue delivered (not clean) | **980** | 150 |
| Red cuts cooling **and** silences the alarm | Meltdown | 431 | **1025** |

## What's built

All three software subsystems run entirely on a PC with no hardware — the ESP32
firmware later reimplements the same Modbus register map the sim already defines.

| Area | Where | Status |
|---|---|---|
| Plant process sim + Modbus/TCP slave | [`rvb_sim/`](rvb_sim/) | ✅ |
| Vulnerable plant HMI (IT→OT pivot) | [`rvb_hmi/`](rvb_hmi/) | ✅ |
| Hybrid Blue/Red scoring (pluggable objective registry) | [`rvb_score/`](rvb_score/) | ✅ |
| Subsystem contract + registry (`Subsystem`/`SubsystemRegistry`) | [`rvb_core/`](rvb_core/) | ✅ |
| Subsystems: plant (reference), crossing (first new) | [`subsystems/`](subsystems/) | ✅ |
| Demos (process, HMI, scoreboard) | [`scripts/`](scripts/) | ✅ |
| Tests | [`tests/`](tests/) | ✅ 31 passing |

## Roadmap & progress

Tracked in [`docs/ROADMAP.md`](docs/ROADMAP.md). Summary:

- ✅ **M0** Design & architecture
- ✅ **M1** Process-sim plant + Modbus slave (20-min margin tuned & validated)
- ✅ **M2** Vulnerable plant HMI (4 planted bug classes, all proven exploitable)
- ✅ **M4** Hybrid scoring service
- ⬜ **M3** MQTT truck + cars (onboard autonomy + hijack path)
- ⬜ Live scoreboard web UI
- ⬜ **M5** ESP32 field-device firmware *(hardware)*
- ⬜ **M6** Network/range provisioning (VLANs, two Red tiers, attack van, offline images)
- ⬜ **M7** Blue defensive baseline (base-tool hardening per vuln)
- ⬜ **M8** Effects controller (siren/smoke one-way; annunciator contested)
- ⬜ **M9** GM console + one-button round reset
- ⬜ **M10** Facilitator runbook

### To do next (open questions that shape the hardware work)

See [`docs/DESIGN.md`](docs/DESIGN.md) "Open questions" — the main ones still
open: team-vs-team simultaneous vs alternating attempts, exact device counts,
and which planted bug classes land on the HMI at which difficulty per tier.

## Quick start

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# run the tests
PYTHONPATH=. python -m pytest -q

# watch a 20-minute round play out (pressure gauge, three scenarios)
PYTHONPATH=. python scripts/demo_round.py

# see the scoreboard for each scenario
PYTHONPATH=. python scripts/demo_score.py

# run the plant + HMI live (two terminals)
PYTHONPATH=. python -m rvb_sim.plant_server          # Modbus/TCP on :5020
PYTHONPATH=. python scripts/run_hmi.py               # HMI on http://localhost:8080
```

## Extending the game

New board subsystems (crossings, signals, traffic, trains, switches, cars) and
new scoring objectives are added **without editing the core**, following a
Green-Thumb-style passthrough contract: each subsystem exposes telemetry,
commands, and a self-describing manifest; the core only moves the envelope.
Objectives live in a pluggable registry and reference subsystem signals by name
(works for both teams, supports reclaim/"that's mine!" recoveries and hidden
Easter eggs). The plant is the reference implementation and the board's final
endpoint. Full contract: [`docs/EXTENDING.md`](docs/EXTENDING.md).

## Docs

- [`docs/DESIGN.md`](docs/DESIGN.md) — full architecture & design decisions
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — living build status
- [`docs/EXTENDING.md`](docs/EXTENDING.md) — subsystem & objective contract (how to add things)
- [`docs/VULNS.md`](docs/VULNS.md) — planted HMI vulnerabilities + Blue fixes

## Tech

Python 3.13; `pymodbus` 3.8.x (dev-time stand-in for the ESP32 Modbus devices),
Flask, pytest. The real board adds ESP32 field controllers, Raspberry Pis for
the HMI/game services, and laptops for the scoreboard and team jump boxes.
