# R vs B Train Game — Design

*Draft — 2026-10-23. Target venue: SecKC / BSidesKC. Audience: security pros, mixed experience.*

A tabletop-diorama ICS Red-vs-Blue game. A self-driving transport truck must deliver
to a power plant before the plant's core process crosses a redline. Blue operates the
plant and the truck; Red starts with no control and must seize it to cause chaos,
steal the truck off the map, or force a meltdown-lockout. An homage to the cheesy
hacker-vs-defender trope: direct contest, hard time limit, dramatic consequences.

**Scope rule (read first):** everything here is *vulnerable by design* in the
Metasploitable / DVWA / GRFICS tradition — known protocol weaknesses and well-known
bug classes, on a network-isolated tabletop. No novel exploits, no faithful clone of
any real safety-critical signalling standard, no internet/real-network route. See
[Safety & isolation](#safety--isolation).

---

## 1. Game shape: asymmetric sabotage

Blue begins in control of everything it needs. **If nobody does anything, Blue wins.**
Red is the sole aggressor; every moment of danger is something Red actively caused.

**Tuning principle (drives the whole sim):** with nominal cooling and the truck on its
normal route, *time-to-redline always exceeds the round length and the truck always
docks*. The default trajectory is a Blue win. Red must degrade that margin faster than
Blue can restore it.

| Outcome | Condition |
|---|---|
| **Blue win (default)** | Truck docks before redline AND plant stays sub-redline for the round |
| **Blue win (clean)** | Above, with no successful Red sabotage milestone — score bonus |
| **Red win (primary)** | Round timer expires with truck not docked, OR truck driven off-map |
| **Red win (secondary)** | Core crosses redline → meltdown-lockout (terminal theater fires) |
| **Draw / partial** | Truck docks but Red logged sabotage milestones — resolved on score |

## 2. Difficulty tiers (Red entry points)

Two ways in, run as separate brackets or back-to-back rounds.

- **Tier 1 — Blackbox (outside-in).** Red starts fully outside with no foothold: only
  RF/WiFi reach to the "enterprise" edge. Must breach the wireless/network boundary
  before any OT traversal. Hard mode; for experienced players.
- **Tier 2 — Attack Van (staged foothold).** Red is handed a jump box on the enterprise
  VLAN — the "attack van" — and jumps off from there. The OT boundary is the real
  challenge, not initial access. Beginner-friendly; nobody is stuck at packet zero.
  *Option:* make the attack van a physical prop on the diorama — a model van housing
  the jump-box Pi.

Both tiers converge on the same OT objective; only the starting line differs.

## 3. Architecture — Purdue model

Maps the board onto real OT architecture so the layout is legible to the audience.

- **Level 0 — physical:** train block power, turnout servos, crossing gates, signal
  LEDs, road stoplights, truck/car motors, siren, smoke generator.
- **Level 1 — field controllers (ESP32):** each ESP32 is a "PLC." Fixed devices speak
  **Modbus/TCP** (no auth, by design — this *is* the realism). Mobile units (truck,
  cars) speak **MQTT** because they roam the WiFi.
- **Level 2 — supervisory (Raspberry Pi):** plant HMI web app, SCADA-style Modbus
  poller, and the game/timer service (the referee).
- **Level 3 — ops (laptops):** scoreboard display, game-master console, team jump boxes.

### Host / service map (draft)

| Device | Lvl | Runs | Attack surface |
|---|---|---|---|
| Plant controller ESP32 | 1 | Modbus/TCP slave: cooling, feed valve, pressure/temp regs, annunciator coil | Coil/register writes = sabotage |
| Signals/crossings ESP32 | 1 | Modbus/TCP slave: gate servos, signal + stoplight LEDs | Flip signals, strand the truck |
| Turnout ESP32 | 1 | Modbus/TCP slave: track switches | Reroute trains into the truck's path |
| Truck (onboard ESP32) | 1 | MQTT: waypoints, go/stop, obstacle sensors | Route injection, geofence disable, sensor spoof |
| Car(s) ESP32 | 1 | MQTT: scripted routes | Hijack into mobile roadblocks |
| Effects ESP32 | 1 | **receive-only** siren/smoke fire line | *none by design* |
| Plant HMI Pi | 2 | Web HMI + Modbus poller | Default creds, cmd injection, missing authz, path traversal |
| Game/timer Pi | 2 | Process sim, scoreboard feed, flag server | Hardened referee |
| Scoreboard / GM laptop | 3 | Display + GM overrides | operator only |

## 4. Network topology & segmentation

Classic IT → DMZ → OT zoning. Up to 10 players per team.

- **Enterprise VLAN/SSID:** where Tier-2's attack van lives and Tier-1 must first reach.
- **DMZ:** historian / HMI-facing services; the pivot Red must cross.
- **OT segment:** Modbus field devices + MQTT broker. No auth on the wire — reaching
  this segment is the exploit.
- **Blue** starts with a legitimate route into OT (they operate it).
- **Game-master segment:** referee + scoreboard, isolated from both teams.

Boundary enforcement is itself a (configurable) Blue asset — see open questions on
whether Blue can harden the DMZ firewall mid-round.

## 5. The plant as a process simulation (the game clock)

The "timer" is not an abstract countdown — it is a live process. The plant ESP32
exposes core **pressure** and **temperature** as Modbus registers. Pressure climbs on
its own; a truck delivery injects coolant/fuel and pushes the redline out. Cross the
redline → meltdown-lockout.

Example register shape (plant controller):

- **Coils (RW bit):** `0 cooling_pump` · `1 feed_valve` · `2 warning_annunciator` · `3 stack_vent`
- **Input regs (RO word):** `0 core_pressure` · `1 core_temp` · `2 time_to_redline` · `3 truck_docked`
- **Holding regs (RW word):** `0 cooling_rate` · `1 pressure_setpoint`

**Red sabotage vectors (OT segment, unauthenticated Modbus):**
- Write `cooling_pump = 0` → pressure climbs faster.
- Raise `cooling_rate` holding reg the wrong way / open `stack_vent`.
- Silence or false-trigger `warning_annunciator` (information warfare, see §7).
- Drive pressure past redline directly for the secondary win.

Because it's Modbus, none of this is authenticated — the skill under test is reaching
the segment and reading the register map, not breaking crypto.

## 6. Mobile units — truck & cars (onboard autonomy)

Both truck and cars carry an onboard ESP32 doing line-following + obstacle avoidance.
They default to running a set route; MQTT carries high-level intent, not motor commands.

- **Truck topics:** waypoint/route, go/stop, geofence enable, obstacle-sensor feed.
- **Car topics:** route select, go/stop.
- **Hijack vectors:** inject a waypoint that leads off the map edge (the "steal the
  truck" win); disable the geofence; spoof an obstacle to force a stall or reroute;
  commandeer cars into blocking the truck's path or a crossing.

Onboard autonomy chosen over remote-brain: the units keep working if WiFi is flaky, and
it yields a richer surface (command channel *and* sensor spoofing).

## 7. Effects — two tiers

- **Terminal loss theater:** stack smoke + big siren. Fires *only* after the game
  service resolves a loss. One-way, dumb, not a target — so Red can't trip the smoke and
  declare victory. Consequence, not cause.
- **Contested annunciator:** low-time warning light/chime + stoplight states. Legitimate
  attackable assets. Red silencing Blue's warning, or false-triggering it as a feint,
  changes *information* only — it can't end the game outright.

Rule of thumb: **consequence effects are dumb; information effects are contested.**

## 8. Scoring (hybrid)

Live score, not just win/lose. Numbers below are a starting economy, not final.

- **Blue:** continuous "plant-stable" uptime points (per tick sub-redline) + large bonus
  for truck delivered + clean-game bonus if Red logged zero sabotage milestones.
- **Red:** per-milestone awards — annunciator silenced, cooling off for N seconds, car
  hijacked, truck driven off-map (primary), meltdown-lockout (secondary, largest).

Milestones are auto-detected by the game service from device state where possible, so
scoring is objective and doesn't rely on self-reporting.

## 9. Flags

Hybrid, matching the scoring:
- **Submittable flags** planted as proof-of-access on compromised hosts (e.g. a flag
  file readable only after a shell on the plant HMI). Classic CTF submission.
- **State-based milestones** auto-detected by the game service (cooling off, truck
  off-map). No string to submit; the board state *is* the proof.

## 10. Hardware inventory (draft — counts TBD)

- ESP32 ×N: plant, signals/crossings, turnouts, effects, truck, each car.
- Raspberry Pi ×2+: HMI, game/timer (+ attack-van jump box for Tier 2).
- Laptops: scoreboard/GM, team workstations.
- Props: siren, water-based fog machine, LEDs, servos, relays for block power.
- Network: managed switch (VLANs) + AP(s) with separate SSIDs per zone.

## 11. Reset model

Round reset must restore: process-sim state, all coil/register values, truck/car routes
and positions, planted flags, firewall config, and scoreboard. Target a one-command or
one-button reset from the GM console. (Design detail TBD.)

## 12. Safety & isolation

- Network-isolated: no route to the internet or any real network. Stated in setup docs.
- All vulnerabilities are known classes / inherent protocol weaknesses; no novel
  exploits authored.
- Fog: water-based fluid, kept clear of electronics; coordinate with venue on smoke
  detectors before running the terminal theater.
- Mains/track power and LiPo handling per normal bench safety.

## Open questions

1. Round length, and the pressure-climb rate that satisfies the Blue-default margin.
2. Can Blue harden the DMZ firewall mid-round, or is segmentation fixed? (A configurable
   boundary gives Blue real defensive agency; a fixed one keeps rounds simpler.)
3. Team-vs-team simultaneous, or Red-and-Blue alternating attempts on the clock?
4. Exact device counts (how many cars, how many crossings/turnouts on the board).
5. Reset mechanism detail.
6. Which planted bug classes go on the HMI (default creds / cmd injection / authz /
   traversal) and at what difficulty per tier.
