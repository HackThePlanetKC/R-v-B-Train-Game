"""Tunable constants for the process sim.

These are the dials. The design principle (see docs/DESIGN.md) is that with
nominal cooling and the truck on its normal route, the default trajectory is a
Blue win: pressure never redlines inside a round, and the truck docks before
the clock expires. Red must actively overcome that margin.

Pressure is a unitless 0..100 "process value" (PV). Rates are PV per second.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SimConfig:
    # --- round / clock ---
    round_seconds: int = 1200          # 20-minute rounds
    tick_dt: float = 1.0               # sim step size (seconds)

    # --- pressure process ---
    pressure_start: float = 40.0       # PV at round start
    pressure_redline: float = 100.0    # meltdown-lockout threshold
    pressure_floor: float = 10.0       # cooling can't push below this

    base_gen: float = 0.167            # natural pressurization, ~10 PV/min
    cooling_rate_default: float = 0.200  # cooling when pump on, ~12 PV/min
    #   net with cooling on = 0.167 - 0.200 = -0.033 PV/s  -> trends to floor
    #   net with cooling off = +0.167 PV/s -> 40->100 in ~360 s (~6 min)
    vent_relief: float = 0.300         # extra relief if Blue opens stack vent

    # --- truck ---
    truck_route_seconds: float = 480.0  # nominal unobstructed dock time (8 min)
    #   default: truck docks (Blue win) at 8 min, well inside the 20-min round

    # --- warning annunciator (contested signal) ---
    warn_redline_seconds: float = 120.0  # warn if projected meltdown within 2 min
    warn_clock_seconds: float = 180.0    # warn if under 3 min left on the round

    # --- Modbus register scaling ---
    pv_scale: int = 10                 # PV stored as int(PV * 10) in registers


DEFAULT = SimConfig()
