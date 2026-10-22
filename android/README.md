# JetLink Android APK

**October 21 model status:** the installed APK remains current. The comma selects V3, but the Pixel V3 compilation still fails extended accuracy validation. The Pixel was restored to V2; V3 candidates are quarantined. [Results and handoff](../docs/PIXEL_V3_MODEL_2026-10-21.md).

[Download jetlink-0.8.7-clarity-tensor.10-pixel.apk](https://github.com/ryanafdahl/Clarity-Pilot/raw/refs/heads/main/android/jetlink-0.8.7-clarity-tensor.10-pixel.apk)

Installed and verified on the Pixel 11 Pro XL on October 17, 2026. This updates upstream to v0.8.7 while preserving Tensor support, LiteRT 2.3.0, the model, CPU hints, USB recovery and thermal protections. Upstream changes improve model catalog and LFS lookup; **the APK maintenance update alone did not establish a speedup**. The subsequent SDK v2.1 model compile reduced average phone processing by **7.4–8.4%** in two separate balanced desk app comparisons, using this same APK. A 6,000-frame screen-off run averaged 34.19 ms, with one frame at 50.10 ms. [Compiler/runtime results](../docs/TENSOR_COMPILER_RUNTIME_2026-10-17.md) · [APK maintenance validation](../docs/PIXEL_UPDATE_2026-10-17.md).

| Field | Value |
| --- | --- |
| Version / code | `0.8.7-clarity-tensor.10` / `80710` |
| Package | `io.zoompilot.jetlink.android` |
| Source base | [zoompilot/jetlink `d26001b4161f33bab28d806de6a99b96325a429b`](https://github.com/zoompilot/jetlink/tree/d26001b4161f33bab28d806de6a99b96325a429b) |
| Local changes | [Reproducible Tensor support patch](tensor/tensor-support.patch) |
| Architecture / protocol | ARM64 / v3 |
| APK bytes | `104213812` |
| SHA-256 | `cf760fe7c69c8d56e2eb0dc2bd45bf2cc9c8780548e8dbbe909834ead66872bd` |
| Signer certificate SHA-256 | `50e670489a4ba19aec5e9fbad6f06074556d4d07be629ba012b3ca78f1eabb4e` |
| Build tools | Swift 6.4.0 and matching Android SDK, Android platform 37, NDK 30.0.16248370, Gradle 9.8, JDK 17, Ubuntu under WSL |
| Signing | Same private local debug key as the previous installed APK; key is not included |

## Install on the Pixel

Enable Android Developer options and USB debugging, connect to a computer with platform-tools, and authorize the computer. From this repository's root:

```powershell
Get-FileHash .\android\jetlink-0.8.7-clarity-tensor.10-pixel.apk -Algorithm SHA256
adb devices
adb install -r .\android\jetlink-0.8.7-clarity-tensor.10-pixel.apk
adb shell am start -n io.zoompilot.jetlink.android/io.zoompilot.jetlink.MainActivity
```

Compare the hash above before installing. With multiple devices, add `-s YOUR_DEVICE_SERIAL` after `adb`. Allow JetLink notifications. The in-place update preserves settings, imported models and prepared engines. A different signing key cannot update this installation; do not uninstall automatically to get around that check.

Select **Settings → Processor → Tensor TPU (precompiled)** and **Cinque Terre Model V2**. The installed Pixel retained both selections. This option uses the imported, explicit-FP16 Tensor G6 model. **Tensor NPU (on-device)** is a separate upstream compiler path; its presence does not prove a particular model compiled for the NPU. The precompiled path requires full NPU execution and refuses silent GPU fallback. Models and the private Tensor SDK are not bundled in the APK. [Model identity, compilation and import](tensor/README.md).

## Connect to the comma

The tested wiring is a **direct USB-C data cable between the Pixel and comma**. For the next comparison, leave the separately connected Android Auto adapter unplugged and keep the Pixel off the wireless charger. Cool the phone with air conditioning while remaining parked. Accept Android's USB permission prompt. Attach one accelerator at a time. Select **Settings → Models → Jetlink: USB** and **Cinque Terre Model V2** as Big Model on the comma. Open JetLink on the Pixel. There is no parked-test toggle or special test handshake.

On the Pixel, **Keep CPU Awake** now enables advisory Android performance hints for Tensor inference. It is enabled on this device; Android still controls clocks and thermals. Select **Tensor TPU (precompiled)**. LiteRT 2.3 requires the matched recompiled model and [manifest](tensor/qualified-model.json); installing the APK alone over a 2.2 import is insufficient. Follow [compilation and import](tensor/README.md).

The comma needs the [previous recovery patch](../patches/jetlink-usb-recovery/recovery.patch) followed by the [stability patch](../patches/jetlink-usb-stability/recovery.patch). [Install, verify and roll back](../docs/PIXEL_USB_STABILITY_LITERT23_2026-10-10.md#reapply-and-roll-back-the-comma-patch). Frame deadlines, proving, fallback, thermal protections and the steering-active model-swap rule remain intact. The [updated direct-USB drive](../docs/PIXEL_DRIVE_SCREEN_OFF_2026-10-10.md) recorded approximately **8.67 assisted miles on the Pixel large-model path**, but three early resets remained. Its final 11 min 45.7 s had no fallback. Screen-off is not a proven fix; the next controlled investigation should stay parked. USB reliability and rare stalls remain unresolved.

## Validation and rebuilding

The `.10` release build passed **59 Android tests**, **53 native tests**, and a fresh **32-frame recurrent reference comparison across all 15 output slices**. A 1,200-frame run had no protocol failures or phone frames over 50 ms: average **34.403 ms**, p95 **36.263 ms**, maximum **38.885 ms**. ADB round-trip p95 was **57.510 ms** and failed the transport timing check. This desk check does not exercise direct comma USB or qualify driving. [Full comparison](../docs/PIXEL_UPDATE_2026-10-17.md).

The [October 11 investigation](../docs/TPU_PERFORMANCE_2026-10-11.md) and its follow-ups found no reliable production gain from priority, sharding or runtime-mode experiments; those experimental changes are not included. [Profiler](tensor/profiling/README.md).

```sh
git clone https://github.com/zoompilot/jetlink.git
cd jetlink
git checkout d26001b4161f33bab28d806de6a99b96325a429b
git apply /path/to/Clarity-Pilot/android/tensor/tensor-support.patch
cd android
./gradlew :app:assembleRelease :app:testDebugUnitTest
```

Use Linux/WSL for the upstream checkout and keep the original signing key privately. The patch applies cleanly to this exact base. A rebuild is not guaranteed to produce identical APK bytes or a matching signature. The comma repository's separate JetLink submodule remains pinned to v0.8.5; changing its adapter/warp implementation is outside this Android update.

JetLink's [MIT license](LICENSE-JetLink) is included. The APK also bundles LiteRT, ONNX Runtime and QNN; see [upstream license notes](https://github.com/zoompilot/jetlink/blob/d26001b4161f33bab28d806de6a99b96325a429b/android/README.md#licenses). The core, GPU and Google Tensor runtimes come from matched, hash-checked LiteRT 2.3.0 Maven AARs; the private compiler and compiled V2 model remain local.

The [previous `.9` APK and instructions](README-0.8.5-clarity-tensor.9.md), [`.8` APK and instructions](README-0.8.5-clarity-tensor.8.md), [`.6` APK and instructions](README-0.8.5-clarity-tensor.6.md), [`.5` APK and instructions](README-0.8.5-clarity-tensor.5.md), [`.4` archive](README-0.8.0-clarity-tensor.4.md), earlier APKs and [October 3 results](tensor/history-2026-10-03.md) remain archived. Android may refuse a downgrade from version code 80710; do not uninstall automatically because that removes app data.
