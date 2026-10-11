# Recovered big-model assistance — October 10, 2026

The website now displays **161.14 recovered big-model assisted miles**, replacing the zero from the previous forward-only activation filter. Historical evidence remains separate from Connect lifetime driving statistics.

## Evidence and coverage

- 389 unique segments from 18 recordings: 260 full-rate and 129 compact-log segments.
- 133.02 miles from full-rate logs; 28.12 miles estimated from compact logs.
- 132.44 miles have recorded Pixel or Jetson identity. 28.70 confirmed large-model miles have no recorded accelerator identity and remain unattributed.
- The oldest positive-distance evidence is October 3, 2026. This is available-log coverage, not lifetime large-model mileage.

The audit processed all 254 retained full-rate segments, six additional archived full-rate segments, and 129 additional unique saved compact segments. Archive/device duplicates count once. Full-rate evidence replaces sampled evidence for the same segment and survives raw-log cleanup in the private durable ledger.

Distance requires valid speed, logged large-model execution and active lateral or longitudinal control, counting their union once. Compact estimates require matching valid model samples no more than 0.75 seconds apart. Final samples, missing data and differing-state intervals are not extrapolated. Brief transitions between compact samples cannot be recovered.

Six matching full-rate/compact segments from the latest Pixel drive yielded 1.9398 and 1.9258 miles respectively, a 0.0140-mile difference. This comparison does not establish a correction factor for other drives.

## Connect availability

All 15 currently listed routes returned empty downloadable log lists through the comma device authentication. Another 23 cached older route identities returned errors; a sampled follow-up returned HTTP 403. This is an access limitation, not proof that those logs were deleted. No missing miles were guessed from lifetime totals or manual reports.

## Validation and automatic updates

All 31 updater tests passed on the comma, including real compressed log fixtures for compact recovery, full-rate replacement and preservation after raw-log cleanup. The updated collector and publisher are installed offroad. Publication now includes the complete deduplicated ledger rather than only recordings after activation. The existing 30-minute offroad timer continues collecting and publishing; hourly Connect lifetime totals remain independent.

Only public aggregates are committed. Raw logs, credentials, route identifiers and per-device evidence stay private. No driving-control or model-runtime behavior changed in this update.
