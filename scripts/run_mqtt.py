#!/usr/bin/env python3
"""Run the dev MQTT broker + bridge with a truck and two cars, stepping them.

    PYTHONPATH=. python scripts/run_mqtt.py        # broker on :1883

Then drive a unit from another shell, e.g.:
    mosquitto_pub -t rvb/truck/command -m '{"action":"set_geofence","on":false}'
or any MQTT client. Subscribe to rvb/+/state to watch telemetry.
"""

from __future__ import annotations

import os
import time

from rvb_core.subsystem import SubsystemRegistry
from rvb_mqtt.broker import DevBroker
from rvb_mqtt.bridge import MqttBridge
from subsystems.truck import TruckSubsystem
from subsystems.car import CarSubsystem

if __name__ == "__main__":
    port = int(os.environ.get("MQTT_PORT", "1883"))
    reg = SubsystemRegistry()
    reg.register(TruckSubsystem())
    reg.register(CarSubsystem("car.1"))
    reg.register(CarSubsystem("car.2", start=(6, 0), route=[(6, 0), (6, 7)]))

    broker = DevBroker(port=port)
    broker.start()
    bridge = MqttBridge(reg, port=port)
    bridge.start()
    print(f"broker + bridge on :{port}; topics rvb/<id>/command and rvb/<id>/state")
    try:
        while True:
            for sub in reg.all():
                if getattr(sub, "kind", None) in ("truck", "car"):
                    sub.step(1.0)
            bridge.publish_telemetry()
            time.sleep(1.0)
    except KeyboardInterrupt:
        bridge.stop()
        broker.stop()
