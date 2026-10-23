"""PlantSubsystem -- wraps PlantModel as the reference Subsystem.

The plant is the board's final controller and endpoint (see docs/EXTENDING.md
Sec.7): other subsystems feed its outcome, it owns the game clock via the
pressure process, and it drives the terminal theater. Here it is expressed in
the generic contract so every other subsystem can follow the same shape.

Telemetry excludes the warning/annunciator state, which depends on the round
clock and so is resolved at the round level, not inside the plant.
"""

from __future__ import annotations

from rvb_core.subsystem import Subsystem
from rvb_sim.sim import PlantModel


class PlantSubsystem(Subsystem):
    kind = "plant"

    def __init__(self, model: PlantModel, sid: str = "plant"):
        self.id = sid
        self.model = model

    def telemetry(self) -> dict:
        m = self.model
        return {
            "core_pressure": round(m.pressure, 2),
            "core_temp": round(m.temp, 2),
            "cooling_on": m.cooling_pump,
            "feed_valve": m.feed_valve,
            "stack_vent": m.stack_vent,
            "cooling_rate": m.cooling_rate,
            "redlined": m.redlined,
            "time_to_redline": m.time_to_redline(),
        }

    def command(self, action: str, **kw) -> bool:
        m = self.model
        if action == "set_cooling_pump":
            m.cooling_pump = bool(kw["on"])
        elif action == "set_feed_valve":
            m.feed_valve = bool(kw["open"])
        elif action == "set_stack_vent":
            m.stack_vent = bool(kw["open"])
        elif action == "set_cooling_rate":
            m.cooling_rate = float(kw["rate"])
        elif action == "set_annunciator":
            # None = auto, True = forced on, False = forced off (see sim.py)
            m.annunciator_override = kw.get("override")
        else:
            return False
        return True

    def manifest(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "signals": {
                "core_pressure": {"type": "float", "desc": "core pressure process value"},
                "core_temp": {"type": "float", "desc": "core temperature (display)"},
                "cooling_on": {"type": "bool", "desc": "cooling pump running"},
                "feed_valve": {"type": "bool", "desc": "feed valve open (accepts delivery)"},
                "stack_vent": {"type": "bool", "desc": "emergency relief vent open"},
                "cooling_rate": {"type": "float", "desc": "cooling magnitude, PV/s"},
                "redlined": {"type": "bool", "desc": "meltdown-lockout reached"},
                "time_to_redline": {"type": "float", "desc": "projected seconds to redline (inf if safe)"},
            },
            "commands": {
                "set_cooling_pump": {"params": {"on": "bool"}, "control": "blue",
                                     "desc": "run/stop the cooling pump"},
                "set_feed_valve": {"params": {"open": "bool"}, "control": "blue",
                                   "desc": "open/close the feed valve"},
                "set_stack_vent": {"params": {"open": "bool"}, "control": "blue",
                                   "desc": "open/close the emergency relief vent"},
                "set_cooling_rate": {"params": {"rate": "float"}, "control": "blue",
                                     "desc": "set cooling magnitude"},
                "set_annunciator": {"params": {"override": "bool|null"}, "control": "blue",
                                    "desc": "force the alarm on/off, or null for auto"},
            },
            # Everything on the plant is a writable Modbus coil/register, so the
            # whole command set is reachable over the unauthenticated field bus.
            "attack_surface": ["set_cooling_pump", "set_feed_valve", "set_stack_vent",
                               "set_cooling_rate", "set_annunciator"],
        }

    def reset(self) -> None:
        m = self.model
        m.pressure = m.cfg.pressure_start
        m.cooling_pump = True
        m.feed_valve = True
        m.stack_vent = False
        m.cooling_rate = m.cfg.cooling_rate_default
        m.annunciator_override = None
