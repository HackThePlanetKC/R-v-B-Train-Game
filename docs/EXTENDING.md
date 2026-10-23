# Extending the game — the subsystem & objective contract

How to add new board subsystems (crossings, signals, traffic, trains, switches,
cars — and ones not thought of yet) and new scoring objectives **without editing
the core**. The pattern is lifted from the Green Thumb module contract: the core
never interprets a subsystem's internals, it only moves a fixed, documented
envelope through. Add hardware or an objective by *registering* it, not by
editing the referee.

This contract is **transport-agnostic**. A subsystem is the software sim today
and an ESP32 on the real board later; the objective that scores it doesn't
change. Telemetry maps to Modbus input registers / an MQTT state topic; commands
map to coils-holding-registers / an MQTT command topic. The game core only ever
sees the envelope.

---

## 1. The three fixed things (everything else is opaque)

Every subsystem exposes exactly these, and the core treats all field *contents*
as passthrough — it does not hardcode any subsystem's field names:

1. **Telemetry out** — a flat dict of named signals the subsystem publishes.
2. **Commands in** — a generic `command(action, **params)` envelope. This is
   also the Blue control surface and the Red attack surface.
3. **A manifest** — the subsystem self-describes its signals and commands, so
   objectives, the scoreboard, the HMI, and *you* can discover what exists to
   write rules against — including hooks for objectives not yet imagined.

Plus a `reset()` for round reset (M9) and a stable, namespaced `id`.

> **Built:** the base lives in [`rvb_core/subsystem.py`](../rvb_core/subsystem.py)
> (`Subsystem` + `SubsystemRegistry`). The plant is the reference implementation
> ([`subsystems/plant/`](../subsystems/plant/)); the crossing
> ([`subsystems/crossing/`](../subsystems/crossing/)) is the first new subsystem,
> added with no core/scorer change.

```python
class Subsystem:
    id: str      # namespaced + instanced: "crossing.north", "signals.main", "plant"
    kind: str    # "crossing" | "signal" | "train" | "switch" | "car" | "plant" | ...

    def telemetry(self) -> dict: ...          # signals OUT  -> merged into the snapshot
    def command(self, action: str, **kw) -> bool: ...   # control / attack surface IN
    def manifest(self) -> dict: ...           # self-description (see Sec.3)
    def reset(self) -> None: ...              # back to round-start state
```

## 2. Signal naming

Signals live in one flat, namespaced map so an objective can reference any
subsystem by name. Convention:

```
<subsystem.id>.<signal>
```

e.g. `plant.core_pressure`, `crossing.north.gates_down`, `signals.main.all_red`,
`truck.off_route`. Lowercase snake for signal names; dots for hierarchy. The
registry builds this map by prefixing each subsystem's `telemetry()` keys with
its `id` — the subsystem itself only returns bare keys (`{"gates_down": True}`).

## 3. The manifest (the discoverable hook list)

This is the one addition over Green Thumb's contract, and the most useful part:
each subsystem declares what it emits and accepts, so you can see the available
hooks without reading source. Shape:

```python
{
  "id": "crossing.north",
  "kind": "crossing",
  "signals": {
     "gates_down": {"type": "bool", "desc": "crossing gates are lowered"},
     "bell":       {"type": "bool", "desc": "warning bell active"},
  },
  "commands": {
     "set_gates": {"params": {"down": "bool"}, "control": "blue",
                   "desc": "raise/lower the gates"},
  },
  "attack_surface": ["set_gates"],   # commands reachable over the unauthenticated bus
}
```

- `control` names who *legitimately* drives a command (usually `blue`).
- `attack_surface` lists the commands reachable over the field bus (Modbus/MQTT,
  unauthenticated by design) — i.e. what Red can hit once on-segment. Keeping
  this explicit is the same spirit as flagging "known simplifications" rather
  than hiding them.

## 4. The registry — how a snapshot is assembled

A `SubsystemRegistry` (the analog of Green Thumb's `module_manager`) owns the
set of subsystems, assembles the game-state `Snapshot`, and routes commands.

```python
def build_snapshot(registry, round_meta) -> Snapshot:
    signals = {}
    for sub in registry.all():
        for key, val in sub.telemetry().items():
            signals[f"{sub.id}.{key}"] = val          # namespaced, passthrough
    return Snapshot(..., signals=signals, **round_meta)  # round_meta = t, clock, outcome

registry.dispatch("crossing.north", "set_gates", down=True)   # command routing
```

The core merges telemetry blindly. It never needs to know `crossing` exists.
Commands from the HMI (Modbus write) or an MQTT client land on
`registry.dispatch(...)` — so the same call is the legitimate control path *and*
the thing Red exercises when they reach the bus.

> **Current state vs target.** `Snapshot` already carries a `signals` dict
> (ready for this) alongside typed convenience fields (`pressure`, `cooling_on`,
> …) that today come straight from the plant. New subsystems go under `signals`
> immediately. The typed plant fields stay as back-compat conveniences and will
> later be *derived* from `signals["plant.*"]`; no rule needs to change when that
> happens, because detectors can read either (see Sec.6).

## 5. Adding a subsystem (the checklist)

1. New directory `subsystems/<kind>/` with the subsystem class, its own
   `README.md`, and — if it has hardware — its own `BUILD.md`. **Do not** fold
   it into the core or another subsystem's docs (same rule as Green Thumb's
   `modules/` layout).
2. Implement `telemetry()`, `command()`, `manifest()`, `reset()`.
3. Register it with the `SubsystemRegistry` at startup.
4. Later, the ESP32 firmware reimplements the same signals/commands over Modbus
   or MQTT; the register map / topic shape is the manifest made concrete.

That's it — the scorer, the HMI, and the snapshot assembly are untouched.

## 6. Adding an objective

Objectives live in the scoring registry (`rvb_score/scoring.py`) and reference
signals **by name**. Adding one is a single entry — no scorer surgery. The
detector factories cover the common shapes:

| Factory | Fires when | Use for |
|---|---|---|
| `rising_edge("sig")` | signal goes false→true | derail, breach, gate forced |
| `sustained(pred, secs)` | `pred` held N seconds (once per streak) | cooling off, alarm silenced, gridlock |
| `recovery(pred)` | a bad condition clears (true→false) | "that's mine!" reclaim |
| `on_outcome(Outcome.X)` | a terminal result | win conditions |
| `when(fn)` | arbitrary `fn(snapshot, scorer)` | hidden/compound eggs |

```python
# A Red objective over a traffic subsystem — zero core edits. Use .get() so the
# rule is harmless (dormant) if the subsystem isn't present on a given board.
Objective("red_gridlock", "red", 200, "junction gridlocked",
          detect=sustained(lambda s: s.signals.get("crossing.north.gates_down")
                                  and s.signals.get("signals.main.all_red"), 20),
          repeatable=True)
```

Instance-specific objectives (tied to `crossing.north`) are registered
*alongside* their subsystem, not in the default registry; board-wide ones (plant,
truck, derail) ship as defaults. See `tests/test_subsystem.py` for a crossing
objective scoring both sides end to end.

Rules for both teams, same mechanism:
- `team` is `"blue"` or `"red"`.
- `repeatable=True` lets a milestone re-fire (once per streak/recovery).
- `hidden=True` keeps it off the published `catalog()` until it fires — the
  Easter-egg switch. Available to either side.
- Detectors read `s.signals["<id>.<sig>"]` for subsystem signals, or a typed
  `Snapshot` attribute for the core plant/truck fields — both work, which is why
  the typed→derived migration in Sec.4 is safe.

When a referenced signal doesn't exist yet (its subsystem isn't built), the
objective is simply dormant — `rising_edge("train_derailed")` already ships this
way and fires the moment a train subsystem supplies that signal.

## 7. The plant is the reference implementation — and the final endpoint

The plant is written up first against this contract, for two reasons:

- **It proves the pattern** the way Green Thumb's camera module proves the
  module contract. `telemetry()` → core pressure/temp/time-to-redline/annunciator;
  `command()` → cooling pump, feed valve, stack vent, cooling rate, annunciator
  override; `manifest()` → the Modbus register map, made explicit.
- **It is the final controller and endpoint of the whole board**, not just one
  box among many. The truck's delivery is a signal *into* the plant
  (`plant.truck_docked`); the plant owns the game clock (the pressure process);
  and the plant is the subsystem that drives the terminal theater — the stack
  smoke and the big siren fire from the plant resolving a loss. Every other
  subsystem ultimately feeds the plant's outcome. Tying the contract's reference
  implementation to the board's dramatic sink keeps the software model and the
  table's aesthetics the same shape.

The contested annunciator is the template for "a subsystem signal that is both a
Blue responsibility and a Red target": the plant *recommends* the alarm
(`plant.warning_due`), something drives the actual annunciator
(`plant.annunciator_on`), and the gap between them is scorable (Red silencing a
due alarm). New subsystems should expose their contested state the same way — a
"what it should be" signal and a "what it is" signal — so objectives can score
the divergence.

## 8. Open contract points (flagged, not hidden)

Following Green Thumb's habit of naming the not-yet-done rather than papering
over it:

- **Manifest versioning** — no version field yet. Add one before a subsystem's
  signals/commands change shape across firmware revisions.
- **Reset semantics** — `reset()` is specified but the round-reset orchestration
  (M9) that calls every subsystem's `reset()` + restores flags/firewall/score
  isn't built.
- **Health / contribution aggregation** — Green Thumb has an unwired
  `on_module_health` hook; the equivalent here (a subsystem contributing to an
  overall board-health or an objective) is intentionally not defined until a
  real subsystem needs it.
- **Signal typing** — the manifest declares types as strings (`"bool"`,
  `"int"`); nothing enforces them yet. Fine at this scale; revisit if objectives
  start depending on ranges/units.
```
