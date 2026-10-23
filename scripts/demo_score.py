#!/usr/bin/env python3
"""Scored playthroughs -- shows the hybrid scoreboard for each scenario.

    PYTHONPATH=. python scripts/demo_score.py
"""

from __future__ import annotations

from rvb_score.scoring import run_scored_round


def cut_cooling(r):
    r.plant.cooling_pump = False


def restore_cooling(r):
    r.plant.cooling_pump = True


def silence(r):
    r.plant.annunciator_override = False  # force the alarm off


def show(title: str, events) -> None:
    r, sc = run_scored_round(events=events)
    sb = sc.scoreboard()
    print(f"\n=== {title} ===")
    print(f"  outcome: {r.outcome.value}   at t={int(r.t)}s")
    print(f"  BLUE {sb['blue']:>7}   RED {sb['red']:>7}   leader: {sb['leader']}")
    for e in sb["events"]:
        print(f"    t={int(e['t']):>4}s  {e['team']:<4} +{e['points']:<6g} {e['label']}")


def main() -> None:
    show("A: nobody acts (Blue default)", [])
    show("B: Red cuts cooling at 60s, never answered", [(60.0, cut_cooling)])
    show("C: Red cuts cooling at 60s, Blue reverts at 300s",
         [(60.0, cut_cooling), (300.0, restore_cooling)])
    show("D: Red cuts cooling and silences the alarm at 60s",
         [(60.0, cut_cooling), (60.0, silence)])


if __name__ == "__main__":
    main()
