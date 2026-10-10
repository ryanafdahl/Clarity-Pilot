# JetLink Android APK

[Download jetlink-0.8.5-clarity-tensor.8-pixel.apk](https://github.com/ryanafdahl/Clarity-Pilot/raw/refs/heads/main/android/jetlink-0.8.5-clarity-tensor.8-pixel.apk)

This is the exact APK installed on the Pixel 11 Pro XL on October 10, 2026. It combines pinned upstream source with this project's precompiled Google Tensor support and USB recovery, bounded inference requests and Tensor performance hints. It upgrades the matched runtime and model compiler to LiteRT 2.3.0. **Normal Tensor USB connections are enabled: the parked-only handshake and temporary Parked USB Test switch have been removed.** Phone thermal protections remain active. [Update and measured results](../docs/PIXEL_USB_STABILITY_LITERT23_2026-10-10.md).

| Field | Value |
| --- | --- |
| Version / code | `0.8.5-clarity-tensor.8` / `80508` |
| Package | `io.zoompilot.jetlink.android` |
| Source base | [zoompilot/jetlink `b079496816e617ffd891ea12e5bee5d116db1383`](https://github.com/zoompilot/jetlink/tree/b079496816e617ffd891ea12e5bee5d116db1383) |
| Local changes | [Reproducible Tensor support patch](tensor/tensor-support.patch) |
| Architecture / protocol | ARM64 / v3 |
| APK bytes | `104211360` |
| SHA-256 | `a51d60b8445a5f89664d34658292e0d44cf946bbc5604045ffe3870690220df5` |
| Signer certificate SHA-256 | `50e670489a4ba19aec5e9fbad6f06074556d4d07be629ba012b3ca78f1eabb4e` |
| Build tools | Swift 6.4.0 and matching Android SDK, Android platform 37, NDK 30.0.16248370, Gradle 9.8, JDK 17, Ubuntu under WSL |
| Signing | Same private local debug key as the previous installed APK; key is not included |

## Install on the Pixel

Enable Android Developer options and USB debugging, connect to a computer with platform-tools, and authorize the computer. From this repository's root:

```powershell
Get-FileHash .\android\jetlink-0.8.5-clarity-tensor.8-pixel.apk -Algorithm SHA256
adb devices
adb install -r .\android\jetlink-0.8.5-clarity-tensor.8-pixel.apk
adb shell am start -n io.zoompilot.jetlink.android/io.zoompilot.jetlink.MainActivity
```

Compare the hash above before installing. With multiple devices, add `-s YOUR_DEVICE_SERIAL` after `adb`. Allow JetLink notifications. The in-place update preserves settings, imported models and prepared engines. A different signing key cannot update this installation; do not uninstall automatically to get around that check.

Select **Settings → Processor → Tensor TPU (precompiled)** and **Cinque Terre Model V2**. The installed Pixel retained both selections. This option uses the imported, explicit-FP16 Tensor G6 model. **Tensor NPU (on-device)** is a separate upstream compiler path; its presence does not prove a particular model compiled for the NPU. The precompiled path requires full NPU execution and refuses silent GPU fallback. Models and the private Tensor SDK are not bundled in the APK. [Model identity, compilation and import](tensor/README.md).

## Connect to the comma

The tested wiring is a **direct USB-C data cable between the Pixel and comma**. For the next comparison, leave the separately connected Android Auto adapter unplugged and keep the Pixel off the wireless charger. Cool the phone with air conditioning while remaining parked. Accept Android's USB permission prompt. Attach one accelerator at a time. Select **Settings → Models → Jetlink: USB** and **Cinque Terre Model V2** as Big Model on the comma. Open JetLink on the Pixel. There is no parked-test toggle or special test handshake.

On the Pixel, **Keep CPU Awake** now enables advisory Android performance hints for Tensor inference. It is enabled on this device; Android still controls clocks and thermals. Select **Tensor TPU (precompiled)**. LiteRT 2.3 requires the matched recompiled model and [manifest](tensor/qualified-model.json); installing the APK alone over a 2.2 import is insufficient. Follow [compilation and import](tensor/README.md).

The comma needs the [previous recovery patch](../patches/jetlink-usb-recovery/recovery.patch) followed by the [stability patch](../patches/jetlink-usb-stability/recovery.patch). [Install, verify and roll back](../docs/PIXEL_USB_STABILITY_LITERT23_2026-10-10.md#reapply-and-roll-back-the-comma-patch). Frame deadlines, proving, fallback, thermal protections and the steering-active model-swap rule remain intact. The updated pair still needs a direct-USB parked test; earlier USB resets are not proven fixed.

## Validation and rebuilding

The release build, **59 Android tests**, **53 native tests** and **285 comma tests plus 9 subtests** passed. Native USB tests use simulated transport; device inference was checked separately. All 15 output slices passed a fresh 32-frame recurrent comparison against the original V2 reference with 64 byte-identical inputs. The 6,000-frame desk run completed without protocol or health failures: phone processing p95 **36.580 ms**, maximum **38.989 ms**; ADB/TCP round-trip p95 **55.087 ms**. [Comparison and limitations](../docs/PIXEL_USB_STABILITY_LITERT23_2026-10-10.md). Desk ADB/TCP is not the direct comma USB path and does not qualify driving.

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

The [previous `.6` APK and instructions](README-0.8.5-clarity-tensor.6.md), [`.5` APK and instructions](README-0.8.5-clarity-tensor.5.md), [`.4` archive](README-0.8.0-clarity-tensor.4.md), earlier APKs and [October 3 results](tensor/history-2026-10-03.md) remain archived. Android may refuse a downgrade from version code 80508; do not uninstall automatically because that removes app data.
