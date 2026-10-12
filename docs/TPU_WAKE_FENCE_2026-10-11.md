# Pixel wake: completion-fence timestamps and deadline hints — October 11, 2026

**The long wait occurs before the TPU completion fence signals.** On the new
92 ms example, the app returned only **0.026 ms after the signal**. A public
50 ms fence-deadline hint did not establish an improvement: all 23 attempts
that reached wake failed a timing guard. One additional attempt stopped during
warmup after a thermal-monitor timeout. The original JetLink `.9` remains the
installation release.

[Aggregate evidence](../android/tensor/profiling/results-wake-fence-2026-10-11.json) ·
[Reproduce the experiment](../android/tensor/profiling/WAKE_EXPERIMENT.md) ·
[Previous async comparison](TPU_WAKE_ASYNC_2026-10-11.md).

## Where the 91 ms wait occurs

The previous trace measured a 90.983 ms output-event wait. This follow-up reads
the kernel's completion-fence status and signal timestamp before and after the
same public LiteRT wait. It uses `SYNC_IOC_FILE_INFO` on the borrowed output
fence, without changing its ownership, completion behavior or wait timeout.
Timestamps are compared with `CLOCK_MONOTONIC`; compound, failed or invalid
timestamps are unavailable, never assumed zero.
[Linux sync-file API](https://github.com/torvalds/linux/blob/master/include/uapi/linux/sync_file.h).

All 300 frames in the probe trace had one active `edgetpu` fence before waiting,
a signaled fence afterward, and a valid signal timestamp between submission
and return. The kernel exposes the completed fence as `detached-driver` after
waiting. All hardware-counter reads succeeded with one execution per frame.
There were no reported trace errors or lost events, and the invocation, submit
and wait slices had complete scheduler coverage.

| New probe's slowest wake frame (ID 210) | Duration |
| --- | ---: |
| Complete phone processing | 92.710 ms |
| Invocation | 92.172 ms |
| Async submission slice | 0.176 ms |
| Output-event wait slice | 91.892 ms |
| Submission start to kernel fence signal | **92.002 ms** |
| Kernel signal to return from wait | **0.026 ms** |
| Vendor-reported hardware execution | 34.662 ms |
| CPU runnable time inside the wait | 0.009 ms |

These intervals have different boundaries and nest; do not add the rows.
In particular, submission-to-signal starts before the output-wait slice.
Across the 100 wake frames, median signal-to-return was 0.0795 ms, mean
0.1072 ms and maximum 1.606 ms. Baseline maximum was 2.138 ms. During the
91.892 ms wait, the visible TPU service's `HighPriWorker` spent 0.171 ms
runnable and `MainTpuActor` 0.030 ms runnable. Neither explains the long wait
as a CPU scheduling delay in those observed workers.

| Probe window (100 frames each) | Baseline | Wake |
| --- | ---: | ---: |
| Mean submission-to-signal | 31.497 ms | 39.725 ms |
| Mean hardware counter | 29.569 ms | 32.013 ms |
| Difference of those means | 1.929 ms | 7.712 ms |
| Mean signal-to-return | 0.783 ms | 0.107 ms |

The app's return from the completed fence was actually quicker during this
wake window. Both the reported hardware time and the pre-signal residual grew.
This is descriptive evidence from one diagnostic, not a repeated performance
comparison or a causal breakdown of the runtime.

**The dominant delay precedes the completion signal.** On the example frame,
submission-to-signal exceeded the hardware counter by 57.340 ms. This is a
residual between different measurement scopes, not a direct queue-time timer.
Device queuing, preemption, synchronization and completion handling remain
possible contributors. The trace does not distinguish them or establish the
exact TPU scheduling policy. Faster resumption of the waiting app thread
cannot recover most of this example's delay.

An earlier diagnostic pair in this session added camera, NNAPI and sync tracing
and requested `DarwiNNRuntime` / `edgetpu_fences`. It captured camera processing
associated with Face Unlock during the slow wake interval: 68 algorithm slices,
beginning 206.860 ms after frame 200 and ending 2400.007 ms after it. That is a
temporal association, not proof of causation or of concurrent TPU execution.
The requested vendor track events did not appear, so there is no vendor queue
timeline. Face Unlock settings were left unchanged, as requested.

## Next candidate: a public deadline hint

Both new variants retain async submission, burst mode 5 and complete output
waits. The candidate additionally calls `SYNC_IOC_SET_DEADLINE` on its own
output fence with an absolute deadline 50 ms after submission starts. The
control retrieves the same fence descriptor and takes the same clock readings.
The two source variants differ only in the hint flag and diagnostic version
label. Fence-info ioctls and hardware metrics run only during tracing.

This is an advisory kernel request, not a timeout or a way to make an unfinished
output available. The existing whole-frame 100 ms limit, 100-frame p95 below
50 ms, thermal limits and complete wait remain in force. Linux explicitly
allows the signaling driver to ignore the hint; an accepted ioctl does not
prove a driver callback exists or that scheduling changed.
[Kernel deadline semantics](https://www.kernel.org/doc/html/v6.15/driver-api/dma-buf.html#dma-fence-deadline-hints).
The Linux sync-file implementation returns success after passing the hint
down, independent of whether a driver changes its behavior.
[Sync-file deadline implementation](https://github.com/torvalds/linux/blob/master/drivers/dma-buf/sync_file.c).

In the separate deadline diagnostic, all 222 candidate frames—including
warmups—reported an accepted request, actual async execution, one completed
output fence and a valid signal timestamp. There were no reported trace errors.
The candidate nevertheless stopped at a 117.249 ms frame; the control completed
its window and failed the p95 guard. This pair is retained as diagnostic
evidence and excluded from the untraced performance comparison.

## Repeated controls

Before testing, six AB and six BA pairs were shuffled with seed 202610114:
`AB BA AB BA BA BA AB AB AB AB BA BA`. Every trial restarted the app, slept
the screen for ten seconds, used 100 warmups, measured baseline frames 100–199,
woke the screen concurrently with frame 200, and attempted frames 200–299.
The harness did not unlock the phone. Wake command durations are retained.

The primary outcome is paired mean phone-processing latency across the entire
fixed wake window. Any censored window withholds the uncensored overall gain;
all timing failures remain outcomes. The predeclared secondary baseline
comparison requires complete baseline windows in all trials. Uncertainty uses
50,000 paired bootstrap draws and an exact paired sign-flip test. Trial pairs,
not individual frames, are the replication unit. Secondary tests are
exploratory and uncorrected for multiple comparisons.

All 24 planned attempts are accounted for. Eleven control trials and twelve
candidate trials reached wake; all 23 failed a timing guard. Twenty-two
completed their 100-frame wake windows and failed the p95 limit. One control
stopped at 106.238 ms after only five wake frames. No overall uncensored
wake-mean gain is reported.

Trial 10 (control, pair 5) stopped after 95 warmup frames because an ADB
`dumpsys thermalservice` query exceeded its five-second timeout. It had zero
measured frames and no wake. The runner restored `.9`; a fresh check showed
32.7 C and thermal status 0. Only the exact 14-trial unrun suffix was resumed,
with the original APK hashes, order and guards. The failed attempt was not
replayed or replaced. Both manifests and the failed trial are retained, with
their hashes in the aggregate evidence.

The predeclared all-pair baseline comparison is unavailable because trial 10
has no baseline. An explicitly **post-hoc, exploratory** comparison of the
11 complete baseline pairs excludes pair 5 in its entirety. It averages
**34.398 ms control** versus **34.560 ms candidate**: the hint is **0.162 ms
slower**, with a 95% paired interval from **0.115 ms faster to 0.427 ms slower**.
The candidate is faster in only **3 of 11 pairs**, and the two-sided sign-flip
p-value is **0.2832**. This does not establish either a small gain or a slowdown,
and it is not an estimate of wake improvement.

| Pair | Control baseline | Deadline baseline | Control wake max / frames | Deadline wake max / frames |
| --- | ---: | ---: | ---: | ---: |
| 1 | 34.107 ms | 34.437 ms | 84.081 ms / 100 | 89.832 ms / 100 |
| 2 | 34.407 ms | 34.430 ms | 106.238 ms / 5 | 80.461 ms / 100 |
| 3 | 34.334 ms | 34.838 ms | 86.578 ms / 100 | 88.978 ms / 100 |
| 4 | 34.141 ms | 34.766 ms | 85.039 ms / 100 | 88.547 ms / 100 |
| 5 | unavailable | 34.406 ms | unavailable / 0 | 89.515 ms / 100 |
| 6 | 34.647 ms | 34.390 ms | 90.179 ms / 100 | 90.342 ms / 100 |
| 7 | 34.187 ms | 34.999 ms | 86.802 ms / 100 | 89.028 ms / 100 |
| 8 | 34.563 ms | 34.636 ms | 92.054 ms / 100 | 86.837 ms / 100 |
| 9 | 34.567 ms | 33.836 ms | 89.402 ms / 100 | 92.288 ms / 100 |
| 10 | 34.285 ms | 34.319 ms | 88.304 ms / 100 | 92.486 ms / 100 |
| 11 | 35.034 ms | 34.694 ms | 89.298 ms / 100 | 88.698 ms / 100 |
| 12 | 34.109 ms | 34.822 ms | 92.730 ms / 100 | 88.237 ms / 100 |

The five-frame maximum is a censored observation. Pair 5's unavailable control
is an infrastructure failure, not a timing success. The candidate's absence of
a >100 ms stop in this small series does not establish a tail-latency benefit.
Every common output byte matched across all attempted runs, including warmups.

The comparison collected **4,505 measured frames** and **2,395 warmup frames**.
Maximum sampled battery temperature was **33.9 C**; sampled Android thermal
status was always **0**. Three separate diagnostic pairs contributed another
1,122 measured frames and are excluded from the timing comparison. The 64
reference-parity frames are also separate.


## Validation and deployment

Both builds passed 59 Android unit tests and fresh 32-frame recurrent reference
comparisons across all 15 output slices using the existing tolerances. The
runner and analysis passed 13 offline tests, including refusing a continuation
with a different diagnostic trace configuration. Both APKs use the original
signer and version code 80509. The two new experimental patches reproduce the
tested source exactly after the existing async patches.

Model, LiteRT 2.3.0, precision, buffers, recurrence, CPU hints and nice level
were matched. No allowlist, first-party scheduling API, system priority or
security-setting change was made. Raw traces, APKs and weights remain local;
the published JSON contains aggregate evidence and provenance hashes. Desk
ADB/TCP testing on one phone does not qualify a driving deployment.

After testing, the installed `.9` APK was hash-verified, Cinque Terre Model V2
remained selected, the developer listener was disabled, port 5599 was closed,
ADB forwarding was empty, and the owned remote UI-dump file was removed.
The phone was returned to JetLink's Status screen. Face Unlock settings were
unchanged. Neither experimental APK replaces the installation release.

The next unresolved measurement is the vendor's dispatch/queue/preemption
timeline before the fence signal. These results do not justify boosting the
waiting app thread or assuming that an accepted hint changed TPU scheduling.
