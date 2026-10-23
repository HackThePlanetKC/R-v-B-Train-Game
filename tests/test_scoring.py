"""Scoring: direct snapshot-driven milestone tests + integrated scored rounds."""

from rvb_sim.game import Outcome
from rvb_score.scoring import (
    Scorer, ScoreConfig, Snapshot, Objective, when, run_scored_round,
)


def cut_cooling(r):
    r.plant.cooling_pump = False


def restore_cooling(r):
    r.plant.cooling_pump = True


def steal_truck(r):
    r.truck.stolen = True


def snap(t, **kw):
    base = dict(clock_remaining=1200 - t, pressure=50.0, redlined=False,
                cooling_on=True, warning_due=False, annunciator_on=False,
                truck_docked=False, truck_stolen=False, outcome=None)
    base.update(kw)
    return Snapshot(t=t, **base)


def test_sustained_cooling_outage_awards_once_per_streak():
    sc = Scorer(ScoreConfig())
    for t in range(0, 40):  # cooling off the whole time, 1s ticks
        sc.observe(snap(t, cooling_on=False))
    red_events = [e for e in sc.events if e.team == "red"]
    assert len(red_events) == 1
    assert red_events[0].label == "cooling sustained off"
    assert sc.red == ScoreConfig().red_cooling_cut


def test_silencing_a_due_warning_scores_red():
    sc = Scorer(ScoreConfig())
    for t in range(0, 20):  # warning due but annunciator forced off
        sc.observe(snap(t, warning_due=True, annunciator_on=False))
    assert any(e.label == "warning silenced" for e in sc.events)
    assert sc.red == ScoreConfig().red_silence


def test_warning_that_is_sounding_scores_nothing():
    sc = Scorer(ScoreConfig())
    for t in range(0, 30):  # warning due AND annunciator on -> honest, no points
        sc.observe(snap(t, warning_due=True, annunciator_on=True))
    assert sc.red == 0.0


def test_blue_clean_win():
    r, sc = run_scored_round()
    assert r.outcome is Outcome.BLUE_DELIVERED
    assert sc.red == 0.0 and sc.red_milestones == 0
    labels = [e.label for e in sc.events]
    assert "truck delivered" in labels and "clean round" in labels
    assert sc.blue > ScoreConfig().blue_delivery  # delivery + clean + uptime


def test_red_meltdown_scores_big_and_denies_blue():
    r, sc = run_scored_round(events=[(0.0, cut_cooling)])
    assert r.outcome is Outcome.RED_MELTDOWN
    labels = [e.label for e in sc.events]
    assert "meltdown-lockout" in labels
    assert "cooling sustained off" in labels  # it was off >30s before meltdown
    assert sc.red_milestones >= 2
    assert "truck delivered" not in labels


def test_blue_wins_but_not_clean_when_red_harassed():
    r, sc = run_scored_round(events=[(60.0, cut_cooling), (300.0, restore_cooling)])
    assert r.outcome is Outcome.BLUE_DELIVERED
    labels = [e.label for e in sc.events]
    assert "truck delivered" in labels
    assert "clean round" not in labels      # Red logged a milestone
    assert sc.red_milestones == 1
    assert sc.red == ScoreConfig().red_cooling_cut


def test_stolen_truck_scores_red_primary():
    r, sc = run_scored_round(events=[(30.0, steal_truck)])
    assert r.outcome is Outcome.RED_STOLEN
    assert any(e.label == "truck stolen off-map" for e in sc.events)


# --- new objectives: reclaim (both sides), dormant signal, hidden egg -------

def test_reclaim_scores_both_sides():
    # Red holds cooling off >30s (sustained), Blue reclaims it -> both score.
    r, sc = run_scored_round(events=[(60.0, cut_cooling), (100.0, restore_cooling)])
    assert r.outcome is Outcome.BLUE_DELIVERED
    ids = [e.objective_id for e in sc.events]
    assert "red_cooling_cut" in ids          # Red: off 40s >= 30
    assert "blue_reclaim_cooling" in ids      # Blue: "that's mine!"
    assert sc.red_milestones == 1             # reclaim is Blue, doesn't count as Red
    assert sc.red == ScoreConfig().red_cooling_cut
    assert sc.blue > 0


def test_quick_reclaim_denies_red_and_stays_clean():
    # Blue reclaims before Red's 30s sustained award -> Red gets nothing,
    # Blue still earns the reclaim, and the round is still clean.
    r, sc = run_scored_round(events=[(60.0, cut_cooling), (80.0, restore_cooling)])
    assert r.outcome is Outcome.BLUE_DELIVERED
    labels = [e.label for e in sc.events]
    assert "cooling sustained off" not in labels   # off only 20s < 30
    assert "reclaimed cooling (that's mine!)" in labels
    assert "clean round" in labels
    assert sc.red == 0.0


def test_dormant_signal_objective_fires_when_signal_appears():
    # red_derail reads a signal no subsystem supplies yet; it stays dormant
    # until that signal shows up, then fires once.
    sc = Scorer()
    sc.observe(snap(0, signals={"train_derailed": False}))
    assert sc.red == 0.0
    sc.observe(snap(1, signals={"train_derailed": True}))
    assert any(e.objective_id == "red_derail" for e in sc.events)
    assert sc.red == ScoreConfig().red_derail


def test_hidden_objective_stays_off_catalog_until_fired():
    sc = Scorer()
    egg = Objective("egg", "blue", 50, "found the egg",
                    detect=when(lambda s, scr: s.t >= 5), hidden=True)
    sc.add_objective(egg)
    assert "egg" not in [o["id"] for o in sc.catalog()]   # secret before firing
    sc.observe(snap(0))
    sc.observe(snap(6))                                    # t >= 5 -> fires
    assert any(e.objective_id == "egg" for e in sc.events)
    assert "egg" in [o["id"] for o in sc.catalog()]        # revealed once sprung
