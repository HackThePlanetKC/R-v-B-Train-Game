"""Smoke test: drive the plant over real Modbus/TCP like Red would.

Binds a localhost socket, so it's a bit heavier than the pure-sim tests.
"""

import time

import pytest

from pymodbus.client import ModbusTcpClient

from rvb_sim.config import SimConfig
from rvb_sim.plant_server import PlantServer, SLAVE_ID


@pytest.fixture
def server():
    # fast ticks so the test runs quickly; tiny cooling margin as usual
    cfg = SimConfig(tick_dt=0.05)
    srv = PlantServer(cfg=cfg, host="127.0.0.1", port=15020, tick_dt=0.05)
    srv.start_background()
    time.sleep(0.5)  # let the socket bind
    yield srv
    srv.stop()


def _read_ir(client, addr, count=1):
    rr = client.read_input_registers(address=addr, count=count, slave=SLAVE_ID)
    assert not rr.isError(), rr
    return rr.registers


def test_red_can_read_and_sabotage_over_modbus(server):
    client = ModbusTcpClient("127.0.0.1", port=15020)
    assert client.connect()
    try:
        # Red reads the gauges: cooling is on, so time-to-redline is "never".
        ttr_before = _read_ir(client, 2)[0]
        assert ttr_before == 65535

        # Red writes the cooling pump coil OFF -- the core sabotage.
        wr = client.write_coil(address=0, value=False, slave=SLAVE_ID)
        assert not wr.isError(), wr

        # Pressure now climbs; time-to-redline becomes a finite, shrinking number.
        time.sleep(1.0)
        ttr_after = _read_ir(client, 2)[0]
        press_after = _read_ir(client, 0)[0]
        assert ttr_after < 65535
        assert press_after > 400  # PV x10: risen above the 40.0 start
    finally:
        client.close()
