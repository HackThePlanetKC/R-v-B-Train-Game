#!/usr/bin/env python3
"""Headless, accelerated playthroughs that show the tug-of-war.

Run from the repo root:
    PYTHONPATH=. python scripts/demo_round.py

No hardware, no network -- drives PlantModel/Round directly so we can read the
pressure gauge over a whole 20-minute round in a fraction of a second.
"""

from __future__ import annotations

from rvb_sim.game import Round, Outcome


def cut_cooling(r: Round) -> None:
    r.plant.cooling_pump = False


def restore_cooling(r: Round) -> None:
    r.plant.cooling_pump = True


def gauge(p: float, width: int = 30) -> str:
    fill = int(round(width * min(p, 100.0) / 100.0))
    return "[" + "#" * fill + "-" * (width - fill) + "]"


def play(title: str, events, print_every: int = 60) -> None:
    r = Round()
    pending = sorted(events, key=lambda e: e[0])
    i = 0
    print(f"\n=== {title} ===")
    print(f"{'t':>5} {'press':>6} {'temp':>6} {'ttr':>6} {'truck':>6}  gauge")
    while r.outcome is None:
        while i < len(pending) and pending[i][0] <= r.t:
            label = pending[i][2] if len(pending[i]) > 2 else "event"
            print(f"  >> t={int(r.t):>4}s  {label}")
            pending[i][1](r)
            i += 1
        if int(r.t) % print_every == 0:
            ttr = r.plant.time_to_redline()
            ttr_s = "inf" if ttr == float("inf") else f"{int(ttr)}"
            warn = " WARN" if r.plant.warning_active(r.clock_remaining) else ""
            print(
                f"{int(r.t):>5} {r.plant.pressure:>6.1f} {r.plant.temp:>6.1f} "
                f"{ttr_s:>6} {r.truck.progress*100:>5.0f}% {gauge(r.plant.pressure)}{warn}"
            )
        r.step()

    verdict = {
        Outcome.BLUE_DELIVERED: "BLUE WIN - truck delivered",
        Outcome.RED_TIMER: "RED WIN - timer expired, no delivery",
        Outcome.RED_STOLEN: "RED WIN - truck stolen off-map",
        Outcome.RED_MELTDOWN: "RED WIN - meltdown-lockout",
    }[r.outcome]
    tag = "  (clean)" if r.clean_blue_win else ""
    print(f"  -> {verdict} at t={int(r.t)}s{tag}")


def main() -> None:
    play("Scenario A: nobody acts (Blue default)", [])
    play(
        "Scenario B: Red cuts cooling at 60s, Blue never reacts",
        [(60.0, cut_cooling, "RED: cooling_pump -> OFF")],
    )
    play(
        "Scenario C: Red cuts cooling at 60s, Blue reverts at 300s",
        [
            (60.0, cut_cooling, "RED: cooling_pump -> OFF"),
            (300.0, restore_cooling, "BLUE: cooling_pump -> ON"),
        ],
    )


if __name__ == "__main__":
    main()
