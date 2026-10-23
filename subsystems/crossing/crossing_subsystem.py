"""CrossingSubsystem -- a level crossing (gates + warning bell).

The first subsystem built to the contract after the plant, to prove the pattern:
no scorer or core change was needed to score objectives over it. On the real
board this is an ESP32 driving gate servos and a bell, as a Modbus slave; here
it is the software stand-in.

`train_present` is a convenience the train subsystem will eventually drive; it's
exposed as a command now so crossing objectives can be exercised before trains
exist. The "contested" shape from docs/EXTENDING.md Sec.7 applies: a crossing
held down with no train present is a Red harassment target (stranding road
traffic / the truck), the gap between "should be down" (a train is coming) and
"is down".
"""

from __future__ import annotations

from rvb_core.subsystem import Subsystem


class CrossingSubsystem(Subsystem):
    kind = "crossing"

    def __init__(self, sid: str):
        self.id = sid
        self.gates_down = False
        self.bell = False
        self.train_present = False

    def telemetry(self) -> dict:
        return {
            "gates_down": self.gates_down,
            "bell": self.bell,
            "train_present": self.train_present,
        }

    def command(self, action: str, **kw) -> bool:
        if action == "set_gates":
            self.gates_down = bool(kw["down"])
        elif action == "set_bell":
            self.bell = bool(kw["on"])
        elif action == "set_train":            # placeholder until the train subsystem exists
            self.train_present = bool(kw["present"])
        else:
            return False
        return True

    def manifest(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "signals": {
                "gates_down": {"type": "bool", "desc": "crossing gates lowered"},
                "bell": {"type": "bool", "desc": "warning bell active"},
                "train_present": {"type": "bool", "desc": "a train is in the crossing block"},
            },
            "commands": {
                "set_gates": {"params": {"down": "bool"}, "control": "blue",
                              "desc": "raise/lower the gates"},
                "set_bell": {"params": {"on": "bool"}, "control": "blue",
                             "desc": "sound/silence the bell"},
                "set_train": {"params": {"present": "bool"}, "control": "system",
                              "desc": "block occupancy (train subsystem drives this later)"},
            },
            "attack_surface": ["set_gates", "set_bell"],
        }

    def reset(self) -> None:
        self.gates_down = False
        self.bell = False
        self.train_present = False
