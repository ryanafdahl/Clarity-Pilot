# Comma and Jetson maintenance — October 17, 2026

The Jetson now runs **JetLink 0.8.7**, with **32 compatible Ubuntu security-package updates**. It rebooted successfully, loaded the existing Cinque Terre V2 engine, and reported zero service restarts. The comma driving code already matched the current Clarity Pilot source; its **v0.8.5 client / adapter API 2** and existing USB fixes were retained. Both devices remain on protocol 3.

The comma's mileage job had been failing on a truncated recording. Both collectors now skip unreadable segments, retain prior verified history, and continue through healthy recordings. A successful publisher rerun processed 155 new healthy segments, reused 94, and skipped one unreadable segment; verified Connect lifetime totals remained 60,995 miles. The exact USB patches are also packaged in the reinstall branch as one guarded recovery step.

## Follow-up: Connect-only mileage

After the checks above, the owner requested removal of the local mileage updater.
Its timer and service were stopped, disabled and removed, along with the installed
`/data/maintenance/ai-mileage` directory and its device-side website deploy key.
Both systemd units now report `not-found`; the system mount was restored read-only.
Twelve historical JSON files were preserved privately under
`/data/maintenance/20261017/mileage-retired-data`.

The website's existing hourly GitHub Actions Connect refresh remains active and
independent of the comma. The displayed total is the sum of verified comma 3 and
comma 4 Connect statistics, with no local-log increments or manual additions.
The homepage now contains only miles, current work and LinkedIn. Its big-model
section and GitHub links were removed. The collector repair and test results
above document the investigation before retirement, not a currently installed job.

## What the drive logs show

Reviewed **246 compact logs and 246 full-rate segments from nine retained recordings**. The earliest recording has a missing prefix. Totals describe readable retained records, not lifetime use or uninterrupted coverage of the missing period. The general log reader reported a corrupt/truncated tail; the collectors conservatively exclude unreadable segments from new mileage rather than crediting partial data. Raw logs, private identifiers, coordinates and credentials are not published.

There were **285,467 large-model outputs**, with output-weighted reported execution averaging **22.88 ms**, maximum **55.48 ms**. The session table separates this execution measurement from camera-to-publication latency. A 23 ms execution time does not mean a 23 ms camera-to-control pipeline.

| Session | Segments | Large outputs | Execution mean / p95 / max, ms | Camera-to-publication p95, ms | Largest large-frame ID increment |
| --- | --- | --- | --- | --- | --- |
| 1 | 17 | 19,553 | 22.97 / 24.89 / 32.17 | 50.00 | 1 |
| 2 | 1 | 135 | 23.17 / 24.58 / 44.68 | 49.99 | 1 |
| 3 | 3 | 2,605 | 23.82 / 25.98 / 35.69 | 51.07 | 1 |
| 4 | 24 | 28,021 | 22.69 / 24.14 / 32.06 | 49.37 | 1 |
| 5 | 44 | 51,644 | 22.90 / 24.74 / 32.72 | 50.00 | 1 |
| 6 | 2 | 1,314 | 22.89 / 24.24 / 37.82 | 49.61 | 1 |
| 7 | 37 | 43,032 | 22.87 / 24.43 / 55.48 | 49.42 | 1 |
| 8 | 117 | 139,163 | 22.88 / 24.59 / 41.35 | 49.55 | 1 |
| 9 | 1 | 0 | 0.00 / 0.00 / 0.00 | 0.00 | n/a |

Session numbers above are local report labels, not public route IDs. Zeros in the small-only recording mean no large-model samples. No large-to-small fallback was observed after joining in the readable reviewed sessions; large-model frame IDs remained consecutive within each observed large-model interval. This does not fill missing prefixes or unreadable tails. **8,854 large outputs exceeded 50 ms camera-to-publication**, even though the reported model execution was faster. These are distinct measurements.

The full starts identify **Orin-sm87 / TensorRT 10.16.2.10**. The retained partial prefix cannot supply its original hello. Jetson telemetry across retained samples ranged from **24.1 to 71.9 °C**. These are historical drive results on the previous 0.8.5 server, not road qualification of today's 0.8.7 update.

Several starts logged `gadget read failed: [Errno 19] No such device`, followed by a five-second retry and a successful join around 26–28 seconds. That remains a startup issue to investigate with paired physical USB logs. The retained large-model intervals showed no subsequent fallback. The short final recording remained small-model only; absence of an accelerator there is not by itself an inference failure.

## Driving warnings

Four `controlsMismatch` samples occurred during one startup, at +13.49 to +14.23 seconds, before either lateral or longitudinal control or MADS was active. Panda reported controls disallowed at those samples. The only large-model execution over 50 ms was the first joined frame at +14.77 seconds (**55.48 ms**), also before active assistance. This is startup evidence, not a shutdown-only event or an observed interruption of active assistance; the root cause of the mismatch remains unproven.

The reviewed records contain a forward-collision-warning sample while lateral and longitudinal control were active. At that sample the large model was still running at **22.69 ms**. A separate steering-saturation sample occurred with **MADS lateral control active**, brake pressed and longitudinal control inactive; execution was **22.57 ms**. Ordinary `selfdriveState.enabled` was false for that second sample, but MADS was enabled, so describing it as unassisted would be wrong. Stock forward-collision-warning samples are listed separately in the machine-readable results.

These observations do not establish the traffic cause, appropriateness of either warning, or a steering/EPS fault. There is no coincident model-runtime stall in those warning samples. No control thresholds, EPS firmware, steering settings, alarms or phone authentication settings were changed.

## What changed and what was verified

- Jetson: native server **0.8.5 → 0.8.7**. TensorRT **10.16.2.10**, CUDA driver **13.2**, L4T **39.2.1**, MAXN_SUPER, switched-power configuration and model cache preserved.
- Ubuntu: **32 security updates**, including OpenSSH, systemd, curl and Bluetooth libraries. No kernel/NVIDIA/CUDA/TensorRT upgrade. Package audit was clean and a fresh query found no remaining candidate from the selected Ubuntu security origin; general upgrades and Pro/ESM are outside this statement.
- Comma: the two mileage collectors were fixed and deployed outside the driving checkout, with private ledgers backed up. Fourteen collector/counter tests passed, including real malformed Cap'n Proto and Zstandard fixtures, continued processing, repeat-run deduplication and prior-evidence preservation.
- USB recovery: all eight patched source hashes matched the live comma. The consolidated bundle passed fresh-baseline application and already-applied checks. Installed protocol/client/FunctionFS/link regressions passed **200 tests plus two subtests** from an isolated test copy. An initial run from `/data` triggered the test suite's filesystem guard on Python bytecode reads; the isolated run passed without changing the guard.
- Endpoint compatibility: **101 finite synthetic inference frames** over desk TCP, including a full raw-output response, protocol 3, expected V2 model SHA and Orin peer. Round-trip mean **99.72 ms**, maximum **188.29 ms**, while other analysis work was running. This is a compatibility check, not a USB throughput or 50 ms qualification.
- Jetson engine-only check: requested 60 seconds at model cadence; frame mean **18.1 ms**, maximum **18.3 ms**, accelerator mean **17.6 ms**, zero frames over 35 or 50 ms, thermal state nominal throughout. It excludes camera, comma warp and transport. No controlled before/after speedup is claimed.
- Post-reboot Jetson: normal USB service active, cached V2 engine ready, zero restarts. The temporary desk listener was removed and port 15599 closed. The devices were physically separate at the desk, as confirmed by the owner.

### Why the comma client remains v0.8.5

[Upstream v0.8.7](https://github.com/zoompilot/jetlink/releases/tag/v0.8.7) is the current stable server release checked for this maintenance. Its Python client now requires adapter API 3, the newer shared driving warp and changed model-state/reset contracts. Clarity Pilot uses the earlier model pipeline. Changing just the gitlink would disable or break that integration. The v0.8.5 and v0.8.7 Python/Swift wire protocol definitions are unchanged, and the live mixed-version check above passed.

The comma was therefore brought current within **Clarity Pilot's supported pipeline**, including its repaired maintenance job. A complete upstream model-pipeline migration remains separate work; this report does not claim it was installed. CD210 (`5b6436a9`) and Cinque Terre V2 (`37bfa141`) selections were preserved. V2 SHA-256: `09d080f36965bb2a0790500452bd328aa03c484d0222aa79d1ad9f021a522aec`.

## Reinstall, backups and next check

Use **`installer.comma.ai/ryanafdahl/Clarity-Pilot`**, which selects `ryanafdahl/openpilot`, branch `Clarity-Pilot`. The source of record remains `ryanafdahl/Clarity-Pilot`, branch `main`. Both repositories include this report and the [exact USB recovery bundle](../patches/jetlink-usb-current/README.md). Apply that bundle explicitly while offroad after a fresh install; it is not silently auto-applied at boot.

Private comma logs and maintenance backups are under `/data/maintenance/20261017`; the mileage-job backups are in its `mileage-before` directory. The Jetson retains `/opt/jetlink/0.8.5` and a root-only configuration backup under `/var/tmp/clarity-maint-20261017`. Preserve the separate mileage ledgers before wiping `/data`. Repository publication does not restore private device settings or model downloads automatically.

The Jetson's pre-network boot clock produced 1969/July timestamps, so date-filtered journals missed startup entries. A bounded all-history/boot review recovered engine-ready evidence but not a complete matching server journal for all drives. Paired service-causality claims are therefore limited. Three pre-existing, unrelated dnsmasq/ISC DHCP failures remain documented; the working desk network was preserved.

Next, with the Jetson back on the car's USB cable, confirm enumeration, the expected V2 engine and a sustained parked inference session before evaluating road behavior. Investigate the startup retry with both endpoints' monotonic logs. Today's desk evidence does not qualify direct USB or the unchanged Pixel backend.

[Sanitized measurements](validation/device-maintenance-2026-10-17.json).
