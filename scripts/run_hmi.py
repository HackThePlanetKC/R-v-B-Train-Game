#!/usr/bin/env python3
"""Run the plant HMI against a running plant Modbus slave.

    # terminal 1: the plant
    PYTHONPATH=. python -m rvb_sim.plant_server
    # terminal 2: the HMI
    PYTHONPATH=. python scripts/run_hmi.py        # http://localhost:8080
"""

from __future__ import annotations

import os

from rvb_hmi.app import create_app
from rvb_hmi.config import HmiConfig

if __name__ == "__main__":
    cfg = HmiConfig(
        plant_host=os.environ.get("PLANT_HOST", "127.0.0.1"),
        plant_port=int(os.environ.get("PLANT_PORT", "5020")),
    )
    create_app(cfg).run(host="0.0.0.0", port=int(os.environ.get("HMI_PORT", "8080")))
