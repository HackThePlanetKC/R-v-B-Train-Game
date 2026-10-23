"""Validate the Blue-default margin and the sabotage tug-of-war."""

import math

from rvb_sim.config import DEFAULT
from rvb_sim.game import Round, Outcome


def cut_cooling(r: Round) -> None:
    r.plant.cooling_pump = False


def restore_cooling(r: Round) -> None:
    r.plant.cooling_pump = True


def steal_truck(r: Round) -> None:
    r.truck.stolen = True


def test_blue_default_wins_untouched():
    """If nobody acts, the truck docks and the plant never redlines."""
    r = Round()
    assert r.run() is Outcome.BLUE_DELIVERED
    assert r.clean_blue_win
    assert not r.plant.redlined


def test_cooling_winning_never_redlines():
    """With the pump on, projected time-to-redline is infinite."""
    r = Round()
    assert r.plant.time_to_redline() == math.inf


def test_cooling_off_redlines_inside_round():
    """Red cutting cooling at the start causes a meltdown before the clock,
    but not instantly -- Blue has minutes to notice and react."""
    r = Round()
    out = r.run(events=[(0.0, cut_cooling)])
    assert out is Outcome.RED_MELTDOWN
    assert 240.0 < r.t < 480.0  # ~6-7 min: inside the round, before truck docks


def test_blue_restore_saves_the_round():
    """Red cuts cooling; Blue reverts it in time and the truck still docks."""
    r = Round()
    out = r.run(events=[(60.0, cut_cooling), (300.0, restore_cooling)])
    assert out is Outcome.BLUE_DELIVERED
    assert not r.plant.redlined
    assert r.sabotage_logged  # not a clean win -- Red still scored the cut
    assert not r.clean_blue_win


def test_truck_stolen_is_red_primary():
    r = Round()
    out = r.run(events=[(30.0, steal_truck)])
    assert out is Outcome.RED_STOLEN


def test_timer_expiry_when_truck_never_moves():
    r = Round()
    r.truck.moving = False
    out = r.run()
    assert out is Outcome.RED_TIMER
    assert r.t >= DEFAULT.round_seconds


def test_warning_annunciator_trips_near_meltdown():
    r = Round()
    r.plant.cooling_pump = False
    # advance until meltdown is close
    while r.plant.time_to_redline() > DEFAULT.warn_redline_seconds:
        r.step()
    assert r.plant.warning_active(r.clock_remaining)
