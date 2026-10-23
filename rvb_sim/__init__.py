"""Game/timer process-sim for the R-vs-B train game.

The plant is a physics-lite process simulation, not an abstract countdown.
Core pressure climbs on its own; cooling holds it down. A truck delivery is
the primary Blue win. Red sabotage (killing cooling) pushes pressure past the
redline for a meltdown-lockout.

Modules:
    config  -- tunable constants (the dials we sweep to find the Blue margin)
    sim     -- PlantModel: the pure, deterministic process model (no I/O)
    game    -- Round: 20-minute clock, truck race, outcome resolution
    plant_server -- a Modbus/TCP slave wrapping PlantModel (the attack surface)
"""
