# Sustained TPU mode: 12 repeated wake-control pairs — October 11, 2026

**Sustained performance mode made the baseline slower and did not produce a
passing wake trial.** The installed JetLink release remains
`0.8.5-clarity-tensor.9`; the experimental mode is not promoted.

Across 12 pairs, burst mode averaged **35.00 ms** before wake, versus **47.39 ms**
for sustained mode. The candidate was slower in every pair, by **12.40 ms** on
average. The paired bootstrap 95% interval for the slowdown is **11.96–12.81 ms**.
This is a baseline result, not a measurement of wake-stall improvement.

[Aggregate evidence](../android/tensor/profiling/results-wake-sustained-2026-10-11.json) ·
[Reproduction](../android/tensor/profiling/WAKE_EXPERIMENT.md) ·
[Earlier burst versus high-performance comparison](TPU_WAKE_RUNTIME_2026-10-11.md).

## What changed

On the same Pixel 11 Pro XL / Tensor G6, A requested Google Tensor mode 5
(burst); B requested mode 4 (sustained performance). The diagnostic version
label was the only other source change. Model, precision, LiteRT 2.3.0,
recurrent state, input sequence, nice 0, Android CPU hints, instrumentation and
all timing/health guards stayed the same. Tracing was off during these trials.
No Face Unlock or other security settings were changed.

LiteRT describes sustained mode as intended for long-running heavy workloads.
That is not a promise of lower wake latency or priority over system workloads.
The test changes a requested runtime policy; it does not measure the effective
clock or establish a particular driver mechanism.
[Official performance-mode definitions](https://github.com/google-ai-edge/LiteRT/blob/main/litert/c/options/litert_google_tensor_options_type.h).

Both builds passed fresh 32-frame recurrent reference comparisons across all
15 output slices. All common output bytes matched across the timing trials,
including warmups. The candidate build passed 59 Android unit tests, and its
signing certificate matched the original release.

## Repeated controls and all failures

Before measuring, six AB and six BA pairs were shuffled with seed 202610112:
`AB AB BA BA AB BA BA BA AB BA AB AB`. Each trial reinstalled/restarted the app,
slept the screen for 10 seconds, excluded 100 warmup frames and attempted 100
baseline frames followed by 100 wake frames. A concurrent `KEYCODE_WAKEUP` was
scheduled at frame ID 200. The harness did not unlock the phone.

All 24 trials hit the existing 100-frame p95 limit. The 12 burst controls reached
the wake window. Nine sustained candidates stopped at the baseline guard before
wake; their wake windows are unavailable. The other three sustained candidates
reached wake and also failed the p95 limit. In total, **15 wake stimuli** were
delivered and **3,900 frames** were measured, excluding 2,400 warmup frames and
64 reference-parity frames.

| Pair | Burst baseline mean | Sustained baseline mean | Burst wake maximum | Sustained wake outcome |
| --- | ---: | ---: | ---: | --- |
| 1 | 35.074 ms | 47.719 ms | 93.015 ms | Stopped before wake |
| 2 | 35.692 ms | 47.543 ms | 87.463 ms | Stopped before wake |
| 3 | 36.018 ms | 47.955 ms | 83.201 ms | Stopped before wake |
| 4 | 35.078 ms | 47.923 ms | 87.395 ms | Stopped before wake |
| 5 | 34.957 ms | 47.542 ms | 90.807 ms | Stopped before wake |
| 6 | 35.772 ms | 48.423 ms | 90.317 ms | Stopped before wake |
| 7 | 34.622 ms | 48.169 ms | 85.076 ms | Stopped before wake |
| 8 | 34.530 ms | 46.651 ms | 94.840 ms | Stopped before wake |
| 9 | 34.492 ms | 47.616 ms | 84.584 ms | Maximum 88.605 ms; failed p95 |
| 10 | 34.633 ms | 47.889 ms | 87.837 ms | Stopped before wake |
| 11* | 34.458 ms | 45.606 ms | 91.527 ms | Maximum 91.493 ms; failed p95 |
| 12 | 34.637 ms | 45.694 ms | 82.635 ms | Maximum 84.684 ms; failed p95 |

Every observed wake window in this table contains 100 frames. Nine missing
candidate windows are censored, so an uncensored overall wake-mean improvement
is not reported. Comparing only the three surviving candidate windows would
select on timing success. No failed trial was discarded, replaced or relaxed.

The complete baseline windows permit the secondary paired comparison above:
50,000 seeded bootstrap resamples; exact two-sided sign-flip p = 0.00048828125.
Pairs, not individual frames, are the replicates. Secondary statistics are
exploratory, without multiple-comparison correction.

## Interruptions and sensitivity check

This was an interrupted sequence collected in three batches, with the original
24-trial order preserved:

1. After pair 1, the runner incorrectly treated the candidate's intentional
   pre-wake timing stop as a missing stimulus. It restored `.9`. The classifier
   was fixed to retain a timing-only pre-wake stop as a censored outcome. The
   first two trials remain unchanged; only unrun trials continued.
2. Before trial 22, an ADB battery query returned exit 1. The runner stopped
   before installing or measuring that trial and restored `.9`. A live check
   subsequently found the same Pixel answering normally at 32.3 C with thermal
   status 0. The cause of that one query failure is undetermined. Only the final
   B A B suffix continued, after health checks and matching APK/hash validation.

The second gap splits pair 11, marked with an asterisk. Before collecting the
final three trials, a sensitivity analysis excluding that pair was specified.
The remaining 11 pairs still show the candidate slower in every pair: **12.51 ms**
mean slowdown, bootstrap 95% interval **12.09–12.90 ms**. Thus this gap does not
explain away the baseline regression. Both interruptions and original manifest
hashes are retained in the aggregate evidence; raw result files were combined
without changing their bytes.

Twelve offline runner/analysis tests passed, including pre-wake censoring,
rollback, missing-stimulus rejection and exact-suffix continuation. Continuation
also rejects saved results absent from the manifest, preventing a replay after
a failure between saving a result and recording it in the manifest. The revised
analyzer also reproduced the earlier 16-trial aggregate statistics exactly.

## Decision and cleanup

Sustained mode is rejected for this workload. The earlier high-performance
comparison also did not establish a shippable gain. The prior hardware-counter
traces still identify runtime waiting beyond reported TPU execution as the
next useful target for investigation; this experiment does not establish its
cause or a fix.

Sampled thermal status stayed 0; maximum sampled battery temperature was
32.3 C. This is one phone using synthetic desk ADB/TCP traffic, not direct comma
USB or driving qualification. The repeated controls improve confidence in this
candidate's baseline regression, not in a general solution to wake stalls.

The original `.9` APK was restored, Cinque Terre Model V2 remained selected, the
temporary developer listener was disabled, port 5599 closed, ADB forwarding
cleared and the owned UI dump removed. No tests were left running. The original
production source was verified unchanged, and the published experimental patch
reproduced the tested candidate source exactly.
