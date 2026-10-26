"""CarSubsystem -- a road car on a set loop.

No route lock and no delivery goal: a single on-board `set_waypoint` write
commandeers it into a roadblock (on a crossing, or across the truck's path).
Cars are the easy tier where a newer Red player gets a first win; the truck is
the trophy. Geofence stays on so a car can't be flung off-map (nothing to gain).
"""

from __future__ import annotations

from rvb_sim.mobile import Grid
from subsystems._mobile_base import MobileSubsystem


class CarSubsystem(MobileSubsystem):
    def __init__(self, sid: str, grid: Grid | None = None,
                 start: tuple[float, float] = (2, 0),
                 route: list[tuple[float, float]] | None = None):
        grid = grid or Grid()
        super().__init__(sid, "car", grid, start=start,
                         route=route or [(2, 0), (2, 7)],
                         route_lock=False, geofence=True, has_goal=False)
