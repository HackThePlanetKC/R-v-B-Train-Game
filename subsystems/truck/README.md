# Truck subsystem

The self-driving transport truck — **the hardest unit to take, by design** (see
[DESIGN §6](../../docs/DESIGN.md)). Onboard autonomy: follows a committed route
to the plant dock; MQTT carries high-level intent, not motor commands.
`TruckSubsystem` wraps the [`MobileUnit`](../../rvb_sim/mobile.py) model; on the
board it's an ESP32 doing line-follow + obstacle avoidance.

## Signals

| Signal | Type | Meaning |
|---|---|---|
| `x`, `y` | float | grid position |
| `moving` | bool | under power |
| `obstacle` | bool | obstacle sensor asserted (holds the truck) |
| `geofence` | bool | off-board waypoints rejected |
| `route_lock` | bool | only adjacent waypoints accepted |
| `off_map` | bool | driven off the edge — **stolen** |
| `delivered` | bool | reached the plant dock |

## Commands (control / attack surface)

| Command | Params | Effect |
|---|---|---|
| `set_waypoint` | `x, y, replace` | queue/redirect a waypoint (**guarded**) |
| `go` / `stop` | — | resume / halt |
| `set_geofence` | `on` | enable/disable the off-board guard |
| `set_route_lock` | `on` | enable/disable the adjacent-only guard |
| `set_obstacle` | `on` | obstacle sensor (spoofable) |

## The two guards (why the truck is hard to steal)

- **geofence** — rejects any off-board waypoint. **Necessary** to defeat for a
  steal; on its own it makes the truck unstealable.
- **route_lock** — rejects any non-adjacent waypoint. Forces a hijack to be a
  *chain* of adjacent steps, not a single teleport to an edge.

So an off-map steal needs geofence **off** AND either route_lock **off** (a
one-shot far waypoint) or a walked adjacent chain. Both guards are
Blue-revertible mid-round, so a half-finished heist can be clawed back
("that's mine!"). Cars, by contrast, take one write — see `subsystems/car/`.
