"""Flask HMI app factory and routes.

Planted weaknesses are tagged `# PLANTED VULN`. See docs/VULNS.md for the
catalogue, the intended Red path, and the base-tool Blue fix for each.
"""

from __future__ import annotations

import os
import subprocess

from flask import (
    Flask, redirect, render_template, request, session, url_for, jsonify, Response,
)

from .config import HmiConfig, DEFAULT
from .modbus_link import PlantLink

HERE = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(HERE, "reports")
ADMIN_FLAG = "flag{br0ken_access_control_pivot}"


def create_app(cfg: HmiConfig = DEFAULT) -> Flask:
    app = Flask(__name__)
    app.secret_key = cfg.secret_key
    app.config["HMI"] = cfg
    link = PlantLink(cfg.plant_host, cfg.plant_port)

    def logged_in() -> bool:
        return session.get("user") == cfg.username

    # --- operator views ---------------------------------------------------

    @app.get("/")
    def dashboard():
        return render_template("dashboard.html", state=link.read_state(),
                               logged_in=logged_in())

    @app.get("/login")
    def login_form():
        return render_template("login.html", error=None)

    @app.post("/login")
    def login():
        # PLANTED VULN (default credentials): accepts the shipped operator creds.
        # Blue fix: set HMI_USER/HMI_PASS to non-default values and restart.
        if (request.form.get("username") == cfg.username
                and request.form.get("password") == cfg.password):
            session["user"] = cfg.username
            return redirect(url_for("admin"))
        return render_template("login.html", error="Invalid credentials"), 401

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect(url_for("dashboard"))

    @app.get("/admin")
    def admin():
        # The UI gates the control panel behind login...
        if not logged_in():
            return redirect(url_for("login_form"))
        return render_template("admin.html", state=link.read_state(),
                               actions=cfg.actions, flag=ADMIN_FLAG)

    # --- control + tooling APIs ------------------------------------------

    @app.post("/api/control")
    def api_control():
        # PLANTED VULN (broken access control): the API does NOT check the
        # session, even though /admin's UI does. Red who can reach the HMI can
        # drive the plant without creds -- the IT->OT pivot.
        # Blue fix: add `if not logged_in(): abort(403)` here and restart, or
        # firewall this endpoint from untrusted sources.
        action = (request.json or {}).get("action")
        value = (request.json or {}).get("value")
        if action not in cfg.actions:
            return jsonify(ok=False, error="unknown action"), 400
        block, addr = cfg.actions[action]
        if block == "coil":
            ok = link.write_coil(addr, bool(value))
        else:
            ok = link.write_register(addr, int(round(float(value) * 1000)))
        return jsonify(ok=ok, action=action, value=value)

    @app.post("/api/diag")
    def api_diag():
        # PLANTED VULN (OS command injection): the "network diagnostics" tool
        # shells out with the host string unsanitised. e.g. host =
        # "127.0.0.1; cat flags/operator.flag" leaks the flag.
        # Blue fix: drop shell=True and pass an argv list, or remove the tool.
        host = (request.json or {}).get("host", "")
        try:
            out = subprocess.run(f"ping -c 1 -W 1 {host}", shell=True,
                                 capture_output=True, text=True, timeout=5)
            return jsonify(ok=True, output=out.stdout + out.stderr)
        except subprocess.TimeoutExpired:
            return jsonify(ok=False, error="timeout"), 504

    @app.get("/api/report")
    def api_report():
        # PLANTED VULN (path traversal): reads reports/<name> with no
        # sanitisation. name = "../flags/operator.flag" escapes the directory.
        # Blue fix: reject names containing "/" or "..", or resolve+confine.
        name = request.args.get("name", "daily_summary.txt")
        path = os.path.join(REPORTS_DIR, name)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return Response(fh.read(), mimetype="text/plain")
        except (FileNotFoundError, IsADirectoryError, PermissionError) as exc:
            return jsonify(ok=False, error=str(exc)), 404

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8080)
