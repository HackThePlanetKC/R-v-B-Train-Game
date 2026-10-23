"""Core game contract shared across subsystems.

`subsystem` defines the passthrough contract every board subsystem implements
(telemetry out, commands in, a self-describing manifest) and the registry that
assembles their telemetry into one namespaced signal map. See docs/EXTENDING.md.
"""
