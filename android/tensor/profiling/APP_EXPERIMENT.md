# Real-app runtime and scheduling experiment

Status, October 11: **device measurements completed, including a retained
interrupted trial and a controlled screen-wake reproduction**. The candidate's
0.132 ms mean advantage was inconsistent across pairs. The installation APK
remains `.9`. [Results and limitations](../../../docs/TPU_RUNTIME_SCHEDULING_2026-10-11.md).

The earlier priority experiment had too few repeated controls to resolve very
small effects. A gain of a tenth of a millisecond is worth measuring. This
follow-up uses repeated paired runs and reports uncertainty instead of treating
one return control as proof of no effect.

## Diagnostic builds

Start from the pinned JetLink base and apply the current
[Tensor support patch](../tensor-support.patch), following the
[Android build instructions](../../README.md). Work in a separate checkout.

1. Apply `app-tracing-experimental.patch` and build a release APK. Save it as
   `trace-control.apk` before proceeding.
2. Apply `app-priority-experimental.patch` and build again. Save this APK as
   `trace-priority.apk`.
3. Verify both APKs have the installed app's signer. Keep the exact original
   `.9` APK available for an in-place rollback. Do not uninstall the app.

Both experimental versions retain code 80509 for reversible installation.
Only the candidate raises the dedicated session thread from nice 0 to -4,
restoring it on exit. Both contain identical trace points. The model, LiteRT
runtime, CPU hint target, transport, thermal protections and comma deadlines
are unchanged.

The trace patch marks request handling, waiting for the host lock, queue
preparation, NPU input copies, runtime invocation, output copies, performance
hints, telemetry and response sending. Frame IDs are counters. Static section
names avoid per-frame string formatting. The diagnostic release is profileable
by the local Android shell; it is not a debuggable build. Markers are active
only when a system trace selects the app.

Local builds prepared October 11:

| Build | Version suffix | SHA-256 |
| --- | --- | --- |
| Control | `.9-trace1` | `469ab35fd01cb8b968e703bd430d0d22607f9a3398d52b07790f0220aee4cbd9` |
| Candidate | `.9-trace-priority1` | `19d6815d6e4d75e3e71d8617d8ab8838ad3a0a1d1a2467dbfe6f0a1cb70f58b4` |

These experimental APKs are retained locally, not offered as installation
releases. Both release builds and 59 Android tests passed. The candidate also
passed 53 native regressions. The source used for the installed release was
verified unchanged. Both builds passed on-phone recurrent parity; trace-marker
capture and the repeated latency experiment are now recorded in the results.

## First capture, then compare

Keep the phone connected to a desk computer, disconnected from the comma.
Enable the listener in **JetLink Settings → About → tap Version seven times**.
This reveals Developer/Port 5599 and enables the listener automatically; there
is no separate TCP switch. Seven taps again disables it.

First install the trace control, verify its model identity and a 32-frame
recurrent reference comparison, then capture a bounded trace using
`app-scheduler.pbtxt`. It records 120 seconds with a 128 MiB cap. Pipe the
configuration into Perfetto when its service cannot read `/data/local/tmp`:

```sh
adb -s SERIAL shell 'cat /data/local/tmp/OWNED/app-scheduler.pbtxt | perfetto --txt -c - -o /data/misc/perfetto-traces/OWNED.pftrace --background-wait'
```

Start the synthetic app benchmark immediately in the same orchestration
script, with `--serial SERIAL --frame-output frames.json`. Verify capture
completion before pulling the trace. Stop on the existing health/timing guards.
Keep raw traces local: scheduler data may include unrelated process names.

```sh
trace_processor query -f app-stages.sql OWNED.pftrace > stages.csv
```

Check trace loss/overrun statistics and each stage's `covered_ms` against
`wall_ms`. Incomplete coverage is not zero wait. `running_ms` is scheduled CPU
time; `runnable_ms` is time ready but not scheduled. `blocked_ms` includes
runtime/hardware waits and other sleeping states. It is **not** pure TPU time.
Frame IDs are matched to the containing request, including lock waits that
occur before the frame counter is written. On-phone captures validated the new
stage rows in both quiet traces and the controlled-wake trace, with complete
scheduling coverage and zero reported trace loss/errors.

## Repeated small-gain comparison

After parity/smoke checks, stop tracing. The latency experiment uses:

- Eight adjacent pairs, four A/B and four B/A, shuffled with fixed seed 20261011
  before any results are observed.
- 600 measured frames per run after 100 excluded warmup frames: 9,600 measured
  frames total, same seed-17 input sequence and recurrent resets.
- The same app restart/install procedure before **every** run, including
  consecutive runs of the same variant, and the screen off for every run.
- Existing per-frame, rolling timing and thermal stops; failures remain failures.
- Exact output fingerprints, per-frame timings, before/after health and one
  thread snapshot per run. Inspect the session thread's actual nice value.

The runner requires an unused local forwarded port 5599 and an already enabled
phone listener. It changes the installed APK for this desk experiment and
restores the supplied, hash-checked original in `finally`. A disconnected device
can prevent rollback; that is recorded and exits as a failure. It preserves
preexisting ADB forwards and removes only its own. Disable the listener after
testing and verify the original version and selected model on the phone.

```sh
python paired_app.py --adb /path/to/adb --serial SERIAL \
  --control-apk /path/to/trace-control.apk \
  --candidate-apk /path/to/trace-priority.apk \
  --rollback-apk /path/to/jetlink-0.8.5-clarity-tensor.9-pixel.apk \
  --rollback-sha256 b3b69287a6bb2a9209a604003937435c2ce1715329881eb66154afbef8a0f07d \
  --client-path /path/to/compatible/jetlink-python-checkout \
  --source-sha256 09d080f36965bb2a0790500452bd328aa03c484d0222aa79d1ad9f021a522aec \
  --source-bytes 766040736 --output /path/to/new-results
python paired_analysis.py /path/to/new-results --output /path/to/new-comparison.json
```

`--order BA` runs an explicitly declared final pair in a **new** result
directory. Preserve interrupted trials and explain any derived analysis set;
do not silently overwrite a failed run or label it a pass. The October 11
comparison repeated its final B/A pair after Android recorded a power-button
wake during the original B run. The interrupted trial remains in the report.

The primary measure is paired **mean phone-processing latency**. Report every
pair's control-minus-candidate difference, the number of pairs favoring the
candidate, and a paired bootstrap interval. p95, p99, maximum and full exchange
are secondary exploratory measures. No multiple-comparison correction is
applied. The unit of replication is a run pair, not thousands of correlated
frames. Eight pairs still give imprecise tail estimates and do not guarantee
resolution of every small gain. An interval spanning zero is inconclusive,
not proof that the effect is zero. Inspect thermal/order trends before attributing
a difference to scheduling. Desk TCP results do not qualify direct USB or driving.

Offline tool validation: three paired-statistics tests, five runner failure/
rollback/order tests and two per-frame metadata tests pass. The tests cover a known
0.1 ms gain, mixed noise, incomplete replication, rollback after failure,
preservation of existing forwards, failed rollback, frame IDs/warmup boundaries,
output fingerprints, output-path collisions and validation of explicit pair order.

References: [Android custom trace events](https://developer.android.com/topic/performance/tracing/custom-events),
[profileable release builds](https://developer.android.com/guide/topics/manifest/profileable-element),
[Perfetto scheduling data](https://perfetto.dev/docs/data-sources/cpu-scheduling).
