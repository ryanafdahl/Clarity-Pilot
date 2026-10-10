# Google Tensor support on the Pixel

The installed **0.8.5-clarity-tensor.6** app uses pinned upstream source plus precompiled Tensor support and the October 10 USB receive/recovery fixes. **The parked-only handshake and Parked USB Test switch are removed.** Ordinary protocol-v3 engine requests and USB service are enabled. The selected processor is **Tensor TPU (precompiled)**, and the selected model remains **Cinque Terre V2**. [APK, installation and build provenance](../README.md).

The app retains phone health monitoring in its foreground service, including when its screen is hidden. Tensor engine requests and inference stop if telemetry is missing, malformed or five seconds old, Android thermal status is severe (3+), or battery temperature reaches 43°C. After a thermal refusal, a fresh engine request is needed once health recovers. These app thresholds do not alter Android's thermal or charging limits.

The separate **Tensor NPU (on-device)** choice uses upstream's runtime compiler and its reported execution backend. The selected precompiled path checks the imported model and requires full NPU execution; it refuses GPU fallback. Logs on the installed Pixel confirm `NPU(Tensor G6)`.

## Current results and remaining checks

[October 10 USB repair report](../../docs/PIXEL_USB_RECOVERY_2026-10-10.md) records the installed APK identity, normal handshake, numerical comparison, sustained desk timing and test counts. Removal of the parked restriction is a functional change, not driving qualification. Direct comma USB on this APK, repeated reconnects, sustained cooling/charging in the intended mount, camera-derived outputs and fallback behavior still need physical verification. The comma's existing warmup, timing and fallback logic is unchanged.

The [October 3 archive](history-2026-10-03.md) retains the short direct-USB passes and subsequent timing failures. Its stationary scripts and deployment manifest describe the previous comma integration and are not the setup procedure for this app. They have not been changed to bypass their compatibility checks.

## Exact model and compiler

- Original V2 ONNX: `09d080f36965bb2a0790500452bd328aa03c484d0222aa79d1ad9f021a522aec`, 766,040,736 bytes.
- Compiled model: `fc393523c5c1ddba9774382db513a5c62fad50cb187968ea25bc96db5480b51b`, 834,528,528 bytes.
- Compiler: `d74bea45081aa90a39505a675c15f566d46dbcc35e55a98f755c02017464cd1f`.
- Target `Tensor_G6`, precision `half`, sharding `minimal`, LiteRT `2.2.0`; original compilation placed all 2,424 operators in one TPU partition.
- [Machine-readable manifest](qualified-model.json). Model weights and the private SDK compiler are not redistributed.

The update reused the existing compiled model and verified its output again. Image history retains exact bytes; feature/desire history retains the existing half-precision rounding. Burst scheduling is unchanged from the previously tested Tensor build.

## Rebuild and compile

Check out upstream `b079496816e617ffd891ea12e5bee5d116db1383`, apply [tensor-support.patch](tensor-support.patch), and build using [the Android instructions](../README.md#validation-and-rebuilding). The patch is for that exact base. The previous [`.5` patch](tensor-support-0.8.5-clarity-tensor.5.patch) and [`.4` patch](tensor-support-0.8.0-clarity-tensor.4.patch) remain archived.

The app build uses upstream's hash-checked LiteRT 2.2.0 NPU runtime bundle. It does not download the private SDK compiler. If compiling a new model, extract your SDK locally and use Python with `ai-edge-litert==2.2.0`:

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

Use the actual phone chipset and validate each new model. Automatic precision was an unsuccessful earlier candidate for this V2 model. Compilation previously required around 14.7 GiB peak compiler RSS; allow additional memory for the OS and other processes.

## Import into the Pixel

Open the app once to create its `tensor-models` folder. Replace `SOURCE_SHA256` with the original ONNX hash and copy the two compiler outputs directly into that folder:

```sh
adb push /path/to/compiled/SOURCE_SHA256/model.tflite /sdcard/Android/data/io.zoompilot.jetlink.android/files/tensor-models/SOURCE_SHA256.tflite
adb push /path/to/compiled/SOURCE_SHA256/manifest.json /sdcard/Android/data/io.zoompilot.jetlink.android/files/tensor-models/SOURCE_SHA256.json
```

Do not create a shell-owned nested directory. Restart the app after replacing a model. Select **Settings → Processor → Tensor TPU (precompiled)**, then prepare Cinque Terre V2. Source, chipset, runtime and compiled-file checks protect imports; a changed manifest hash invalidates the cached compiled artifact.

## Connect and repeat desk validation

For normal comma USB use, follow [the connection instructions](../README.md#connect-to-the-comma). There is no test flag to enable. The app's Developer setting is unnecessary for direct USB.

For a desk benchmark, tap **Settings → About → Version** seven times to expose Developer settings and enable the TCP listener. Put the patched upstream checkout on `PYTHONPATH` and forward its port:

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
- [LiteRT 2.2.0 performance modes](https://github.com/google-ai-edge/LiteRT/blob/v2.2.0/litert/c/options/litert_google_tensor_options_type.h)
