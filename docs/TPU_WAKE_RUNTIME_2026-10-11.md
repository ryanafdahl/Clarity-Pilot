# Pixel wake stalls: repeated runtime-mode controls — October 11, 2026

**High-performance mode did not remove the wake stall: all eight control trials
and all eight candidate trials hit an existing timing limit.** The original
JetLink `0.8.5-clarity-tensor.9` remains installed. No production runtime-mode
change is promoted.

[Aggregate evidence](../android/tensor/profiling/results-wake-2026-10-11.json) ·
[Reproduce the experiment](../android/tensor/profiling/WAKE_EXPERIMENT.md) ·
[Earlier scheduling controls](TPU_RUNTIME_SCHEDULING_2026-10-11.md).

[Later sustained-mode comparison](TPU_WAKE_SUSTAINED_2026-10-11.md): 12 additional
pairs showed a baseline regression; no production mode change was promoted.

## Matched controls and small effects

Pixel 11 Pro XL / Tensor G6, LiteRT 2.3.0, Cinque Terre V2. A requested Tensor
performance mode 5 (burst); B requested mode 3 (high performance). Both used
identical diagnostic instrumentation, nice 0, CPU hints, model, precision,
input sequence, recurrent resets and health/timing limits. Instrumentation was
inactive during the primary comparison. These settings request a runtime mode;
they do not establish an exclusive TPU reservation or an effective clock rate.

The order was declared before measuring: `AB BA BA AB BA AB AB BA`. Every trial
reinstalled/restarted the app, slept the screen for 10 seconds, excluded 100
warmup frames and measured 100 screen-off baseline frames. One concurrent
`KEYCODE_WAKEUP` began at frame ID 200, followed by a planned 100-frame wake
window. The phone was not unlocked by the harness. Stimulus-command timestamps
are retained; dispatch is not instantaneous. Traced diagnostic runs were separate.

| Pair | Control wake mean | Candidate wake mean | Control observed maximum | Candidate maximum |
| --- | ---: | ---: | ---: | ---: |
| 1 | 39.595 ms | 40.092 ms | 81.668 ms | 89.567 ms |
| 2 | Incomplete: 8 frames | 40.469 ms | 112.620 ms | 90.257 ms |
| 3 | 40.529 ms | 40.321 ms | 96.116 ms | 89.622 ms |
| 4 | 40.391 ms | 40.614 ms | 93.592 ms | 91.619 ms |
| 5 | 40.877 ms | 40.336 ms | 91.528 ms | 90.611 ms |
| 6 | 39.980 ms | 40.239 ms | 79.977 ms | 91.487 ms |
| 7 | 43.712 ms | 40.728 ms | 90.430 ms | 91.231 ms |
| 8 | 40.235 ms | 41.001 ms | 92.546 ms | 92.681 ms |

Fifteen trials stopped at the 100-frame p95 guard; the other control stopped
immediately at the 100 ms per-frame guard. That control's missing 92 wake frames
are **censored**. Its observed maximum is not the maximum of a complete wake
window. We do not drop it, substitute a passing retry, or compute an uncensored
overall wake-mean gain from the surviving windows. One control exceeding 100 ms
and no candidate doing so is insufficient evidence of a reliable tail benefit.

The complete screen-off baselines permit a secondary small-gain comparison:
candidate mean advantage **0.051764 ms**, favoring B in **5 of 8 pairs**. The
paired 50,000-resample bootstrap 95% interval is **0.155 ms slower to 0.243 ms
faster**, with exact two-sided sign-flip p = **0.640625**. This result is
inconclusive and does not measure improvement during wake. Pairs, not individual
frames, are the replicates; secondary comparisons are exploratory.

All common output bytes matched, including warmup. Both builds separately
passed the 32-frame recurrent reference comparison across all 15 output slices.
Sampled thermal status stayed 0; maximum sampled battery temperature was 30.9 C.

## Separating TPU execution from runtime waiting

Two diagnostic traces recorded vendor counters for every invocation. All 600
frames including warmup had successful counter status and exactly one reported
hardware execution. Every measured stage had complete scheduler coverage, with
zero trace loss/errors.

| Slowest traced invocation | Burst control | High-performance candidate |
| --- | ---: | ---: |
| Invocation wall time | 91.828 ms | 89.345 ms |
| Vendor hardware execution | 36.206 ms | 33.921 ms |
| Running on CPU | 0.421 ms | 0.607 ms |
| Runnable, waiting for CPU | 0.113 ms | 0.035 ms |
| Blocked thread time | 91.294 ms | 88.703 ms |

The control's invocation exceeded its hardware counter by **55.622 ms**; the
candidate's difference was **55.424 ms**. These differences include dispatch,
completion/synchronization, scheduling and diagnostic overhead. They are not
precise measurements of one driver function, but show why the full invocation
cannot be labeled pure TPU execution time. Raising CPU thread priority alone
does not target the dominant delay in these examples.

System camera/authentication activity and a TPU cease event coincided with wake.
This is a lead, not proof that one service caused the stall. No system-feature
isolation test was performed and no biometric settings were changed. Raw traces
and system logs remain local.

## Allowlist question

Google Project Zero documented an EdgeTPU application allowlist on the Pixel 7
in 2024. Google subsequently announced a Tensor SDK beta workflow for custom
models through LiteRT in May 2026. Those descriptions refer to particular
devices and access paths, not a universal guarantee about every Pixel runtime.
On this tested Pixel, NPU-only execution and per-frame hardware counters show
that JetLink reaches the TPU. They do not establish its priority relative to
system workloads, nor explain the wake stall by an allowlist restriction.

Sources: [Google Project Zero](https://projectzero.google/2024/06/driving-forward-in-android-drivers.html),
[Google Tensor SDK beta announcement](https://developers.googleblog.com/google-tensor-sdk-beta-with-litert/).

## Retained work and cleanup

This follow-up measured **3,508 frames**: 3,108 untraced and 400 traced, excluding
warmups and reference-parity captures. Every timing stop remains recorded. This
is a single-device synthetic desk ADB/TCP experiment; it does not qualify direct
comma USB or driving.

Retained: a controlled-wake benchmark option, repeated-trial runner, censor-aware
analysis, diagnostic-only hardware-counter/mode patches and aggregate evidence.
Both Android builds passed 59 unit tests; ten benchmark/runner/analysis tests
passed. Patch application reproduced the tested source, and the original
production source was verified unchanged.

The original `.9` APK was restored, Cinque Terre V2 remained selected, the
temporary developer listener was disabled, port 5599 closed, ADB forwarding
cleared, and owned phone trace/config/UI files removed. No further device tests
were left running.
