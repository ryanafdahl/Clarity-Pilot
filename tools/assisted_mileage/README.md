# Connect driving history and private assistance ledger

The public tracker uses only verified comma Connect device statistics. Manual additions and the owner-reported baseline were removed on October 10, 2026. `baseline.json` is no longer read. Local log mileage is never added to Connect totals, avoiding overlap and incompatible engagement definitions.

The current comma 4 retrieves its own `v1.1/devices/:dongle_id/stats` using the existing device identity. Credentials are used only for normal authentication with comma's service. The offline comma 3's whole-number display totals were verified in Connect on October 10 and are retained in `connect-devices.json`, with that source and date. They are not refreshed by the comma 4. Reverify them in Connect if the older device is used again.

The [official API](https://api.comma.ai/) defines these as total driving distance, minutes and routes. The public figures are **driving totals**, not verified active-assistance totals. Each device is rounded to Connect's whole-mile/hour display precision before summing. On October 10 the combined display totals were **60,805 miles, 3,399 drives and 1,662 hours**.

## Private log collection

`collect.py` still integrates valid speed while lateral or longitudinal control is active, counting their union once. It rejects stale/invalid samples and excessive gaps. Its private, deduplicated ledger supports drive analysis and survives deletion of old logs. It is independent of the public Connect count. Raw logs, identifiers, coordinates, keys and the ledger are never committed or published.

## Deployment and schedule

The files live under `/data/maintenance/ai-mileage`. Deploy `publish.py`, `collect.py`, `core.py`, `connect-devices.json` and tests there. Keep the existing dedicated website deploy key and known-hosts configuration. The publisher only modifies `data/assisted-miles.json`; the legacy filename remains for existing links, but schema 2 uses `driving_miles` and contains no manual baseline.

`clarity-ai-mileage.timer` retains its existing five-minute boot check and subsequent 30-minute checks. Collection requires offroad state. Publication is due nightly at 11 p.m. Pacific, with catch-up while powered, offroad and online. A failed Connect request leaves the published snapshot unchanged. Each published device has its own verification date; no cached observation is relabeled as freshly fetched. Connect corrections may lower totals, so the old baseline-based monotonic guard has been removed.

```sh
cd /data/maintenance/ai-mileage
PYTHONPATH=/data/openpilot /usr/local/venv/bin/python -m unittest test_core test_publish
PYTHONPATH=/data/openpilot /usr/local/venv/bin/python publish.py --force-publish
```

Verify the remote commit and public JSON after publication. The publisher never force-pushes. A concurrent site update is retried from the latest remote branch. The original private ledger is preserved; no historical reclassification is implied by changing the public data source.
