"""Hybrid Blue/Red scorer, driven by game-state snapshots.

Objectives live in a registry, not in hardcoded branches. Each `Objective` is a
self-contained rule for either team; the scorer just runs them every tick.
Adding an objective -- a new Red win, a Blue reclaim, a hidden Easter egg -- is
one entry in `default_objectives()` (or appended at runtime), no scorer surgery.

Objective kinds (pick one per rule):
    detect(snap, dt, mem, scorer) -> bool   event: award `points` when it fires
    accrue(snap) -> bool                    continuous: award `points`/sec while true

Reusable detector factories cover the common shapes: `rising_edge` (a signal
goes true: derail, breach), `sustained` (a bad condition held N seconds, once
per streak: cooling off, alarm silenced), `recovery` (a bad condition cleared:
the "that's mine!" reclaim), `on_outcome` (a terminal result), and `when` (any
predicate over snapshot + live score, for hidden/compound eggs).

Point values are a starting economy (see docs/DESIGN.md Sec.8), not final.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from rvb_sim.config import SimConfig, DEFAULT
from rvb_sim.game import Round, Outcome


@dataclass(frozen=True)
class Snapshot:
    """A single tick of game state, all the scorer needs.

    `signals` carries named booleans/values from subsystems that don't have a
    typed field yet (trains, switches, cars), so new objectives can reference
    them without changing this dataclass each time.
    """

    t: float
    clock_remaining: float
    pressure: float
    redlined: bool
    cooling_on: bool
    warning_due: bool
    annunciator_on: bool
    truck_docked: bool
    truck_stolen: bool
    outcome: Outcome | None
    signals: dict = field(default_factory=dict)

    @classmethod
    def from_round(cls, r: Round, registry=None, signals: dict | None = None) -> "Snapshot":
        """Build a snapshot from the Round's typed state. If a SubsystemRegistry
        is given, its namespaced telemetry map is merged into `signals` so
        objectives can reference any subsystem (plant.*, crossing.*, ...)."""
        sig = dict(signals) if signals else {}
        if registry is not None:
            sig.update(registry.telemetry_map())
        return cls(
            t=r.t,
            clock_remaining=r.clock_remaining,
            pressure=r.plant.pressure,
            redlined=r.plant.redlined,
            cooling_on=r.plant.cooling_pump,
            warning_due=r.warning_due,
            annunciator_on=r.annunciator_on,
            truck_docked=r.truck.docked,
            truck_stolen=r.truck.stolen,
            outcome=r.outcome,
            signals=sig,
        )


@dataclass(frozen=True)
class ScoreConfig:
    # Blue
    blue_uptime_per_sec: float = 1.0   # accrued each second the plant is safe
    blue_delivery: float = 500.0       # truck docked
    blue_clean: float = 250.0          # delivered with zero Red milestones
    blue_reclaim: float = 120.0        # "that's mine!" -- regained a sabotaged system

    # Red harassment milestones (repeatable, once per sustained streak)
    cooling_cut_seconds: float = 30.0
    red_cooling_cut: float = 150.0
    silence_seconds: float = 15.0
    red_silence: float = 75.0
    red_derail: float = 250.0          # a train derailed (signal lands with M3/M5)

    # Red win conditions (one-time)
    red_truck_stolen: float = 600.0
    red_meltdown: float = 800.0
    red_timer: float = 600.0


@dataclass
class ScoreEvent:
    t: float
    team: str          # "blue" | "red"
    label: str
    points: float
    objective_id: str = ""


# A detector: did this objective fire on this tick?
Detector = Callable[[Snapshot, float, dict, "Scorer"], bool]


@dataclass
class Objective:
    id: str
    team: str                      # "blue" | "red"
    points: float
    label: str
    detect: Detector | None = None            # event-style
    accrue: Callable[[Snapshot], bool] | None = None  # continuous-style
    repeatable: bool = False       # event objectives: may fire more than once
    hidden: bool = False           # Easter egg: omit from the catalog until fired


# --- detector factories ---------------------------------------------------

def rising_edge(name: str) -> Detector:
    """Fire once when `name` (a snapshot signal or attribute) goes false->true."""
    def d(s: Snapshot, dt: float, mem: dict, sc: "Scorer") -> bool:
        cur = bool(s.signals.get(name, getattr(s, name, False)))
        prev = mem.get("prev", False)
        mem["prev"] = cur
        return cur and not prev
    return d


def sustained(pred: Callable[[Snapshot], bool], seconds: float) -> Detector:
    """Fire once when `pred` has held continuously for `seconds`; re-arm when it
    clears. Pair with repeatable=True to reward repeated sabotage."""
    def d(s: Snapshot, dt: float, mem: dict, sc: "Scorer") -> bool:
        if pred(s):
            mem["streak"] = mem.get("streak", 0.0) + dt
            if mem["streak"] >= seconds and not mem.get("done"):
                mem["done"] = True
                return True
        else:
            mem["streak"] = 0.0
            mem["done"] = False
        return False
    return d


def recovery(pred: Callable[[Snapshot], bool]) -> Detector:
    """Fire when `pred` (a bad condition) clears: true->false. The reclaim."""
    def d(s: Snapshot, dt: float, mem: dict, sc: "Scorer") -> bool:
        cur = pred(s)
        prev = mem.get("prev", cur)
        mem["prev"] = cur
        return prev and not cur
    return d


def on_outcome(outcome: Outcome) -> Detector:
    def d(s: Snapshot, dt: float, mem: dict, sc: "Scorer") -> bool:
        return s.outcome is outcome
    return d


def when(fn: Callable[[Snapshot, "Scorer"], bool]) -> Detector:
    """Arbitrary predicate over the snapshot and the live score (hidden/compound)."""
    def d(s: Snapshot, dt: float, mem: dict, sc: "Scorer") -> bool:
        return fn(s, sc)
    return d


# --- the default objective registry ---------------------------------------

def default_objectives(cfg: ScoreConfig) -> list[Objective]:
    cooling_bad = lambda s: not s.cooling_on
    silenced = lambda s: s.warning_due and not s.annunciator_on
    return [
        Objective("blue_uptime", "blue", cfg.blue_uptime_per_sec,
                  "plant-stable uptime",
                  accrue=lambda s: not s.redlined and not s.truck_stolen),

        Objective("red_cooling_cut", "red", cfg.red_cooling_cut,
                  "cooling sustained off",
                  detect=sustained(cooling_bad, cfg.cooling_cut_seconds),
                  repeatable=True),
        Objective("red_silence", "red", cfg.red_silence, "warning silenced",
                  detect=sustained(silenced, cfg.silence_seconds), repeatable=True),

        # "That's mine!" -- Blue regains a system Red had sabotaged.
        Objective("blue_reclaim_cooling", "blue", cfg.blue_reclaim,
                  "reclaimed cooling (that's mine!)",
                  detect=recovery(cooling_bad), repeatable=True),

        # Signal lands with the train subsystem (M3/M5); dormant until then.
        Objective("red_derail", "red", cfg.red_derail, "train derailed",
                  detect=rising_edge("train_derailed")),

        Objective("red_stolen", "red", cfg.red_truck_stolen, "truck stolen off-map",
                  detect=on_outcome(Outcome.RED_STOLEN)),
        Objective("red_meltdown", "red", cfg.red_meltdown, "meltdown-lockout",
                  detect=on_outcome(Outcome.RED_MELTDOWN)),
        Objective("red_timer", "red", cfg.red_timer, "timer expired, no delivery",
                  detect=on_outcome(Outcome.RED_TIMER)),

        Objective("blue_delivered", "blue", cfg.blue_delivery, "truck delivered",
                  detect=on_outcome(Outcome.BLUE_DELIVERED)),
        # Must come after blue_delivered so the milestone count is final.
        Objective("blue_clean", "blue", cfg.blue_clean, "clean round",
                  detect=when(lambda s, sc: s.outcome is Outcome.BLUE_DELIVERED
                              and sc.red_milestones == 0)),
    ]


@dataclass
class Scorer:
    cfg: ScoreConfig = field(default_factory=ScoreConfig)
    objectives: list[Objective] = field(default=None)  # type: ignore[assignment]
    blue: float = 0.0
    red: float = 0.0
    red_milestones: int = 0
    events: list[ScoreEvent] = field(default_factory=list)

    _last_t: float | None = None
    _mem: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.objectives is None:
            self.objectives = default_objectives(self.cfg)

    def add_objective(self, obj: Objective) -> None:
        self.objectives.append(obj)

    def _award(self, t: float, obj: Objective) -> None:
        if obj.team == "blue":
            self.blue += obj.points
        else:
            self.red += obj.points
            self.red_milestones += 1
        self.events.append(ScoreEvent(t, obj.team, obj.label, obj.points, obj.id))

    def observe(self, s: Snapshot) -> None:
        dt = 0.0 if self._last_t is None else max(0.0, s.t - self._last_t)
        self._last_t = s.t
        live = s.outcome is None

        for obj in self.objectives:
            mem = self._mem.setdefault(obj.id, {})
            if obj.accrue is not None:
                if live and obj.accrue(s):
                    if obj.team == "blue":
                        self.blue += obj.points * dt
                    else:
                        self.red += obj.points * dt
                continue
            if not obj.repeatable and mem.get("fired"):
                continue
            if obj.detect(s, dt, mem, self):
                mem["fired"] = True
                self._award(s.t, obj)

    def catalog(self, include_hidden: bool = False) -> list[dict]:
        """Objectives visible on the board: non-hidden, plus any already fired
        (so a sprung Easter egg shows up, but an unsprung one stays secret)."""
        out = []
        for obj in self.objectives:
            fired = self._mem.get(obj.id, {}).get("fired", False)
            if obj.hidden and not include_hidden and not fired:
                continue
            out.append({"id": obj.id, "team": obj.team, "points": obj.points,
                        "label": obj.label})
        return out

    def scoreboard(self) -> dict:
        leader = "tie"
        if self.blue > self.red:
            leader = "blue"
        elif self.red > self.blue:
            leader = "red"
        return {
            "blue": round(self.blue, 1),
            "red": round(self.red, 1),
            "leader": leader,
            "red_milestones": self.red_milestones,
            "events": [vars(e) for e in self.events],
        }


def run_scored_round(events=None, cfg: SimConfig = DEFAULT,
                     score_cfg: ScoreConfig | None = None,
                     scorer: Scorer | None = None,
                     registry=None) -> tuple[Round, Scorer]:
    """Run a Round to completion with a Scorer observing every tick.

    A SubsystemRegistry, if given, contributes its telemetry to every snapshot
    (so objectives over crossings/signals/etc. see those signals). Events are
    ``(t, callable(round))``; a crossing-forcing event closes over the registry
    it was built with."""
    r = Round(cfg)
    scorer = scorer or Scorer(score_cfg or ScoreConfig())
    pending = sorted(events or [], key=lambda e: e[0])
    i = 0
    # Mobile subsystems (truck/cars) are stepped each tick so commanded/hijacked
    # waypoints take effect; a physical truck driven off-map is synced into the
    # abstract round as a theft (-> RED_STOLEN). The abstract Round.Truck still
    # owns normal delivery timing vs the 20-min clock -- unifying the two truck
    # models is a documented future refinement (see docs/ROADMAP.md M3).
    mobiles = ([s for s in registry.all() if getattr(s, "kind", None) in ("truck", "car")]
               if registry is not None else [])
    trucks = [s for s in mobiles if s.kind == "truck"]
    scorer.observe(Snapshot.from_round(r, registry))
    while r.outcome is None:
        while i < len(pending) and pending[i][0] <= r.t:
            pending[i][1](r)
            i += 1
        for m in mobiles:
            m.step(cfg.tick_dt)
        if any(t.unit.off_map for t in trucks):
            r.truck.stolen = True
        r.step()
        scorer.observe(Snapshot.from_round(r, registry))
    return r, scorer
