"""Shared base for mobile-unit subsystems (truck, cars).

Wraps a `MobileUnit` in the subsystem contract. Truck and car differ only in
their guard defaults and whether they have a delivery goal, so the telemetry,
command, manifest, and reset logic live here once.
"""

from __future__ import annotations

from rvb_core.subsystem import Subsystem
from rvb_sim.mobile import Grid, MobileUnit


class MobileSubsystem(Subsystem):
    def __init__(self, sid: str, kind: str, grid: Grid, start: tuple[float, float],
                 route: list[tuple[float, float]] | None = None,
                 route_lock: bool = True, geofence: bool = True,
                 has_goal: bool = True, speed: float = 1.0):
        self.id = sid
        self.kind = kind
        self._init = dict(grid=grid, start=start, route=list(route or []),
                          route_lock=route_lock, geofence=geofence,
                          has_goal=has_goal, speed=speed)
        self.unit = self._fresh_unit()

    def _fresh_unit(self) -> MobileUnit:
        c = self._init
        u = MobileUnit(grid=c["grid"], pos=c["start"], speed=c["speed"],
                       route_lock=c["route_lock"], geofence=c["geofence"],
                       has_goal=c["has_goal"])
        u.set_route(c["route"])
        return u

    def step(self, dt: float) -> None:
        self.unit.step(dt)

    def telemetry(self) -> dict:
        u = self.unit
        t = {
            "x": round(u.pos[0], 3),
            "y": round(u.pos[1], 3),
            "moving": u.moving,
            "obstacle": u.obstacle,
            "geofence": u.geofence,
            "route_lock": u.route_lock,
            "off_map": u.off_map,
        }
        if u.has_goal:
            t["delivered"] = u.delivered
        return t

    def command(self, action: str, **kw) -> bool:
        u = self.unit
        if action == "set_waypoint":
            return u.set_waypoint(float(kw["x"]), float(kw["y"]),
                                  replace=bool(kw.get("replace", False)))
        if action == "go":
            u.moving = True
        elif action == "stop":
            u.moving = False
        elif action == "set_geofence":
            u.geofence = bool(kw["on"])
        elif action == "set_route_lock":
            u.route_lock = bool(kw["on"])
        elif action == "set_obstacle":          # sensor spoof surface
            u.obstacle = bool(kw["on"])
        else:
            return False
        return True

    def manifest(self) -> dict:
        signals = {
            "x": {"type": "float", "desc": "grid x position"},
            "y": {"type": "float", "desc": "grid y position"},
            "moving": {"type": "bool", "desc": "under power"},
            "obstacle": {"type": "bool", "desc": "obstacle sensor asserted (holds the unit)"},
            "geofence": {"type": "bool", "desc": "off-board waypoints rejected"},
            "route_lock": {"type": "bool", "desc": "only adjacent waypoints accepted"},
            "off_map": {"type": "bool", "desc": "driven off the board edge (stolen)"},
        }
        if self._init["has_goal"]:
            signals["delivered"] = {"type": "bool", "desc": "reached the plant dock"}
        return {
            "id": self.id,
            "kind": self.kind,
            "signals": signals,
            "commands": {
                "set_waypoint": {"params": {"x": "float", "y": "float", "replace": "bool"},
                                 "control": "blue", "desc": "queue/redirect a waypoint (guarded)"},
                "go": {"params": {}, "control": "blue", "desc": "resume motion"},
                "stop": {"params": {}, "control": "blue", "desc": "halt"},
                "set_geofence": {"params": {"on": "bool"}, "control": "blue",
                                 "desc": "enable/disable the off-board guard"},
                "set_route_lock": {"params": {"on": "bool"}, "control": "blue",
                                   "desc": "enable/disable the adjacent-only guard"},
                "set_obstacle": {"params": {"on": "bool"}, "control": "system",
                                 "desc": "obstacle sensor (spoofable)"},
            },
            # The guards themselves are writable over the bus -- that's what makes
            # a heist possible (and Blue's re-arm possible).
            "attack_surface": ["set_waypoint", "set_geofence", "set_route_lock",
                               "set_obstacle"],
        }

    def reset(self) -> None:
        self.unit = self._fresh_unit()
