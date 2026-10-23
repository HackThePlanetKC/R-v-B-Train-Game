"""Plant HMI: the Level-2 supervisory web app.

A deliberately vulnerable operator console (Flask) that reads the plant gauges
and drives the Modbus control coils on the plant slave. It is Red's IT->OT
pivot: popping the HMI from the enterprise/DMZ side lets Red sabotage the plant
without first standing on the OT segment.

Every planted weakness is a well-known bug class (see docs/VULNS.md), tagged in
the source with `# PLANTED VULN`, and each has a base-tool Blue fix. This is a
training target in the Metasploitable/DVWA tradition -- not a real product.
"""
