# Google Tensor support on the Pixel

**October 21 V3 update:** the comma selects Cinque Terre V3. A Tensor image-history defect was repaired, but the 160-frame check still failed one accuracy criterion. The Pixel remains on V2. [Evidence and rollback](../../docs/PIXEL_V3_MODEL_2026-10-21.md) · [Unqualified V3 reproduction tools](v3-2026-10-21/README.md). The qualified V2 instructions below remain unchanged.

The installed **0.8.7-clarity-tensor.10** app uses pinned upstream source plus precompiled Tensor support and the October 10 USB stability repairs, optional Android CPU hints and the matched LiteRT 2.3.0 runtime. **The parked-only handshake and Parked USB Test switch are removed.** Ordinary protocol-v3 engine requests and USB service are enabled. The selected processor is **Tensor TPU (precompiled)**, and the selected model remains **Cinque Terre V2**. [APK, installation and build provenance](../README.md).

The app retains phone health monitoring in its foreground service, including when its screen is hidden. Tensor engine requests and inference stop if telemetry is missing, malformed or five seconds old, Android thermal status is severe (3+), or battery temperature reaches 43°C. After a thermal refusal, a fresh engine request is needed once health recovers. These app thresholds do not alter Android's thermal or charging limits.

The separate **Tensor NPU (on-device)** choice uses upstream's runtime compiler and its reported execution backend. The selected precompiled path checks the imported model and requires full NPU execution; it refuses GPU fallback. Logs on the installed Pixel confirm `NPU(Tensor G6)`.

## Current results and remaining checks

[October 17 compiler/runtime investigation](../../docs/TENSOR_COMPILER_RUNTIME_2026-10-17.md) found a repeatable gain from Tensor SDK v2.1: two separate balanced comparisons on the unchanged `.10` app showed **7.4–8.4% lower average processing time**. The subsequent 6,000-frame screen-off run averaged **34.19 ms**, with one frame at **50.10 ms**. Three subsequent wake checks still hit the timing guard, with maxima of 84–93 ms. The source model and FP16 precision stay unchanged. This is desk phone processing, not full vehicle latency. [Earlier TPU profiling](../../docs/TPU_PERFORMANCE_2026-10-11.md) and the [isolated profiler](profiling/README.md) retain the hardware-counter workflow and unsuccessful candidates.

[October 10 stability and LiteRT report](../../docs/PIXEL_USB_STABILITY_LITERT23_2026-10-10.md) records the installed APK identity, normal handshake, numerical comparison, sustained desk timing and test counts. Removal of the parked restriction is a functional change, not driving qualification. The subsequent [direct-USB drive](../../docs/PIXEL_DRIVE_SCREEN_OFF_2026-10-10.md) recorded 8.67 assisted miles on the Pixel large-model path and a clean 11 min 45.7 s finish, but also three early USB resets. Screen/charging/Android Auto effects remain unisolated, detailed phone stage logs are unavailable, and repeated failure recovery and sustained reliability remain open. The comma retains its existing warmup, deadlines and fallback limits and now bounds optional USB inference to one outstanding request.

The [October 3 archive](history-2026-10-03.md) retains the short direct-USB passes and subsequent timing failures. Its stationary scripts and deployment manifest describe the previous comma integration and are not the setup procedure for this app. They have not been changed to bypass their compatibility checks.

## Exact model and compiler

- Original V2 ONNX: `09d080f36965bb2a0790500452bd328aa03c484d0222aa79d1ad9f021a522aec`, 766,040,736 bytes.
- Compiled model: `328ae315dcd6e62e08aa670e04f11219e4766a11cfc37c261a54ef89f7c6c571`, 835,398,160 bytes.
- Tensor SDK v2.1 compiler library: `14e84153cbcf60463d011ba739fc15ff222188c6448a283c0abea639fa19cb68`.
- Compiler worker: `e6a8f7c0bdfebbb754e18f82b7bcde83b22c526c1297ce555a1797a2cd099294`.
- Target `Tensor_G6`, precision `half`, sharding `minimal`, LiteRT `2.3.0`; all 2,424 operators compiled into one NPU partition, and the live engine requires full NPU execution.
- [Current desk-validated manifest](qualified-model.json), with archive and converted-input hashes. [Prior SDK v2.0/LiteRT 2.3 manifest](qualified-model-sdk20-litert23.json) is retained for rollback. Model weights and the private SDK compiler are not redistributed.

The update recompiled V2 with ai-edge-litert 2.3.0 and verified its output again. Image history retains exact bytes; feature/desire history retains the existing half-precision rounding. Burst scheduling is unchanged from the previously tested Tensor build.

## Rebuild and compile

Check out upstream `d26001b4161f33bab28d806de6a99b96325a429b`, apply [tensor-support.patch](tensor-support.patch), and build using [the Android instructions](../README.md#validation-and-rebuilding). The patch is for that exact base. Its compile helper has an additional provenance-only update; the [archived exact `.10` source patch](tensor-support-0.8.7-clarity-tensor.10.patch) matches the APK source. Runtime code is unchanged. The previous [`.6` patch](tensor-support-0.8.5-clarity-tensor.6.patch), [`.5` patch](tensor-support-0.8.5-clarity-tensor.5.patch) and [`.4` patch](tensor-support-0.8.0-clarity-tensor.4.patch) remain archived.

The app build pins and verifies all three LiteRT 2.3.0 Maven AARs: core, GPU and Google Tensor NPU runtime. It does not download the private SDK compiler. Extract Tensor SDK v2.1 locally and use Python with `ai-edge-litert==2.3.0`. Keep the worker beside its compiler library. The compile helper records converted input, library and executable hashes; `--sdk-worker` selects a helper if the layout is ambiguous. Library-only SDK v2.0 remains supported for rollback. The [Tensor SDK codelab](https://codelabs.developers.google.com/codelabs/google-tensor-ml-sdk#0) documents the stable backend switch; the compiler script sets it before importing LiteRT and points explicitly at your private compiler directory:

```sh
cd JetlinkKit
swift build --product tensor-convert -c release
.build/release/tensor-convert /path/to/source.onnx /path/to/converted
cd ..
python android/scripts/compile-tensor.py \
  --source /path/to/source.onnx --model /path/to/converted/model.tflite \
  --sdk /path/to/google_tensor_ml_sdk --output /path/to/compiled \
  --soc Tensor_G6 --precision half --sharding minimal
```

Use the actual phone chipset and validate each new model. Automatic precision was an unsuccessful earlier candidate for this V2 model. This large model needs substantial compilation memory. WSL exhausted its default memory while compiling this update; use an isolated compiler run and sufficient RAM/swap, and avoid concurrent Android builds. Do not change model precision just to reduce build memory.

## Import into the Pixel

Open the app once to create its `tensor-models` folder. Replace `SOURCE_SHA256` with the original ONNX hash and copy the two compiler outputs directly into that folder:

Stop JetLink before replacing either file. Preserve the previous model and manifest locally for rollback, then stage the replacement under temporary names:

```sh
adb shell am force-stop io.zoompilot.jetlink.android
adb push /path/to/compiled/SOURCE_SHA256/model.tflite /sdcard/Android/data/io.zoompilot.jetlink.android/files/tensor-models/SOURCE_SHA256.tflite.pending
adb push /path/to/compiled/SOURCE_SHA256/manifest.json /sdcard/Android/data/io.zoompilot.jetlink.android/files/tensor-models/SOURCE_SHA256.json.pending
adb shell sha256sum /sdcard/Android/data/io.zoompilot.jetlink.android/files/tensor-models/SOURCE_SHA256.tflite.pending
```

Compare that digest with `compiled_sha256` in the manifest before continuing. Keep the app stopped while replacing the pair:

```sh
adb shell mv /sdcard/Android/data/io.zoompilot.jetlink.android/files/tensor-models/SOURCE_SHA256.tflite.pending /sdcard/Android/data/io.zoompilot.jetlink.android/files/tensor-models/SOURCE_SHA256.tflite
adb shell mv /sdcard/Android/data/io.zoompilot.jetlink.android/files/tensor-models/SOURCE_SHA256.json.pending /sdcard/Android/data/io.zoompilot.jetlink.android/files/tensor-models/SOURCE_SHA256.json
adb shell am start -n io.zoompilot.jetlink.android/io.zoompilot.jetlink.MainActivity
```

Do not create a shell-owned nested directory. A fresh process is required: a live engine request can reuse an already loaded model with the same source identity. On fresh load, the imported compiled hash is compared with prepared metadata and a changed hash triggers rebuild. The copied model is hashed during preparation; existing prepared bytes are not rehashed on every load. Select **Settings → Processor → Tensor TPU (precompiled)**, then prepare Cinque Terre V2. Source, chipset, runtime and compiled-file checks protect imports; a changed manifest hash invalidates the cached compiled artifact.

## Connect and repeat desk validation

For normal comma USB use, follow [the connection instructions](../README.md#connect-to-the-comma). There is no test flag to enable. The app's Developer setting is unnecessary for direct USB.

For a desk benchmark, open **JetLink's Settings**, scroll to **About**, and tap **Version** seven times. This shows the **Developer** section and automatically enables its listener. The control is labeled **Port**, normally **5599**; there is no separate TCP-listener switch. This is separate from Android's Developer options. Put the patched upstream checkout on `PYTHONPATH` and forward its port:

```sh
adb forward tcp:5599 tcp:5599
python scripts/verify_parity.py capture --host 127.0.0.1 --port 5599 \
  --sha256 09d080f36965bb2a0790500452bd328aa03c484d0222aa79d1ad9f021a522aec \
  --nbytes 766040736 --dir /path/to/new-parity-output
python scripts/verify_parity.py reference --onnx /path/to/source.onnx --dir /path/to/new-parity-output
python scripts/verify_parity.py compare --dir /path/to/new-parity-output
```

No `--parked` argument is used. [benchmark.py](benchmark.py), with adjacent [validation.py](validation.py), measures bounded synthetic runs using normal engine requests and checks phone health. Start with 120 measured frames, then extend after reviewing results. It requires `--source-sha256`, `--source-bytes`, `--transport` and a new `--output` path; optionally supply `--adb` for independent thermal sampling. The desk timing guard uses phone/server time, not ADB round-trip time. Each 100-frame phone p95 must stay below 50 ms and every phone execution below 100 ms. These benchmark checks do not add a parked restriction to the app.

Remove forwarding afterward with `adb forward --remove tcp:5599`, and tap Version seven times again to disable the Developer listener. ADB/TCP measurements are not direct comma USB measurements.

## Historical results

- [Direct comma USB results](history-2026-10-03.md#direct-comma-usb-results)
- [Ignition-on results](history-2026-10-03.md#ignition-on-results)
- [Archived stationary ignition-on procedure](history-2026-10-03.md#stationary-ignition-onac-test)
- [Earlier Tensor compilation results](history-2026-10-03.md#results-on-october-3-2026)

## References

- [Google Tensor support](https://developers.google.com/edge/litert/next/tensor-sdk)
- [Compiler precision and sharding flags](https://developers.google.com/edge/tensor-sdk/compilation-flags)
- [LiteRT 2.3.0 performance modes](https://github.com/google-ai-edge/LiteRT/blob/v2.3.0/litert/c/options/litert_google_tensor_options_type.h)

- [LiteRT 2.3 release and Android artifact split](https://github.com/google-ai-edge/LiteRT/releases/tag/v2.3.0)
- [Google Tensor ML SDK codelab](https://codelabs.developers.google.com/codelabs/google-tensor-ml-sdk#0)
