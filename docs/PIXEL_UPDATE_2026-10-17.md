# Pixel update and performance check — October 17, 2026

The Pixel 11 Pro XL was updated in place from `0.8.5-clarity-tensor.9` to **`0.8.7-clarity-tensor.10`**. Its existing Tensor TPU (precompiled) selection, Cinque Terre Model V2 import, LiteRT 2.3.0 runtime, recurrent state behavior, USB recovery, CPU hints and thermal protections were retained. No comma software or driving configuration was changed.

Upstream v0.8.7 changes model catalog and LFS lookup. The inference loop is unchanged relative to the previous patched release. This is a maintenance update, **not a demonstrated speed improvement**. [APK and rebuild instructions](../android/README.md), [sanitized evidence](../android/tensor/update-2026-10-17.json).

## Measured on the connected phone

Each run used the same model identity, 20 warmup frames and 1,200 measured frames at a requested 50 ms period. These are synthetic recurrent tests over PC ADB TCP forwarding, not comma direct USB. Tests ran sequentially, baseline first; order and temperature are not controlled sufficiently to attribute small differences to the update.

| Metric, milliseconds | Previous .9 | Updated .10 |
| --- | ---: | ---: |
| Phone processing mean | 34.671 | 34.403 |
| Phone processing p95 | 36.287 | 36.263 |
| Phone processing p99 | 37.090 | 37.393 |
| Phone processing maximum | 37.899 | 38.885 |
| Inference mean | 33.689 | 33.377 |
| PC round-trip p95 | 53.716 | 57.510 |
| PC round-trip maximum | 103.517 | 72.842 |
| Phone frames over 50 ms | 0 | 0 |
| Protocol/finite-output failures | 0 | 0 |

Both phone timing checks passed. Both PC round-trip timing checks failed. The updated average leaves about 15.6 ms of a 50 ms frame period for other work, but this is not the full vehicle pipeline. It does not establish reliable USB transport, wake behavior, thermal endurance or driving qualification. Recorded thermal status remained normal (0); sampled battery temperatures stayed below 29 C.

The release build passed 59 Android unit tests and 53 selected native regressions, including wire/layout/stats, staging, health, Tensor manifests/protocol, USB ring and model-pointer checks. The updated app passed all 15 output slices of a 32-frame recurrent comparison against the existing reference. All 64 captured input arrays exactly matched the reference fixtures. The installed APK hash matched the release file and its signing certificate matched the previous APK.

## What can still make it faster?

The current phone-side overhead outside inference is about 1.0 ms per frame. The October 11 instrumented native baseline measured roughly 29.36 ms of TPU hardware execution within a 32.27 ms runtime call, plus about 0.93 ms input copying and 0.32 ms output copying. Those older component figures are leads, not fresh measurements of this build.

* **Runtime/driver completion latency:** the strongest unresolved issue is rare long waits, especially during screen wake. Prior fence traces placed the delay before completion signaling. Higher thread priority, sustained mode, async completion and deadline hints did not resolve wake failures. A matched newer runtime/compiler or vendor fix needs separate compatibility, output and repeated wake testing before adoption.
* **Input preparation directly into supported NPU buffers:** eliminating a copy could reduce some overhead, but the prior resident-input upper-bound experiment saved only about 0.08 ms. That experiment cannot process changing camera frames. Any implementation must preserve buffer ownership, synchronization and exact image history; no unsafe persistent mapping or skipped updates is included.
* **Compiler/operator optimization:** most time is actual TPU work. Operation-level profiling is the next route to a substantial gain. Existing sharding trials did not help. This release preserves the validated model and FP16 precision.

See the [performance investigation](TPU_PERFORMANCE_2026-10-11.md) and [fence experiment](TPU_WAKE_FENCE_2026-10-11.md). No experimental scheduling or runtime-mode patch is promoted based on these two maintenance checks.

## Handoff and rollback

The prior `.9` APK and its exact source patch are archived. Android may reject downgrading from code 80710 to 80509; do not uninstall to bypass that restriction because it removes imported models and app data. A data-preserving rollback may require rebuilding the archived source with a higher version code and the same signing key.

After testing, the temporary Developer listener and ADB forwarding are disabled and the app is left at Waiting for Comma with Cinque Terre Model V2. The next physical check should be parked: connect the phone directly to the comma and verify selection, handshake, frame timings and absence of resets. No connection window was armed. Desk evidence alone is not approval for an on-road test.
