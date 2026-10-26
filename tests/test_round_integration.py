"""Integration: a truck hijack over the subsystem command path flips the round
to RED_STOLEN, and a clean round still works with mobiles present."""

from rvb_core.subsystem import SubsystemRegistry
from rvb_sim.game import Outcome
from rvb_score.scoring import run_scored_round
from subsystems.truck import TruckSubsystem
from subsystems.car import CarSubsystem


def test_truck_hijack_results_in_red_stolen():
    reg = SubsystemRegistry()
    truck = reg.register(TruckSubsystem())
    truck.unit.set_route([])            # idle hijack target; abstract clock owns delivery

    def heist(r):                        # Red, having reached the bus, defeats both guards
        reg.dispatch("truck", "set_geofence", on=False)
        reg.dispatch("truck", "set_route_lock", on=False)
        reg.dispatch("truck", "set_waypoint", x=-1, y=4, replace=True)

    r, sc = run_scored_round(events=[(30.0, heist)], registry=reg)
    assert r.outcome is Outcome.RED_STOLEN
    assert any(e.objective_id == "red_stolen" for e in sc.events)


def test_geofence_held_truck_is_not_stolen():
    # Red flips route_lock but never defeats the geofence -> off-board waypoint
    # is rejected, the truck is never taken, Blue delivers by default.
    reg = SubsystemRegistry()
    truck = reg.register(TruckSubsystem())
    truck.unit.set_route([])

    def attempt(r):
        reg.dispatch("truck", "set_route_lock", on=False)
        reg.dispatch("truck", "set_waypoint", x=-1, y=4, replace=True)  # rejected

    r, sc = run_scored_round(events=[(30.0, attempt)], registry=reg)
    assert r.outcome is Outcome.BLUE_DELIVERED
    assert not truck.unit.off_map


def test_cars_present_do_not_disturb_a_clean_round():
    reg = SubsystemRegistry()
    reg.register(TruckSubsystem()).unit.set_route([])
    reg.register(CarSubsystem("car.1"))
    r, sc = run_scored_round(registry=reg)
    assert r.outcome is Outcome.BLUE_DELIVERED
    assert sc.red == 0.0
    assert any(e.objective_id == "blue_clean" for e in sc.events)