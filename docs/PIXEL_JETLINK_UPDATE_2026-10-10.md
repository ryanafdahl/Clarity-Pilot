# Pixel JetLink update — October 10, 2026

The Pixel 11 Pro XL now has **0.8.5-clarity-tensor.5** (code **80505**), based on the latest upstream `main` checked for this update: [`b079496816e617ffd891ea12e5bee5d116db1383`](https://github.com/zoompilot/jetlink/commit/b079496816e617ffd891ea12e5bee5d116db1383). The latest published release was v0.8.5. The existing explicit-FP16 Cinque Terre V2 model and precompiled Tensor G6 selection were preserved.

**The parked-only restriction is removed.** The app no longer advertises `validation=parked_only`, requires `validation_mode=parked`, or offers the temporary Parked USB Test switch. USB service uses the normal upstream connection path. A live ordinary ENGINE_REQ completed successfully, followed by finite inference output, without a test flag. Phone health monitoring and its thermal refusal/recovery behavior remain active.

## What changed

- Updated from upstream v0.8.0 to the current `main` source, retaining this project's imported Tensor model support and byte image-history optimization.
- Kept the existing NPU-only precompiled path as **Tensor TPU (precompiled)**. Upstream's separate runtime compiler choice is labeled **Tensor NPU (on-device)**. Both retain phone health checks. On-device compilation was not qualified in this update.
- Used upstream's hash-checked LiteRT 2.2.0 Tensor runtime bundle, avoiding a duplicate private runtime fetch step. The existing model loaded successfully with `NPU(Tensor G6)` in the live app logs. The generic `gpu` timing field in upstream's session logs names the inference interval; it does not contradict that backend identity.
- Preserved the original signing identity and installed with `adb install -r`. Models and app data were retained. Read back the installed APK hash and verified it matches the archived APK.
- Retained the thresholds for missing/invalid/stale health (five seconds), Android severe thermal status (3+) and battery temperature (43°C). A health stop requires a fresh engine request after recovery. Android thermal and charging limits were not changed.

The comma and Jetson remain on their separately deployed v0.8.5 revisions. Their adapter, warp, model selections, controls and fallback logic were not changed by this Android update. The new app speaks protocol 3 and does not trigger the comma's legacy parked-only-peer rejection. A physical pairing of this APK with the comma has not yet been performed.

## Installed identity

| Field | Verified value |
| --- | --- |
| Device | Pixel 11 Pro XL, Tensor G6, Android 17 |
| APK | [jetlink-0.8.5-clarity-tensor.5-pixel.apk](../android/jetlink-0.8.5-clarity-tensor.5-pixel.apk) |
| APK bytes | 103915328 |
| APK SHA-256 | `6fd1bf4690a21156b29fd2033b3e6455627a0c72122453e47214c36aab66c642` |
| Signing certificate SHA-256 | `50e670489a4ba19aec5e9fbad6f06074556d4d07be629ba012b3ca78f1eabb4e` |
| Model | Cinque Terre V2, source SHA-256 `09d080f36965bb2a0790500452bd328aa03c484d0222aa79d1ad9f021a522aec` |
| Runtime | LiteRT 2.2.0, NPU(Tensor G6), existing FP16/minimal-sharding compilation |
| Model/source manifests | [qualified-model.json](../android/tensor/qualified-model.json) |

[Install and rebuild instructions](../android/README.md) · [Tensor source patch](../android/tensor/tensor-support.patch) · [Normal handshake evidence](../android/tensor/installed-protocol-2026-10-10.json) · [Machine-readable update record](../android/tensor/update-2026-10-10.json).

## Numerical and runtime checks

The release build and **59 Android tests** passed. The selected native suite passed **47 tests across 13 suites**, covering normal Tensor protocol, thermal health, manifest identity, queue staging, wire/layout conformance and LiteRT helpers. Python protocol/client/stateful/queue/Windows-framing tests passed **88 tests plus two subtests** in the existing Linux validation environment. The Windows partial-send fallback also passed directly on Windows. Initial attempts using system Python could not import pytest; they were rerun successfully in the existing validation environment. The exported patch was checked against a clean index of the exact upstream base.

All **15 output slices passed** the unchanged numerical criteria over **32 recurrent seed-0 frames**. All 64 captured input arrays were verified byte-identical to the existing original-ONNX reference fixtures before comparison. The pooled plan's weakest correlated column was **0.999904**, above the 0.999 threshold; small/quiet outputs retained upstream's absolute-error checks. [Numerical report](../android/tensor/parity-2026-10-10.txt). This is synthetic numerical parity, not a camera-input or driving-quality assessment.

The installed APK first completed 120 measured frames with phone/server p95 **37.43 ms**, then completed **6,000 measured frames plus 20 warmups** in **315.70 seconds**. The app was sent to the home screen during the longer run to exercise background monitoring.

| Longer desk run | Mean | p95 | Maximum | Samples over 50 ms |
| --- | ---: | ---: | ---: | ---: |
| Phone inference | 34.64 ms | 36.58 ms | 82.67 ms | 2 / 6,000 |
| Phone total, including queues | 35.84 ms | 38.01 ms | 83.90 ms | 3 / 6,000 |
| Full desk ADB/TCP exchange | 51.90 ms | 60.29 ms | 155.81 ms | 4124 / 6,000 |

All 60 phone timing blocks passed the existing criterion: 100-frame p95 below 50 ms and no phone execution reaching 100 ms. All measured outputs were finite, with no protocol or health failures. Phone telemetry included **302 samples**, battery **26.2–30.5°C**, thermal status **0**, and maximum sample age **1.00 seconds**. Slow frames are retained in the maximum and missed-deadline counts; this is not an every-frame 50 ms pass. [Short run](../android/tensor/desk-short-2026-10-10.json) · [Full soak](../android/tensor/desk-soak-2026-10-10.json).

**The ADB exchange did not pass a 50 ms p95 timing criterion.** Desk forwarding is a different transport from the comma's direct USB connection. These results establish normal protocol operation and phone-side execution at the desk; they do not establish direct-USB or driving readiness. The earlier direct-USB timing failures remain in the [October 3 archive](../android/tensor/history-2026-10-03.md). Reconnects, sustained in-mount cooling/charging, camera-derived outputs and physical fallback behavior remain unverified with this APK.

## Use and archives

Select **Tensor TPU (precompiled)** and **Cinque Terre Model V2**, and use the ordinary [USB connection procedure](../android/README.md#connect-to-the-comma). No special parked-test switch is needed. The app's Developer TCP listener was used only for the desk checks and is disabled afterward; direct USB remains enabled.

Previous APKs, the previous source patch and [October 3 instructions/results](../android/tensor/history-2026-10-03.md) are retained. The historical comma test harness and its original deployment manifest are unchanged; this update does not bypass that harness's compatibility checks. The private Tensor SDK, compiled model, signing key and device credentials are not published.
