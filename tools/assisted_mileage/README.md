# Connect driving history and private assistance ledger

## Model and accelerator usage

The offroad updater also runs `collect_model_usage.py`. It records a separate,
durable private `model-usage-ledger.json` and `model-usage-summary.json`, with
Pixel large-model, Jetson large-model, unknown large-model hardware, small-model,
and unknown-output categories. Each category separates observed model time/distance
from assisted time/distance. Assistance requires valid active lateral or longitudinal
control, counted as a union; merely running the model is not assisted driving.

Attribution combines valid `modelV2.big` output with the device identity logged
by the JetLink HELLO handshake. Tensor device identities identify the Pixel backend;
explicit Orin/Jetson identities identify Jetson. Generic “jetson attached” text,
`bigModelAvailable`, or the current plugged-in device are not evidence of historical
hardware use. Link loss clears the peer. Identity may continue only across adjacent
segments of the same route with a gap no greater than one second. Missing identities
remain unknown, including old logs without usable handshakes.

Speed, controls and model outputs are aligned by monotonic timestamps. Full-rate model/control
samples expire after 0.25 seconds; missing or invalid speed intervals are excluded.
The collector is incremental, runs only offroad, and has a three-minute work budget
per updater run. Existing assistance and engagement ledgers are preserved. Historical
coverage is limited to retained logs; this does not reconstruct lifetime model use.
The historical per-device model-use ledger stays private. A separate, authorized combined recovered-log counter is published as `data/model-miles.json`; it is never added to Connect lifetime totals.

## Cloud totals handoff

The website repository now contains an hourly Connect statistics workflow. Its
account token stays in GitHub Actions secrets. After its first successful refresh,
the published JSON declares `publisher: github-actions`; this comma publisher
preserves that snapshot and continues its separate engagement and private-log work.
Before that first success, the current comma-based nightly totals remain active.

The public tracker uses only verified comma Connect device statistics. Manual additions and the owner-reported baseline were removed on October 10, 2026. `baseline.json` is no longer read. Local log mileage is never added to Connect totals, avoiding overlap and incompatible engagement definitions.

The current comma 4 retrieves both authorized devices' `v1.1/devices/:dongle_id/stats` using its existing device identity. Credentials are used only for normal authentication with comma's service. `connect-devices.json` retains the older device's last verified observation when its refresh fails. Each device keeps its own source and verification date.

The [official API](https://api.comma.ai/) defines these as total driving distance, minutes and routes. The public figures are **driving totals**, not verified active-assistance totals. Each device is rounded to Connect's whole-mile/hour display precision before summing. On October 10 the combined display totals were **60,805 miles, 3,399 drives and 1,662 hours**.

## Private log collection

`collect.py` still integrates valid speed while lateral or longitudinal control is active, counting their union once. It rejects stale/invalid samples and excessive gaps. Its private, deduplicated ledger supports drive analysis and survives deletion of old logs. It is independent of the public Connect count. Raw logs, identifiers, coordinates, keys and the ledger are never committed or published.

## Deployment and schedule

The files live under `/data/maintenance/ai-mileage`. Deploy `publish.py`, `engagement.py`, `collect.py`, `core.py`, `collect_model_usage.py`, `model_usage.py`, `connect-devices.json` and tests there. Keep the existing dedicated website deploy key and known-hosts configuration. The publisher only modifies `data/assisted-miles.json` and `data/engagement.json`; the legacy mileage filename remains for existing links, but schema 2 uses `driving_miles` and contains no manual baseline.

The private `connect-private-devices.json` lists the current device as `{"name":"comma 4","current":true}` and an authorized older device as `{"name":"comma 3","id":"<private device identity>"}`. Never commit this file or `engagement-ledger.json`. Preserve the ledger on upgrades. Back up existing files and deploy only offroad with no publisher running.

## Recovered engagement

The deeper recovery on October 10 added **1h 44m 15s** from eight distinct saved/retained comma 4 recordings (200 qlog segments), with owner approval to include them as **Recovered device logs**. Seven have positive enabled time; one has no observed enabled samples. The combined recovered total is approximately **7h 58m**, while Connect evidence remains approximately **6h 14m**. These sampled observations integrate `selfdriveState.enabled` only between adjacent valid samples at most one second apart, without extrapolating outside the observed window. Public `sources` separates the two origins; a future Connect event record replaces the same private route key rather than adding it again.

The authenticated account inventory was expanded beyond its initial page: comma 4 retained 23 routes, comma 3 seven, and neither had preserved routes. Saved archives were also checked; overlaps were excluded. The owner no longer has the old comma 3 or other backups. Published retention is three days without Prime or one year with Prime ([comma support](https://www.comma.ai/support)). Lifetime driving statistics cannot reconstruct discarded engagement states. This does not establish whether comma support has any internal recovery option.

The October 10 audit recovered approximately **6h 14m**: 3h 57m from 15 recent comma 4 timelines, 2h 14m 37s from eight older comma 4 event recordings, and 2m 14s from three reviewed comma 3 recordings. Two of those comma 3 recordings had no state events; their engagement is unknown, not confirmed zero. Four additional 2023 comma 3 recordings retained metadata but returned 404 for event files and empty downloadable-log lists. Thirty distinct routes were inspected; 26 had timeline/event material. This is not a lifetime engaged total or model attribution.

`engagement.py` queries all available route metadata with bounded pagination, integrates Connect's enabled intervals, and deduplicates by private route identity. It clips incompletely processed recordings, leaves unknown prefixes uncounted, and preserves prior observations if files disappear. Downloads are size/time bounded and offroad checks occur throughout. Failed files are retried on a later date. A refresh has a four-minute work budget, then continues at the next publication. Only device/month aggregates are public.

The API currently returns fewer recent routes than the browser. The private ledger therefore retains the 15 dated, approximate timeline observations. These are evidence-derived, not owner estimates. Automatic updates can add event-backed routes when the API exposes them; the updater cannot reconstruct unavailable history. Connect statistics are never multiplied by the sample engagement percentage.

`clarity-ai-mileage.timer` retains its existing five-minute boot check and subsequent 30-minute checks. Collection requires offroad state. Publication is due nightly at 11 p.m. Pacific, with catch-up while powered, offroad and online. A failed Connect request leaves the published snapshot unchanged. Each published device has its own verification date; no cached observation is relabeled as freshly fetched. Connect corrections may lower totals, so the old baseline-based monotonic guard has been removed.

```sh
cd /data/maintenance/ai-mileage
PYTHONPATH=/data/openpilot /usr/local/venv/bin/python -m unittest test_core test_publish test_engagement test_model_usage
PYTHONPATH=/data/openpilot /usr/local/venv/bin/python publish.py --force-publish
```

Verify the remote commit and public JSON after publication. The publisher never force-pushes. A concurrent site update is retried from the latest remote branch. The original private ledger is preserved; no historical reclassification is implied by changing the public data source.

## Recovered combined big-model miles

The October 10 update backfills all available retained and archived logs. The earlier forward-only activation filter has been removed from public totals; `model-tracking.json` remains a private audit artifact and does not exclude older miles. This count is recovered log coverage, not lifetime big-model driving. It stays separate from Connect lifetime driving totals.

`publish_model_miles.py` publishes `data/model-miles.json` schema 3, including separate assisted-mile totals for Pixel and Jetson. The hourly GitHub Actions workflow refreshes Connect lifetime statistics only; the comma updater computes device model use and pushes the split to the website. It adds Pixel, Jetson and explicitly **unattributed large-model** assisted distance. A positive logged execution flag is required; merely selecting or making a large model available does not count. Lateral or longitudinal control must be active; their union is counted once. Unknown accelerator identities are never silently credited to Pixel or Jetson. The public summary distinguishes full-rate miles, sampled miles and unrecorded hardware identity without exposing route IDs or device identifiers.

`collect_model_usage.py` prefers full-rate `rlog.zst` over `qlog.zst` for each segment. Full-rate evidence uses `modelV2.big`, 0.25-second model/control freshness and adjacent valid speed samples. Compact logs preserve the copied execution flag in `drivingModelData.big` at approximately 2 Hz. For compact logs, a model interval is counted only between two matching valid model samples no more than 0.75 seconds apart; the last sample is never extrapolated. Controls retain 0.25-second freshness and speed gaps remain limited to 0.25 seconds. Compact recovery is a sampled estimate: brief changes between model samples remain unknowable.

The private segment ledger deduplicates archived/device copies. A later full-rate record replaces a compact record for the same segment; a compact copy cannot overwrite full-rate evidence after raw-log cleanup. Historical backfill is idempotent. Existing private assistance and engagement ledgers are preserved.

Deploy `publish_model_miles.py`, `test_model_history.py` and `test_model_collection.py` with the other updater files. The parent publisher lock protects the durable ledger and the dedicated model-site checkout. Only `data/model-miles.json` may be staged by this publisher. The existing 30-minute offroad timer refreshes this aggregate independently of nightly engagement publication and hourly cloud Connect totals. The comma must be powered, offroad and online to publish; failures leave dated public data intact. No manually reported miles are added.

## Truncated recordings (October 17 maintenance)

Both local collectors now catch malformed Cap'n Proto records and invalid Zstandard
streams per segment. An unreadable segment contributes no new count. A previously
verified record remains intact; the bad file's fingerprint is not cached, so a
repaired copy can be retried. Other recordings continue processing, and the
summary reports `unreadable_this_run`. This recovered the offroad publisher from
a truncated-recording crash that had blocked the model-mileage website refresh.
Connect lifetime totals remain independently owned by GitHub Actions.

The isolated regression fixtures exercise both malformed formats, continued
collection, repeat-run deduplication and preservation of an earlier good record.
Run `test_collect_corruption` with the comma's Python/cereal environment alongside
the existing counter tests. Deploy both `collect.py` and `collect_model_usage.py`
while holding the publisher lock; preserve private ledgers before replacing them.
