"""HMI configuration.

Defaults are intentionally weak (this is a CTF target). Blue's hardening path
is to change these on the box, with no package install -- see docs/VULNS.md.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class HmiConfig:
    plant_host: str = "127.0.0.1"
    plant_port: int = 5020

    # PLANTED VULN (default credentials). Blue fix: change these / use env.
    username: str = os.environ.get("HMI_USER", "operator")
    password: str = os.environ.get("HMI_PASS", "operator")

    # Weak, hardcoded session secret -- predictable session forgery. Blue fix:
    # set HMI_SECRET to a long random value.
    secret_key: str = os.environ.get("HMI_SECRET", "change-me-plant-hmi")

    # Control actions the console exposes -> Modbus target (block, address).
    # "coil" writes a single coil; "reg" writes a holding register (PV/s x1000).
    actions: dict[str, tuple[str, int]] = field(default_factory=lambda: {
        "cooling_pump": ("coil", 0),
        "feed_valve": ("coil", 1),
        "annunciator": ("coil", 2),
        "stack_vent": ("coil", 3),
        "cooling_rate": ("reg", 0),
    })


DEFAULT = HmiConfig()
