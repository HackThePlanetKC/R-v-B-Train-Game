# Crossing subsystem

A level crossing (gates + warning bell). The **first subsystem built to the
[contract](../../docs/EXTENDING.md) after the plant**, to prove the pattern:
adding it and scoring objectives over it needed **no change to the game core or
the scorer**.

On the real board this is an ESP32 driving gate servos and a bell, exposed as a
Modbus slave; `CrossingSubsystem` is the software stand-in.

## Signals (telemetry out)

| Signal | Type | Meaning |
|---|---|---|
| `gates_down` | bool | gates lowered |
| `bell` | bool | warning bell active |
| `train_present` | bool | a train occupies the crossing block |

## Commands (control in / attack surface)

| Command | Params | Who | Effect |
|---|---|---|---|
| `set_gates` | `down: bool` | blue | raise/lower the gates |
| `set_bell` | `on: bool` | blue | sound/silence the bell |
| `set_train` | `present: bool` | system | block occupancy (placeholder) |

`set_gates` and `set_bell` are the attack surface. `set_train` is a placeholder:
once the **train subsystem** exists it will drive `train_present`, and this
command goes away.

## The contested shape

Per [EXTENDING §7](../../docs/EXTENDING.md), a crossing exposes a "what it should
be" vs "what it is": gates *should* be down when `train_present`. Gates held
down with **no** train is a Red harassment target — it strands road traffic and
the truck. The shipped example objectives score exactly that gap: Red for
holding the crossing against traffic, Blue for clearing it ("that's mine!").
