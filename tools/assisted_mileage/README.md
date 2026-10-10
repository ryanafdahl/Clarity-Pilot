# Recorded AI-assisted mileage

The comma runs this maintenance task independently of the desktop computer. It integrates valid `carState.vEgo` speed over time while `carControl.latActive` **or** `longActive` is true, including lateral-only MADS assistance. It counts the union once, not the sum of steering and speed-control distances. A running model alone does not count as assistance.

The October 10, 2026 historical baseline is owner-reported: comma 4 **11,571 miles / 722 drives / 348 hours**, plus comma 3 **49,220 miles / 2,673 drives / 1,313 hours**, totaling **60,791 miles / 3,395 drives / 1,661 hours**. These historical figures were not independently classified from raw logs. `baseline.json` anchors the existing retained-log totals; they are treated as already included and are not added again. Only increases after this anchor are added to the historical baseline. A new recording with any active assistance adds one drive; active-assistance duration adds hours.

`core.py` linearly interpolates speed and splits intervals at control changes. It excludes invalid/CAN-invalid speed, impossible speed, stationary drift, speed gaps over 250 ms and control state older than 250 ms. Each segment starts fresh; the tiny unobserved interval between segments is omitted. Distances are estimates from vehicle speed, not GPS or a certified odometer.

## Collection and privacy

`collect.py` reads closed full-rate `rlog.zst` files while offroad, checks the state again before each segment, and atomically stores per-segment totals. Hashed segment identities prevent double counting. Changed files replace their prior contribution. Recorded totals survive log deletion; recordings deleted before initial collection are unavailable. Repeating an unchanged collection reuses the ledger without decoding logs again.

The private ledger, historical anchor, receipt, website checkout, and dedicated deploy key live under `/data/maintenance/ai-mileage`, outside the driving checkout. Back up **both `ledger.json` and `baseline.json`** privately before reinstalling or wiping `/data`. Loss of the ledger must be repaired from backup; the publisher refuses totals below the anchor or a decrease in published mileage. Never commit the ledger, key, raw logs, route identifiers or coordinates.

The public `data/assisted-miles.json` contains only cumulative miles/drives/hours, the owner-reported baseline, update date and fixed descriptions. The deploy key is restricted to `ryanafdahl/t3st.site`; no account-wide GitHub credential is installed on the comma. The publisher edits only that JSON file and never force-pushes. A concurrent website edit causes a rejected push to be retried from the latest remote branch next time.

## Schedule

`clarity-ai-mileage.timer` checks five minutes after boot and every 30 minutes after the prior run ends. This retains mileage sooner than waiting for the nightly publish. Publication is due at **11:00 p.m. America/Los_Angeles**, including daylight-saving changes. `Persistent=true` and the repeated offroad check permit catch-up after missed nights. An onroad check returns without reading logs or publishing. Offline checks can still retain counts locally; publishing retries later.

The comma must be powered and eventually have internet access. Neither this timer nor a desktop automation can update from a powered-off comma. It does not wake the car or change its power policy. The existing emergency log deleter still takes priority, so uncollected logs can be lost after long offline/onroad periods or abrupt power loss.

## Installation and verification

Copy `core.py`, `collect.py`, `publish.py`, and tests to `/data/maintenance/ai-mileage`, owned by `comma`, mode 700 on the directory. Use the comma venv and `PYTHONPATH=/data/openpilot`. Create an Ed25519 key there and register only its public half as a write-enabled deploy key on the website repository. Populate its dedicated `known_hosts` from GitHub's HTTPS-authenticated public metadata. Keep host checking enabled.

Install the service and timer in `/etc/systemd/system`, briefly remounting AGNOS `/` writable if necessary and restoring it read-only afterward. The service runs as `comma`, with low CPU/I/O priority, a 20% CPU quota, and a private temporary directory. No driving runtime file is modified.

```sh
cd /data/maintenance/ai-mileage
PYTHONPATH=/data/openpilot /usr/local/venv/bin/python -m unittest test_core test_publish
PYTHONPATH=/data/openpilot /usr/local/venv/bin/python publish.py --force-publish
sudo systemctl daemon-reload
sudo systemctl enable --now clarity-ai-mileage.timer
systemctl list-timers clarity-ai-mileage.timer
journalctl -u clarity-ai-mileage.service -n 20 --no-pager
```

Verify the public JSON on `https://t3st.site/data/assisted-miles.json` after GitHub Pages finishes publishing. The homepage badge links to an explanation of scope. It displays an unavailable state if JSON retrieval or validation fails.

Disable with `sudo systemctl disable --now clarity-ai-mileage.timer`; preserve the ledger. Revoke the repository deploy key to remove publishing access. AGNOS image replacement may remove the systemd units, so verify or reinstall them after an OS upgrade.

## Initial verification — October 10, 2026

- Eleven on-device tests passed: active lateral-only counting, control transitions, stale/invalid data, recording boundaries, nightly cutoff, daylight-saving handling, public-field allowlist, historical overlap and lost-ledger rejection.
- The initial pass counted 248 full-rate segments across eight retained recordings. Six had active assistance: 149.4256 assisted miles and 3.5720 assisted hours. These are anchored as already included in the owner's history, not added to the 60,791-mile baseline.
- A repeat pass decoded zero segments, reused all 248, and returned unchanged distance.
- The comma's dedicated key successfully committed and pushed the aggregate JSON to the website repository. The installed systemd service then returned `Result=success`, exit status zero, and the timer was enabled.
- The calendar resolved the next 11 p.m. Pacific publication to 06:00 UTC on October 11. The earlier 30-minute timer wakes collect only; publication is gated by the local nightly date.
- Private ledger and baseline backups were retained on the maintenance computer. Driving services and the driving checkout were not changed by the collector installation.
