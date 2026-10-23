"""Thin Modbus/TCP client wrapper between the HMI and the plant slave.

Mirrors the register map in rvb_sim/plant_server.py. A fresh connection per
call keeps it simple and stateless -- fine at HMI poll rates.
"""

from __future__ import annotations

from pymodbus.client import ModbusTcpClient

SLAVE_ID = 1


class PlantLink:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port

    def read_state(self) -> dict:
        client = ModbusTcpClient(self.host, port=self.port, timeout=1)
        if not client.connect():
            return {"online": False}
        try:
            ir = client.read_input_registers(address=0, count=4, slave=SLAVE_ID)
            di = client.read_discrete_inputs(address=0, count=3, slave=SLAVE_ID)
            co = client.read_coils(address=0, count=4, slave=SLAVE_ID)
            hr = client.read_holding_registers(address=0, count=2, slave=SLAVE_ID)
            if any(r.isError() for r in (ir, di, co, hr)):
                return {"online": False}
            return {
                "online": True,
                "pressure": ir.registers[0] / 10.0,
                "temp": ir.registers[1] / 10.0,
                "time_to_redline": ir.registers[2],
                "truck_pct": ir.registers[3],
                "truck_docked": bool(di.bits[0]),
                "redlined": bool(di.bits[1]),
                "warning_recommended": bool(di.bits[2]),
                "cooling_pump": bool(co.bits[0]),
                "feed_valve": bool(co.bits[1]),
                "annunciator": bool(co.bits[2]),
                "stack_vent": bool(co.bits[3]),
                "cooling_rate": hr.registers[0] / 1000.0,
            }
        finally:
            client.close()

    def write_coil(self, address: int, value: bool) -> bool:
        client = ModbusTcpClient(self.host, port=self.port, timeout=1)
        if not client.connect():
            return False
        try:
            rr = client.write_coil(address=address, value=bool(value), slave=SLAVE_ID)
            return not rr.isError()
        finally:
            client.close()

    def write_register(self, address: int, value: int) -> bool:
        client = ModbusTcpClient(self.host, port=self.port, timeout=1)
        if not client.connect():
            return False
        try:
            rr = client.write_register(address=address, value=int(value), slave=SLAVE_ID)
            return not rr.isError()
        finally:
            client.close()
