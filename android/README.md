# JetLink Android APK

[Download jetlink-0.8.5-clarity-tensor.9-pixel.apk](https://github.com/ryanafdahl/Clarity-Pilot/raw/refs/heads/main/android/jetlink-0.8.5-clarity-tensor.9-pixel.apk)

This is the exact APK installed on the Pixel 11 Pro XL on October 10, 2026. It combines pinned upstream source with this project's precompiled Google Tensor support and USB recovery, bounded inference requests and Tensor performance hints. It retains the matched LiteRT 2.3.0 runtime and model compiler, and changes host USB receive requests from 16 KiB to 8 KiB while preserving the 512 KiB receive reserve. This is a mitigation awaiting physical USB verification; it does not establish the cause of the remaining bus error. **Normal Tensor USB connections are enabled: the parked-only handshake and temporary Parked USB Test switch have been removed.** Phone thermal protections remain active. [Update and measured results](../docs/PIXEL_USB_STABILITY_LITERT23_2026-10-10.md).

| Field | Value |
| --- | --- |
| Version / code | `0.8.5-clarity-tensor.9` / `80509` |
| Package | `io.zoompilot.jetlink.android` |
| Source base | [zoompilot/jetlink `b079496816e617ffd891ea12e5bee5d116db1383`](https://github.com/zoompilot/jetlink/tree/b079496816e617ffd891ea12e5bee5d116db1383) |
| Local changes | [Reproducible Tensor support patch](tensor/tensor-support.patch) |
| Architecture / protocol | ARM64 / v3 |
| APK bytes | `104209968` |
| SHA-256 | `b3b69287a6bb2a9209a604003937435c2ce1715329881eb66154afbef8a0f07d` |
| Signer certificate SHA-256 | `50e670489a4ba19aec5e9fbad6f06074556d4d07be629ba012b3ca78f1eabb4e` |
| Build tools | Swift 6.4.0 and matching Android SDK, Android platform 37, NDK 30.0.16248370, Gradle 9.8, JDK 17, Ubuntu under WSL |
| Signing | Same private local debug key as the previous installed APK; key is not included |

## Install on the Pixel

Enable Android Developer options and USB debugging, connect to a computer with platform-tools, and authorize the computer. From this repository's root:

```powershell
Get-FileHash .\android\jetlink-0.8.5-clarity-tensor.9-pixel.apk -Algorithm SHA256
adb devices
adb install -r .\android\jetlink-0.8.5-clarity-tensor.9-pixel.apk
adb shell am start -n io.zoompilot.jetlink.android/io.zoompilot.jetlink.MainActivity
```

Compare the hash above before installing. With multiple devices, add `-s YOUR_DEVICE_SERIAL` after `adb`. Allow JetLink notifications. The in-place update preserves settings, imported models and prepared engines. A different signing key cannot update this installation; do not uninstall automatically to get around that check.

Select **Settings → Processor → Tensor TPU (precompiled)** and **Cinque Terre Model V2**. The installed Pixel retained both selections. This option uses the imported, explicit-FP16 Tensor G6 model. **Tensor NPU (on-device)** is a separate upstream compiler path; its presence does not prove a particular model compiled for the NPU. The precompiled path requires full NPU execution and refuses silent GPU fallback. Models and the private Tensor SDK are not bundled in the APK. [Model identity, compilation and import](tensor/README.md).

## Connect to the comma

The tested wiring is a **direct USB-C data cable between the Pixel and comma**. For the next comparison, leave the separately connected Android Auto adapter unplugged and keep the Pixel off the wireless charger. Cool the phone with air conditioning while remaining parked. Accept Android's USB permission prompt. Attach one accelerator at a time. Select **Settings → Models → Jetlink: USB** and **Cinque Terre Model V2** as Big Model on the comma. Open JetLink on the Pixel. There is no parked-test toggle or special test handshake.

On the Pixel, **Keep CPU Awake** now enables advisory Android performance hints for Tensor inference. It is enabled on this device; Android still controls clocks and thermals. Select **Tensor TPU (precompiled)**. LiteRT 2.3 requires the matched recompiled model and [manifest](tensor/qualified-model.json); installing the APK alone over a 2.2 import is insufficient. Follow [compilation and import](tensor/README.md).

The comma needs the [previous recovery patch](../patches/jetlink-usb-recovery/recovery.patch) followed by the [stability patch](../patches/jetlink-usb-stability/recovery.patch). [Install, verify and roll back](../docs/PIXEL_USB_STABILITY_LITERT23_2026-10-10.md#reapply-and-roll-back-the-comma-patch). Frame deadlines, proving, fallback, thermal protections and the steering-active model-swap rule remain intact. The [updated direct-USB drive](../docs/PIXEL_DRIVE_SCREEN_OFF_2026-10-10.md) recorded approximately **8.67 assisted miles on the Pixel large-model path**, but three early resets remained. Its final 11 min 45.7 s had no fallback. Screen-off is not a proven fix; the next controlled investigation should stay parked. USB reliability and rare stalls remain unresolved.

## Validation and rebuilding

The `.9` release build, **59 Android tests** and **53 native tests** passed. Existing native regressions cover framed multi-slot messages, ordered completion, EPROTO failure propagation, cancel/reopen and resident buffer reuse. All 15 output slices passed a fresh 32-frame recurrent reference comparison. A 1,200-frame ADB/TCP run had no failures: phone processing p95 **37.045 ms**, maximum **38.967 ms**; round-trip p95 **56.256 ms**, maximum **124.011 ms**. The round-trip timing check failed. ADB/TCP does not exercise the host USB receive ring and does not qualify driving. [Current mitigation and limitations](../docs/PIXEL_USB_HOST_BUFFER_2026-10-10.md).

```sh
git clone https://github.com/zoompilot/jetlink.git
cd jetlink
git checkout b079496816e617ffd891ea12e5bee5d116db1383
git apply /path/to/Clarity-Pilot/android/tensor/tensor-support.patch
cd android
./gradlew :app:assembleRelease :app:testDebugUnitTest
```

Use Linux/WSL for the upstream checkout and keep the original signing key privately. The patch applies cleanly to this exact base. A rebuild is not guaranteed to produce identical APK bytes or a matching signature. The comma repository's separate JetLink submodule remains pinned to v0.8.5; changing its adapter/warp implementation is outside this Android update.

JetLink's [MIT license](LICENSE-JetLink) is included. The APK also bundles LiteRT, ONNX Runtime and QNN; see [upstream license notes](https://github.com/zoompilot/jetlink/blob/b079496816e617ffd891ea12e5bee5d116db1383/android/README.md#licenses). The core, GPU and Google Tensor runtimes come from matched, hash-checked LiteRT 2.3.0 Maven AARs; the private compiler and compiled V2 model remain local.

The [previous `.8` APK and instructions](README-0.8.5-clarity-tensor.8.md), [`.6` APK and instructions](README-0.8.5-clarity-tensor.6.md), [`.5` APK and instructions](README-0.8.5-clarity-tensor.5.md), [`.4` archive](README-0.8.0-clarity-tensor.4.md), earlier APKs and [October 3 results](tensor/history-2026-10-03.md) remain archived. Android may refuse a downgrade from version code 80509; do not uninstall automatically because that removes app data.
