"""Round: the 20-minute clock, the truck race, and outcome resolution.

Two races run at once (see docs/DESIGN.md):
    primary   -- truck docks before the round clock expires (and isn't stolen)
    secondary -- core pressure vs the redline (meltdown-lockout)

Outcomes:
    BLUE_DELIVERED  -- truck docked in time; plant sub-redline
    RED_TIMER       -- clock expired, truck not docked
    RED_STOLEN      -- truck driven off the map
    RED_MELTDOWN    -- pressure crossed the redline

A Blue win with zero logged sabotage milestones is a "clean" win (score bonus).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from .config import SimConfig, DEFAULT
from .sim import PlantModel


class Outcome(Enum):
    BLUE_DELIVERED = "blue_delivered"
    RED_TIMER = "red_timer"
    RED_STOLEN = "red_stolen"
    RED_MELTDOWN = "red_meltdown"

    @property
    def blue_won(self) -> bool:
        return self is Outcome.BLUE_DELIVERED


@dataclass
class Truck:
    """Minimal truck for the sim. Real autonomy lives on the ESP32 later.

    progress advances toward 1.0 at nominal speed while moving and not stolen.
    """

    cfg: SimConfig = DEFAULT
    progress: float = 0.0
    moving: bool = True
    stolen: bool = False  # driven off-map by a hijacked waypoint

    def step(self, dt: float) -> None:
        if self.moving and not self.stolen and self.progress < 1.0:
            self.progress += dt / self.cfg.truck_route_seconds

    @property
    def docked(self) -> bool:
        return self.progress >= 1.0 and not self.stolen


# An event is (time_seconds, callable(round) -> None): a scripted Red/Blue act.
Event = tuple[float, Callable[["Round"], None]]


@dataclass
class Round:
    cfg: SimConfig = DEFAULT
    plant: PlantModel = field(default_factory=lambda: PlantModel(DEFAULT))
    truck: Truck = field(default_factory=lambda: Truck(DEFAULT))
    t: float = 0.0
    outcome: Outcome | None = None

    # sabotage bookkeeping for clean-win detection / Red scoring
    cooling_off_seconds: float = 0.0
    sabotage_logged: bool = False

    def __post_init__(self) -> None:
        # keep plant/truck on the same config the round was built with
        self.plant.cfg = self.cfg
        self.truck.cfg = self.cfg

    @property
    def clock_remaining(self) -> float:
        return max(0.0, self.cfg.round_seconds - self.t)

    def _resolve(self) -> Outcome | None:
        if self.truck.stolen:
            self.sabotage_logged = True
            return Outcome.RED_STOLEN
        if self.plant.redlined:
            self.sabotage_logged = True
            return Outcome.RED_MELTDOWN
        if self.truck.docked:
            return Outcome.BLUE_DELIVERED
        if self.t >= self.cfg.round_seconds:
            return Outcome.RED_TIMER
        return None

    def step(self, dt: float | None = None) -> Outcome | None:
        dt = self.cfg.tick_dt if dt is None else dt
        if not self.plant.cooling_pump:
            self.cooling_off_seconds += dt
            self.sabotage_logged = True
        self.plant.step(dt)
        self.truck.step(dt)
        self.t += dt
        self.outcome = self._resolve()
        return self.outcome

    def run(self, events: list[Event] | None = None) -> Outcome:
        """Run to completion, applying scripted events at their timestamps."""
        pending = sorted(events or [], key=lambda e: e[0])
        i = 0
        while self.outcome is None:
            while i < len(pending) and pending[i][0] <= self.t:
                pending[i][1](self)
                i += 1
            self.step()
        return self.outcome

    @property
    def clean_blue_win(self) -> bool:
        return self.outcome is Outcome.BLUE_DELIVERED and not self.sabotage_logged
