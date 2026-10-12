# Repeated real-app wake experiment

This desk experiment compares requested Tensor performance mode 5 (burst) with
mode 3 (high performance) around a controlled screen wake. It keeps the model,
LiteRT runtime, buffers, session nice 0, CPU hints and all health/timing guards
unchanged. The original `.9` remains the installation release.

## Reproduce the diagnostic builds

Start in a separate checkout with the pinned base and Tensor support patch from
[the Android build instructions](../../README.md), then apply:

1. `app-tracing-experimental.patch`.
2. `app-wake-metrics-experimental.patch`; build and retain the control APK.
3. `app-wake-mode-experimental.patch`; build and retain the candidate APK.

For the sustained-performance follow-up, substitute
`app-wake-sustained-experimental.patch` in step 3. It requests mode 4 instead of
mode 3. Pass `--candidate-label 'sustained performance 4'` to the runner and an
explicit predeclared `--order`; the APK hashes identify the actual builds.

For the async-completion follow-up, apply `app-wake-async-control-experimental.patch`
after the tracing and metrics patches, then build the synchronous control.
Apply `app-wake-async-experimental.patch` and build the candidate. Both request
burst mode 5. The second patch changes only `JL_WAKE_ASYNC` from 0 to 1 and the
diagnostic version label. These patches do not stack on either mode-3 or mode-4
patch. Pass explicit labels and the predeclared order
`BABABAABABBABAABABABABBA` (12 pairs, seed 202610113).

For the fence/deadline follow-up, apply `app-wake-fence-control-experimental.patch`
after **both** async patches and build the new matched control. Then apply
`app-wake-deadline-experimental.patch` and build the candidate. This changes
`JL_WAKE_DEADLINE` from 0 to 1 and the label. Both retain async mode and burst 5.
Use labels `async deadline control` and `async 50 ms deadline`, with order
`ABBAABBABABAABABABABBABA` (12 pairs, seed 202610114).

The common code uses `LiteRtGetEventSyncFenceFd` on borrowed output events,
without closing their descriptors. While tracing, `SYNC_IOC_FILE_INFO` records
fence status/count and the kernel signal timestamp. Require exactly one fence,
successful before/after info reads, and `jl.fence_clock_valid=1` on each frame.
`jl.submit_to_signal_us` and `jl.signal_to_return_us` use `CLOCK_MONOTONIC`.
Missing or compound timestamps are unavailable; do not treat them as zero.
The candidate sends `SYNC_IOC_SET_DEADLINE` for submission-start plus 50 ms,
then performs the same full wait. Require `jl.deadline_enabled=1` and
`jl.deadline_rc=0` throughout its traced diagnostic. API acceptance does not
establish that the optional driver hint is honored. Do not claim a performance
comparison if requests fail. Untraced controls keep descriptor lookup and
clock reads matched, with fence-info diagnostics and vendor metrics disabled.

The candidate uses the public async invocation API, waits on every attached
output event, then clears completed events. It retains the synchronous bridge
contract: outputs and recurrent state are unavailable until completion. The
existing `jl.invoke`, inference and phone-processing timers include submission
and the entire completion wait. No frames are pipelined and no wait is excluded
from the timing guard. Missing APIs or a silent synchronous fallback fail this
experiment. It does not use the internal first-party scheduling-info API.

In a separate traced pair, require `jl.async_actual=1` and a positive
`jl.output_events` count on every candidate frame, in addition to the existing
hardware-counter and trace-coverage checks. `jl.async_submit` and `jl.output_wait`
divide the candidate invocation; `jl.sync_run` identifies the control's blocking
call. These stages nest inside `jl.invoke`; do not sum them with their parent.
All counters and extra trace sections are inactive during untraced controls.
The event-wait declaration follows the public
[LiteRT event C API](https://github.com/google-ai-edge/LiteRT/blob/main/litert/c/litert_event.h).
Borrowed events must not be destroyed separately. A `-1` event timeout preserves
the existing blocking runtime contract; it is not a relaxed frame deadline.

Both releases use code 80509 and the original signer for in-place restoration.
The mode patch changes only the requested mode and version label. It does not
change system allowlists, privileges, clocks, precision or thermal policy.

The metrics patch collects vendor counters only while an authorized system
trace selects the app. Each invocation records `jl.hw_us`, `jl.hw_executions`
and `jl.metrics_status` with the existing `jl.frame_id`. Require one successful
execution and status zero per invocation; missing/failed counters are unavailable.
The difference between invocation wall time and vendor hardware execution time
also contains instrumentation overhead; do not label it a precise driver timer.

Keep the APKs, compiled model, SDK binaries and raw system traces local. Publish
aggregate evidence only. Confirm recurrent reference parity on both builds
before interpreting timing differences.

## Repeated controls

Connect only the desk computer. In JetLink, enable the temporary listener via
Settings → About → seven taps on Version. Seven taps again disables it.

`wake_app.py` requires explicit control, candidate and hash-checked rollback
APKs. Each trial reinstalls/restarts, sleeps the display, waits 10 seconds,
discards 100 warmup frames, measures 100 screen-off frames, then launches one
`KEYCODE_WAKEUP` concurrently with frame ID 200 and measures through frame 299.
It never unlocks the phone or operates another application. The command's host
start/end timestamps are recorded; stimulus dispatch is not instantaneous.

Run one diagnostic A/B pair with `--trace`. Inspect coverage and counter errors.
An explicit `--trace-config /path/to/config.pbtxt` permits diagnostic categories;
the effective UTF-8 text with normalized newlines is hashed into new manifests. A traced continuation
requires the same hash and refuses old manifests without it. Never mix traced
runs into the primary latency comparison.
`app-completion.pbtxt` is the fence investigation's 35-second configuration;
it adds camera/sync/NNAPI tracing and requests vendor event categories. Their
presence in the configuration does not mean the device emitted those events.
Then run the untraced predeclared eight-pair order `AB BA BA AB BA AB AB BA`:

```sh
python wake_app.py --adb /path/to/adb --serial SERIAL \
  --control-apk /path/to/control.apk --candidate-apk /path/to/candidate.apk \
  --rollback-apk /path/to/jetlink-0.8.5-clarity-tensor.9-pixel.apk \
  --rollback-sha256 b3b69287a6bb2a9209a604003937435c2ce1715329881eb66154afbef8a0f07d \
  --client-path /path/to/compatible/jetlink-python-checkout \
  --source-sha256 09d080f36965bb2a0790500452bd328aa03c484d0222aa79d1ad9f021a522aec \
  --source-bytes 766040736 --output /path/to/new-results
python wake_analysis.py /path/to/new-results --output /path/to/new-analysis.json
```

Every timing stop ends its trial and is retained. The next predeclared trial
uses a fresh session after health checks; a non-timing failure aborts the whole
experiment. No timing threshold is relaxed. The runner restores `.9` in
`finally` and removes its own forward. Verify restoration, selected model and
disable the temporary listener afterward. A disconnected device can prevent
cleanup; failed restoration is recorded and raised.

A timing guard may stop the baseline before frame 200. In that case no wake
should be sent: retain the failed trial with a censored, unavailable wake window.
An absent wake without a legitimate pre-wake timing stop remains an error.

After diagnosing an interrupted experiment and verifying healthy device access,
`--continuation-of /path/to/interrupted/manifest.json` permits only the exact
unrun suffix in `--order`, with identical APK hashes, rollback, tracing and
variant labels. It requires a new output directory and retains the parent
manifest hash. It never retries a measured trial. Keep the original failure.
Reconcile any saved result absent from the manifest before continuing; the
runner refuses that case rather than replaying the measurement.
Report the interruption, especially if it splits a pair; do not silently present
separate batches as uninterrupted controls.

Primary outcome: mean phone-processing latency in fixed frame IDs 200–299,
paired by trial. Secondary measures: wake p95, maximum, over-50ms count,
timing-stop rate and baseline-adjusted mean. Frames are not independent repeats.
For complete windows, use the seeded 50,000-resample paired bootstrap and exact
sign-flip test. Secondary comparisons have no multiple-testing adjustment.

A 100 ms stop can truncate the wake window. Such a trial is **censored**, not a
short successful sample. The analyzer retains it and withholds the uncensored
overall mean-gain calculation. Do not silently drop failed trials, rerun until
they pass, or claim a speedup from the surviving windows. Equal output hashes
are required on all common frames. Desk ADB/TCP is not direct-USB qualification.

Offline coverage: four benchmark tests (including concurrent wake dispatch and
its failure), eight runner rollback/guard/forward/continuation tests, and five analysis tests
covering a 0.1 ms gain, censored windows, changed output bytes and pre-wake stops.

References: [LiteRT metrics API](https://github.com/google-ai-edge/LiteRT/blob/v2.3.0/litert/c/litert_metrics.h),
[Tensor runtime options](https://github.com/google-ai-edge/LiteRT/blob/main/litert/c/options/litert_google_tensor_options.h).
