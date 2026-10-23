"""A Modbus/TCP slave that exposes the plant process as the attack surface.

This is the unauthenticated OT device. Any client that can reach the segment
can read the gauges and write the control coils/registers -- reaching the
segment IS the exploit, which is the lesson. On the real board an ESP32
reimplements this exact register map.

Register map (slave id 1):

  Coils (client read/write, fc 1/5/15)
    0  cooling_pump         Blue default 1 (ON). Red writing 0 = main sabotage.
    1  feed_valve           1 = OPEN, needed to accept a truck delivery.
    2  warning_annunciator  physical warning light/chime. Contested: Blue
                            raises it, Red can silence (0) or false-trigger (1).
    3  stack_vent           Blue emergency relief: extra pressure shed.

  Discrete inputs (read-only, fc 2)
    0  truck_docked         1 once the truck has delivered.
    1  redlined             1 on meltdown-lockout.
    2  warning_recommended  sim's advice for the annunciator (Blue mirrors it).

  Input registers (read-only, fc 4)
    0  core_pressure        PV x10 (e.g. 735 = 73.5).
    1  core_temp            degrees x10.
    2  time_to_redline      seconds, 65535 = "never at current rate".
    3  truck_progress       percent 0..100.

  Holding registers (client read/write, fc 3/6/16)
    0  cooling_rate         PV/s x1000 (e.g. 200 = 0.200/s).
    1  pressure_setpoint    reserved.
"""

from __future__ import annotations

import math
import threading
import time

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.server import StartTcpServer

from .config import SimConfig, DEFAULT
from .game import Round

SLAVE_ID = 1
# pymodbus function codes used for datastore access
FC_COIL = 1
FC_DISCRETE = 2
FC_HOLDING = 3
FC_INPUT = 4

U16_MAX = 65535


def _u16(x: float) -> int:
    return max(0, min(U16_MAX, int(round(x))))


class PlantServer:
    def __init__(self, cfg: SimConfig = DEFAULT, host: str = "127.0.0.1",
                 port: int = 5020, tick_dt: float = 1.0):
        self.cfg = cfg
        self.host = host
        self.port = port
        self.tick_dt = tick_dt
        self.round = Round(cfg)
        self._stop = threading.Event()

        block = lambda n: ModbusSequentialDataBlock(0, [0] * n)
        self.store = ModbusSlaveContext(
            co=block(16), di=block(16), hr=block(16), ir=block(16)
        )
        self.context = ModbusServerContext(slaves={SLAVE_ID: self.store}, single=False)
        self._init_registers()

    # --- datastore <-> model sync ----------------------------------------

    def _init_registers(self) -> None:
        self.store.setValues(FC_COIL, 0, [1, 1, 0, 0])  # pump on, valve open
        self.store.setValues(FC_HOLDING, 0,
                             [_u16(self.cfg.cooling_rate_default * 1000), 0])

    def _pull_controls(self) -> None:
        """Read client-writable coils/holding into the model."""
        co = self.store.getValues(FC_COIL, 0, 4)
        hr = self.store.getValues(FC_HOLDING, 0, 1)
        self.round.plant.cooling_pump = bool(co[0])
        self.round.plant.feed_valve = bool(co[1])
        self.round.plant.stack_vent = bool(co[3])
        self.round.plant.cooling_rate = hr[0] / 1000.0

    def _push_readouts(self) -> None:
        """Write model outputs into the read-only blocks."""
        p = self.round.plant
        ttr = p.time_to_redline()
        ttr_s = U16_MAX if ttr == math.inf else _u16(ttr)
        self.store.setValues(FC_INPUT, 0, [
            _u16(p.pressure * 10),
            _u16(p.temp * 10),
            ttr_s,
            _u16(self.round.truck.progress * 100),
        ])
        self.store.setValues(FC_DISCRETE, 0, [
            int(self.round.truck.docked),
            int(p.redlined),
            int(p.warning_active(self.round.clock_remaining)),
        ])

    def tick(self) -> None:
        self._pull_controls()
        self.round.step(self.tick_dt)
        self._push_readouts()

    # --- threads ----------------------------------------------------------

    def _update_loop(self) -> None:
        self._push_readouts()
        while not self._stop.is_set():
            self.tick()
            time.sleep(self.tick_dt)

    def start_background(self) -> threading.Thread:
        """Start the server + updater in daemon threads; return server thread."""
        updater = threading.Thread(target=self._update_loop, daemon=True)
        updater.start()
        server = threading.Thread(
            target=lambda: StartTcpServer(context=self.context,
                                          address=(self.host, self.port)),
            daemon=True,
        )
        server.start()
        return server

    def stop(self) -> None:
        self._stop.set()


def main() -> None:
    srv = PlantServer(host="0.0.0.0", port=5020)
    print("plant Modbus/TCP slave on 0.0.0.0:5020 (slave id 1)")
    srv.start_background()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        srv.stop()


if __name__ == "__main__":
    main()
