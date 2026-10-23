"""Scoring service: the hybrid live scoreboard.

Consumes game-state snapshots (from the sim's Round now, from the real
game/timer Pi later) and keeps running Blue and Red scores:

    Blue -- continuous "plant-stable" uptime, a big delivery bonus, and a
            clean-game bonus if Red logged zero sabotage milestones.
    Red  -- per-milestone awards: cooling sustained off, warning silenced,
            truck stolen, meltdown, timer expiry.

The Scorer takes Snapshots, not a Round, so the same engine scores the sim and
(later) live hardware telemetry. See docs/DESIGN.md Sec.8.
"""
