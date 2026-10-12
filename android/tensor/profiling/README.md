# Isolated Google Tensor profiler

Measures input copies, runtime calls, output copies, per-stage thread CPU time,
context switches, and optional vendor hardware execution counters. It uses the
same patched C bridge and runtime libraries as JetLink. It does not modify the
installed app or select a driving model.

[October 11 findings](../../../docs/TPU_PERFORMANCE_2026-10-11.md) and
[aggregate measurements](results-2026-10-11.json).

[Real-app tracing and repeated small-gain experiment](APP_EXPERIMENT.md):
experimental patches, eight paired controls, per-frame output fingerprints and
paired uncertainty analysis. [Completed follow-up](../../../docs/TPU_RUNTIME_SCHEDULING_2026-10-11.md):
a 0.132 ms mean advantage remained uncertain, and a controlled screen wake
reproduced a runtime stall on the control build. The installation release remains `.9`.

[Repeated wake-mode controls](../../../docs/TPU_WAKE_RUNTIME_2026-10-11.md):
all 16 trials hit a wake-related timing limit. Per-invocation hardware counters
separate TPU execution from the much longer runtime wait.
[Reproduction instructions](WAKE_EXPERIMENT.md).

## Boundaries

- Desk use only. Disconnect the phone from the comma before running this tool.
- Every run requires full NPU delegation, checks every output for finiteness,
  discards 20 warmup frames, and aims for a 50 ms start-to-start period. If a
  frame overruns, the next begins as soon as possible; no frames are skipped.
- Fixed seed-17 synthetic inputs isolate execution cost. This is not the
  recurrent JetLink pipeline, accuracy validation, or direct-USB qualification.
- `--copy-inputs 0` is an upper-bound experiment with unchanged resident input.
  It cannot be used for actual changing camera frames.
- `profile.py` samples battery temperature and Android thermal status every
  five seconds. Missing health data, battery 43 C+, or thermal status 3+ stops
  the owned benchmark. Android's own thermal policy remains active.
- The shell process has different scheduling and Android performance-hint
  context from the app. Compare the real app before adopting a result.
- Hardware metrics are aggregate vendor counters, collected after warmup.
  A missing/failed metric is unavailable, not zero. Runtime invocation includes
  driver and scheduling delays and must not be labeled pure TPU execution.

## Build and stage

Use the exact upstream base and Tensor patch from [the Android README](../../README.md).
Build on Linux/WSL with the Android NDK; Python 3 is required. The source checkout
is read only, and the build refuses to overwrite an existing output directory.

```sh
python android/tensor/profiling/build.py \
  --source /path/to/patched-jetlink --ndk /path/to/android-ndk \
  --output /path/to/new-profile-build
```

Stage `tensor-bench`, an already validated compiled model, and a `runtime`
directory containing these libraries from the **same APK** being investigated:
`libLiteRt.so`, `libLiteRtClGlAccelerator.so`,
`libLiteRtCompilerPlugin_google_tensor.so`,
`libLiteRtDispatch_GoogleTensor.so`, and `libc++_shared.so`.
Keep the SDK compiler and model weights local.

```sh
adb -s DEVICE_SERIAL shell mkdir -p /data/local/tmp/jetlink-profile
adb -s DEVICE_SERIAL push /path/to/new-profile-build/tensor-bench /data/local/tmp/jetlink-profile/
adb -s DEVICE_SERIAL push /path/to/runtime /data/local/tmp/jetlink-profile/
adb -s DEVICE_SERIAL push /path/to/validated/model.tflite /data/local/tmp/jetlink-profile/model-minimal.tflite
adb -s DEVICE_SERIAL shell chmod 700 /data/local/tmp/jetlink-profile/tensor-bench
adb -s DEVICE_SERIAL shell sha256sum /data/local/tmp/jetlink-profile/model-minimal.tflite
```

Verify the model hash against its manifest. Use native `/data/local/tmp` storage:
the direct runtime failed on this Pixel when the model was opened from `/sdcard`
because that filesystem did not support the runtime's `preadv2` call.

## Run

Run from a host with ADB and Python 3. Pass `--adb` if ADB is not on PATH.
The explicit serial prevents an accidental test on another device. Output
directories must be new for each case; existing results are never overwritten.

```sh
python android/tensor/profiling/profile.py \
  --serial DEVICE_SERIAL --remote-dir /data/local/tmp/jetlink-profile \
  --output /path/to/results --prefix baseline --modes 5 --frames 120 --metrics
```

After reviewing the smoke run, extend to 600 or 1,200 frames. Modes are 3
(high performance), 4 (sustained), and 5 (burst). `--nice -4` is an isolated
per-thread scheduling experiment; the phone must accept the priority, and the
change ends with that process. It is not an installed JetLink setting.

Use repeated, interleaved controls. Compare mean, p95, p99, maxima, thermal
conditions, and actual outputs. Do not infer a speedup from two runs alone.
The October 11 app experiment looked faster before the original build was
retested; the return control eliminated the apparent improvement.

`scheduler.pbtxt` captures 45 seconds of scheduler and CPU-frequency events
with Perfetto. Raw traces can include unrelated process names; keep them local.
The benchmark emits monotonic/boottime anchors and its PID for correlation.
After collection, stop all runs and remove only the temporary directory and
trace files you created. No listener or forwarding is needed by this tool.

`litert_metrics.h` is the Apache-2.0 header from
[LiteRT v2.3.0](https://github.com/google-ai-edge/LiteRT/blob/v2.3.0/litert/c/litert_metrics.h),
with its original copyright notice. The build checks its SHA-256.

Validation on October 11: the packaged tool built successfully and completed
120 measured frames with finite, matching output bytes and 120 reported
hardware executions. `python android/tensor/profiling/test_profile.py` covers
thermal limits, unavailable telemetry, and stopping only the owned process.
