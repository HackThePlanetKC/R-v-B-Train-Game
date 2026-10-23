# Planted Vulnerabilities — Plant HMI

Catalogue of the **intentional** weaknesses in `rvb_hmi/` for the CTF. Every one
is a well-known bug class on a network-isolated training target (Metasploitable/
DVWA tradition) — no novel exploits. Each is tagged `# PLANTED VULN` in source.

For each: the class, the Red path, and the **Blue fix** — which must be doable
with base tools already on the box (edit source/config, restart the service, or
a host firewall rule), because the range is offline (no package installs).

| ID | Class (CWE) | Endpoint | Yields |
|----|-------------|----------|--------|
| V1 | Default credentials (CWE-798) | `POST /login` | admin console + `ADMIN_FLAG` |
| V2 | Missing authorization (CWE-862) | `POST /api/control` | live plant sabotage (IT→OT pivot) |
| V3 | OS command injection (CWE-78) | `POST /api/diag` | RCE as the service user |
| V4 | Path traversal (CWE-22) | `GET /api/report` | arbitrary file read (`operator.flag`) |

## V1 — Default credentials
- **Red:** log in with the shipped `operator` / `operator`; the admin page shows
  `flag{br0ken_access_control_pivot}` and the control panel.
- **Blue:** set `HMI_USER` / `HMI_PASS` to non-defaults (env or edit
  `rvb_hmi/config.py`) and restart. Also set `HMI_SECRET` to a long random value
  — the default session key is predictable (session forgery).

## V2 — Missing authorization on the control API (the pivot)
- **Red:** `POST /api/control {"action":"cooling_pump","value":false}` with **no
  session**. The UI hides the panel behind login, but the API does not check —
  so Red reaching the HMI from enterprise/DMZ drives the OT plant without creds.
  This is the central IT→OT pivot: HMI write → Modbus coil → pressure climbs.
- **Blue:** add an auth gate at the top of `api_control` (`if not logged_in():
  abort(403)`) and restart; or firewall the endpoint from untrusted sources.

## V3 — OS command injection in diagnostics
- **Red:** the "ping a host" tool shells out unsanitised. `{"host":"x; id"}` runs
  `id`; `{"host":"x; cat <path>"}` reads files. RCE on the HMI host.
- **Blue:** drop `shell=True` and pass an argv list
  (`["ping","-c","1","-W","1",host]`), validate `host` against a hostname/IP
  pattern, or remove the feature. Restart after editing.

## V4 — Path traversal in report viewer
- **Red:** `GET /api/report?name=../flags/operator.flag` escapes the reports
  directory; `../../../../etc/passwd` reads host files. Leaks `operator.flag`
  (`flag{d3fault_cr3ds_on_the_hmi}`).
- **Blue:** reject `name` containing `/` or `..`, or resolve the path and confirm
  it stays under `REPORTS_DIR` (`os.path.realpath` + `startswith`). Restart.

## Defense-in-depth (range hardening, not a single endpoint)
- Run the HMI as a **low-privilege user**, not root — blunts V3/V4 blast radius.
  (In the dev container it runs as root; fix in the service unit for the range.)
- Network-segment the HMI so only Blue and the intended operator nets can reach
  it; this is itself a contested, Blue-tunable control (see DESIGN.md §4).

## Flags
- `ADMIN_FLAG = flag{br0ken_access_control_pivot}` — admin page, via V1 login.
- `operator.flag = flag{d3fault_cr3ds_on_the_hmi}` — file read, via V3 or V4.
