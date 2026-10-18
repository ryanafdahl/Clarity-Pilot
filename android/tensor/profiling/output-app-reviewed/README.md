# Experimental output allocation pair

This is an isolated diagnostic pair based on JetLink upstream commit `d26001b4161f33bab28d806de6a99b96325a429b` plus the archived exact `.10` Tensor support patch. The full `rare-source.patch` and `often-source.patch` each apply directly to that clean upstream commit. Do not stack them on an already patched source tree.

Both variants retain the LiteRT 2.3 runtime, synchronous execution, managed input buffers, model/precision selection, all existing locks, copies, fences, thermal/warmup controls, and normal protocol and USB behavior. The compiled model is imported separately; neither APK bundles the private compiled model or Tensor SDK. There is no per-frame tracing or metrics instrumentation in this experiment.

The control imports only precompiled Tensor output buffers with CPU_READ_RARELY | CPU_WRITE_RARELY. The candidate changes only those two frequency flags to OFTEN, plus its version label. GPU_DATA_BUFFER is present in both. All six current-model inputs still use the original managed allocation path. Model `.tensor` sets the dedicated gate; GPU and on-device `.npu` retain their original allocation routes.

## Ownership and recovery

Every imported Swift output buffer holds a strong model reference before entering C construction. The model never owns Swift buffers, so there is no ARC cycle. Buffer destruction releases its LiteRT wrapper while retaining the model. The model destroys the compiled-model cache before releasing the raw AHWB references it owns. This also covers an output that outlives engine close, partial construction, and buffer rebinding. Ledger mutation follows the existing serialized engine construction/run/close contract; there is no process-global buffer-handle registry or per-frame lookup.

The import uses a NULL deallocator and explicitly retains the caller's original AHWB reference. Pre-lock construction failures release any imported wrapper before its raw AHWB. Uncertain imported-output mapping/unmapping or Tensor execution failures terminate the diagnostic process before ordinary cleanup. Restart the entire app process after any such failure; an in-process retry is not supported. Error-message OOM also aborts instead of disguising a failed operation as success. That OOM-only hardening applies to both Android diagnostic variants.

The one-time allocation path verifies supported buffer types, zero-stride requirements, size, allocation descriptor, imported type, underlying AHWB identity, and packed size. It refuses unsupported or inconsistent cases without falling back to managed outputs. Descriptor logs occur only during allocation.

## Validation and next test

The parameterized `test.py` compiles the actual C bridge twice against mocked public APIs and extracts the actual Swift buffer/run implementation for host fixtures. C fixtures cover copy/lock order, six managed inputs, other-backend behavior, model-cache-before-raw release, multiple outputs, partial rebind, all public API construction failures, descriptor/type/size rejection, initialization lock/unlock aborts, and OOM during failed unlock/run. Swift release-mode tests use active preconditions and require the intended failure message for fatal cases, so an unrelated crash cannot count as success. They cover strong-owner lifetimes and construction failure as well as preserved nonimported error handling. `manifest.json` records the successful reviewed suites and independent source review. Each local fixture run writes its own ownership-tests.json and logs under the selected build directory. The bridge also compiles with NDK ARM64 and -Wall -Wextra -Werror.

Build sequentially with the normal Swift/Android toolchain and the previously verified signer. Both APKs must retain version code 80710 and signer SHA-256 `50e670489a4ba19aec5e9fbad6f06074556d4d07be629ba012b3ca78f1eabb4e`. Verify these values with `apksigner verify --print-certs` and `aapt2 dump badging`. Each captured variant passed the existing Android unit suite. This package contains no private build script, SDK, model, vendor headers, APK or runtime binary. Artifact hashes identify the reviewed private builds; local rebuilds may differ in signing or build metadata.

Before any phone experiment, independently verify APK hashes and normalized source differences. Hold the same original SDK v2.1 compiled model fixed, require exact recurrent parity, use the same screen/warmup/thermal state, and compare balanced paired raw frame distributions. A native timing improvement alone does not establish an application improvement. Neither this pair nor a desk benchmark qualifies a driving test.

The production `.10` rollback remains separate and unchanged: SHA-256 `cf760fe7c69c8d56e2eb0dc2bd45bf2cc9c8780548e8dbbe909834ead66872bd`. Restore it after the experiment. Production adoption needs separate validation, including failure and recovery behavior.

## Reproduction commands

Use a fresh checkout of the upstream base for each variant. These are complete
patches, including the exact `.10` support changes. Preserve the existing signer
if comparing on an already provisioned test phone; version code remains 80710.

```sh
git checkout --detach d26001b4161f33bab28d806de6a99b96325a429b
git apply /path/to/output-app-reviewed/rare-source.patch
python /path/to/output-app-reviewed/test.py \
  --source-dir /path/to/patched-jetlink --build-dir /path/to/new-fixture-output \
  --swiftc /path/to/swiftc --cc cc
cd android
./gradlew :app:assembleRelease :app:testDebugUnitTest --console plain --no-daemon --max-workers=1
```

Use `often-source.patch` in the candidate checkout instead. The host fixtures
require Linux/WSL, Python 3.11+, a C compiler and Swift 6.4. Both macro variants
are tested from either patched source tree. Inputs to the test remain local;
the complete CLiteRt tree comes from the patched JetLink checkout. The included
minimal AHWB header is a test mock, not an Android or Tensor SDK redistribution.
Build and phone operations must be serialized. No performance result is implied
by successful compilation or these ownership fixtures.
