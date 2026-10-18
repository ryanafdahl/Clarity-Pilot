# Reproduce a paired native model comparison

run_model_pairs.py runs the existing profiling/profile.py against two models
already staged in one /data/local/tmp directory. It does not push files, install
an APK, change app state, or select a driving model. Desk connection only.

Build and stage the existing native profiler, both validated compiled models
and the matching runtime libraries using the profiling README. Leave all other
inference loads idle. The runner requires an explicit ADB serial and the two
expected model SHA-256 values; it verifies the remote files before and after
the comparison. It also records and verifies the native binary hash before and after the run. Keep the same
native binary and runtime for both variants.

From this directory, run (the default profiler is the profile.py in the parent directory):

~~~sh
python run_model_pairs.py --adb /path/to/adb --serial DEVICE_SERIAL \
  --remote-dir /data/local/tmp/jetlink-profile \
  --model-a model-a.tflite --sha-a EXPECTED_64_HEX_SHA256 \
  --model-b model-b.tflite --sha-b EXPECTED_64_HEX_SHA256 \
  --output /path/to/new-results --prefix compiler-pairs
~~~

Use --profile /path/to/profiling/profile.py to select another profiler checkout.
--plan-only writes the full randomized plan without importing the profiler or
contacting ADB. Give the subsequent real run a new output directory.

Defaults match the compiler experiment: six pairs (three AB and three BA),
randomized with order seed 20261017, 600 measured frames per run, 20 warmups,
mode 5, a 50 ms period, input copies and vendor metrics enabled. The native
input generator keeps its separate fixed seed 17. Warmups and input seed come
from native_profile.c; the runner accepts only the existing 20-warmup setting.
Order randomization does not alter inputs.

The local output directory must be new. All planned remote run directories must
be absent. An atomic .native-model-pairs-lock directory prevents two copies of
this paired runner from sharing a prepared directory concurrently. It cannot
detect an unrelated app or benchmark load; ensure those are idle yourself.
A successful run removes only its empty lock directory. A failed run retains
the lock so the failure can be inspected before another load starts.

The existing profiler checks battery/thermal telemetry before and during each
run and stops only its owned benchmark on failure. Its remote timeout remains a
second bound. Missing health data, battery temperature 43 C or higher, or thermal
status 3 or higher aborts. The runner preserves raw health observations, including
one that triggers the guard, stdout/stderr, per-frame samples, output files,
per-run summaries, a checkpoint and a final result or failure record. It stops
if final output hashes are absent or differ from the first run, or requested
hardware metrics are unavailable or do not cover every measured frame. Failed
runs retain the checkpoint without publishing a successful results.json. Equality here
covers the fixed-input final output only; use recurrent correctness validation
separately.

After failure inspect failure.json, the relevant bench.pid and the remote
process/timeout before removing that run's empty lock directory. Do not delete
other result directories or kill unrelated processes. A rerun needs a fresh local
output directory and an unused --prefix.

Keep raw output private: it includes process/timing anchors and battery/thermal
service output. Publish a sanitized aggregate of paired run differences, not raw
logs. A frame is not an independent experimental replicate; the adjacent pair
is the comparison unit. Missing vendor counters are unavailable, not zero.
Native fixed-input latency excludes physical USB transport, the recurrent app,
wake behavior and vehicle qualification.

Offline checks:

~~~sh
python test_run_model_pairs.py
~~~

The checks validate order balance/reproducibility, safe argument boundaries,
existing-output refusal, exact remote hash parsing, final-output comparison and
a plan-only path that cannot import the profiler or contact the device.

