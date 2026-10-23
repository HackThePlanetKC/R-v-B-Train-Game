"""The subsystem contract: registry, the plant reference, and a crossing +
an objective over it -- proving a new subsystem needs no core/scorer change."""

from rvb_core.subsystem import SubsystemRegistry
from rvb_sim.sim import PlantModel
from rvb_sim.game import Round, Outcome
from rvb_score.scoring import (
    Scorer, Snapshot, Objective, sustained, recovery, run_scored_round,
)
from subsystems.plant import PlantSubsystem
from subsystems.crossing import CrossingSubsystem


def make_registry():
    reg = SubsystemRegistry()
    reg.register(PlantSubsystem(PlantModel()))
    reg.register(CrossingSubsystem("crossing.north"))
    return reg


def test_registry_namespaces_telemetry():
    reg = make_registry()
    sig = reg.telemetry_map()
    assert "plant.core_pressure" in sig
    assert "crossing.north.gates_down" in sig
    assert sig["crossing.north.gates_down"] is False


def test_dispatch_routes_commands_and_unknown_is_false():
    reg = make_registry()
    assert reg.dispatch("plant", "set_cooling_pump", on=False) is True
    assert reg.telemetry_map()["plant.cooling_on"] is False
    assert reg.dispatch("crossing.north", "set_gates", down=True) is True
    assert reg.telemetry_map()["crossing.north.gates_down"] is True
    assert reg.dispatch("nope", "whatever") is False
    assert reg.dispatch("plant", "bogus_action") is False


def test_plant_manifest_declares_signals_commands_and_attack_surface():
    m = PlantSubsystem(PlantModel()).manifest()
    assert m["id"] == "plant" and m["kind"] == "plant"
    assert "core_pressure" in m["signals"]
    assert "set_cooling_pump" in m["commands"]
    assert "set_cooling_pump" in m["attack_surface"]


def test_reset_restores_start_state():
    reg = make_registry()
    reg.dispatch("plant", "set_cooling_pump", on=False)
    reg.dispatch("crossing.north", "set_gates", down=True)
    reg.reset_all()
    sig = reg.telemetry_map()
    assert sig["plant.cooling_on"] is True
    assert sig["crossing.north.gates_down"] is False


def test_snapshot_from_round_merges_registry_signals():
    reg = make_registry()
    r = Round()
    snap = Snapshot.from_round(r, reg)
    assert "crossing.north.gates_down" in snap.signals
    assert "plant.core_pressure" in snap.signals


def test_new_subsystem_objective_scores_without_core_changes():
    # A Red objective over the crossing, registered alongside the subsystem --
    # the scorer and game core are untouched.
    reg = SubsystemRegistry()
    crossing = reg.register(CrossingSubsystem("crossing.north"))
    sc = Scorer()
    sc.add_objective(Objective(
        "red_crossing_abuse", "red", 120, "crossing held against traffic",
        detect=sustained(
            lambda s: s.signals.get("crossing.north.gates_down")
            and not s.signals.get("crossing.north.train_present"), 15),
        repeatable=True))
    sc.add_objective(Objective(
        "blue_reclaim_crossing", "blue", 80, "crossing cleared (that's mine!)",
        detect=recovery(lambda s: s.signals.get("crossing.north.gates_down")),
        repeatable=True))

    force = lambda r: reg.dispatch("crossing.north", "set_gates", down=True)
    clear = lambda r: reg.dispatch("crossing.north", "set_gates", down=False)
    r, sc = run_scored_round(
        events=[(10.0, force), (40.0, clear)], scorer=sc, registry=reg)

    assert r.outcome is Outcome.BLUE_DELIVERED           # plant fine, truck delivered
    ids = [e.objective_id for e in sc.events]
    assert "red_crossing_abuse" in ids                    # gates held >15s
    assert "blue_reclaim_crossing" in ids                 # gates cleared -> both sides score
