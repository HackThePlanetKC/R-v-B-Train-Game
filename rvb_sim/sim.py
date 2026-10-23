"""PlantModel: the pure, deterministic process model.

No network, no threads, no wall-clock. `step(dt)` advances the process by dt
seconds. Everything the Modbus slave or the demo mutates goes through this one
object, so there is a single source of truth for plant state.

Control surface (what a Modbus client can write):
    cooling_pump (coil)  -- ON removes pressure. Blue default ON.
                            Red writing OFF is the main sabotage lever.
    feed_valve   (coil)  -- must be OPEN to accept a truck delivery.
    stack_vent   (coil)  -- Blue emergency relief: extra pressure shed.
    cooling_rate (holding) -- magnitude of cooling when the pump is on.

Readback (what a client/HMI sees):
    core_pressure, core_temp, time_to_redline, warning_annunciator
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .config import SimConfig, DEFAULT


@dataclass
class PlantModel:
    cfg: SimConfig = DEFAULT

    pressure: float = field(init=False)
    cooling_pump: bool = field(init=False)   # Blue default ON
    feed_valve: bool = field(init=False)     # Blue default OPEN
    stack_vent: bool = field(init=False)     # default CLOSED
    cooling_rate: float = field(init=False)

    def __post_init__(self) -> None:
        self.pressure = self.cfg.pressure_start
        self.cooling_pump = True
        self.feed_valve = True
        self.stack_vent = False
        self.cooling_rate = self.cfg.cooling_rate_default

    # --- dynamics ---------------------------------------------------------

    def net_rate(self) -> float:
        """Instantaneous pressure change in PV/second at current state."""
        rate = self.cfg.base_gen
        if self.cooling_pump:
            rate -= self.cooling_rate
        if self.stack_vent:
            rate -= self.cfg.vent_relief
        return rate

    def step(self, dt: float) -> None:
        self.pressure += self.net_rate() * dt
        if self.pressure < self.cfg.pressure_floor:
            self.pressure = self.cfg.pressure_floor
        # no upper clamp: the caller checks redline so meltdown is detectable

    # --- derived readouts -------------------------------------------------

    @property
    def temp(self) -> float:
        """Display-only core temperature, tracks pressure. Not load-bearing."""
        return 20.0 + 0.8 * self.pressure

    @property
    def redlined(self) -> bool:
        return self.pressure >= self.cfg.pressure_redline

    def time_to_redline(self) -> float:
        """Projected seconds until meltdown at the current rate.

        math.inf when cooling is winning (rate <= 0) -- pressure is falling,
        so the plant will never redline on its own.
        """
        rate = self.net_rate()
        if rate <= 0:
            return math.inf
        return (self.cfg.pressure_redline - self.pressure) / rate

    def warning_active(self, clock_remaining: float) -> bool:
        """The contested low-time annunciator.

        True when meltdown is projected soon, or the round clock is nearly up.
        On hardware this drives a coil Red can silence or false-trigger.
        """
        return (
            self.time_to_redline() <= self.cfg.warn_redline_seconds
            or clock_remaining <= self.cfg.warn_clock_seconds
        )
