# Pixel wake: async submission and completion waits — October 11, 2026

**Async submission did not remove the wake stall.** The 12 repeated pairs showed a small screen-off baseline benefit: **0.226 ms (0.65%)** faster on average, with a paired 95% bootstrap interval of **0.095–0.358 ms**. All 24 wake trials still hit a timing limit.
The original JetLink `.9` remains the installation release.

[Aggregate evidence](../android/tensor/profiling/results-wake-async-2026-10-11.json) ·
[Reproduce the builds and controls](../android/tensor/profiling/WAKE_EXPERIMENT.md) ·
[Previous sustained-mode comparison](TPU_WAKE_SUSTAINED_2026-10-11.md).

## Where the runtime waits

One separate diagnostic pair recorded every invocation, the thread's scheduler
state and vendor hardware counters. Both variants used burst mode 5. The
candidate submitted asynchronously, then waited for all attached output events
before exposing outputs or updating recurrent state. All **300 candidate
frames**, including warmups, reported actual async execution and one output
event; this was not a silent synchronous fallback. Both traces had complete
invocation scheduler coverage and no reported trace errors or lost events.

| Slowest measured invocation in each diagnostic | Synchronous control | Async candidate |
| --- | ---: | ---: |
| Frame ID | 209 | 215 |
| Complete invocation wall time | 97.586 ms | 91.326 ms |
| TPU hardware counter | 37.469 ms | 33.996 ms |
| Async submission | — | 0.180 ms |
| Output-event wait | — | 90.983 ms |
| CPU running during invocation | 0.542 ms | 0.375 ms |
| Runnable, waiting for a CPU turn | 0.704 ms | 0.046 ms |
| Blocked during invocation | 96.340 ms | 90.905 ms |

These are different frames from one traced pair, **not an estimated speedup**.
Both diagnostic trials failed the existing p95 limit. The candidate's long
delay persisted after submission, inside the output-event wait. Its 91.326 ms
invocation exceeded the vendor counter by 57.330 ms. That difference can include
queueing, synchronization and instrumentation outside the counter's scope;
it does not identify a precise driver timer or prove which system task caused it.

LiteRT's Google Tensor dispatch source exposes a blocking invocation wait and
an async path returning completion fences. LiteRT 2.3.0 waits for a sync-fence
event using `poll()`. The observation is consistent with waiting for
accelerator completion, rather than spending the spike actively computing on
the application CPU. It does not establish that a higher application CPU
priority would make the fence signal sooner.
[Google Tensor dispatch](https://github.com/google-ai-edge/LiteRT/blob/main/litert/vendors/google_tensor/dispatch/litert_dispatch_invocation_context.cc) ·
[LiteRT 2.3.0 event wait](https://github.com/google-ai-edge/LiteRT/blob/v2.3.0/litert/runtime/event.cc).

## Repeated controls, including every failure

Before either new APK was installed, six BA and six AB pairs were shuffled with
seed 202610113: `BA BA BA AB AB BA BA AB AB AB AB BA`. Each trial restarted the
app, slept the display for ten seconds, discarded 100 warmups, measured 100
screen-off baseline frames, sent one wake concurrently with frame 200, and
attempted 100 wake frames. ADB stimulus dispatch takes time; each command's
duration is retained in the aggregate data. The harness did not unlock the phone.

The primary outcome was mean phone-processing latency in the fixed wake window
200–299. The unit of replication is a trial pair, not a frame. Tracing was off
for all 24 comparison trials. Model, precision, recurrent inputs, buffers,
LiteRT 2.3.0, CPU hints, nice level, signing key and thermal/timing limits were
matched. The candidate's submit and output waits remain inside all existing
inference and phone-processing timers. No frame pipelining, early response,
system allowlist, security-setting or priority change was made.

All 24 trials reached wake and failed a timing guard. One control and two candidates stopped above 100 ms, leaving three censored wake windows. The other 21 trials reached all 100 wake frames and failed the 100-frame p95 limit. Consequently, the predeclared full-window wake-mean comparison is unavailable; no overall wake-speedup estimate is reported.

| Pair | Sync baseline | Async baseline | Sync wake max / frames | Async wake max / frames |
| --- | ---: | ---: | ---: | ---: |
| 1 | 34.565 ms | 34.509 ms | 135.682 ms / 26 | 131.808 ms / 10 |
| 2 | 34.935 ms | 34.354 ms | 91.337 ms / 100 | 95.492 ms / 100 |
| 3 | 34.684 ms | 34.636 ms | 92.548 ms / 100 | 93.259 ms / 100 |
| 4 | 34.764 ms | 34.198 ms | 91.053 ms / 100 | 92.083 ms / 100 |
| 5 | 34.939 ms | 34.500 ms | 92.246 ms / 100 | 92.681 ms / 100 |
| 6 | 34.777 ms | 34.567 ms | 91.321 ms / 100 | 84.749 ms / 100 |
| 7 | 34.668 ms | 34.774 ms | 92.796 ms / 100 | 89.784 ms / 100 |
| 8 | 34.595 ms | 34.143 ms | 89.500 ms / 100 | 89.305 ms / 100 |
| 9 | 34.504 ms | 34.249 ms | 89.746 ms / 100 | 102.597 ms / 6 |
| 10 | 34.424 ms | 34.149 ms | 90.829 ms / 100 | 93.209 ms / 100 |
| 11 | 34.710 ms | 34.658 ms | 89.921 ms / 100 | 87.765 ms / 100 |
| 12 | 34.514 ms | 34.623 ms | 95.547 ms / 100 | 90.473 ms / 100 |

Wake maxima from fewer than 100 frames are **censored observations**, not
complete-window maxima. No failed trial was replayed, omitted or replaced.
All baseline windows completed. Synchronous processing averaged **34.673 ms**, versus **34.447 ms** with async submission and waits. The candidate was faster in **10 of 12 pairs**. The paired two-sided sign-flip p-value is **0.01123**. This is an exploratory secondary baseline result on one phone, without correction for multiple comparisons; it warrants independent replication and does not estimate wake-stall improvement.

The measured sequence contained 4,542 frames, excluding 2,400 warmups,
400 measured diagnostic frames and 64 recurrent reference-parity frames.
Maximum sampled battery temperature was **34.3 C** and Android thermal status remained **0**.

An ADB thermal-service query returned exit 1 before trial 12 began. The harness
stopped and restored `.9`; a fresh check showed 32.9 C and thermal status 0.
Only the exact 13-trial remainder was resumed, using the runner's validated
continuation. The interruption splits pair 6. Both original manifests and
their failure record remain local; their hashes and the interruption are in
the aggregate evidence. Combined frame/result files are byte-identical copies.
Excluding the interrupted pair leaves **11 pairs** and a baseline advantage of **0.228 ms**, 95% interval **0.085–0.372 ms**, p = **0.02148**. The small baseline signal survives this sensitivity check.

## How the upstream phone notes apply

The linked v0.8.5 README reports an allowlist rejection on a Pixel 10 Pro Fold:
the upstream on-phone NPU path was denied and the app fell back to GPU. It
also calls for parity checks, sustained charging benchmarks and a comma live
benchmark before driving.
[Upstream phone notes](https://github.com/zoompilot/jetlink/blob/v0.8.5/android/README.md#on-a-phone).

This experiment uses the custom **precompiled Tensor G6** model path and
LiteRT **2.3.0**. Its model options request NPU execution, and the backend
rejects a non-NPU engine or incomplete acceleration. Successful vendor
execution counters provide additional evidence that these timings are not a
silent GPU fallback. That does not establish equivalence with Google's
allowlisted applications or their scheduling privileges. The reported
allowlist rejection is not evidence that it caused these completion delays.

Both new builds passed fresh 32-frame recurrent reference comparisons across
all 15 output slices, using the existing correlation/error tolerances.
Every common output byte matched across all repeated timing trials, and all 300 corresponding diagnostic frames matched between variants. The build and 59 Android unit tests passed for each variant;
the 12 wake-harness/analysis tests also passed. Both signatures match `.9`.
The two experimental patches reproduce the tested source files when applied
in order after the existing tracing and metrics patches. Experimental APKs,
model weights and raw system traces remain local.

## Decision and next evidence

Retain the async path as an experimental candidate for reproducing the small baseline benefit. Keep `.9` installed because this test has not established a wake improvement. The investigation now distinguishes rapid submission from a long
completion wait. A useful next diagnostic would correlate the driver's
submission, execution and fence-signal times across wake, if this unrooted
phone exposes them. That can separate accelerator queueing/preemption from
notification delay; this trace cannot. Face Unlock remains unchanged, as
requested. These desk results do not qualify direct USB or driving.

After testing, the original `.9` was reinstalled and launched. Its APK hash was verified directly on the phone against the release hash. The developer section was disabled, port 5599 was closed, ADB forwarding was empty, the owned UI dump was removed, and Cinque Terre Model V2 remained selected. Read-only follow-up found `sync`, `camera`, `nnapi`, `sched` and `freq` trace categories; direct shell access to the kernel event list was denied. Specific driver-event availability remains unverified.
