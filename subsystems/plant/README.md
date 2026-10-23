# Plant subsystem

The **reference implementation** of the [subsystem contract](../../docs/EXTENDING.md)
and the board's **final controller and endpoint**: other subsystems feed its
outcome, it owns the game clock via the pressure process, and it drives the
terminal theater (stack smoke + siren) on a loss.

`PlantSubsystem` wraps the process model in [`rvb_sim/sim.py`](../../rvb_sim/sim.py).
On the real board this is an ESP32 Modbus/TCP slave; the register map in
[`rvb_sim/plant_server.py`](../../rvb_sim/plant_server.py) is this manifest made
concrete.

## Signals (telemetry out)

| Signal | Type | Meaning |
|---|---|---|
| `core_pressure` | float | core pressure process value |
| `core_temp` | float | core temperature (display) |
| `cooling_on` | bool | cooling pump running |
| `feed_valve` | bool | feed valve open (accepts a delivery) |
| `stack_vent` | bool | emergency relief vent open |
| `cooling_rate` | float | cooling magnitude, PV/s |
| `redlined` | bool | meltdown-lockout reached |
| `time_to_redline` | float | projected seconds to redline (`inf` if safe) |

The warning/annunciator state is **not** here — it depends on the round clock,
so it's resolved at the round level (`warning_due` / `annunciator_on`), not
inside the plant.

## Commands (control in / attack surface)

| Command | Params | Who | Effect |
|---|---|---|---|
| `set_cooling_pump` | `on: bool` | blue | run/stop the cooling pump |
| `set_feed_valve` | `open: bool` | blue | open/close the feed valve |
| `set_stack_vent` | `open: bool` | blue | open/close the emergency relief vent |
| `set_cooling_rate` | `rate: float` | blue | set cooling magnitude |
| `set_annunciator` | `override: bool\|null` | blue | force alarm on/off, or `null` for auto |

Every command is a writable Modbus coil/register, so the whole set is reachable
over the unauthenticated field bus — the entire command list is the attack
surface. Red killing `set_cooling_pump(on=False)` is the central sabotage.
