"""MqttBridge -- exposes a SubsystemRegistry over MQTT.

Subscribes to ``<prefix>/<id>/command`` and dispatches the JSON envelope to the
matching subsystem; publishes each subsystem's telemetry to
``<prefix>/<id>/state`` (retained). This is the roaming field bus and, since it
is unauthenticated by design, the Red attack surface for mobile units.

The bridge does not step the units -- a game loop (or the dev runner) does that
and calls `publish_telemetry()`.
"""

from __future__ import annotations

import json

import paho.mqtt.client as mqtt

from rvb_core.subsystem import SubsystemRegistry


class MqttBridge:
    def __init__(self, registry: SubsystemRegistry, host: str = "127.0.0.1",
                 port: int = 1883, prefix: str = "rvb"):
        self.registry = registry
        self.host = host
        self.port = port
        self.prefix = prefix
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        client.subscribe(f"{self.prefix}/+/command")

    def _on_message(self, client, userdata, msg):
        parts = msg.topic.split("/")
        if len(parts) != 3 or parts[2] != "command":
            return
        sid = parts[1]
        try:
            payload = json.loads(msg.payload.decode())
        except (ValueError, UnicodeDecodeError):
            return
        action = payload.pop("action", None)
        if action:
            self.registry.dispatch(sid, action, **payload)

    def start(self) -> None:
        self.client.connect(self.host, self.port)
        self.client.loop_start()

    def stop(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()

    def publish_telemetry(self) -> None:
        for sub in self.registry.all():
            topic = f"{self.prefix}/{sub.id}/state"
            self.client.publish(topic, json.dumps(sub.telemetry()), retain=True)
