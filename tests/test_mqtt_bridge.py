"""End-to-end over MQTT: Red defeats the truck guards via command topics
(in), and the truck's stolen state comes back on the state topic (out).

Uses the in-process amqtt dev broker. A bit heavier than the pure tests.
"""

import json
import time

import pytest

import paho.mqtt.client as mqtt

from rvb_core.subsystem import SubsystemRegistry
from subsystems.truck import TruckSubsystem
from rvb_mqtt.broker import DevBroker
from rvb_mqtt.bridge import MqttBridge

PORT = 1890


@pytest.fixture
def broker():
    b = DevBroker(port=PORT)
    b.start()
    time.sleep(0.4)
    yield b
    b.stop()


def _client():
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.connect("127.0.0.1", PORT)
    c.loop_start()
    return c


def test_hijack_commands_in_and_stolen_state_out(broker):
    reg = SubsystemRegistry()
    truck = reg.register(TruckSubsystem())
    truck.unit.set_route([])                 # idle hijack target

    bridge = MqttBridge(reg, port=PORT)
    bridge.start()
    time.sleep(0.3)

    seen = {}
    sub = _client()
    sub.on_message = lambda c, u, m: seen.update(state=json.loads(m.payload))
    sub.subscribe("rvb/truck/state")
    time.sleep(0.2)

    pub = _client()

    def cmd(d):
        pub.publish("rvb/truck/command", json.dumps(d))
        time.sleep(0.15)

    # Red, over MQTT, defeats both guards and points the truck off the board.
    cmd({"action": "set_geofence", "on": False})
    cmd({"action": "set_route_lock", "on": False})
    cmd({"action": "set_waypoint", "x": -1, "y": 4, "replace": True})
    time.sleep(0.2)
    assert truck.unit.geofence is False      # command arrived through the broker

    # The game loop steps the unit; the bridge publishes telemetry.
    truck.step(1.0)
    bridge.publish_telemetry()
    time.sleep(0.3)

    assert seen.get("state", {}).get("off_map") is True   # stolen state came back out

    pub.loop_stop(); pub.disconnect()
    sub.loop_stop(); sub.disconnect()
    bridge.stop()
