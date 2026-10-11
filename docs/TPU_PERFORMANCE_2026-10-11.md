# Pixel TPU performance investigation — October 11, 2026

**Keep JetLink `0.8.5-clarity-tensor.9`, the existing FP16/minimal-sharding
model, and burst mode 5. No repeatable production speedup was established.**
Three new compiler variants, runtime modes, copy overhead, scheduling traces,
hardware counters, and a real Android priority candidate were tested. The
candidate initially looked faster; returning to the original app removed the
apparent gain. The original APK was restored, and the temporary Developer
listener and ADB forwarding were disabled.

The useful result is a clearer measurement boundary: actual TPU execution
averaged **29.4–31.0 ms** across measured minimal-model runs. A runtime call
also includes driver work and Android scheduling. One 55.16 ms native frame
contained **20.10 ms runnable but waiting for CPU time**. That spike cannot be
attributed to TPU compute time alone.

[Reusable profiler](../android/tensor/profiling/README.md) ·
[Machine-readable aggregate results](../android/tensor/profiling/results-2026-10-11.json)

## Device and model

- Live device: Pixel 11 Pro XL, Tensor G6, Android 17.
- Installed/restored app: `0.8.5-clarity-tensor.9`, code `80509`, LiteRT `2.3.0`.
- Source model: Cinque Terre V2, SHA-256
  `09d080f36965bb2a0790500452bd328aa03c484d0222aa79d1ad9f021a522aec`.
- Installed compiled model:
  `fc393523c5c1ddba9774382db513a5c62fad50cb187968ea25bc96db5480b51b`.
- SDK compiler:
  `d74bea45081aa90a39505a675c15f566d46dbcc35e55a98f755c02017464cd1f`.
- All four sharding variants used the same source, explicit `half`, Tensor G6,
  LiteRT 2.3.0, and compiler. Each compiled 2,424/2,424 operators into one NPU
  partition. The native harness also refused partial or non-NPU execution.

The phone was connected to the desk PC, not the comma. No vehicle controls,
comma timing limits, Jetson configuration, or installed model were changed.

## Where the time goes

The 120-frame hardware-counter run measured this average breakdown:

| Component | Mean |
| --- | ---: |
| Input-buffer writes | 0.834 ms |
| TPU hardware execution, vendor counter | 30.893 ms |
| Runtime-call remainder: driver, synchronization, scheduling | 3.200 ms |
| Output-buffer reads | 0.320 ms |
| Complete native call | 35.247 ms |

The runtime-call remainder is calculated by subtracting aggregate hardware
time from invocation wall time. It is not a separately measured pure driver
counter. Hardware time is approximately 88% of this native total; eliminating
every input copy would save less than a millisecond at this operating point.

Hardware counters were collected with LiteRT's metrics API, after warmup:
`hardware_execution_time_us` and `number_of_graph_executions`. They are
aggregate measurements, not a hardware latency distribution. Runtime-call
p95 must not be presented as TPU-hardware p95.

Reusing unchanged resident inputs measured approximately 0.01 ms input
handling, but the later copied-input control ran faster overall because
execution conditions drifted. This is an overhead bound, not a demonstrated
real-camera optimization. Actual camera and recurrent inputs must still be
updated correctly every frame.

## Compiler and runtime experiments

Native process, fixed synthetic inputs, copies enabled, 600 measured frames
per run after 20 warmup frames. These totals exclude the full JetLink protocol
and recurrent-history staging.

| Configuration | Mean | p95 | Maximum | Decision |
| --- | ---: | ---: | ---: | --- |
| Minimal, burst 5, initial | 35.400 | 37.281 | 64.617 | Current baseline |
| Minimal, high performance 3 | 35.135 | 36.909 | 42.648 | Small single-run difference; no established app gain |
| Minimal, sustained 4 | 47.703 | 49.372 | 67.528 | Reject: little timing margin |
| Minimal, burst 5, repeat | 35.460 | 37.409 | 43.987 | Baseline repeated |
| Moderate, burst 5 | 35.523 | 38.309 | 59.977 | No improvement established |
| Extensive, burst 5 | 37.446 | 39.411 | 53.483 | Reject: slower |
| Maximum, burst 5, first | 41.195 | 42.680 | 61.950 | Reject: slower |
| Maximum, burst 5, repeat | 41.009 | 42.645 | 45.644 | Regression repeated |

All times are milliseconds. Sharding was tested sequentially rather than in a
randomized crossover; small differences are not causal estimates. Battery
temperatures remained below the guard, and Android thermal status remained 0.
Status 0 does not mean CPU/TPU clocks were fixed.

All native measured outputs were finite. The final output hash for the same
fixed input was identical across these models and modes. That narrow check is
not recurrent parity qualification of the alternate compiled models. They
were rejected on performance and were never installed into JetLink.

Compiled candidate SHA-256 values:

| Sharding | Compiled SHA-256 |
| --- | --- |
| Moderate | `3c4b0b914fd9ba300ae91a29a438f57e9d317436ffa40c4ab1d2c9e1a67e9d40` |
| Extensive | `306586e51e465ca5dbe40b1b78d14772af944dac8374c440791d3ce00924d12e` |
| Maximum | `60f2db3084e832f31606cda24c539e137301d89f1f36224acd086200b362a025` |

## Android scheduling experiment

Perfetto covered 202 complete native frames in the aligned trace. Its longest
frame was 55.160 ms: 2.665 ms running on CPU, 32.398 ms sleeping/waiting, and
20.097 ms runnable. The runtime invocation included that scheduling wait.
No lost-event, overrun, or error counters were reported for this trace. This
proves one scheduling-induced spike in the shell benchmark; it does not prove
the cause of every app or driving outlier.

The app's dedicated session thread had Android nice 0 despite a Swift
`.userInteractive` property. A separate candidate explicitly requested nice
-4 for that thread, preserved an already higher priority, restored the prior
value at thread exit, and left ordinary scheduling, clocks, thermal limits,
model precision, and transport behavior unchanged. The device confirmed the
requested nice value. No busy-spin or real-time policy was introduced.

An interleaved native A/B/B/A experiment, 600 frames per case, changed pooled
mean total latency from about 34.746 to 34.665 ms: only 0.081 ms. Hardware means
remained approximately 30.3 ms. This did not establish a useful speedup.

Full app comparison, using its real recurrent pipeline and existing Android
CPU hints, produced the following **phone processing** times:

| App / run order | Measured frames | Mean | p95 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| Original .9 | 1,200 | 35.209 | 37.161 | 38.770 |
| Original .9, traced | 600 | 35.294 | 37.115 | 39.214 |
| Priority candidate, traced | 600 | 33.911 | 36.169 | 38.572 |
| Priority candidate, repeat | 1,200 | 34.359 | 36.373 | 38.338 |
| Original .9, return control | 1,200 | 34.281 | 36.438 | 39.363 |

The return control was 0.078 ms faster on average than the candidate repeat.
The candidate's p95 was only 0.065 ms lower. The early apparent 1.38 ms gain
was not reproduced against the return control. **Do not ship the priority
candidate as a performance fix.**

The traced candidate had shorter average runnable periods, 0.227 versus
0.329 ms, but that scheduling observation did not translate into an established
repeatable end-to-end gain. The five app runs had no measured phone frames
over 50 ms and no protocol or finite-output failures. ADB round-trip p95
remained above 50 ms in every run; desk transport timing is not direct-USB
timing. Twenty startup frames were excluded from each timing run.

The candidate also passed 59 Android tests, 53 native regressions, and the
existing 32-frame recurrent comparison across all 15 output slices. Those
checks support correctness within their scope; they do not establish a
performance improvement or driving qualification.

## Retained changes and next optimization targets

Follow-up: [real-app runtime and scheduling experiment](../android/tensor/profiling/APP_EXPERIMENT.md).
The [completed follow-up](TPU_RUNTIME_SCHEDULING_2026-10-11.md) measured a
0.132 ms mean advantage across eight eligible paired comparisons, but the
interval spanned both a slowdown and an improvement. A controlled screen wake
reproduced a large runtime stall on the control build. The earlier return
control does not establish that the true priority effect is exactly zero.

Retained: the profiler, aggregate evidence, and corrected Developer-listener
instructions. The installed .9 APK, compiled model, and production source
patch remain unchanged. The original working source checkout was preserved.
Raw traces, transient build artifacts, model weights, and the SDK stay local.

Prioritize future work in this order:

1. Capture rare **real-app** stalls with per-stage wall/CPU timings and
   synchronized scheduling traces. Keep raw traces private. The observed
   native scheduling stall is a lead to investigate, not a driving diagnosis.
2. Measure runtime/driver overhead separately from hardware time. The metrics
   API is usable on this device, so future profiling can stop conflating the
   entire invocation with TPU execution.
3. Investigate direct preparation into supported NPU buffers while preserving
   exact image history and recurrent state. Typical copy cost bounds the likely
   benefit; prove ownership and synchronization rather than skipping updates.
4. For larger hardware gains, use operation-level compiler/vendor profiling
   before graph changes or quantization. Preserve the original model as the
   reference; synthetic parity alone is insufficient to qualify altered model
   precision or architecture.

Keep repeat/return controls in every experiment. Never relax the comma's
existing deadlines or phone thermal guards to improve a benchmark score.

## References

- [Google Tensor compiler precision and sharding flags](https://developers.google.com/edge/tensor-sdk/compilation-flags)
- [LiteRT 2.3.0 metrics API](https://github.com/google-ai-edge/LiteRT/blob/v2.3.0/litert/c/litert_metrics.h)
- [Google Tensor metric implementation](https://github.com/google-ai-edge/LiteRT/blob/v2.3.0/litert/vendors/google_tensor/dispatch/litert_dispatch_metrics.h)
- [Perfetto CPU scheduling events](https://perfetto.dev/docs/data-sources/cpu-scheduling)
