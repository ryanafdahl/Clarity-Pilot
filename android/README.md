# JetLink Android APK

[Download jetlink-0.8.5-clarity-tensor.6-pixel.apk](https://github.com/ryanafdahl/Clarity-Pilot/raw/refs/heads/main/android/jetlink-0.8.5-clarity-tensor.6-pixel.apk)

This is the exact APK installed on the Pixel 11 Pro XL on October 10, 2026. It combines pinned upstream source with this project's precompiled Google Tensor support and USB receive/recovery fixes. **Normal Tensor USB connections are enabled: the parked-only handshake and temporary Parked USB Test switch have been removed.** Phone thermal protections remain active. [Update and measured results](../docs/PIXEL_USB_RECOVERY_2026-10-10.md).

| Field | Value |
| --- | --- |
| Version / code | `0.8.5-clarity-tensor.6` / `80506` |
| Package | `io.zoompilot.jetlink.android` |
| Source base | [zoompilot/jetlink `b079496816e617ffd891ea12e5bee5d116db1383`](https://github.com/zoompilot/jetlink/tree/b079496816e617ffd891ea12e5bee5d116db1383) |
| Local changes | [Reproducible Tensor support patch](tensor/tensor-support.patch) |
| Architecture / protocol | ARM64 / v3 |
| APK bytes | `103915440` |
| SHA-256 | `e17bdb13f6f9748825837b3ce376194887a15145ca7c238f69fecf48d15e491a` |
| Signer certificate SHA-256 | `50e670489a4ba19aec5e9fbad6f06074556d4d07be629ba012b3ca78f1eabb4e` |
| Build tools | Swift 6.4.0 and matching Android SDK, Android platform 37, NDK 30.0.16248370, Gradle 9.8, JDK 17, Ubuntu under WSL |
| Signing | Same private local debug key as the previous installed APK; key is not included |

## Install on the Pixel

Enable Android Developer options and USB debugging, connect to a computer with platform-tools, and authorize the computer. From this repository's root:

```powershell
Get-FileHash .\android\jetlink-0.8.5-clarity-tensor.6-pixel.apk -Algorithm SHA256
adb devices
adb install -r .\android\jetlink-0.8.5-clarity-tensor.6-pixel.apk
adb shell am start -n io.zoompilot.jetlink.android/io.zoompilot.jetlink.MainActivity
```

Compare the hash above before installing. With multiple devices, add `-s YOUR_DEVICE_SERIAL` after `adb`. Allow JetLink notifications. The in-place update preserves settings, imported models and prepared engines. A different signing key cannot update this installation; do not uninstall automatically to get around that check.

Select **Settings → Processor → Tensor TPU (precompiled)** and **Cinque Terre Model V2**. The installed Pixel retained both selections. This option uses the imported, explicit-FP16 Tensor G6 model. **Tensor NPU (on-device)** is a separate upstream compiler path; its presence does not prove a particular model compiled for the NPU. The precompiled path requires full NPU execution and refuses silent GPU fallback. Models and the private Tensor SDK are not bundled in the APK. [Model identity, compilation and import](tensor/README.md).

## Connect to the comma

Use a powered USB 3 hub with USB-C power pass-through for the phone and a USB-A-to-C data cable from the hub to the comma. Accept Android's USB permission prompt. Attach one accelerator at a time. On the comma select **Settings → Models → Jetlink: USB**, and **Cinque Terre Model V2** as Big Model. Open JetLink on the Pixel. There is no parked-test toggle or special test handshake in this version.

The comma's existing model selection, warmup, timing checks and fallback remain in place. Its companion [recovery patch](../patches/jetlink-usb-recovery/recovery.patch) detects failed asynchronous USB transfers before rejoining. [Installation and rollback](../docs/PIXEL_USB_RECOVERY_2026-10-10.md#reapply-and-rollback-on-the-comma). Vehicle-control tuning is unchanged. The normal connection was verified over desk ADB/TCP; direct comma USB, reconnects, in-mount cooling and driving with this APK still need physical verification. The earlier sustained USB timing failures remain in the [history](tensor/history-2026-10-03.md).

## Validation and rebuilding

The release build, **59 Android tests**, **41 native USB/protocol/thermal tests across 7 suites**, and **217 comma transport/joining/client tests plus 9 subtests** passed. The new regressions reproduce receive-buffer starvation and stale transport recovery on the original code. All 15 output slices passed a fresh 32-frame comparison against the original V2 reference with 64 byte-identical input arrays. A 1,200-frame desk run had no failures and phone processing p95 37.646 ms, but ADB/TCP round-trip p95 was 59.161 ms. See the [current results](../docs/PIXEL_USB_RECOVERY_2026-10-10.md) for the physical USB limits and next adapter-off test.

```sh
git clone https://github.com/zoompilot/jetlink.git
cd jetlink
git checkout b079496816e617ffd891ea12e5bee5d116db1383
git apply /path/to/Clarity-Pilot/android/tensor/tensor-support.patch
cd android
./gradlew :app:assembleRelease :app:testDebugUnitTest
```

Use Linux/WSL for the upstream checkout and keep the original signing key privately. The patch applies cleanly to this exact base. A rebuild is not guaranteed to produce identical APK bytes or a matching signature. The comma repository's separate JetLink submodule remains pinned to v0.8.5; changing its adapter/warp implementation is outside this Android update.

JetLink's [MIT license](LICENSE-JetLink) is included. The APK also bundles LiteRT, ONNX Runtime and QNN; see [upstream license notes](https://github.com/zoompilot/jetlink/blob/b079496816e617ffd891ea12e5bee5d116db1383/android/README.md#licenses). The Google Tensor runtime comes from upstream's hash-checked LiteRT 2.2.0 bundle; the private compiler and compiled V2 model remain local.

The [previous `.5` APK and instructions](README-0.8.5-clarity-tensor.5.md), [`.4` archive](README-0.8.0-clarity-tensor.4.md), earlier APKs and [October 3 results](tensor/history-2026-10-03.md) remain archived. Android may refuse a downgrade from version code 80506; do not uninstall automatically because that removes app data.
