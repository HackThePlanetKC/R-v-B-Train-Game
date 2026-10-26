"""Mobile-unit autonomy + the layered truck-steal guards, and easy car hijack."""

from rvb_core.subsystem import SubsystemRegistry
from rvb_sim.mobile import Grid
from subsystems.truck import TruckSubsystem
from subsystems.car import CarSubsystem


def test_truck_delivers_on_its_route():
    t = TruckSubsystem()
    for _ in range(12):
        t.step(1.0)
    assert t.unit.delivered is True
    assert t.unit.off_map is False


def test_geofence_alone_blocks_any_steal():
    # Both guards on (defaults). No off-board waypoint is ever accepted.
    t = TruckSubsystem()
    assert t.command("set_waypoint", x=-1, y=4) is False   # adjacent but off-board
    assert t.command("set_waypoint", x=-2, y=4) is False   # far and off-board
    for _ in range(5):
        t.step(1.0)
    assert t.unit.off_map is False


def test_oneshot_steal_needs_both_guards_defeated():
    t = TruckSubsystem()
    assert t.command("set_geofence", on=False) is True
    assert t.command("set_route_lock", on=False) is True
    assert t.command("set_waypoint", x=-1, y=4, replace=True) is True
    t.step(1.0)
    assert t.unit.off_map is True


def test_route_lock_forces_an_adjacent_chain():
    # Geofence off but route_lock on: a far off-board jump is rejected, so Red
    # must walk the truck off the edge one adjacent step at a time.
    t = TruckSubsystem()
    t.command("set_geofence", on=False)
    t.unit.pos = (2, 4)
    assert t.command("set_waypoint", x=-1, y=4, replace=True) is False  # dist 3, rejected
    for wx in (1, 0, -1):                       # adjacent chain to the edge
        assert t.command("set_waypoint", x=wx, y=4, replace=True) is True
        t.step(1.0)
    assert t.unit.off_map is True


def test_car_commandeered_with_a_single_write():
    c = CarSubsystem("car.1")
    assert c.command("set_waypoint", x=5, y=3, replace=True) is True   # one write, no route lock
    for _ in range(6):
        c.step(1.0)
    assert c.unit.pos == (5, 3)
    assert c.unit.off_map is False


def test_car_cannot_be_flung_off_map():
    c = CarSubsystem("car.1")
    assert c.command("set_waypoint", x=-1, y=0) is False   # geofence still guards cars


def test_manifest_and_telemetry_shape():
    t = TruckSubsystem()
    m = t.manifest()
    assert m["kind"] == "truck"
    assert {"set_geofence", "set_route_lock"} <= set(m["attack_surface"])
    tel = t.telemetry()
    assert "off_map" in tel and "delivered" in tel
    assert "delivered" not in CarSubsystem("car.1").telemetry()  # cars have no goal


def test_registry_namespaces_mobile_signals():
    reg = SubsystemRegistry()
    reg.register(TruckSubsystem())
    reg.register(CarSubsystem("car.1"))
    sig = reg.telemetry_map()
    assert "truck.off_map" in sig
    assert "car.1.geofence" in sig


def test_reset_restores_truck():
    t = TruckSubsystem()
    t.command("set_geofence", on=False)
    t.unit.pos = (5, 4)
    t.reset()
    assert t.unit.geofence is True
    assert t.unit.pos == (0, 4)
