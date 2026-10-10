# Connect driving history and private assistance ledger

The public tracker uses only verified comma Connect device statistics. Manual additions and the owner-reported baseline were removed on October 10, 2026. `baseline.json` is no longer read. Local log mileage is never added to Connect totals, avoiding overlap and incompatible engagement definitions.

The current comma 4 retrieves both authorized devices' `v1.1/devices/:dongle_id/stats` using its existing device identity. Credentials are used only for normal authentication with comma's service. `connect-devices.json` retains the older device's last verified observation when its refresh fails. Each device keeps its own source and verification date.

The [official API](https://api.comma.ai/) defines these as total driving distance, minutes and routes. The public figures are **driving totals**, not verified active-assistance totals. Each device is rounded to Connect's whole-mile/hour display precision before summing. On October 10 the combined display totals were **60,805 miles, 3,399 drives and 1,662 hours**.

## Private log collection

`collect.py` still integrates valid speed while lateral or longitudinal control is active, counting their union once. It rejects stale/invalid samples and excessive gaps. Its private, deduplicated ledger supports drive analysis and survives deletion of old logs. It is independent of the public Connect count. Raw logs, identifiers, coordinates, keys and the ledger are never committed or published.

## Deployment and schedule

The files live under `/data/maintenance/ai-mileage`. Deploy `publish.py`, `engagement.py`, `collect.py`, `core.py`, `connect-devices.json` and tests there. Keep the existing dedicated website deploy key and known-hosts configuration. The publisher only modifies `data/assisted-miles.json` and `data/engagement.json`; the legacy mileage filename remains for existing links, but schema 2 uses `driving_miles` and contains no manual baseline.

The private `connect-private-devices.json` lists the current device as `{"name":"comma 4","current":true}` and an authorized older device as `{"name":"comma 3","id":"<private device identity>"}`. Never commit this file or `engagement-ledger.json`. Preserve the ledger on upgrades. Back up existing files and deploy only offroad with no publisher running.

## Recovered engagement

The October 10 audit recovered approximately **6h 14m**: 3h 57m from 15 recent comma 4 timelines, 2h 14m 37s from eight older comma 4 event recordings, and 2m 14s from three reviewed comma 3 recordings. Two of those comma 3 recordings had no state events; their engagement is unknown, not confirmed zero. Four additional 2023 comma 3 recordings retained metadata but returned 404 for event files and empty downloadable-log lists. Thirty distinct routes were inspected; 26 had timeline/event material. This is not a lifetime engaged total or model attribution.

`engagement.py` queries all available route metadata with bounded pagination, integrates Connect's enabled intervals, and deduplicates by private route identity. It clips incompletely processed recordings, leaves unknown prefixes uncounted, and preserves prior observations if files disappear. Downloads are size/time bounded and offroad checks occur throughout. Failed files are retried on a later date. A refresh has a four-minute work budget, then continues at the next publication. Only device/month aggregates are public.

The API currently returns fewer recent routes than the browser. The private ledger therefore retains the 15 dated, approximate timeline observations. These are evidence-derived, not owner estimates. Automatic updates can add event-backed routes when the API exposes them; the updater cannot reconstruct unavailable history. Connect statistics are never multiplied by the sample engagement percentage.

`clarity-ai-mileage.timer` retains its existing five-minute boot check and subsequent 30-minute checks. Collection requires offroad state. Publication is due nightly at 11 p.m. Pacific, with catch-up while powered, offroad and online. A failed Connect request leaves the published snapshot unchanged. Each published device has its own verification date; no cached observation is relabeled as freshly fetched. Connect corrections may lower totals, so the old baseline-based monotonic guard has been removed.

```sh
cd /data/maintenance/ai-mileage
PYTHONPATH=/data/openpilot /usr/local/venv/bin/python -m unittest test_core test_publish test_engagement
PYTHONPATH=/data/openpilot /usr/local/venv/bin/python publish.py --force-publish
```

Verify the remote commit and public JSON after publication. The publisher never force-pushes. A concurrent site update is retried from the latest remote branch. The original private ledger is preserved; no historical reclassification is implied by changing the public data source.
