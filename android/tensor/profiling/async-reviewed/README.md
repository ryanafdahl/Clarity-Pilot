# Synchronous and asynchronous Tensor control experiment

These are the reviewed `deep-sync2` and `deep-async2` diagnostic sources. They are not the production APK. No APK, private SDK, runtime library, model or device data is included. They preserve the current model, FP16 precision, burst mode, warmup, health gates and normal protocol.

Both complete patches start from [zoompilot/jetlink d26001b4161f33bab28d806de6a99b96325a429b](https://github.com/zoompilot/jetlink/tree/d26001b4161f33bab28d806de6a99b96325a429b). Apply exactly one patch to a clean checkout of that commit. Do not stack it on the current Tensor support patch or apply the two diagnostic patches together. The normalized patches differ only in `JL_WAKE_ASYNC=0/1` and the `deep-sync2/deep-async2` version label.

## Prepare and build

Set `JETLINK_CHECKOUT` to a fresh checkout path and `PATCH_FILE` to the absolute path of the selected patch. Use separate checkouts for control and candidate.

```sh
git clone https://github.com/zoompilot/jetlink.git "$JETLINK_CHECKOUT"
git -C "$JETLINK_CHECKOUT" checkout --detach d26001b4161f33bab28d806de6a99b96325a429b
git -C "$JETLINK_CHECKOUT" apply --check "$PATCH_FILE"
git -C "$JETLINK_CHECKOUT" apply "$PATCH_FILE"
```

Use the repository's Android build prerequisites: Linux/WSL, JDK 17, Swift 6.4.0 with its Android SDK, Android platform 37, NDK 30.0.16248370 and the pinned Gradle wrapper. Set `ANDROID_HOME` and `SWIFT` to those installed tools. Preserve the existing application's signing configuration; this package contains no key.

```sh
cd "$JETLINK_CHECKOUT/android"
./gradlew :app:assembleRelease :app:testDebugUnitTest --console plain --no-daemon --max-workers=1
```

The release APK is generated in `android/app/build/outputs/apk/release/app-release.apk`. The reviewed local builds both used version code **80710** and signing-certificate SHA-256 **50e670489a4ba19aec5e9fbad6f06074556d4d07be629ba012b3ca78f1eabb4e**. Verify the new artifact with your SDK's `apksigner verify --print-certs` and `aapt2 dump badging` before considering installation. A rebuild needs the original signing key to update that installation; matching source does not reproduce a private key. Do not uninstall to bypass a signer mismatch. Original reviewed APK hashes are recorded in the manifest for provenance, but APK files are not distributed here.

## Offline ownership tests

Use Python 3.11+ on Linux and a host C compiler. Set `TOOLS_DIR` to this package and `TEST_OUTPUT` to a fresh directory outside the package and checkout.

```sh
python3 "$TOOLS_DIR/test.py" \
  --bridge-dir "$JETLINK_CHECKOUT/JetlinkKit/Sources/CLiteRt" \
  --build-dir "$TEST_OUTPUT"
```

`--cc` or `CC` selects the host compiler. The runner executes the actual C bridge with mocked public LiteRT APIs: three control cases and twelve candidate cases. The retain-failure case deliberately verifies a child-process SIGABRT with core dumps disabled. Fifteen tests passed for the reviewed sources, and 59 Android unit tests passed in each original build. These checks do not simulate driver failures or prove performance.

## Completion and recovery contract

The control calls the usual synchronous API. Only the precompiled Tensor candidate submits asynchronously, and it still waits for every output before returning. There is no frame pipeline. The candidate refuses synchronous fallback, missing API functions, and any missing/null output event when asynchronous execution was reported. Present events are drained even after another event or a partial submission fails. Events are borrowed from their buffers and cleared only after successful waits; they are never independently freed.

Any uncertain failure latches the process closed. Buffer references and the model/options/environment remain retained so normal close cannot free possibly active device resources. Reads, writes, model creation and subsequent runs refuse. **Force-stop the process after any experimental error and restore the preserved production APK.** No in-process retry, queue reset or model switch clears the latch. A failed retain terminates the diagnostic process. Waits remain blocking; the host controller must keep a timeout and terminate a hung diagnostic process.

## Interpreting timing

The two diagnostic variants share trace wrappers, optional vendor metrics, a profileable manifest and the failure latch. With tracing off, they perform disabled trace checks but do not collect hardware metrics or write trace sections/counters. Those checks and Swift closure wrappers are not proven to be free. Comparisons between this pair estimate the async change; a diagnostic-control versus production comparison also includes the shared instrumentation. The packaged runtime libraries are unchanged from the reviewed production `.10` APK.

Hardware metrics currently require an app-selected ATrace session; there is no independent hardware-metrics switch in these APKs. Keep tracing off for primary timing. Use the same compiled-model hash, output fixture, screen policy, thermal conditions, warmup, frame count and health controller. Require fresh recurrent parity in both variants, retain all failures/outliers, and compare balanced paired runs. A measured desk gain does not establish a fix for wake stalls or vehicle USB behavior. Restore the verified production app and normal listener settings after experiments.
