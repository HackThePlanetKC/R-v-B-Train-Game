"""The subsystem passthrough contract and the registry.

A `Subsystem` exposes exactly three things; the core treats their *contents* as
opaque (it never hardcodes a subsystem's field names):

    telemetry() -> dict          named signals OUT (bare keys, no namespace)
    command(action, **kw) -> bool  control surface IN (also the Red attack surface)
    manifest() -> dict           self-description of signals + commands

plus reset() for round reset. The `SubsystemRegistry` collects subsystems,
builds one namespaced signal map (``<id>.<signal>``), and routes commands. See
docs/EXTENDING.md for the full contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Subsystem(ABC):
    id: str      # namespaced + instanced, e.g. "crossing.north", "plant"
    kind: str    # "crossing" | "signal" | "train" | "switch" | "car" | "plant" | ...

    @abstractmethod
    def telemetry(self) -> dict:
        """Flat dict of bare signal names -> values. No namespace prefix here;
        the registry prefixes with ``id``."""

    @abstractmethod
    def command(self, action: str, **kw) -> bool:
        """Apply a command. Returns True if accepted. This is both Blue's
        control path and (over the unauthenticated field bus) Red's."""

    @abstractmethod
    def manifest(self) -> dict:
        """Self-description: {id, kind, signals{...}, commands{...}, attack_surface[...]}"""

    def reset(self) -> None:
        """Return to round-start state. Default no-op; override as needed."""


class SubsystemRegistry:
    def __init__(self) -> None:
        self._subs: dict[str, Subsystem] = {}

    def register(self, sub: Subsystem) -> Subsystem:
        if sub.id in self._subs:
            raise ValueError(f"duplicate subsystem id: {sub.id!r}")
        self._subs[sub.id] = sub
        return sub

    def get(self, sid: str) -> Subsystem | None:
        return self._subs.get(sid)

    def all(self) -> list[Subsystem]:
        return list(self._subs.values())

    def dispatch(self, sid: str, action: str, **kw) -> bool:
        """Route a command to a subsystem. False if the subsystem is unknown."""
        sub = self._subs.get(sid)
        return sub.command(action, **kw) if sub is not None else False

    def telemetry_map(self) -> dict:
        """Merge every subsystem's telemetry into one namespaced signal map:
        ``{"<id>.<signal>": value}``. The core copies this through blind."""
        out: dict = {}
        for sub in self._subs.values():
            for key, val in sub.telemetry().items():
                out[f"{sub.id}.{key}"] = val
        return out

    def manifests(self) -> list[dict]:
        """Every subsystem's manifest -- the discoverable catalog of signals and
        commands available to write objectives against."""
        return [sub.manifest() for sub in self._subs.values()]

    def reset_all(self) -> None:
        for sub in self._subs.values():
            sub.reset()
