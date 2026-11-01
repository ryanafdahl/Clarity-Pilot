# Longer Pixel JetLink tests — November 1, 2026

**Both longer runs completed:** 12,000 measured frames each, approximately ten minutes per run, on `0.8.12-clarity-tensor.11`. All **24,000 measured phone-processing times were below 50 ms**, with maxima of 41.662 and 39.794 ms. Each run had one warmup frame above 50 ms, and both PC round-trip timing checks failed. [Sanitized results](../android/tensor/long-tests-2026-11-01.json).

These runs extend the [app-update checks](PIXEL_UPDATE_2026-11-01.md). The earlier 275.406 ms phone-processing stall remains unresolved; a later successful run would not erase it. Cinque Terre V3 remains [unqualified on the Pixel](PIXEL_V3_MODEL_2026-10-21.md).

## Test conditions

- Pixel 11 Pro XL, Tensor G6, `0.8.12-clarity-tensor.11` / code `81211`, LiteRT 2.3.0.
- Tensor TPU (precompiled), Cinque Terre V2, with the existing FP16 model and settings. No app, compiler, precision or timing-limit changes.
- V2 source SHA-256: `09d080f36965bb2a0790500452bd328aa03c484d0222aa79d1ad9f021a522aec`; compiled SHA-256: `328ae315dcd6e62e08aa670e04f11219e4766a11cfc37c261a54ef89f7c6c571`.
- PC ADB/TCP forwarding over USB. This does not exercise the direct comma-to-Pixel USB connection.
- Phone telemetry reported plugged-in at every recorded sample; the reported charging state varied during each run.
- Each run has 20 warmup frames followed by up to 12,000 measured frames, with 30 seconds of rest between attempts. Actual duration and rate are reported from captured timestamps.
- Inputs are 32 deterministic synthetic frames generated with seed 17, then cycled. Recurrent state resets only at frame zero and continues for the rest of each run. This is an endurance and repeatability test, not a new comparison against reference outputs or road data.

The existing harness stops when any measured phone-processing time reaches 100 ms, or a 100-frame phone-processing p95 reaches 50 ms. Health checks stop at battery temperature 43°C, Android severe thermal status (3), or missing/invalid/stale phone telemetry. These limits are unchanged. PC round-trip timing is reported separately; passing the phone guard does not mean every full exchange met 50 ms.

## Results

Times below are milliseconds unless stated otherwise. Measured statistics exclude the 20 warmup frames in each run; warmup maxima are listed separately.

| Metric | Run 1 | Run 2 |
| --- | ---: | ---: |
| Measured frames / requested | 12,000 / 12,000 | 12,000 / 12,000 |
| Measured duration, seconds | 603.315 | 604.046 |
| Achieved measured rate, Hz | 19.890 | 19.866 |
| Phone processing mean | 32.042 | 32.137 |
| Phone processing p95 | 33.922 | 34.006 |
| Phone processing p99 | 34.781 | 34.839 |
| Phone processing maximum | 41.662 | 39.794 |
| Measured phone frames over 50 ms | 0 | 0 |
| Warmup phone maximum | 52.947 | 58.055 |
| Warmup phone frames over 50 ms | 1 | 1 |
| PC round-trip p95 | 50.274 | 51.050 |
| PC round-trip maximum | 87.413 | 114.149 |
| PC round trips over 50 ms | 671 | 872 |
| Battery temperature before → after, °C | 27.7 → 34.4 | 34.4 → 37.9 |
| Highest recorded Android thermal status | 0 (normal) | 1 (light) |
| Phone timing guard | Passed | Passed |
| PC round-trip timing check | Failed | Failed |
| Stop reason | Completed requested frames | Completed requested frames |

Phone-processing p95 stayed between 33.777 and 34.106 ms across Run 1's ten 1,200-frame blocks, and between 33.801 and 34.172 ms in Run 2. All 240 shorter 100-frame timing blocks passed. Aggregate and block metrics were independently recomputed from the per-frame captures, with exactly 20 warmup and 12,000 measured frames confirmed per run.

Full-output hashes matched for **all 12,020 corresponding frames**, including warmup, with no mismatches. Every measured output was finite. This demonstrates repeatability between these two runs; it is not a new reference-accuracy result.

Temperature rose to 37.9°C and Android reported light thermal status at the end of Run 2, below the unchanged stop thresholds. The maximum recorded phone-telemetry age was about 1.005 seconds; recorded samples were taken every 20 frames, while health was checked on every frame. These results cover the tested duration, not an established long-term temperature plateau.

The lower phone-processing times do not turn the PC round-trip failures into passes. ADB transport and host scheduling are included in those exchanges, and the direct comma USB path was not exercised. The earlier 275.406 ms phone-processing stall did not recur in these two runs, but its cause remains unresolved. No claim is made that the update fixed stalls or established a speed improvement.

## Handoff

The app and compiled-model hashes were checked unchanged. The phone was left at **Waiting for Comma · Cinque Terre Model V2** with no test load running. Its temporary Developer listener was disabled and checked after an app restart; owned ADB forwarding and the temporary phone UI file were removed.

At final handoff the battery had cooled to 35.5°C and Android thermal status was normal (0). The phone was USB-powered, with no wireless power reported. The comma was not contacted or reconfigured. No physical comma USB test or driving qualification is established by these desk runs.
