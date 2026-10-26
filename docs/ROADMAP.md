# R vs B Train Game — Roadmap & Build Status

*Living doc — updated as milestones move. Last updated: 2026-10-26 (M3 complete).*

Design lives in [`DESIGN.md`](DESIGN.md); this tracks **what's planned, what's
done, and what's left**. Status: ✅ done · 🔨 in progress · ⬜ not started.

## Milestones

| # | Milestone | Status | Notes |
|---|---|---|---|
| M0 | Design & architecture | ✅ | `docs/DESIGN.md`; asymmetric shape, Purdue layering, two Red tiers, hybrid scoring |
| M1 | Process-sim plant + Modbus slave | ✅ | `rvb_sim/`; 20-min margin tuned, Modbus sabotage proven |
| M2 | Plant HMI web app (vulnerable, Modbus-wired) | ✅ | `rvb_hmi/`; 4 planted bug classes, all proven exploitable; `docs/VULNS.md` |
| M3 | MQTT truck + cars (autonomy, hijack path) | ✅ | `rvb_sim/mobile.py`, `subsystems/truck`+`car`, `rvb_mqtt/`; layered truck guards, off-map steal → RED_STOLEN |
| M4 | Scoring service (hybrid) | ✅ | `rvb_score/`; snapshot-driven engine, **pluggable objective registry** (both teams) |
| — | Extensibility contract | ✅ | `docs/EXTENDING.md`; subsystem passthrough contract + manifest, objective registry |
| M4b | `Subsystem`/`SubsystemRegistry` base + plant retrofit | ✅ | `rvb_core/`, `subsystems/plant/` (reference) + `subsystems/crossing/` (first new one) |
| M5 | Field-device firmware (ESP32) | ⬜ | Reimplements the §5 register map; **hardware** |
| M6 | Network / range provisioning | ⬜ | VLANs, two Red entry tiers, attack-van jump box, offline images |
| M7 | Blue defensive baseline | ⬜ | Documented base-tool hardening/revert path per planted vuln |
| M8 | Effects controller | ⬜ | Siren/smoke (one-way) + contested annunciator |
| M9 | GM console + round reset | ⬜ | One-button restore of sim/registers/routes/flags/firewall/score |
| M10 | Facilitator runbook | ⬜ | Setup, isolation, reset, per-tier difficulty |

## Done

- **M0** — design doc with all core decisions locked (asymmetric sabotage,
  Blue-default tuning principle, two difficulty tiers, live Blue revert with
  base tools only, plant-as-process-sim clock, two-tier effects, hybrid scoring).
- **M1** — `rvb_sim/`: `PlantModel` process model, `Round` orchestration,
  `plant_server.py` Modbus/TCP slave, demo + 8 passing tests. Margin validated:
  untouched → clean Blue win ~8 min; cooling cut & ignored → meltdown ~7 min;
  cooling cut then Blue reverts → recovery + delivery.
- **M2** — `rvb_hmi/`: deliberately vulnerable Flask HMI on the supervisory layer,
  reads the gauges and drives the Modbus control coils (Red's IT→OT pivot). Four
  planted, documented bug classes — default creds, broken access control, command
  injection, path traversal — each proven exploitable in tests and over live HTTP,
  each with a base-tool Blue fix. Catalogue in `docs/VULNS.md`. 14 tests total.
- **M4** — `rvb_score/`: snapshot-driven hybrid scorer. Blue earns uptime +
  delivery + clean-round bonus; Red earns per-milestone (sustained cooling
  outage, warning silenced) plus win payouts (stolen/meltdown/timer). Takes
  `Snapshot`s (sim now, hardware telemetry later), edge-triggered and
  auto-detected. Contested-annunciator scoring works end to end (silencing a due
  alarm scores Red).
- **Pluggable objective registry + extensibility contract** — objectives are a
  team-agnostic registry with reusable detectors (`rising_edge`, `sustained`,
  `recovery`, `on_outcome`, `when`); adding one is a single entry, no scorer
  surgery. Supports Blue reclaim ("that's mine!"), dormant signal objectives
  (e.g. train derail, fires when a future subsystem supplies the signal), and
  hidden Easter eggs. The subsystem passthrough contract (telemetry + commands +
  self-describing manifest, core never edited) is written up in
  `docs/EXTENDING.md`, with the plant as the reference implementation and the
  board's final endpoint.
- **M4b** — `rvb_core/subsystem.py`: `Subsystem` contract + `SubsystemRegistry`
  (namespaced telemetry map, command routing, reset). `subsystems/plant/` is the
  reference implementation (wraps `PlantModel`, manifest = the Modbus register
  map); `subsystems/crossing/` is the first new subsystem, added with **no core
  or scorer change** — a crossing objective scores both sides end to end
  (`tests/test_subsystem.py`). Snapshots merge the registry's signal map, so
  objectives reference `plant.*` / `crossing.*` by name. Suite now 31 tests.

- **M3** — `rvb_sim/mobile.py` (`MobileUnit` autonomy), `subsystems/truck/` +
  `subsystems/car/` (contract-conforming), and `rvb_mqtt/` (paho bridge + amqtt
  dev broker). The truck is the hardest unit to take: geofence + route-lock
  guards, both must fall (one-shot off-board waypoint, or an adjacent chain) to
  drive it off-map; cars take a single write. Hijack proven end to end over MQTT,
  and a truck steal syncs into the round as RED_STOLEN. 44 tests.
  *Open refinement:* the abstract `Round.Truck` (delivery vs the 20-min clock)
  and the physical `TruckSubsystem` (hijack surface) are still two models; the
  physical truck idles as the hijack target in the scored sim while the abstract
  clock owns delivery. Unifying them is deferred (doesn't block anything).

## In progress

- *(nothing active — awaiting next-target pick)*

## Next up (unordered, pending open questions)

- **Live scoreboard UI** — a small web view over `rvb_score` (like the HMI), once
  we want to see it on a screen rather than in the demo.
- **More subsystems** — signals, stoplights/traffic, switches, trains (the train
  subsystem supplies `train_present` and the dormant `train_derailed` signal).
- **Open design questions still blocking some work** (see DESIGN.md §Open
  questions): team-vs-team vs alternating, device counts, per-tier bug difficulty.

## Notes / environment

- Dev stack: Python 3.13 venv, `pymodbus==3.8.6` (pinned; 3.9+ reworked the
  datastore API), Flask, pytest. All software milestones run in-container with
  no hardware.
