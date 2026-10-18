# October 17 Tensor experiment evidence

These aggregates describe one Pixel 11 Pro XL / Tensor G6 running Android 17
and the matched LiteRT 2.3.0 runtime. They retain failed checks and outliers.
They contain timing summaries, counts, hashes and sampled health; private SDKs,
model weights, device identifiers and raw traces are excluded.

Read the [investigation report](../../../../docs/TENSOR_COMPILER_RUNTIME_2026-10-17.md)
for methods, interpretation and the final selected configuration.

| Evidence | Workload and comparison |
| --- | --- |
| [Native compiler pairs](compiler-pairs-aggregate.json) | Six balanced pairs; 600 measured fixed-input frames per run; SDK v2.0 versus v2.1. Also includes matched I/O instrumentation controls. |
| [App compiler pairs](app-compiler-pairs-aggregate.json) | Two pairs; 600 measured recurrent frames per run; same production APK. Screen behavior was not explicitly controlled. Per-run summaries only; no reconstructed pooled percentiles. |
| [Screen-off app compiler repeat](app-compiler-screenoff-aggregate.json) | Separate ABBA screen; 300 measured recurrent frames per run; screen explicitly off. Raw frames supported pooled summaries and output-fingerprint comparison. |
| [Production soak](production-soak-aggregate.json) | 6,000 measured recurrent frames with SDK v2.1; one run, not 6,000 independent replicates. |
| [Production wake checks](production-wake-aggregate.json) | Three bounded trials on `.10`/SDK v2.1; all stopped on the timing guard. Completed and unobserved frames are reported separately. |
| [Async app pairs](async-pairs-aggregate.json) | Matched diagnostic APKs; six completed pairs, including a repeated interrupted pair. Original completed runs and the launch failure are retained. |
| [All-buffer allocation](ahwb-pairs-aggregate.json) | Native ABBA screen; CPU RARELY versus OFTEN on every imported buffer. The candidate regressed. |
| [Output-only allocation](ahwb-output-pairs-aggregate.json) | Six native pairs; RARELY inputs and output RARELY versus OFTEN. Full result, last-pair timing shift, first-five sensitivity and the candidate tail outlier are retained; app validation is separate. |
| [Output-allocation app pairs](output-app-pairs-aggregate.json) | Six uninterrupted pairs; managed inputs, imported RARELY versus OFTEN output. Mixed pair directions and interval spanning zero; no app gain established, production restored. |

All tests used the original model architecture and existing explicit FP16
precision. The native fixed-input tests include every input/output copy but do
not exercise the app's recurrent queue logic. App tests exercise that logic
through the normal protocol, but PC ADB/TCP latency is not direct comma USB
latency. None of these reports alone qualifies driving or establishes a hard
50 ms deadline.

Paired uncertainty uses **run pairs** as the replication unit. Six-pair studies
remain small; a narrow bootstrap interval does not represent device-to-device
or long-term environmental variation. Two-pair exploratory screens have no
significance claim. Health is sampled, not continuously measured. Hash parity
covers the stated fixtures, not every possible camera frame.
