# Tensor buffer diagnostics

These native tools measure public LiteRT input/output staging and compare supported Android allocation hints. They are diagnostic experiments for one synchronous model and do not change the Android app, model precision, synchronization requirements or vehicle configuration. No speed improvement is claimed by the tools themselves.

This source package contains no compiled executable, runtime/SDK library, model, private trace, device serial or account identifier. Supply your own authorized runtime and model outside the repository.

## Build prerequisites

Use Python 3.11 or later on Linux or WSL, an Android NDK with the ARM64/API31 compiler, and the CLiteRt bridge source that matches the Tensor app. Supply the adjacent profiling directory containing native_profile.c, metrics.inc and the pinned LiteRT metrics header. The build accepts a supported plain bridge or a previously prepared native-profiler bridge; unexpected source shapes fail rather than applying a patch loosely.

The build script creates a fresh build directory and modifies only copied sources. Use an output directory outside the repository:

    python3 build.py --kind io \
      --bridge-dir /path/to/JetlinkKit/Sources/CLiteRt \
      --profiler-dir /path/to/android/tensor/profiling \
      --ndk-root /path/to/android-ndk \
      --build-dir /path/to/new/io-build

    python3 build.py --kind ahwb \
      --bridge-dir /path/to/JetlinkKit/Sources/CLiteRt \
      --profiler-dir /path/to/android/tensor/profiling \
      --ndk-root /path/to/android-ndk \
      --build-dir /path/to/new/ahwb-build

Build manifests record source and binary hashes. The same binary is used for both variants of each comparison. Parameters, model, runtime, frame count, health guards and instrumentation state must match.

## Per-buffer I/O timing

The io build retains every public size query, lock, memcpy and unlock, plus the original per-frame total. It emits aggregated per-buffer timings without logging on every copy. Each row reports direction, index, name, logical bytes, count, and total/mean/min/max for the four stages. Twenty warmups are excluded.

Five clock reads per measured copy and aggregation add observer overhead. The timer floor is reported, never subtracted. BENCH_IO_PROFILE=0 runs the matched instrumentation-off control; omitting it enables the stage clocks. Both controls retain the same finite-output checks and fixed-input byte consistency test. The original native-profiler CLI is preserved:

    BENCH_IO_PROFILE=0 BENCH_METRICS=1 ./tensor-bench RUNTIME MODEL 5 600 50000 OUTPUT_DIR 1
    BENCH_IO_PROFILE=1 BENCH_METRICS=1 ./tensor-bench RUNTIME MODEL 5 600 50000 OUTPUT_DIR 1

The last argument must remain 1 so inputs are copied each frame. Use different, precreated output directories. A balanced off/on/on/off sequence is a useful initial observer-overhead check. Do not compare an instrumented candidate to an uninstrumented control.

## AHardwareBuffer allocation comparison

LiteRT 2.3's managed allocator requests a one-row BLOB with CPU read/write RARELY and GPU_DATA_BUFFER usage. The ahwb build imports caller-owned BLOB allocations through the public LiteRT API. It compares:

| Variant | Environment | CPU usage |
| --- | --- | --- |
| Control | BENCH_AHWB_USAGE=rarely | READ_RARELY and WRITE_RARELY |
| Candidate | BENCH_AHWB_USAGE=often | READ_OFTEN and WRITE_OFTEN |

GPU_DATA_BUFFER is identical. All LiteRT locks, unlocks, copies, pending-event fence handling and synchronous model execution remain intact. No persistent mapping, direct Android lock, skipped flush or host-memory fallback is introduced. Allocation frequency hints do not guarantee a particular cache policy.

Startup logs every supported numeric buffer type (AHWB is 2), required size/alignment/strides, actual type, packed size, allocation size and descriptor. The tool refuses unsupported AHWB requirements, nonzero strides, sizes outside the 32-bit BLOB width range, unsupported or changed descriptors, and inconsistent buffer identity/type/size. Required alignment is reported; allocation follows AHWB's descriptor-based contract, as the managed allocator does.

The public import receives NULL deallocator. The harness owns the initial AHWB reference. Successful cleanup first drops the public LiteRT wrappers, then destroys the compiled model, then releases raw AHWB references. This accounts for compiled-model buffer caches that may duplicate the wrapper. Pre-lock failures clean known-owned handles in the same safe order. Initialization lock/unlock failures abort without freeing potentially uncertain mapping state; later errors terminate the native process through the original harness. This policy is appropriate only to this bounded diagnostic, not a reusable application buffer manager.

Start with short native smoke tests of both modes, then require descriptor validation, full NPU execution/counters, normal sampled health, finite/deterministic output and matching output hashes before a balanced timing screen:

    BENCH_AHWB_USAGE=rarely BENCH_IO_PROFILE=0 BENCH_METRICS=1 ./tensor-bench RUNTIME MODEL 5 20 50000 OUTPUT_DIR 1
    BENCH_AHWB_USAGE=often BENCH_IO_PROFILE=0 BENCH_METRICS=1 ./tensor-bench RUNTIME MODEL 5 20 50000 OUTPUT_DIR 1

Expected reported descriptor usage is 16777250 for RARELY and 16777267 for OFTEN. A passing short screen does not establish sustained performance, recurrent-model accuracy, wake behavior or physical vehicle USB readiness. This tool does not schedule load or enforce thermal limits by itself; run it under an existing health-guarded controller, one workload at a time.

## Offline checks

The test runner builds local host tests using the exact generated bridge and mocked Android/LiteRT functions. It does not connect to a device. Tests cover unchanged copy bytes and lock ordering, requirement refusal, every pre-lock query/import failure, imported-handle ownership, cache-safe deferred AHWB release and initialization lock/unlock failure paths. Passing mocks does not prove device allocation or driver behavior.

Run the tests after building the ahwb variant:

    python3 test.py --build-dir /path/to/new/ahwb-build

Use a host C compiler through the test runner's compiler option when cc is unavailable. Test outputs and executable artifacts belong outside the source package.

## Public API references

- [LiteRT 2.3 AHWB allocator and synchronization](https://github.com/google-ai-edge/LiteRT/blob/v2.3.0/litert/runtime/ahwb_buffer.cc)
- [LiteRT public buffer import and ownership](https://github.com/google-ai-edge/LiteRT/blob/v2.3.0/litert/c/litert_tensor_buffer.h)
- [LiteRT public buffer requirements](https://github.com/google-ai-edge/LiteRT/blob/v2.3.0/litert/c/litert_tensor_buffer_requirements.h)
- [Compiled-model buffer registration](https://github.com/google-ai-edge/LiteRT/blob/v2.3.0/litert/runtime/compiled_model.cc)
- [Android AHardwareBuffer allocation, usage and locking](https://developer.android.com/ndk/reference/group/a-hardware-buffer)

The checked LiteRT 2.3 runtime exports the required public functions. Device execution remains necessary to verify that a particular platform can allocate/import the requested buffers.


The public metrics-header pin accepts CRLF and LF checkouts by normalizing only
CRLF to LF before comparison. Generated manifests keep raw source hashes and add
the normalized header hash. The captured SOURCE_MANIFEST.json remains historical
provenance. The shared checkout fixtures run with
`python ../metrics-detail/test_source_pins.py`.

CURRENT_SOURCE_MANIFEST.json pins the current published source after that
portability fix. SOURCE_MANIFEST.json identifies the earlier captured package;
its raw hashes are retained as historical evidence, not current-file claims.
