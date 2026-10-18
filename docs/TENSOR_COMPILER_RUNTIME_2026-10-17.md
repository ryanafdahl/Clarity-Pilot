# Tensor compiler and runtime investigation — October 17, 2026

Tensor SDK v2.1 produces a substantial measured improvement for the existing Cinque Terre V2 model on Tensor G6. The source model, explicit FP16 precision, minimal sharding, LiteRT 2.3.0 runtime and model architecture are unchanged. The improvement comes from compiling the original converted graph with the newer vendor compiler.

This report separates native execution, the complete phone app, and vehicle USB behavior. All new measurements here are desk tests on one Pixel 11 Pro XL. They do not qualify the vehicle connection or resolve the previously observed wake stalls.

## Compiler comparison

Six balanced, interleaved pairs used 600 measured frames per run, 20 warmups, burst mode and a 50 ms period. Every run copied all inputs and outputs, required full NPU execution, checked outputs and sampled health. No outliers were removed.

| Native metric | SDK v2.0 | SDK v2.1 |
| --- | ---: | ---: |
| Total mean | 35.081 ms | 31.841 ms |
| Pooled p95 | 36.579 ms | 33.502 ms |
| Pooled p99 | 37.603 ms | 34.705 ms |
| Vendor hardware mean | 31.025 ms | 27.716 ms |
| Frames over 50 ms | 1 / 3,600 | 0 / 3,600 |

All six pairs favored v2.1. The paired mean advantage is **3.240 ms (9.24%)**, with a 50,000-resample paired bootstrap interval of **3.128–3.340 ms**. The run pair is the replication unit; 7,200 frames are not 7,200 independent experiments. The exact two-sided paired sign-flip p-value is 0.03125, with only six pairs. This interval describes this device and workload, not general performance across phones or temperatures.

The retained old-model 72.791 ms outlier included 40.045 ms in input staging; it was not hidden or labeled TPU execution. The new model maximum was 47.016 ms. Sampled battery temperatures were 27.0–31.4 C with thermal status 0. All twelve final native output hashes matched.

The native recurrent checker also fed each model its own previous outputs through the production queue reference. Both old and new compiles matched the original app's 32 saved outputs exactly and passed all 15 reference slices. This checks a finite fixture set; it is not a proof for every possible input.

## Same-APK phone app comparison

An ABBA comparison used the unchanged production `.10` APK and 600 measured recurrent frames per run. Only the imported compiler artifact and matching manifest changed. Both adjacent pairs favored v2.1, by 2.742 and 3.093 ms.

| Phone app metric | SDK v2.0 | SDK v2.1 |
| --- | ---: | ---: |
| Processing mean | 34.616 ms | 31.699 ms |
| Inference mean | 33.623 ms | 30.669 ms |
| Queue preparation mean | 0.856 ms | 0.887 ms |
| Frames over 50 ms | 0 / 1,200 | 0 / 1,200 |

The processing gain is **2.917 ms / 8.43%**. With only two app pairs, no confidence interval or significance claim is made. These results retain per-run percentiles; pooled percentiles cannot be recovered from run summaries.

Sampled health remained normal at 30.6–32.1 C. The PC ADB round-trip timing check still failed: the new model had 86 of 1,200 round trips over 50 ms and a maximum of 86.248 ms. That transport includes PC/ADB overhead and is distinct from the direct comma USB path. A fresh 32-frame app recurrent test with the new import matched all original app outputs exactly and passed all 15 reference slices.

### Explicit screen-off repeat and sustained check

A second, separate ABBA comparison explicitly turned the screen off before each run. With 300 measured frames per run, the unchanged production APK averaged **35.875 ms with v2.0 versus 33.233 ms with v2.1**, a **2.643 ms / 7.37%** improvement. Pooled p95 moved from 37.762 to 35.396 ms and p99 from 38.635 to 36.580 ms. The new model retained one 51.560 ms frame out of 600; the old model had none over 50 ms. All 320 corresponding output fingerprints, including warmups, matched across the four runs. Battery samples were 32.4–33.3 C, thermal status 0. This two-pair screen is reported separately from the earlier comparison, with no significance claim.

The selected v2.1 artifact then completed **6,000 measured recurrent frames** in production `.10`: mean **34.186 ms**, p95 **35.996 ms**, p99 **37.093 ms**, and maximum **50.098 ms**, with **one frame over 50 ms**. Five consecutive 1,200-frame blocks averaged 34.053, 34.304, 34.128, 34.248 and 34.197 ms. Sampled battery temperatures were 32.5–34.5 C with thermal status 0. The first 320 output fingerprints matched the preceding v2.1 recurrent screen; the remaining hashes have no independent per-frame reference. These results support a faster baseline but do not establish a hard real-time guarantee. The USB-to-PC transport is still not the direct vehicle path.

### Fresh wake checks

Three controlled checks used production `.10` and the selected v2.1 artifact. Each requested 300 measured frames and issued a screen-wake command at frame ID 140. All three stopped after 200 measured frames at the existing 100-frame p95 timing guard. **600 measured frames completed; 300 requested frames are unobserved**, not passes.

Before the requested wake frame, the three runs contained 360 measured frames with no processing time over 50 ms and a maximum of 37.346 ms. At or after that frame, **64 of 240** completed frames exceeded 50 ms. Per-trial maxima were **83.996, 83.891 and 92.750 ms**; corresponding post-command-window p95 values were 70.751, 69.303 and 81.518 ms. All 220 corresponding output fingerprints per trial, including warmups, matched the preceding v2.1 sequence. Sampled health remained normal at 35.4–35.8 C, thermal status 0.

The wake commands completed successfully, but no independent display-state capture was recorded. The aggregates retain command-overlap windows and the early-stop censoring. These runs have no per-invocation hardware or fence timing, so they do not locate the delay or establish its cause. **The compiler update has not resolved the wake-associated timing failure.**

## What the remaining work costs

An instrumented native run retained every size query, lock, memcpy and unlock. Its off/on/on/off comparison used the same binary and did not subtract an assumed timer overhead.

| Mean stage per frame | Input buffers | Output buffer |
| --- | ---: | ---: |
| Packed-size query | 0.0073 ms | 0.0007 ms |
| Lock | 0.1999 ms | 0.0779 ms |
| memcpy | 0.6234 ms | 0.2070 ms |
| Unlock | 0.0497 ms | 0.0164 ms |

The **0.8304 ms total memcpy time is an upper bound**, not a promised direct-staging gain. Input conversion/history preparation still has to happen, and supported synchronization remains necessary. The 1 MiB feature-history copy accounts for about 0.346 ms; the two image copies total about 0.272 ms. Run drift exceeded the precision needed to estimate small instrumentation overhead.

LiteRT 2.3's AHardwareBuffer allocator uses CPU read/write RARELY hints. A separately owned imported buffer can test OFTEN hints while retaining all required locks, copies and fences. This is a supported-allocation hypothesis, not evidence that synchronization may be skipped. [Allocator source](https://github.com/google-ai-edge/LiteRT/blob/v2.3.0/litert/runtime/ahwb_buffer.cc).

### Hardware-buffer allocation

A matched native ABBA screen imported independently owned AHardwareBuffers in both variants, changing only their CPU access hints. Applying OFTEN hints to **all** buffers made the total slower: **33.677 ms RARELY versus 34.437 ms OFTEN**. Input staging rose from 0.984 to 1.447 ms while output staging fell from 0.402 to 0.186 ms. Vendor hardware time was essentially unchanged (27.772 versus 27.746 ms). Both pairs regressed overall, so this change is rejected.

All 2,480 warmup and measured frames passed finite/consistent-output checks, descriptors matched except for the intended usage bits, and all four final output hashes matched. Battery samples were 32.3–33.2 C with thermal status 0. The isolated output improvement motivated a separately controlled output-only experiment; all locks, copies, fences and buffer ownership requirements remain intact.

A follow-up retained RARELY inputs and changed only the output allocation to OFTEN. Six balanced pairs, each with 600 measured frames and 20 warmups, averaged **33.767 ms for RARELY versus 33.144 ms for output-only OFTEN**. All six pairs favored the candidate. The complete paired gain was **0.622 ms**, with a 50,000-resample paired bootstrap interval of **0.133–1.492 ms** and exact two-sided sign-flip p=0.03125. Six pairs give coarse uncertainty; this is the smallest nonzero two-sided p-value available for that design.

The final pair had a much larger gain: **2.771 ms**, versus 0.040–0.298 ms in the first five. The last candidate's six 100-frame block means ranged from 30.585 to 31.678 ms, while its vendor hardware mean increased from 27.856 to 28.643 ms relative to its adjacent control. The cause of this change in timing is unknown. A **post-hoc first-five sensitivity** gives a 0.192 ms gain, bootstrap interval 0.103–0.278 ms and exact p=0.0625; it does not replace the complete result.

Output handling fell consistently, from **0.385 to 0.175 ms**, a **0.211 ms** mean gain across the six pairs. Tail behavior did not uniformly improve: pooled p99 was 36.388 ms for control and 36.744 ms for candidate. Control had no frames above 50 ms; candidate retained one **55.382 ms** frame out of 3,600, including 16.398 ms input staging and 38.890 ms invocation. Battery samples were 32.9–35.4 C, thermal status 0. These exploratory stage and tail metrics have no multiplicity correction.

All **7,440** warmup and measured native frames passed finite/consistent-output checks; every final output matched the compiler reference. Full requirements and descriptors confirmed that only the output CPU usage bits changed. Both native variants imported their input buffers, while the separate app experiment keeps the app's managed inputs unchanged. The native result justified the separate app comparison below; it did not establish a production app improvement. All copies, locks, fences and caller-owned buffer lifetimes remain intact. [Complete native output-only evidence](../android/tensor/profiling/results-2026-10-17/ahwb-output-pairs-aggregate.json).


### Output allocation in the phone app

The matched app comparison **did not establish an improvement**, so production `.10` retains its original managed output allocation. Both diagnostic APKs kept managed inputs, synchronous execution, all copies and synchronization, and the same SDK v2.1 model. Both imported output buffers: the control used RARELY flags and the candidate OFTEN. They also shared explicit buffer ownership and failure handling, so the control is not the unchanged production APK.

Six balanced pairs each used 300 measured recurrent frames, 20 warmups and the same screen-off policy. Processing averaged **34.076 ms for control versus 33.892 ms for candidate**. The paired gain was **0.184 ms**, with a 50,000-resample paired bootstrap interval of **−0.201 to 0.559 ms** and exact two-sided sign-flip p=0.34375. Four pairs favored the candidate and two favored control; their gains were 0.147, 0.211, 0.721, 0.775, −0.129 and −0.622 ms. Inference averaged 32.806 versus 32.610 ms; these six pairs do not establish that the native output-stage gain improves the complete app reliably.

Descriptive pooled processing p95 was **36.077 versus 35.726 ms**, p99 **37.564 versus 36.479 ms**, and maximum **47.554 versus 40.108 ms**. Neither variant had a processing frame above 50 ms in its 1,800 measured frames. PC ADB round trips still exceeded 50 ms in 774 control and 791 candidate frames, underscoring the separate transport limit. Tail metrics are exploratory, with no multiplicity correction.

All **320 corresponding output fingerprints**, including warmups, matched across all twelve runs and the preserved production reference. All measured outputs were finite. Battery samples were 33.8–34.8 C with thermal status 0 and no power-save state observed. The suite completed without interruption and restored the exact production `.10` APK. This screen establishes neither a wake improvement nor direct vehicle USB qualification. [Complete app output-allocation evidence](../android/tensor/profiling/results-2026-10-17/output-app-pairs-aggregate.json) · [Reviewed source, ownership fixtures and artifact identities](../android/tensor/profiling/output-app-reviewed/README.md).

## Graph representation and operation profiling

A static census counted 46.73 billion logical multiply-adds per frame. Batch matrix multiplication accounts for 97.1% of that counted arithmetic; its unique constant weight ancestors account for 93.1% of used constant bytes. These estimates identify compiler targets, but they are not measured time shares or DRAM traffic. Layout changes, fusion, tiling, padding and reuse affect the compiled execution.

An equivalent representation replaced 116 eligible constant-matrix BATCH_MATMUL operations with FULLY_CONNECTED, preserving exact FP16 weight bits, signatures, tensor identities and subsequent ADD operations. Fixture tests passed 100 cases. The complete rewritten model produced the same 32 recurrent outputs as the original app.

Their 835,396,288-byte dispatch payloads differed in one eight-byte range inside custom-op options; all nested buffer hashes matched. The outer packages also differed by 16 bytes of opcode metadata. The meaning of the eight differing payload bytes is unknown. Two short balanced timing pairs found **31.789 ms original versus 31.742 ms rewritten**, with inconsistent pair directions and essentially unchanged invocation time. This is no established practical gain, so the original graph is preferred.

[Graph census, exact-weight rewrite and payload comparison tools](../android/tensor/compiler-tools/README.md) reproduce these inspections without redistributing model data.

## Async completion

Reviewed synchronous and asynchronous diagnostic APKs both passed 59 Android tests and 15 targeted ownership/error cases. Both passed fresh 32-frame app parity. The candidate requires completion events for every output, waits before exposing results, and quarantines uncertain buffers/models until process exit after an error. It is a single-frame experiment, not pipelined inference.

The predeclared six-pair run stopped when Android's app-launch command failed before the final control run. The original eleven completed runs and failure remain recorded; the entire interrupted BA pair was repeated. Across the resulting six complete pairs, async averaged **33.670 ms versus 33.922 ms** for the matched synchronous diagnostic. The 0.252 ms advantage has a paired bootstrap interval of **−0.082 to 0.604 ms** and exact sign-flip p=0.28125. Four of six pairs favored async. This does not establish an improvement, so it is not promoted.

All 320 corresponding output hashes matched across all thirteen completed runs, including the unpaired original candidate. The original launch cause is unknown; no inference occurred in the failed launch attempt. A later production `.10` screen-off check averaged 34.204 ms, so the earlier-versus-later absolute difference cannot be assigned to diagnostic instrumentation. Screen policy, time and device conditions differed. The original production APK was restored after both suites.

## Operation timing visibility

The supported `google_tensor_dump_op_timings=true` compilation flag changed custom-op options, but neither the compiler's stdout/stderr nor its isolated output directories contained a per-operation timing table. A separate diagnostic model was then run for 120 measured frames each with vendor metrics detail levels 0 and 1. Both levels were accepted and returned only `hardware_execution_time_us` and `number_of_graph_executions`. The execution count was exactly 120 each, outputs matched, and bounded PID-filtered logcat also exposed no per-operation table.

Detail-level meaning is vendor-dependent; level 1 was an explicit probe, not a claim of documented per-op semantics. [Public detail-level contract](https://github.com/google-ai-edge/LiteRT/blob/v2.3.0/litert/vendors/google_tensor/dispatch/sb_api.h#L827-L833). This result is limited to the tested build, options and capture paths. Logs from separate vendor services are not covered by the process filter. More detailed visibility needs vendor guidance. An evidence-backed support draft is retained locally and has not been sent.

[Metrics diagnostic source and sanitized results](../android/tensor/profiling/metrics-detail/README.md) preserve the exact tested patch, request statuses and counter totals.

## Runtime compatibility and remaining leads

Google's [v2.1 release notes](https://developers.google.com/edge/tensor-sdk/release-notes) support Tensor G6 and stable LiteRT 2.3.0. No verified newer matched Android core/GPU/Tensor dispatch set was found in the official release artifacts. Generic CI AARs do not establish that a newer compatible Tensor dispatch exists.

The vendor SouthBound library is loaded from the phone system image. Replacing an app AAR does not replace that driver/firmware layer. [LiteRT late binding](https://github.com/google-ai-edge/LiteRT/blob/v2.3.0/litert/vendors/google_tensor/dispatch/sb_api_late_binding.cc). No verified public driver fix for the observed wake stalls was found.

In public LiteRT main revision `3a26d1209a24c74b49d552d95a3c5cf8d5c438a9`, Tensor input/output coherency preferences are parsed and stored, but the reviewed Google Tensor dispatch sources contain no consumer. This does not establish an optimization in the shipped LiteRT 2.3.0 runtime or rule out private system implementations. [Parsing](https://github.com/google-ai-edge/LiteRT/blob/3a26d1209a24c74b49d552d95a3c5cf8d5c438a9/litert/vendors/google_tensor/dispatch/litert_dispatch_device_context.cc#L91-L140), [dispatch use](https://github.com/google-ai-edge/LiteRT/blob/3a26d1209a24c74b49d552d95a3c5cf8d5c438a9/litert/vendors/google_tensor/dispatch/litert_dispatch_graph.cc#L85-L108). `LiteRtSchedulingInfo` is explicitly reserved for Android NPU Manager first-party access; it is not a supported JetLink job-priority control. [Stable API restriction](https://github.com/google-ai-edge/LiteRT/blob/v2.3.0/litert/c/internal/litert_scheduling_info.h#L45-L56). The supported compiler controls do not expose a general manual tiling/fusion interface. [Compiler options](https://developers.google.com/edge/tensor-sdk/compilation-flags).

## Reproduction and provenance

[Sanitized experiment aggregates](../android/tensor/profiling/results-2026-10-17/README.md) retain timing distributions, health, failures and paired analyses. [Reproduction tools](../android/tensor/profiling/README.md#october-17-compiler-and-runtime-investigation) include the native paired runner and separate experimental sources.

Keep the private SDK and model weights outside Git. For v2.1, the compiler library alone does not identify the complete compiler: the SDK also ships a worker executable. Record library, worker, converted input and compiled output hashes. All 2,424 original operators compiled into one NPU partition with the same `half` precision and `minimal` sharding. The [current model manifest](../android/tensor/qualified-model.json) records the source ONNX, converted graph, SDK archive, compiler library, worker and compiled output hashes; the [prior SDK v2.0 manifest](../android/tensor/qualified-model-sdk20-litert23.json) preserves rollback identity.

Two initial WSL compiler attempts were interrupted. The retained kernel log directly confirms an out-of-memory kill for the first attempt. The sequential retry ended during WSL instability, with an incomplete compiler log and filesystem/journal restart evidence; its retained log does not contain a second explicit OOM kill. An isolated run with temporary additional swap succeeded in 80.52 seconds; maximum observed process RSS was 15,544,096 KiB. This is process accounting, not total VM peak memory. Compiler and Android builds were then serialized. These interruptions do not establish model incompatibility.

The [paired native-model runner](../android/tensor/profiling/model-pairs/README.md) reproduces the balanced comparison with explicit device selection, verified staged hashes, health guards and preserved raw results.

The prior APK and model remain available for rollback. APK updates must preserve the existing signer and app data; do not uninstall as a downgrade workaround. The next vehicle check remains a supervised parked direct-USB test with normal health, proving, deadlines and fallback behavior.

## Final phone handoff

The phone was left on **Waiting for Comma**, with **Tensor TPU (precompiled)** and **Cinque Terre Model V2** selected. The production `.10` APK and v2.1 imported model hashes were rechecked after restoring the experimental APKs. The Developer listener was disabled and port 5599 remained absent after a fresh app restart; ADB forwarding and the owned native test directory were removed. The temporary host compilation swap file was also removed. Final sampled battery temperature was 32.6 C and thermal status 0.

[Sanitized final-state record](../android/tensor/profiling/results-2026-10-17/final-phone-state.json). The next step is a supervised parked physical USB check. This session did not arm the comma connection window or change its driving configuration, and the wake timing failures remain unresolved.
