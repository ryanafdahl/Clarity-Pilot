# Vendor-dependent metrics detail diagnostic

The October 17 diagnostic used the SDK v2.1 FP16/minimal G6 model compiled with
`--google_tensor_dump_op_timings=true`. Two isolated native runs requested metrics
detail 0 and then 1, each with 20 warmups and 120 measured frames in mode 5.
Both start/stop calls returned status 0 and both outputs matched exactly.

| Requested detail | Graph executions | Aggregate hardware time | Hardware mean | Native total mean |
| --- | ---: | ---: | ---: | ---: |
| 0 | 120 | 3,331,698 us | 27.7642 ms | 33.7968 ms |
| 1 | 120 | 3,331,053 us | 27.7588 ms | 33.4144 ms |

Only hardware_execution_time_us and number_of_graph_executions were returned.
No per-operation table appeared in captured device stdout, stderr or PID-filtered
logcat, or in the earlier host compiler capture. The API accepts the requests;
this experiment does not establish that detail 1 has any different meaning.
Both logcat captures also contained the same library threadpool notice. Its
relation to profiling availability is unknown; it did not prevent completion.

Battery checkpoints were 33.0-33.4 C, thermal status 0. No measured native frame
exceeded 46 or 50 ms. One sequential run at each level is **not a performance
comparison**, and these fixed-input runs do not qualify the recurrent app or
physical USB connection. No app model was replaced.

The public API specifies vendor-dependent detail-level meaning:
[Tensor dispatch API](https://github.com/google-ai-edge/LiteRT/blob/v2.3.0/litert/vendors/google_tensor/dispatch/sb_api.h#L827-L833).
The result is limited to the captured channels and this device/runtime/compiler
combination; another vendor-supported channel may expose additional data.

## Source reproduction

metrics-detail.patch changes only the requested metrics detail argument and
adds strict BENCH_METRICS_DETAIL=0|1 parsing, with default 0. The logger still
enumerates every returned metric. Inference calls, buffer handling and completion
waits are unchanged. native_profile.c and metrics.inc are the exact tested
diagnostic source; reproduction-manifest.json records source and binary hashes.
No model, SDK, runtime library or executable is included.

First prepare a baseline with profiling/build.py and the exact patched JetLink
source and runtime under investigation. The build pins all three baseline source
hashes after CRLF-to-LF normalization and refuses other source drift. This accepts
equivalent Windows and Linux checkouts; it does not trim whitespace or normalize
other changes. Captured raw-byte provenance in reproduction-manifest.json is
unchanged. New build manifests retain raw source hashes and add normalized hashes.
Run `python test_source_pins.py` to check both line-ending forms and drift refusal. Build this separate executable using
the Linux Android NDK:

~~~sh
python build.py --baseline /path/to/baseline-build \
  --profiler /path/to/android/tensor/profiling \
  --ndk /path/to/android-ndk --output /path/to/new-detail-build
~~~

Stage the executable, runtime and already compiled diagnostic model in a new
/data/local/tmp directory. Verify their hashes locally and on the phone. Use
the desk-only profiler's health checks and owned-process timeout wrapper. For a
single invocation, insert BENCH_METRICS_DETAIL=0 or 1 alongside its existing
BENCH_METRICS=1 environment assignment. The underlying command is:

~~~sh
BENCH_METRICS=1 BENCH_METRICS_DETAIL=0 LD_LIBRARY_PATH=runtime \
  timeout 36 ./tensor-bench runtime model-op.tflite 5 120 50000 detail-0 1
~~~

Create a new output directory (detail-0) before invocation. Preserve stdout,
stderr, health observations and logcat filtered to the benchmark's recorded PID.
Do not clear global logcat. Repeat with detail 1 only after the first process has
exited. An unavailable or rejected metric is unavailable, not zero. Keep raw
captures local; publish only the sanitized aggregate JSON.

