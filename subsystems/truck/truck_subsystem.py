"""TruckSubsystem -- the self-driving transport truck.

Both guards on by default (geofence + route_lock) and a delivery goal: the
hardest unit to take (see docs/DESIGN.md Sec.6). Stealing it off-map needs the
geofence defeated AND either the route lock defeated (a one-shot off-board
waypoint) or a walked chain of adjacent waypoints.
"""

from __future__ import annotations

from rvb_sim.mobile import Grid
from subsystems._mobile_base import MobileSubsystem


def default_route(grid: Grid) -> list[tuple[float, float]]:
    """A simple straight run from the left edge to the dock."""
    sx, sy = 0, grid.goal[1]
    return [(x, sy) for x in range(1, grid.goal[0] + 1)]


class TruckSubsystem(MobileSubsystem):
    def __init__(self, sid: str = "truck", grid: Grid | None = None):
        grid = grid or Grid()
        super().__init__(sid, "truck", grid, start=(0, grid.goal[1]),
                         route=default_route(grid),
                         route_lock=True, geofence=True, has_goal=True)
