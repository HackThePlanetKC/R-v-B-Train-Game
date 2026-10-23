# R vs B Train Game — Roadmap & Build Status

*Living doc — updated as milestones move. Last updated: 2026-10-23 (M2 complete).*

Design lives in [`DESIGN.md`](DESIGN.md); this tracks **what's planned, what's
done, and what's left**. Status: ✅ done · 🔨 in progress · ⬜ not started.

## Milestones

| # | Milestone | Status | Notes |
|---|---|---|---|
| M0 | Design & architecture | ✅ | `docs/DESIGN.md`; asymmetric shape, Purdue layering, two Red tiers, hybrid scoring |
| M1 | Process-sim plant + Modbus slave | ✅ | `rvb_sim/`; 20-min margin tuned, Modbus sabotage proven |
| M2 | Plant HMI web app (vulnerable, Modbus-wired) | ✅ | `rvb_hmi/`; 4 planted bug classes, all proven exploitable; `docs/VULNS.md` |
| M3 | MQTT truck + cars (autonomy, hijack path) | ⬜ | Waypoint injection / off-map steal; needs a broker |
| M4 | Scoring service (hybrid) | ⬜ | Consumes `Round` outcome + sabotage milestones; live scoreboard |
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

## In progress

- *(nothing active — awaiting next-target pick)*

## Next up (unordered, pending open questions)

- **M3** — MQTT truck + cars (autonomy + hijack path); needs a broker in-container.
- **M4** — scoring service (hybrid), consumes `Round` outcome + sabotage milestones.
- **Open design questions still blocking some work** (see DESIGN.md §Open
  questions): team-vs-team vs alternating, device counts, per-tier bug difficulty.

## Notes / environment

- Dev stack: Python 3.13 venv, `pymodbus==3.8.6` (pinned; 3.9+ reworked the
  datastore API), Flask, pytest. All software milestones run in-container with
  no hardware.
