# JetLink 0.8.5 drive review — October 10, 2026

**Scope clarification, October 10:** the owner reports Jetson-assisted commuting to and from work throughout the preceding week. This report analyzes the latest two retained sessions in detail; it is not a claim that the Jetson has only been tested twice. Earlier use is not all attributed to this software version, and no exact week-long mileage or trip count is inferred.

Two new recordings on the updated comma/Jetson pair contain **53,609 large-model outputs**, with consecutive frame IDs within each recording and **no fallback after either join**. The user reported no unusual warnings, disconnects, startup delay or steering/braking behavior. The logs still show startup delays and retries, a GPS backup warning, and one controls-mismatch event during shutdown.

These observations support successful USB operation in these two sessions. They do not establish that the earlier intermittent failures are fixed, qualify every vehicle-control behavior, or validate the separate Pixel backend or modified EPS firmware.

## Build and method

- Comma: Clarity Pilot, runtime commit [`9369cf07`](https://github.com/ryanafdahl/openpilot/commit/9369cf07a5afa216283f07519af2c4adb483bf46), including the JetLink integration in `95e5834f`. The checkout later advanced to `895687da` for README-only reinstall documentation; the recordings retain the runtime's startup commit.
- JetLink: **0.8.5**, client/server commit `4b747aebad3d8d96ab26d76f1668f2b2ecb1b667`, protocol 3, adapter API 2.
- Selected models: CD210 on the comma; Cinque Terre V2 on the Jetson Orin Nano Super 8 GB, TensorRT 10.16.2.10.
- All **47 full-rate rlog segments** were parsed without errors: 37 in recording A and 10 in recording B. Their combined recorded span is **45 minutes 32.75 seconds**, including startup, parked time and shutdown; this is not an engagement-duration claim.
- `modelV2.big`, frame IDs, execution time, camera EOF timestamps, events, selfdrive state, panda state, process status and forwarded Jetson telemetry were reviewed. A separate full-rate window resolved the final controls-mismatch event.
- Percentiles use the nearest-rank method. Times prefixed with `+` are relative to each recording's first retained message, not ignition or Jetson boot.
- A private archive contains 47 rlogs and 47 qlogs, all nonempty. Its SHA-256 matches the comma's copy. Public artifacts contain aggregates and relative timings only; raw logs, route identifiers and location data remain private.

The [machine-readable summary](validation/jetlink-085-drive-2026-10-10.json) contains the same aggregate measurements. The [maintenance record](JETLINK_UPDATE_2026-10-10.md) covers installation, security updates, software tests and rollback.

## Continuous large-model output

| Measurement | Recording A | Recording B |
| --- | ---: | ---: |
| Recorded span | 36 min 5.69 s | 9 min 27.06 s |
| First large-model output | +26.204 s | +25.958 s |
| Large-model outputs | 42,788 | 10,821 |
| Reported execution, mean | 22.57 ms | 22.50 ms |
| Reported execution, p95 | 24.24 ms | 23.83 ms |
| Reported execution, p99 | 25.46 ms | 24.11 ms |
| Reported execution, maximum | 37.52 ms | 33.00 ms |
| Execution samples over 50 ms | 0 | 0 |
| Reported large-model frame drops | 0% throughout | 0% throughout |
| Camera EOF to publication, mean | 47.51 ms | 47.32 ms |
| Camera EOF to publication, p95 | 49.22 ms | 48.69 ms |
| Camera EOF to publication, maximum | 62.33 ms | 57.63 ms |
| Camera EOF to publication samples over 50 ms | 645 | 26 |
| Publication interval, mean | 50.001 ms | 50.001 ms |
| Publication interval, maximum | 58.55 ms | 57.35 ms |

Every successive large-model frame ID increased by one within its recording. All large-model outputs were marked valid. Neither recording returned to the small model after joining, and neither recorded `commIssue`, `commIssueAvgFreq`, `selfdrivedLagging` or `modeldLagging`. No logged manager state showed a process required to run but stopped. Neither recording entered `softDisabling`.

**These timing metrics are different.** Comma-reported model execution is not pure GPU inference. Camera EOF to model publication includes more of the pipeline, but still does not measure camera-to-actuator latency. Zero execution samples over 50 ms does not mean all camera-to-publication samples met 50 ms.

The output-weighted execution mean is **22.55 ms**, approximately **14.7% lower** than the earlier 0.8.3 trip's 26.44 ms mean. These were different drives, not a controlled benchmark; the change cannot be attributed entirely to the release. The earlier results and handbacks remain documented in the [maintenance analysis](https://t3st.site/maintenance-005.html).

## Startup still takes time

| Startup observation | Recording A | Recording B |
| --- | ---: | ---: |
| First small-model output | +10.374 s | +8.756 s |
| First small-model execution | 1,150.95 ms, invalid | 1,146.95 ms, invalid |
| Selfdrived initialization wait | 5.47 s, timeout false | 6.01 s, timeout true |
| USB gadget read failure, `ENODEV` | +18.238 s | +18.619 s |
| Large model joined | +26.204 s | +25.958 s |
| First enabled state | +187.004 s | +183.737 s |

The USB failures logged a five-second retry and occurred before the successful joins. The initialization record in B reached its six-second wait limit while initial plan/calibration messages were not yet valid and debug topics were missing; `canValid` was true. The first small-model output was the only execution sample over 50 ms in each recording. Both outliers preceded engagement.

The user's lack of noticed symptoms is consistent with the absence of a recorded driving interruption, but it does not remove these startup findings. An independent drive-time Jetson boot log is missing, so these logs cannot split the roughly 26-second join into host boot, engine preparation and client retry costs.

## The controls-mismatch event was at shutdown

Recording B contains one `controlsMismatch` event at **+566.999 s**, immediately before the recording ends at +567.058 s. The surrounding full-rate window shows:

1. Assistance had been disabled since **+208.123 s**; the car was stationary in Park in the final window, with cruise disabled.
2. Panda ignition was false by **+566.860 s**, with controls disallowed and no panda faults.
3. `deviceState.started` became false at **+566.882 s**.
4. Panda safety mode changed from `hondaNidec` to `noOutput` at **+566.981 s**.
5. The mismatch appeared about 19 ms later.

This is a shutdown transition observation, not an active-driving disengagement or a large-model handback. The ordering is consistent with a shutdown timing race; it does not independently prove or fix its underlying implementation cause. Recording A had no controls-mismatch event.

## GPS backup warnings

There were **eight “Error storing almanac” messages**, seven in A and one in B, approximately every five minutes. In [`pigeond.py`](../openpilot/system/ubloxd/pigeond.py), `save_almanac()` emits that exact message when the receiver returns a negative acknowledgement to the request to save its almanac in flash. A timeout follows a different branch.

This identifies a GPS backup failure, separate from JetLink inference. It does not establish why the receiver rejected the save or prove a positioning fault. Neither recording contained `locationdTemporaryError`. No GPS firmware, receiver reset or control-code change was made on the basis of this warning.

## Jetson telemetry and journal limits

The comma retained **2,586 forwarded Jetson telemetry samples**: 2,060 in A and 526 in B. Reported temperature peaked at **61.0°C** and **61.8°C** respectively; reported power peaked at 12.87 W in each. GPU clocks were 918–1,020 MHz. These samples provide observed thermal and power context, not proof that no brief throttling or supply transient occurred between samples.

At the desk, the Jetson's 0.8.5 service was active with zero restarts in that boot, and the cached V2 engine became ready **10.06 seconds after boot**. The disconnected USB state at the desk was expected. That boot time is not the drive's engine-start measurement.

The retained system journals did **not** contain complete server records for these two car sessions. A scan across journal files found older service boots and the current desk boot, with historical real-time clock jumps and retention gaps. NTP was synchronized at the desk. The precise reason for the missing car-session records is unresolved; retention and clock issues are evidence limits, not established causes of a driving failure.

## Follow-up

- Improve paired server-log capture across car power cycles, retaining boot IDs and monotonic timestamps. Confirm capture survives power removal before relying on it for failure analysis.
- Investigate the repeatable startup USB retry and the initialization wait limit with both endpoints recorded.
- Investigate the receiver's almanac-save rejection separately from inference and control.
- Continue observing ordinary cold starts and longer supervised sessions. These two successful sessions did not exercise the earlier intermittent handback paths or controlled failure recovery.

This publication changes documentation and field notes only. The tested runtime, EPS firmware, steering settings and Pixel restrictions remain as recorded.
