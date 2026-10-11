# Pixel runtime stalls and repeated scheduling controls — October 11, 2026

**The priority candidate averaged 0.132 ms faster (0.37%), but the gain was not
consistent: four pairs favored it and four favored the control.** Keep `.9` as
the installation release. A separate controlled screen wake reproduced a large
runtime stall on the control build, giving us a better target for investigation.

[Aggregate evidence](../android/tensor/profiling/results-scheduling-2026-10-11.json)
and [reproducible experiment](../android/tensor/profiling/APP_EXPERIMENT.md).
Raw system traces and app logs remain local.

## Small-gain comparison

Pixel 11 Pro XL / Tensor G6, Cinque Terre V2, matched LiteRT 2.3.0 and compiled
model. A and B have identical diagnostic trace points; tracing was off during
the paired comparison. A uses the original session nice 0; B uses nice -4.
Every run reinstalls/restarts the app, excludes 100 warmup frames and measures
600 frames with identical synthetic inputs and recurrent resets. Android CPU
hints, thermal protections and existing timing guards remain active.

The predeclared order was `AB BA AB BA BA AB AB BA`. The last B run encountered
a power-button wake, exceeded the timing guard and stopped the original
sequence. Its files are retained unchanged. After examining the event, the
final B/A pair was repeated in a new directory under the intended screen-off
condition. The table below is explicitly a **derived screen-off comparison**:
seven original complete pairs plus that repeated final pair. It must not be
presented as an uninterrupted successful original experiment.

| Pair | Order | Control mean ms | Candidate mean ms | Candidate improvement ms |
| --- | --- | ---: | ---: | ---: |
| 1 | A/B | 35.298 | 36.019 | -0.720 |
| 2 | B/A | 36.085 | 36.270 | -0.185 |
| 3 | A/B | 36.219 | 36.260 | -0.041 |
| 4 | B/A | 35.484 | 35.388 | +0.096 |
| 5 | B/A | 36.144 | 36.241 | -0.097 |
| 6 | A/B | 35.420 | 33.775 | +1.645 |
| 7 | A/B | 35.921 | 35.665 | +0.257 |
| 8, repeated | B/A | 35.283 | 35.183 | +0.100 |

The mean paired improvement is **0.131921 ms**. Its paired percentile-bootstrap
95% interval runs from **0.243 ms slower to 0.625 ms faster**, using 50,000
seeded resamples of run pairs. The two-sided sign-flip p-value is 0.6875. Frames
are not treated as independent replicates. These are exploratory estimates from
one device and session; run-to-run conditions still vary. Removing any one pair
changes the estimated mean improvement to between -0.084 and +0.254 ms.

| Pooled phone-processing metric | Control: 4,800 frames | Candidate: 4,800 frames |
| --- | ---: | ---: |
| Mean | 35.732 ms | 35.600 ms |
| p95 | 37.928 ms | 37.948 ms |
| p99 | 38.904 ms | 38.936 ms |
| Maximum | 40.843 ms | 44.645 ms |
| Frames over 50 ms | 0 | 0 |

All output bytes matched across all 16 eligible runs, including warmup. Session
thread snapshots matched nice 0 or -4 as intended in every run. Thermal status
stayed 0; the maximum sampled battery temperature was 32.7 C. Both builds also
passed the 32-frame recurrent reference comparison across all 15 output slices.
Those checks establish neither a repeatable latency benefit nor driving
qualification. A small gain would matter, but this result cannot establish one.

ADB/TCP round-trip means were 52.634 and 52.445 ms, with p95 values of 60.235
and 59.276 ms. These are desk transport measurements, not direct comma USB.

## A reproduced runtime stall

In the interrupted candidate run, 14 of 600 measured frames exceeded 50 ms;
the maximum was 87.249 ms. Android recorded a power-button wake at 08:19:47.839
Pacific immediately before the burst. The user confirmed waking or using the
phone at that time. Slow-frame logs placed the extra time
inside runtime invocation while inference-thread CPU time stayed below 1 ms
for the logged burst. Sampled thermal status remained 0 at 32.7 C.

To test that lead independently of the priority change, the **control build**
was traced while one `KEYCODE_WAKEUP` was issued 15 seconds after starting a
600-frame test, after its 100 warmup frames. No unlock or app operation was
performed. The timing guard stopped this test after 200 measured frames:

- 12 frames exceeded 50 ms; maximum phone-processing time was **84.435 ms**.
- The slowest runtime invocation took **83.437057 ms**: **82.839373 ms blocked**,
  **0.559923 ms running on a CPU**, and **0.037761 ms runnable but unscheduled**.
- Input copying, output copying and the host lock did not account for this
  long delay. Output bytes still matched the screen-off control sequence.
- All measured trace stages had complete scheduling coverage; trace loss/error
  counters were zero. Sampled thermal status was 0, with battery at most 31.8 C.

The controlled wake reproduced the stall pattern without nice -4. For this
event, raising the inference thread's scheduler priority does not target the
dominant delay: the thread was blocked inside the runtime. That state includes
accelerator/driver/completion waits; **it is not a pure TPU hardware timer**.
This trace does not identify a particular competing service, prove accelerator
contention, or establish that earlier road stalls had the same cause.

## Ordinary frame breakdown and next work

Two earlier quiet traces measured 1,800 frames per build with complete coverage
and no trace errors. The control's average inference section spent 3.274 ms
running, 0.827 ms runnable and 32.107 ms blocked. Its stages averaged:

| Stage | Wall time |
| --- | ---: |
| History/queue preparation | 0.934 ms |
| Input copies | 0.746 ms |
| Runtime invocation | 33.956 ms |
| Output copies | 0.307 ms |
| CPU hint report | 0.108 ms |
| Waiting for host lock | 0.003 ms |

Traced runs are diagnostic observations, not extra untraced control pairs.
The candidate's corresponding inference runnable time averaged 0.831 ms, so
these two traces did not show a clear scheduling improvement either.

Next, instrument vendor hardware execution counters around a controlled wake
to separate actual TPU work from runtime/driver completion waits. Separately,
direct preparation into correctly locked NPU input buffers could target the
ordinary 0.746 ms copy stage. That is an upper bound on removable measured copy
cost, not a predicted gain; buffer ownership, synchronization, image history
and recurrent state must remain exact. The host lock is not a priority target
in these captures.

The investigation measured **14,000 frames** in total: 9,600 eligible paired
frames, 600 from the interrupted trial, 3,600 quiet traced frames and 200 from
the controlled wake. Both timing stops were preserved. No deadline or thermal
limit was relaxed. The original `.9` APK was restored after testing, with
Cinque Terre V2 still selected. The temporary developer listener was disabled,
port 5599 was closed, ADB forwarding was clear, and owned phone trace/config
files were removed. The priority candidate is not promoted to the installation
release.
