"""Mobile-unit autonomy model (truck and cars) -- pure, deterministic, no I/O.

A unit follows a queue of waypoints across a grid at a fixed speed. The truck's
committed route is loaded internally (trusted); the `set_waypoint` *command* is
the contested path -- the operator's redirect and Red's hijack both go through
it, subject to two guards:

    geofence   -- rejects any waypoint off the board. MUST be defeated to steal
                  a unit off-map (necessary condition).
    route_lock -- rejects any waypoint that isn't adjacent (Chebyshev <=1) to the
                  unit's current cell. Forces a hijack to be a *chain* of
                  adjacent steps rather than a single teleport to an edge.

So driving the truck off-map needs geofence off AND either route_lock off (a
one-shot far waypoint) or a walked chain of adjacent waypoints (route_lock on).
Cars ship with route_lock off and no goal -- a single on-board waypoint
commandeers one into a roadblock. See docs/DESIGN.md Sec.6.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Grid:
    width: int = 10
    height: int = 8
    goal: tuple[int, int] = (9, 4)   # the plant dock (interior of the right edge)


def _off_board(grid: Grid, x: float, y: float) -> bool:
    return x < 0 or x > grid.width - 1 or y < 0 or y > grid.height - 1


def _chebyshev(a: tuple[float, float], b: tuple[float, float]) -> int:
    return max(abs(round(a[0]) - round(b[0])), abs(round(a[1]) - round(b[1])))


@dataclass
class MobileUnit:
    grid: Grid
    pos: tuple[float, float]
    speed: float = 1.0            # cells per second
    route_lock: bool = True       # truck default on; cars off
    geofence: bool = True
    has_goal: bool = True         # truck delivers to grid.goal; cars don't
    moving: bool = True
    obstacle: bool = False
    off_map: bool = False
    delivered: bool = False
    waypoints: list[tuple[float, float]] = field(default_factory=list)

    # --- route loading (trusted, bypasses guards) ------------------------

    def set_route(self, waypoints: list[tuple[float, float]]) -> None:
        """Load the committed route. Internal/trusted -- not the attack path."""
        self.waypoints = list(waypoints)

    # --- commanded waypoint (guarded: operator redirect AND Red hijack) ---

    def set_waypoint(self, x: float, y: float, replace: bool = False) -> bool:
        """Queue (or replace with) a waypoint. Returns False if a guard rejects
        it -- which is exactly what makes the truck hard to steal."""
        if self.geofence and _off_board(self.grid, x, y):
            return False
        if self.route_lock and _chebyshev(self.pos, (x, y)) > 1:
            return False
        if replace:
            self.waypoints = [(x, y)]
        else:
            self.waypoints.append((x, y))
        return True

    # --- dynamics --------------------------------------------------------

    def step(self, dt: float) -> None:
        if (not self.moving or self.obstacle or self.off_map
                or self.delivered or not self.waypoints):
            return
        tx, ty = self.waypoints[0]
        x, y = self.pos
        dx, dy = tx - x, ty - y
        dist = (dx * dx + dy * dy) ** 0.5
        reach = self.speed * dt
        if dist <= reach or dist == 0:
            self.pos = (tx, ty)
            self.waypoints.pop(0)
        else:
            self.pos = (x + dx / dist * reach, y + dy / dist * reach)

        if _off_board(self.grid, *self.pos):
            self.off_map = True
        elif self.has_goal and _chebyshev(self.pos, self.grid.goal) == 0:
            self.delivered = True

    @property
    def at_goal(self) -> bool:
        return self.delivered
