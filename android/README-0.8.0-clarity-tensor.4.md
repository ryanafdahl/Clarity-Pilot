> Archived October 3 release. See [the current installed APK](README.md).

# JetLink Android APK

[Download jetlink-0.8.0-clarity-tensor.4-pixel.apk](https://github.com/ryanafdahl/Clarity-Pilot/raw/refs/heads/main/android/jetlink-0.8.0-clarity-tensor.4-pixel.apk)

This is the exact APK built and installed on the Pixel 11 Pro XL on October 3, 2026. It is the upstream JetLink app with the [Clarity Tensor support patch](tensor/history-2026-10-03.md). It uses protocol v3 and matches this repository's JetLink client and the upgraded Jetson server.

| Field | Value |
| --- | --- |
| Version / code | `0.8.0-clarity-tensor.4` / `804` |
| Package | `io.zoompilot.jetlink.android` |
| Source | [zoompilot/jetlink at 9f3d318](https://github.com/zoompilot/jetlink/tree/9f3d3187758b810adc99b06cc0a1a19ab73b7acb) |
| Architecture | ARM64 |
| APK bytes | `103525680` |
| SHA-256 | `aef63a15da83f168b79bca04196c447214e07b6e96fa8357f8d287357d7e472b` |
| Build tools | Swift 6.4.0 + matching Android SDK, Android platform 37, NDK 30.0.16248370, JDK 17, Ubuntu under WSL |
| Signing | Local debug key, as configured by upstream's release build; private key is not included |

## Install on the Pixel

Enable Developer options and USB debugging, connect to a computer with Android platform-tools, and authorize its debugging prompt. From the repository root:

```powershell
Get-FileHash .\android\jetlink-0.8.0-clarity-tensor.4-pixel.apk -Algorithm SHA256
adb devices
adb install -r .\android\jetlink-0.8.0-clarity-tensor.4-pixel.apk
adb shell am start -n io.zoompilot.jetlink.android/io.zoompilot.jetlink.MainActivity
```

Compare the hash above before installing. If several phones are connected, add `-s YOUR_DEVICE_SERIAL` after `adb`. Alternatively, download the APK onto the phone and allow the file manager to install it. Allow JetLink notifications so its foreground service can remain active.

An update must use the same signing key. A signature mismatch means it came from a different builder; do not uninstall automatically, because that removes app data and prepared models. Keep the original signing key privately for future builds.

The Pixel now offers **Settings → Processor → Tensor TPU (parked test)**. Explicit FP16 V2 passes the unchanged numerical checks, and the optimized TPU implementation completed 12,000 desk frames with server-total p95 36.72 ms. **Tensor remains restricted to synthetic parked tests:** its USB switch starts off and normal driving clients are blocked. Models are not bundled in the APK. [Full results, import steps, and supervised parked-test instructions](tensor/history-2026-10-03.md).

For the parked test, use a powered USB 3 hub with USB-C power pass-through and a USB-A-to-C data cable from the hub to the comma. Accept Android's USB permission prompt. Attach one accelerator at a time. For A/C with ignition on, follow the [stationary ignition-on sequence](tensor/history-2026-10-03.md#stationary-ignition-onac-test): arm the comma script with ignition off, wait for its USB-isolation instruction, then start the engine while remaining in Park with the parking brake set and controls disengaged. This does not enable Tensor driving. Keep cruise MAIN off for this test. The first ignition-on session reached 100 measured frames but stopped at full-exchange p95 53.43 ms (phone/server p95 39.83 ms); a passing result remains pending. [Physical results](tensor/history-2026-10-03.md#ignition-on-results).

## Validation and rebuilding

The `.4` release build and **54 Android tests** passed. The comma harness passed **50 Python guard/cleanup tests**, and its read-only preflight passed on the pinned deployed comma version. This APK changes the instructions for ignition-on testing; inference code, the compiled model, phone health gates and driving refusal are unchanged from `.3`. See [preparation evidence](tensor/ignition-preparation-2026-10-03.json). The final installed-app desk check completed 120 finite frames with server p95 36.30 ms and thermal status 0 at 34.7°C; ordinary driving requests and unapproved raw inference remained refused. Full ADB exchange p95 was 57.05 ms, so this is phone runtime verification, not a direct-USB timing pass. [Desk-check evidence](tensor/ignition-desk-check-2026-10-03.json).

The previous `.3` build passed 54 Android tests, plus **29 native tests across 10 suites** and **25 Python parked-harness/health/timing tests**. New cases cover absent/stale/malformed health, thermal thresholds, session revocation, and restoring Accelerator Link after a test stop. A five-minute indoor run completed 6,000 finite frames, with phone/server p95 36.85 ms and maximum 43.22 ms; all 60 timing blocks passed. Health monitoring continued with the app in the background. A fresh 32-frame numerical comparison passed all 15 slices. Full ADB round-trip p95 was 57.64 ms, so the desk transport did not pass the USB deadline requirement. [Recorded results](tensor/health-validation-2026-10-03.json).

The archived `.2` build passed short 120- and 1,200-frame USB runs but failed the extended 2,400-frame run (p95 98.86 ms, 36.5% above 50 ms). The `.3` app adds telemetry and automatic stops so a repeat can distinguish heat, charging and sustained inference latency. No numerical thresholds, model weights, or driving restrictions were relaxed. Normal driving remains blocked. See the [evidence, remaining gates and test instructions](tensor/history-2026-10-03.md).

After installing the documented toolchains on Linux or macOS:

```sh
git clone https://github.com/zoompilot/jetlink.git
cd jetlink
git checkout 9f3d3187758b810adc99b06cc0a1a19ab73b7acb
git apply /path/to/Clarity-Pilot/android/tensor/tensor-support-0.8.0-clarity-tensor.4.patch
cd android
./gradlew :app:assembleRelease :app:testDebugUnitTest
```

A rebuild is not guaranteed to have this APK's exact bytes or signature. JetLink's [MIT license](LICENSE-JetLink) is included. The APK also bundles LiteRT (Apache 2.0), ONNX Runtime (MIT), and Qualcomm QNN libraries under the Qualcomm AI Stack License; see upstream's [license notes](https://github.com/zoompilot/jetlink/blob/9f3d3187758b810adc99b06cc0a1a19ab73b7acb/android/README.md#licenses). QNN libraries are distributed inside the app, not separately.

The prior [health-telemetry `.3` APK](jetlink-0.8.0-clarity-tensor.3-pixel.apk) (code 803), [tested `.2` APK](jetlink-0.8.0-clarity-tensor.2-pixel.apk) (code 802), [initial Tensor APK](jetlink-0.8.0-clarity-tensor.1-pixel.apk) (code 801) and [upstream APK](jetlink-0.8.0-pixel.apk) (code 800) remain as archives. Downgrades from code 804 may require explicit Android downgrade support; do not uninstall automatically. The private SDK compiler and compiled model are not redistributed.
