# Car subsystem

A road car on a set loop — **the easy tier**. No route lock and no delivery
goal, so a single on-board `set_waypoint` write commandeers it into a roadblock
(on a crossing, or across the truck's path). Cars are where a newer Red player
gets a first win; the truck is the trophy. `CarSubsystem` wraps the same
[`MobileUnit`](../../rvb_sim/mobile.py) model as the truck, with the guards
relaxed.

## Signals

`x`, `y`, `moving`, `obstacle`, `geofence`, `route_lock`, `off_map` (same as the
truck, minus `delivered` — cars have no goal).

## Commands (control / attack surface)

Same command set as the truck (`set_waypoint`, `go`, `stop`, `set_geofence`,
`set_route_lock`, `set_obstacle`). The difference is the **defaults**:
`route_lock` is **off**, so any on-board waypoint is accepted in one write.

Geofence stays **on** — a car can't be flung off-map (there's nothing to gain
from it, and it keeps the easy tier about *blocking*, not *stealing*).
