"""Hybrid Blue/Red scorer, driven by game-state snapshots.

Point values and thresholds are a starting economy (see docs/DESIGN.md Sec.8),
not final. Milestones are edge-triggered and auto-detected from snapshots, so
scoring is objective and doesn't depend on self-reporting.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rvb_sim.config import SimConfig, DEFAULT
from rvb_sim.game import Round, Outcome
from rvb_sim.sim import PlantModel


@dataclass(frozen=True)
class Snapshot:
    """A single tick of game state, all the scorer needs."""

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

    @classmethod
    def from_round(cls, r: Round) -> "Snapshot":
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
        )


@dataclass(frozen=True)
class ScoreConfig:
    # Blue
    blue_uptime_per_sec: float = 1.0   # accrued each second the plant is safe
    blue_delivery: float = 500.0       # truck docked
    blue_clean: float = 250.0          # delivered with zero Red milestones

    # Red harassment milestones (repeatable, once per sustained streak)
    cooling_cut_seconds: float = 30.0
    red_cooling_cut: float = 150.0
    silence_seconds: float = 15.0
    red_silence: float = 75.0

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


@dataclass
class Scorer:
    cfg: ScoreConfig = field(default_factory=ScoreConfig)
    blue: float = 0.0
    red: float = 0.0
    red_milestones: int = 0
    events: list[ScoreEvent] = field(default_factory=list)

    _last_t: float | None = None
    _cooling_off_streak: float = 0.0
    _cooling_awarded: bool = False
    _silence_streak: float = 0.0
    _silence_awarded: bool = False
    _resolved: bool = False

    # --- awards -----------------------------------------------------------

    def _award(self, t: float, team: str, label: str, points: float) -> None:
        if team == "blue":
            self.blue += points
        else:
            self.red += points
            self.red_milestones += 1
        self.events.append(ScoreEvent(t, team, label, points))

    # --- main entry -------------------------------------------------------

    def observe(self, s: Snapshot) -> None:
        dt = 0.0 if self._last_t is None else max(0.0, s.t - self._last_t)
        self._last_t = s.t
        live = s.outcome is None

        # Blue uptime: accrue while the round is live and the plant is safe.
        if live and not s.redlined and not s.truck_stolen:
            self.blue += self.cfg.blue_uptime_per_sec * dt

        # Red: sustained cooling outage (once per streak).
        if not s.cooling_on:
            self._cooling_off_streak += dt
            if (self._cooling_off_streak >= self.cfg.cooling_cut_seconds
                    and not self._cooling_awarded):
                self._award(s.t, "red", "cooling sustained off", self.cfg.red_cooling_cut)
                self._cooling_awarded = True
        else:
            self._cooling_off_streak = 0.0
            self._cooling_awarded = False

        # Red: warning silenced (due but not sounding), once per streak.
        if s.warning_due and not s.annunciator_on:
            self._silence_streak += dt
            if (self._silence_streak >= self.cfg.silence_seconds
                    and not self._silence_awarded):
                self._award(s.t, "red", "warning silenced", self.cfg.red_silence)
                self._silence_awarded = True
        else:
            self._silence_streak = 0.0
            self._silence_awarded = False

        # Terminal outcome: award the big payout exactly once.
        if s.outcome is not None and not self._resolved:
            self._resolved = True
            if s.outcome is Outcome.RED_STOLEN:
                self._award(s.t, "red", "truck stolen off-map", self.cfg.red_truck_stolen)
            elif s.outcome is Outcome.RED_MELTDOWN:
                self._award(s.t, "red", "meltdown-lockout", self.cfg.red_meltdown)
            elif s.outcome is Outcome.RED_TIMER:
                self._award(s.t, "red", "timer expired, no delivery", self.cfg.red_timer)
            elif s.outcome is Outcome.BLUE_DELIVERED:
                self._award(s.t, "blue", "truck delivered", self.cfg.blue_delivery)
                if self.red_milestones == 0:
                    self._award(s.t, "blue", "clean round", self.cfg.blue_clean)

    # --- readout ----------------------------------------------------------

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
            "resolved": self._resolved,
            "events": [vars(e) for e in self.events],
        }


def run_scored_round(events=None, cfg: SimConfig = DEFAULT,
                     score_cfg: ScoreConfig | None = None) -> tuple[Round, Scorer]:
    """Run a Round to completion with a Scorer observing every tick."""
    r = Round(cfg)
    scorer = Scorer(score_cfg or ScoreConfig())
    pending = sorted(events or [], key=lambda e: e[0])
    i = 0
    scorer.observe(Snapshot.from_round(r))
    while r.outcome is None:
        while i < len(pending) and pending[i][0] <= r.t:
            pending[i][1](r)
            i += 1
        r.step()
        scorer.observe(Snapshot.from_round(r))
    return r, scorer
