# Pixel USB drive review — October 10, 2026

The updated Pixel contributed approximately **8.67 miles with its large-model path active and steering or speed assistance active**, out of **8.90 recorded miles**. Three early USB disconnect/reconfigure cycles coincided with returns to the small model. The final **11 min 45.7 s** contained no further fallback before the user unplugged the phone in Park.

The owner's observation of a steadier finish is supported. **Screen-off is not established as the cause:** uninterrupted large-model output began about **58 seconds before** JetLink left the foreground. Wireless Android Auto connected later, and the final **5 min 31.2 s** with the display off and Android Auto connected had no fallback. These observations do not establish that USB dropouts or rare inference stalls are fixed.

[Aggregate evidence](validation/pixel-drive-screen-off-2026-10-10.json) · [Previous runtime/repair report](PIXEL_USB_STABILITY_LITERT23_2026-10-10.md) · [APK and installation](../android/README.md)

## Scope, identities and evidence

- Pixel 11 Pro XL / Tensor G6 / Android 17, JetLink **0.8.5-clarity-tensor.8**, version code **80508**. The installed version and update time were checked after the drive. The exact published APK SHA-256 is `a51d60b8445a5f89664d34658292e0d44cf946bbc5604045ffe3870690220df5`.
- LiteRT **2.3.0**, precompiled **Cinque Terre V2**, protocol 3. The previous validation compiled all 2,424 operators into one NPU partition and checked 32 recurrent frames. That numerical check was not repeated during this drive.
- The comma's retained Tensor G6 peer identity and all four deployed USB stability file hashes matched the documented update. Recording initData retained runtime startup commit `9369cf07a5afa216283f07519af2c4adb483bf46`; a startup commit alone does not capture subsequently applied working-tree patches.
- **20 full-rate rlogs**, spanning **1,153.863 seconds** including startup, stationary time and final unplug, were parsed without errors. All 20 rlogs and 20 qlogs were copied and SHA-256 verified against the source manifest. No video was required.
- Comma model outputs, controls, valid vehicle speed, events, manager state, 1,070 forwarded phone-health samples, send telemetry and kernel journal events were correlated with the Pixel's Android lifecycle, power, USB and battery histories.
- Kernel events use their journal real-time timestamps. Raw dmesg timestamps and cereal monotonic time are different clock domains and must not be directly subtracted. Recorded comma clock anchors agreed within 0.8 ms; cross-device Android alignment should still be read at approximately second-level precision.
- Android's rolling system logs retained the screen/power history but not the drive's detailed JetLink per-stage messages. The release app's private log was not available through ADB. Consequently, this report cannot independently reconstruct every Tensor invocation, queue delay or CPU scheduling stall.
- Public results contain aggregate counts and relative timings. Raw logs, route identifiers, device identifiers, exact trip times and location data remain private.

## Miles the Pixel helped drive

| Distance category | Estimated miles |
| --- | ---: |
| Total valid recorded vehicle distance | 8.904 |
| Steering or speed assistance active, any model | 8.706 |
| Assistance active with valid, recent large-model output | **8.671** |
| Assistance active with valid, recent small-model output | 0.032 |
| Assistance active but model state unavailable/stale | 0.003 |

Distance uses trapezoidal integration of valid `carState.vEgo` with `canValid`, and `carControl.latActive OR carControl.longActive`, including steering-only MADS. Lateral and longitudinal assistance are a union, never counted twice. Parked speed contributes zero. Invalid samples, speed gaps over 250 ms and cross-segment intervals are excluded. Control and model states must each be at most 250 ms old; intervals are split at their changes and expiry. The analysis read 114,485 speed samples, 114,554 control samples and 22,848 model samples; 299 speed intervals were skipped.

The total and assisted totals independently matched the existing mileage collector to less than one micrometer of numerical difference. Model categories sum to the assisted total. Attribution means the Pixel's large-model **path was active**, including any held prior predictions; it is not a claim that every control interval used a fresh NPU result. These miles are part of project use, not an extra amount to add manually to the shared website counter. Its independent ledger remains responsible for deduplication and publication.

## Three early USB interruptions

Times below are relative to the first retained recording message, not ignition or app startup. The initial large-model join occurred at **+36.901 s**.

| Small-model handback | Time on small model | Vehicle state at handback | Kernel evidence |
| --- | ---: | --- | --- |
| +152.442 s | 4.761 s | Stationary in Drive; enabled; MADS active | USB disconnect, then SuperSpeed reconfiguration |
| +372.002 s | 3.093 s | Stationary in Drive; regular controls disabled; MADS active | USB disconnect, then SuperSpeed reconfiguration |
| +443.659 s | 2.854 s | Moving in Drive; enabled; MADS active | USB disconnect, then SuperSpeed reconfiguration |

The three intervals total **10.708 seconds**. Each kernel disconnect timestamp is within 69 ms of its model handback; the bus reconfigured about 90–99 ms after each disconnect. No intervening Type-C physical detach was recorded for these three cycles. A logical reset can therefore occur while the cable remains attached. The data does not identify the initiating host, cable, connector, charger or driver as the cause.

Bus reconfiguration and return to the large model are different durations. The client must reconnect, prove the engine and satisfy its existing model-swap gate. Around the first and third recoveries, the enabled state dropped near the eventual rejoin. Do not remove the steering-active swap rule or lengthen stale-result allowances to make the interruptions disappear from the UI.

The final Type-C removal at approximately **+1,152.223 s** occurred in Park with assistance disabled. It is excluded from the unexpected-reset count, even though a generic log calls the resulting handback “mid-drive.”

## Screen, charging and Android Auto

The phone reported wireless power before USB attachment and until the final unplug. Near full battery, charging status alternated between charging and not charging; charger presence does not mean constant charging power.

The uninterrupted finish began at **+446.513 s**. JetLink left the foreground for **Dreamliner**, the charging screensaver, at approximately **+504.817 s**. This is not the same as the display being fully off. Wireless Android Auto started at approximately **+811.272 s**, briefly woke the display, and a later power-button event turned the display off at approximately **+820.995 s**.

| Phase, starting with first large-model output | Large outputs | Small outputs | Unexpected fallbacks | Comma execution p95 / max |
| --- | ---: | ---: | ---: | ---: |
| JetLink in foreground, 7 min 47.9 s | 9,146 | 211 | 3 | 43.14 / 102.48 ms |
| Dreamliner in foreground, 5 min 6.5 s | 6,129 | 0 | 0 | 42.82 / 47.00 ms |
| Android Auto connecting, 9.7 s | 194 | 0 | 0 | 43.83 / 46.91 ms |
| Display off with Android Auto, 5 min 31.2 s | 6,624 | 0 | 0 | 42.31 / 47.14 ms |

The complete steady finish contained **14,114 large-labelled outputs and zero small outputs**. Android Auto was absent when the early resets occurred and present during the clean final sample. That rules out a simple claim that Android Auto was necessary for these resets; it does not prove that wireless Android Auto or charging can never affect performance. The phases were sequential, with changing temperature, traffic and device state, not a controlled comparison.

## Timing, held results and thermals

| Measurement | Result |
| --- | ---: |
| Large-labelled model outputs, all marked valid | 22,093 |
| Small-model outputs, including startup and final unplug | 755 |
| Large-model execution mean / p95 / p99 | 39.95 / 42.86 / 44.37 ms |
| Largest execution observation | 102.48 ms |
| Execution observations over 50 ms | 4, all initial join/rejoin outputs |
| Camera EOF to model publication mean / p95 | 65.29 / 68.27 ms |
| Camera EOF to model publication maximum | 127.57 ms |
| Maximum sampled USB submission time / backlog | 1.44 / 0 ms |
| Largest send-refusal counter in 1,070 send samples | 0 |

**Comma-reported model execution is not isolated Tensor inference time.** Camera-to-publication includes more of the pipeline and is also not actuator latency. Neither should be substituted for the historical phone-processing or desk ADB/TCP round-trip metrics. The four execution outliers were 60.78, 102.48, 73.52 and 85.05 ms at initial join/rejoins. They are not proof of four equivalent NPU stalls.

Bounded backpressure remained active. During the stable finish, the cumulative held-result counter reached **15**, including “not sent” observations while an earlier request was outstanding. Thus “no fallback” does not mean every publication contains a fresh inference or that there were no delayed requests. Last-response timing printed near a reset can describe the previous reply and cannot establish the duration of the failed request. The missing detailed phone log prevents declaring the earlier isolated 124 ms Tensor spike eliminated.

Forwarded phone health reported **31.0–36.1°C battery temperature**, 267 samples with thermal status **0 (none)** and 803 with **1 (light)**. There were no severe-or-higher samples or power-save samples; maximum health age was about 1.00 s. Battery history reached 36.3°C near removal. Battery temperature is not SoC temperature, and a light thermal signal does not reveal the amount of clock throttling. The comma's sampled CPU/GPU maxima were 68.2/67.9°C, with normal thermal status throughout.

## Other observations

- No `commIssue`, `commIssueAvgFreq`, `selfdrivedLagging` or `modeldLagging` event was recorded; no required process was logged as stopped. No `softDisabling` state was observed. These checks do not erase the three model interruptions or certify vehicle-control behavior.
- Startup again reached a 6.01-second selfdrived initialization wait, with CAN valid but several initial messages unavailable. The first small-model output took approximately 1.155 seconds and was invalid; this preceded first engagement and was not Tensor inference.
- One initial location-filter reset, three rejected GPS almanac-save requests, an early cloud websocket error and a final DNS failure were logged. None identifies the cause of the three USB cycles.
- After the trip, the comma kernel reported Wi-Fi buffer-allocation failures about 84 seconds after the final unplug. They may be relevant to intermittent SSH access, but occur too late to explain the drive's earlier resets. A later snapshot had approximately 2 GB available memory and 53 GB free storage. No OOM process death was found in the reviewed kernel evidence.

## Jetson history correction

The owner reports using the **Jetson for commutes to and from work throughout the preceding week**. The [two-session JetLink 0.8.5 analysis](JETLINK_DRIVE_2026-10-10.md) covers the latest two recordings analyzed in detail, **not the Jetson's lifetime test count**. Earlier reports also contain driving evidence. An exact week-long drive count or Jetson-only mileage is not inferred from this statement, and the older commutes are not all attributed to today's software version.

## What this changes

The Pixel has now contributed measured assisted road miles on this update. The record progresses beyond desk-only evidence, while retaining a clear unresolved issue: three USB interruptions survived the repairs. The later clean stretch and modest phase timing difference are useful observations, not a controlled screen-off fix.

A follow-up should reproduce the early connection cycles while parked, with the same cooling, cable and software, changing screen/charger/Android Auto conditions one at a time and retaining both the kernel USB journal and exported JetLink stage logs. No driving-control settings, thermal protections or device software were changed for this analysis. The website now distinguishes owner-reported Jetson commute history, detailed Jetson measurements, measured Pixel contribution and aggregate project mileage.
