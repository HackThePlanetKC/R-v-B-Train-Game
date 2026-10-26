"""MQTT transport for mobile (and other) subsystems.

`bridge` exposes a SubsystemRegistry over MQTT -- the roaming field bus for the
truck and cars (fixed devices use Modbus). Topics:

    rvb/<subsystem_id>/command   {"action": ..., <params>}   (client -> subsystem)
    rvb/<subsystem_id>/state     telemetry JSON (retained)   (subsystem -> clients)

`broker` is a pure-Python amqtt broker for dev/test only; on the real board the
broker is the Home Assistant Mosquitto add-on.
"""
