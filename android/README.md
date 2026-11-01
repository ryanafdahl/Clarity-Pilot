# JetLink on the Pixel

**November 1 update:** `0.8.12-clarity-tensor.11` is installed on the Pixel 11 Pro XL, based on stable upstream v0.8.12. Its outputs matched `.10` across 160 frames. The first timing run stopped after a 275.406 ms phone-processing outlier; a repeat completed 1,200 frames with a 37.261 ms maximum. The unexplained stall remains unresolved, and this maintenance update does not establish a speed improvement. [Update record](../docs/PIXEL_UPDATE_2026-11-01.md).

**V3 remains unqualified on the Pixel.** Its October 21 Tensor compilation failed the extended accuracy check. The validated Pixel model is Cinque Terre V2; the V3 candidates remain quarantined. The comma's current model was not checked for this app update. [V3 findings](../docs/PIXEL_V3_MODEL_2026-10-21.md).

[Download jetlink-0.8.12-clarity-tensor.11-pixel.apk](https://github.com/ryanafdahl/Clarity-Pilot/raw/refs/heads/main/android/jetlink-0.8.12-clarity-tensor.11-pixel.apk)

| Field | Value |
| --- | --- |
| Version / code | `0.8.12-clarity-tensor.11` / `81211` |
| Package | `io.zoompilot.jetlink.android` |
| Source base | [zoompilot/jetlink `a863c3801da6fd925d14eb1f5b1e250f8efcc649`](https://github.com/zoompilot/jetlink/tree/a863c3801da6fd925d14eb1f5b1e250f8efcc649) |
| Local changes | [Tensor support patch](tensor/tensor-support.patch) |
| Architecture / protocol | ARM64 / v3 |
| APK bytes | `104224964` |
| SHA-256 | `30880b942fbc44b8d09f4c54ba25321e60df7f5c0dce235d50b8e74f6f9e6f3e` |
| Signer certificate SHA-256 | `50e670489a4ba19aec5e9fbad6f06074556d4d07be629ba012b3ca78f1eabb4e` |
| Build tools | Swift 6.4.0 and matching Android SDK, Android platform 37, NDK 30.0.16248370, Gradle 9.8, JDK 17, Ubuntu under WSL |
| Signing | Same private local debug key as `.10`; key is not included |

## Install or update

Enable Android Developer options and USB debugging, connect the Pixel to a computer with platform-tools, and authorize the computer. From this repository's root:

```powershell
Get-FileHash .\android\jetlink-0.8.12-clarity-tensor.11-pixel.apk -Algorithm SHA256
adb devices
adb -s YOUR_DEVICE_SERIAL install -r .\android\jetlink-0.8.12-clarity-tensor.11-pixel.apk
adb -s YOUR_DEVICE_SERIAL shell am start -n io.zoompilot.jetlink.android/io.zoompilot.jetlink.MainActivity
```

Compare the APK hash above before installation. An in-place update preserves settings, imported models and prepared engines. A different signing key cannot update this installation; do not uninstall to bypass that restriction because it removes app data.

The qualified processor is **Tensor TPU (precompiled)**. It requires the matched Tensor G6 V2 model and [manifest](tensor/qualified-model.json), uses explicit FP16, and refuses silent GPU fallback. **Tensor NPU (on-device)** is a separate upstream path. The private SDK and model weights are not bundled in this APK. [Model setup and import](tensor/README.md).

## Model choices and USB

Upstream v0.8.12 shares the newest explicit model choice between the phone and comma. Tapping **Use Model** on the phone records a choice that may replace an older comma choice at the next connection. A newer comma choice can likewise take precedence. Updating the app or running a desk engine check does not itself create a phone-side choice. Check the applied model identity before any physical test; do not change a selection merely to complete the app update.

Use a direct USB-C data cable between Pixel and comma, with one accelerator connected at a time. Open JetLink and check the handshake, selected-model hash and frame timing while parked. Android may request USB permission. The app uses ordinary protocol v3, with no parked-test switch or special handshake. Its Developer listener is unnecessary for direct USB.

**Keep CPU Awake** supplies advisory Android performance hints; Android retains control of clocks and thermals. The app's health checks and the comma's deadlines and fallback behavior remain required. The older [USB recovery and stability report](../docs/PIXEL_USB_STABILITY_LITERT23_2026-10-10.md) describes the tested comma integration; an APK update does not verify another comma installation or qualify driving.

## Validation and rebuilding

The release build passed 59 Android unit tests and 226 native regressions. On the installed phone, all 160 full-output frames matched the previous app exactly; the first 32 reference frames passed all 15 output slices. The first timing run failed its 100 ms guard after 490 measured frames. A repeat completed 1,200 frames: average phone processing 32.137 ms, p95 33.638 ms and maximum 37.261 ms, with no phone frames over 50 ms. PC round-trip timing still failed. The [November 1 update report](../docs/PIXEL_UPDATE_2026-11-01.md) and [sanitized evidence](tensor/update-2026-11-01.json) retain both attempts. Desk ADB/TCP evidence is separate from a direct comma USB test.

The phone was left at **Waiting for Comma · Cinque Terre Model V2**. The temporary Developer listener is disabled after restart, ADB forwarding is removed, and a fresh V3 engine request was rejected. No comma configuration or connection window was changed.

```sh
git clone https://github.com/zoompilot/jetlink.git
cd jetlink
git checkout a863c3801da6fd925d14eb1f5b1e250f8efcc649
git apply /path/to/Clarity-Pilot/android/tensor/tensor-support.patch
cd android
./gradlew :app:assembleRelease :app:testDebugUnitTest
```

Use Linux/WSL and retain the original signing key privately. The patch targets this exact upstream base. A rebuild is not guaranteed to produce identical APK bytes or a matching signature. The packaged LiteRT core, GPU and Tensor runtime libraries are unchanged from `.10` and are pinned to matched 2.3.0 artifacts.

JetLink's [MIT license](LICENSE-JetLink) is included. The APK also bundles LiteRT, ONNX Runtime and QNN; see [upstream license notes](https://github.com/zoompilot/jetlink/blob/a863c3801da6fd925d14eb1f5b1e250f8efcc649/android/README.md#licenses).

## Earlier evidence and rollback

The [`.10` APK and exact-source instructions](README-0.8.7-clarity-tensor.10.md) remain available for rollback. Android may refuse a downgrade from code 81211 to 80710; a data-preserving rollback may need the archived source rebuilt with a higher version code and the same signing key. Do not uninstall automatically.

The [October 17 compiler investigation](../docs/TENSOR_COMPILER_RUNTIME_2026-10-17.md) measured a 7.4–8.4% gain from SDK v2.1 on the unchanged `.10` app. That result is not a speed claim for `.11`. Earlier screen-wake stalls and USB resets remain unresolved. The [October 10 drive record](../docs/PIXEL_DRIVE_SCREEN_OFF_2026-10-10.md), [`.9` archive](README-0.8.5-clarity-tensor.9.md) and [older results](tensor/history-2026-10-03.md) retain their original scope.
