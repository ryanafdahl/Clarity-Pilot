# Clarity Pilot

Clarity Pilot is a personal, experimental [sunnypilot](https://github.com/sunnypilot/sunnypilot) build for a **comma 4** paired with either an **NVIDIA Jetson Orin Nano Super Developer Kit (8 GB)** or a **Pixel 11 Pro XL**. It uses [JetLink](https://github.com/zoompilot/jetlink) to run a large driving model on the attached accelerator over USB, while keeping the selected small model available on the comma.

**This is a custom build for my car. Do not use this.**

[Comma setup](#repository-and-comma-installation) · [Jetson setup](#jetson-setup) · [Pixel setup / APK](#pixel-setup) · [Models](#models) · [Validation](#what-has-been-verified) · [Troubleshooting](#troubleshooting) · [Reports](#logs-and-reports)

## How it works

**Storage maintenance:** the comma now keeps a 20 GiB offroad recording budget, with its newest two routes and marked recordings protected; the Jetson has bounded journal storage and hourly system-log rotation. See [retention policies, installation, and rollback](scripts/maintenance/README.md). October 3 cleanup increased comma free space from 8.9 GiB to 56 GiB.

The comma handles cameras, image warp, model-output parsing, vehicle control, driver monitoring, and communication with the car. The Jetson runs TensorRT inference; the Pixel app offers LiteRT GPU inference and experimental Tensor TPU parked testing. Either returns model outputs over the same JetLink protocol. Attach one accelerator at a time. Neither accelerator has a CAN connection.

```text
comma 4                                    Choose one accelerator
cameras → image warp ─── USB 3 ────────────→ Jetson: TensorRT
vehicle control ← model parser ←── USB 3 ─── Pixel: LiteRT GPU
                                           model history → predictions
```

The small model starts first. The updated JetLink adapter warms the large model with shadow frames and checks timing before switching. The resident USB owner keeps the gadget available across ignition transitions. Repeated late responses or a link failure return inference to the selected small model and trigger reconnection; the UI reports the handback. This does not guarantee uninterrupted engagement.

## Verified hardware and software

Comma and Jetson software were updated on October 4, 2026; CD210 and Cinque Terre V2 were preserved. The Pixel APK is unchanged. [Update and validation record](docs/JETLINK_UPDATE_2026-10-04.md). Hardware details retain the earlier live checks:

| Component | Verified configuration |
| --- | --- |
| Driving device | comma 4 |
| Accelerator | NVIDIA Jetson Orin Nano Super Developer Kit, 8 GB |
| Jetson OS | Ubuntu 24.04.4, JetPack 7.2.1 / L4T 39.2.1 |
| JetLink server | 0.8.3, native systemd service, protocol v3 |
| Android accelerator | Pixel 11 Pro XL, Android 17, JetLink 0.8.0-clarity-tensor.4 / version code 804 |
| Pixel inference runtime | LiteRT GPU + Tensor TPU; V2 FP16 parity passed; Tensor restricted to explicit parked tests |
| Inference runtime | TensorRT 10.16.2.10 |
| Power profile | MAXN_SUPER, mode 2 |
| Car power behavior | Switched with the car; suspend timer disabled |
| Data connection | Jetson USB-A host port → comma USB-C, USB 3 data cable |
| Jetson networking | Ethernet; retired USB Wi-Fi driver removed October 3 |
| Model cache | `/mnt/data/jetlink` on the Jetson |

### Which Jetson is it?

A live SSH check returned this device-tree model:

```text
NVIDIA Jetson Orin Nano Engineering Reference Developer Kit Super
```

The identifiers are module `P3767-0005`, carrier `P3768-0000`, and SoC `tegra234`, with the `-super` configuration. NVIDIA identifies that module as the [Jetson Orin Nano 8 GB](https://docs.nvidia.com/jetson/archives/r36.5/DeveloperGuide/IN/QuickStart.html#jetson-modules-and-configurations), and calls the kit the [Jetson Orin Nano Super Developer Kit](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/). **“Orin” is part of the full product name.** This confirms the current platform; it does not establish whether the original retail package predated the Super software update.

Use a separate regulated Jetson supply sized for the selected power profile, with adequate cooling. The Jetson's USB-A port carries the data connection; its USB-C port is not the JetLink host connection to the comma.

## Models

| Role | Selected/default model | Behavior |
| --- | --- | --- |
| Small model on the comma | **The Cool Peoples Model v3 (TCPMV3)**, October 10, 2025 | The source checkout queues it on fresh installs. Existing selections are preserved; the current device deployment retains CD210. |
| Large model on comma + Jetson | **Cinque Terre Model V2**, September 8, 2026, selected on this installation | Choose V2 explicitly in Settings → Models → Big Model; an empty slot can follow a newer upstream default. |

Both source and device deployment now include automatic first-install TCPMV3 selection. Existing selections are preserved; the current device continues to use CD210 Model (February 03, 2026).

In the source checkout, interrupted first-install small-model downloads retry while parked. Explicitly cancelling the download or choosing another small model stops automatic selection. The bundled model remains available during initial provisioning.

On October 3, V2 was downloaded and SHA-256 verified on both the comma and Jetson, and its TensorRT engine was built and loaded. The matching model hash is `09d080f36965bb2a0790500452bd328aa03c484d0222aa79d1ad9f021a522aec`. The Pixel now runs V2 on its Tensor TPU with explicit FP16 compilation. Its numerical checks and 12,000-frame inference soak passed. Supervised direct-USB parked checks then completed 120 and 1,200 frames without protocol errors; the minute run had round-trip p95 42.80 ms and max 97.39 ms, with seven frames above 50 ms. The repeated USB reconnect issue was fixed in the comma daemon. A later 2,400-frame parked run **failed sustained timing**: round-trip p95 98.86 ms, max 109.68 ms, and 36.5% of frames above 50 ms. Phone inference slowed substantially; temperature data is still needed to identify the cause. [Results and limits](android/tensor/README.md#direct-comma-usb-results). Normal driving clients remain blocked in Tensor mode.

The September 26 drive used the previously selected **Cinque Terre Model, September 4, 2026**, not V2. Its model selection was preserved during the Jetson update. Most models in this repository's JetLink catalog are about 766 MB before engine preparation; allow several GB for downloads, engines, containers, and updates.

The comma client is pinned to JetLink commit `fd42477e13d0eb093594be8e7074e9ca2d544dff`, immediately after **v0.8.3**, matching Zoompilot integration `b56bbccc415061cd599d5f1ea8b97083dff59f6b`. It uses **protocol v3** with the **v0.8.3 Jetson server**. Older protocol-v2 servers cannot connect. The separately patched Pixel APK remains experimental and was not upgraded in this update.

Protocol v3 keeps recurrent features on the accelerator and transfers scalar inputs alongside warped images. Full raw predictions remain supported when `SEND_RAW_PRED` is enabled. The comma now uses `jetlink.openpilot` through `openpilot/sunnypilot/jetlink_adapter`; the former private accelerator package and boot-time USB setup entry point were removed. Settings → Models now offers **Jetlink: USB** and a **Big Model** selector. ADB stays disabled while JetLink owns the port.

The October 3 update passed 195 isolated source-integration tests, 164 tests against the installed comma integration, and 107 upstream protocol/USB tests. The Jetson 0.8.0 service loaded its existing engine using TensorRT 10.16.2.10; its cache and switched-power setting were preserved. A staged client on the comma completed a v3 handshake and 21 synthetic inference frames over the desk network, including a full raw-output response. These checks do not replace a parked USB connection test, Android model benchmark/parity checks, or driving validation. The September drive results below describe the older software.

To update an existing Jetson installation while preserving its settings:

```sh
jetlink update --ref v0.8.3
```

Jetson releases from v0.8.0 onward use a native service instead of Docker. For the installed Pixel app, use this repository's [APK and pinned build provenance](android/README.md); it carries custom Google Tensor TPU support and its own parked-only validation restrictions.

## Repository and comma installation

The source of record is **[ryanafdahl/Clarity-Pilot](https://github.com/ryanafdahl/Clarity-Pilot), branch `main`**. For a development checkout:

```sh
git clone --recurse-submodules --branch main https://github.com/ryanafdahl/Clarity-Pilot.git
cd Clarity-Pilot
```

Continue with the [development environment guide](tools/README.md), using this checkout in place of its upstream clone example. Cloning on a development computer does not install the software on the comma.

For this deployment, the Custom Software installation address is **`installer.comma.ai/ryanafdahl/Clarity-Pilot`**. It installs the separately published device branch, not this source repository directly. On a fresh comma, follow its Custom Software setup and enter that address. For an already configured device, preserve settings and logs before using the device’s supported reinstall procedure.

The installation address, `installer.comma.ai/ryanafdahl/Clarity-Pilot`, selects the **`Clarity-Pilot` branch of `ryanafdahl/openpilot`**. The [comma fork installer](https://github.com/commaai/openpilot/wiki/Forks#url-installers) uses an owner and branch and assumes the repository is named `openpilot`. The comma runs that separate deployment repository. Use `Clarity-Pilot` for the current deployment. A dedicated Custom Software installer for this repository's `main` has not been verified, and pushing here does not update the comma automatically.

Before changing a device installation, preserve its settings and needed logs and confirm its repository, branch, and commit. Once the intended build is installed, complete normal vehicle setup and calibration, leave it online while parked for model downloads, and confirm the small model works before pairing the accelerator.

## Jetson setup

The current installed release is **[JetLink v0.8.3](https://github.com/zoompilot/jetlink/releases/tag/v0.8.3)**. Its [Jetson guide](https://github.com/zoompilot/jetlink/blob/v0.8.3/docs/jetson.md) lists JetPack 7.2.1 as tested and 6.2 as untested for this release. This project's device already runs 7.2.1; the previous README's JetPack 6.1 / TensorRT 10.3 / fixed 25 W instructions describe an older setup.

With the Jetson on a stable supply and connected to the internet, run the release-pinned installer on the Jetson:

```sh
curl -fsSL https://raw.githubusercontent.com/zoompilot/jetlink/v0.8.3/install.sh -o install-v0.8.3.sh && \
  bash install-v0.8.3.sh --ref v0.8.3
```

For this car, retain **MAXN SUPER** and choose **switched power**. Keep the existing model cache when updating. Follow any reboot instruction from the installer, then check:

```sh
jetlink status
sudo nvpmodel -q
sudo systemctl status jetlink-server.service --no-pager
```

With the car powered off, connect **Jetson USB-A → comma USB-C** with a USB 3 data cable. On the comma, open **Settings → Models**, set **Jetlink** to **USB**, and select **Cinque Terre Model V2** under **Big Model**. Keep both devices powered and the comma online until model preparation finishes. Verify a live handshake and the selected V2 engine before an ignition-on parked test.

A TensorRT or model change can require a new engine even when the ONNX download is already cached. The October 3 V2 engine build took 32.7 seconds; build time varies. For manual preparation, follow the [model preparation guide](https://github.com/zoompilot/jetlink/blob/v0.8.3/docs/models.md): stop the server before preparing an engine in a separate process, then start it again.

`jetlink update` retains the saved release ref. Choose explicit `--ref v0.8.3` to update an older pinned installation. Preserve settings and engine cache for rollback. The [October 4 update record](docs/JETLINK_UPDATE_2026-10-04.md) contains the current pins, backups, compatibility checks and remaining USB validation. General Ubuntu/NVIDIA platform package upgrades were outside this JetLink update.

## Pixel setup

The installed `.4` APK retains the phone thermal/charging telemetry and automatic validation stops introduced in `.3`. Its desk inference and numerical checks passed, but sustained direct-USB timing remains unresolved. The new comma adapter requires a fresh review of the Pixel test harness before another test can be armed. [Prior results and remaining gates](android/tensor/README.md#driving-test-preparation).

The [Android directory](android/README.md) contains the **exact APK installed on the Pixel**, its SHA-256, build provenance, and full install steps. [Download the Tensor-capable APK](https://github.com/ryanafdahl/Clarity-Pilot/raw/refs/heads/main/android/jetlink-0.8.0-clarity-tensor.4-pixel.apk).

Install with `adb install -r android/jetlink-0.8.0-clarity-tensor.4-pixel.apk`, open JetLink, and allow notifications. The installed processor is **Tensor TPU (parked test)**. The historical stationary ignition-on/A/C harness is now blocked on this updated comma pending review; its original manifest is unchanged. [Ignition-on sequence and stop conditions](android/tensor/README.md#stationary-ignition-onac-test). The first ignition-on run stopped after 100 measured frames at USB exchange p95 53.43 ms; phone/server p95 was 39.83 ms. [Results and remaining work](android/tensor/README.md#ignition-on-results). Explicit FP16 compilation now passes every output slice on both 32-frame and 128-frame recurrent numerical checks; all 2,424 operators run on the TPU.

Byte image history and TPU burst mode reduced short-run mean inference from **49.55 ms to 32.97 ms**. A **12,000-frame / 10-minute** desk soak returned only finite outputs: inference p95 **35.47 ms**, server-total p95 **36.72 ms**, and no server frame exceeded 50 ms. Battery temperature peaked at **34.6°C**, with Android thermal status 0 throughout.

**Pixel testing paused pending compatibility review; driving remains blocked.** The APK still offers a temporary **Parked USB Test** switch and rejects ordinary modeld engine requests. The comma adapter also rejects parked-only peers. The staged legacy harness refuses the new adapter before changing settings. See [historical results and test procedure](android/tensor/README.md). The updated Jetson backend is the next connection-test target.

## October 3 sunnypilot sync

All eight upstream master updates through [`a5f44653d`](https://github.com/sunnypilot/sunnypilot/commit/a5f44653d7f43ad57fef2f546f3916ec4cbf3c56) are integrated: model-loader/tinygrad compatibility and tests, cache clearing on mici, workflow cleanup and fork model builds, camera-offset geometry, modelDataV2SP validity, the LagdToggleDelay UI freeze fix, and model-list refresh feedback. JetLink controls and fallback remain intact.

The source repository imports upstream changes as commits because its initial snapshot has separate history. The comma deployment branch merges upstream history. The staged source suite ran 421 tests (416 passed, five skipped); the staged deployment suite ran 379 (374 passed, five skipped). Both successfully loaded the comma's selected CD210 cached small model with the new tinygrad pin. Hidden-window GUI tests and the overlay's Git-dependent default-model hash test were excluded from these counts. The subsequent [October 3 drive](docs/JETLINK_DRIVE_2026-10-03.md) exercised this deployment over USB; longer-drive and failure-recovery validation remain open.

## What has been verified

The [October 4 update](docs/JETLINK_UPDATE_2026-10-04.md) built successfully on the comma and passed 378 integration tests (6 skipped), 851 upstream protocol/USB tests (1 skipped), and 8 transition traces. A protocol-v3 desk-network check returned 21 finite V2 frames, including full raw output. **This was a compatibility check, not a USB timing pass.** The direct cable connection and ignition-on parked check remain pending. The drive reports below describe earlier builds.

The [October 3 full-rate analysis](docs/JETLINK_DRIVE_2026-10-03.md) covers a **331.80-second** recording on the updated Clarity Pilot deployment. The Jetson joined at **+28.21 s**, followed by **6,071 consecutive large-model outputs** with no recorded fallback or large-model frame-ID gap. Comma-reported model execution averaged **25.77 ms**, with **27.24 ms p95**. Its maximum, **52.36 ms**, was the join frame. These are model-run timings, not pure GPU or complete vehicle-control latency.

The first small-model output took **1.28 s** and was invalid; startup skipped 26 camera frame IDs. Both startup outliers preceded engagement. No lag or communication event was recorded. The comma retained 290 Jetson telemetry samples, but the drive's independent server journal could not be recovered after the Jetson was moved to the desk. Its desk boot loaded V2 at 11.26 s; that is not a measurement of the drive's boot time. See the report for the timeline, other warnings, and limits.

The same report records removal of the retired USB Wi-Fi dongle's `rtl8821au` DKMS driver. Ethernet and JetLink stayed active; a rollback archive was retained on the Jetson. The Pixel still requires its own inference and USB qualification.

The following results describe older builds:

The [September 26 short drive](docs/JETLINK_DRIVE_2026-09-26.md) recorded 3 minutes 50 seconds, including about 3 minutes on the large model. Sampled large-model execution averaged **31.70 ms**, with **33.79 ms p95**. The largest sample, **204.81 ms**, occurred at the initial large-model join. These are sampled inference timings, not complete camera-to-control latency or a guarantee that every frame met its deadline.

A later desk boot exposed a CDI/nvpmodel startup-order problem. The applied fix passed **one software reboot**, with the engine ready **20.61 seconds after boot**. The drive preceded that fix. A new car power-cycle test and complete full-rate logs for the short drive remain pending; the final USB disconnect occurred about two seconds before modeld stopped, and its precise cause is unconfirmed.

The drive used comma commit `d57c4b533558bb2314f542a2ea78c3271b265eda` from the separate deployment repository. These results describe that device configuration, not a road validation of every change on this repository's `main`.

For the next parked check, confirm the server and engine are ready, the comma shows a green accelerator indicator, and telemetry is live. `modelV2.big=true` in full-rate logs or `drivingModelData.big=true` in qlogs confirms large-model output. Keep logs from both devices when investigating a join, fallback, or disconnect; the icon alone cannot establish continuous operation.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| JetLink is inactive after boot | Inspect `jetlink status` and `jetlink-server.service` first. The CDI/nvpmodel notes below describe the older Docker installation; current 0.8.3 runs natively. |
| Accelerator never becomes ready | Check the USB-A-to-USB-C data cable, Jetlink USB setting, server status, selected model, and engine-preparation log. |
| Delay or lag at startup | Separate small-model initialization, Jetson boot, engine loading, and the first USB inference exchange. Startup outliers do not establish steady-state GPU slowdown. |
| USB link drops | Compare both devices' logs with the timing of power changes; inspect the cable, USB negotiation, supply, and cooling. Preserve fallback protections. |
| Model preparation fails | Check runtime compatibility and available cache space. Avoid concurrent engine builds against the same cache. |
| Repeated catalog DNS warnings | Check offroad internet access. The catalog manager retries both sources every second when its cache is expired; cached models may remain usable. Retry backoff has not yet been added. |

The tracked [CDI dependency drop-in](scripts/jetson/nvidia-cdi-refresh.service.d/20-after-nvpmodel.conf) makes CDI wait for successful power initialization. It was applied to this Jetson, whose nvpmodel unit has `RemainAfterExit=yes`. **Do not copy it blindly onto a stock unit with `RemainAfterExit=no`.** The [boot-order investigation](docs/JETLINK_DRIVE_2026-09-26.md#jetson-boot-failure-and-applied-fix) explains the prerequisite, validation, and rollback.

For a bounded startup capture on the Jetson:

```sh
sudo journalctl -b -u nvpmodel.service -u nvidia-cdi-refresh.service -u jetlink-server.service -n 150 --no-pager
```

## Logs and reports

| Report | Covers |
| --- | --- |
| [October 4 JetLink v0.8.3 update](docs/JETLINK_UPDATE_2026-10-04.md) | Device pins, resident USB owner, preserved V2 selection, tests and pending parked validation |
| [October 3 V2 drive and Wi-Fi retirement](docs/JETLINK_DRIVE_2026-10-03.md) | Full-rate frame timings, startup retry, telemetry, journal limits, and external USB Wi-Fi driver removal |
| [Comma drive analysis](docs/COMMA_LOG_ANALYSIS_2026-09-26.md) | Two earlier drives, first-frame delays, and the isolated selfdrive-loop lag investigation |
| [Jetson v0.4.0 update](docs/JETSON_UPDATE_2026-09-26.md) | Release pin, runtime, power configuration, backups, and engine rebuild |
| [Post-update drive and boot repair](docs/JETLINK_DRIVE_2026-09-26.md) | Short-drive results, DNS retries, startup fix, and remaining validation |
| [Earlier device review](docs/DEVICE_LOG_ANALYSIS_2026-09.md) | Historical platform observations and storage concerns; predates the update |

From a development checkout, summarize a saved JetLink server log with:

```sh
python tools/analyze_jetlink_log.py jetlink-server.log
```

For qlogs, use the openpilot Python environment with its dependencies available:

```sh
python tools/analyze_comma_routes.py '/path/to/extracted/*/qlog.zst'
```

The server analyzer summarizes logged slow-frame warnings, not every inference. The route analyzer reports sampled model metrics, mode transitions, and event-message counts. Raw routes and device logs can contain location, video, CAN, and identifiers; keep them in ignored `diagnostics/` rather than committing them.

## Vehicle scope and credits

Vehicle support, including Honda Clarity and modified-EPS behavior, depends on the exact fingerprint and firmware. This repository does not perform an EPS torque modification or establish that a modified EPS is supported. See the project's [safety documentation](docs/SAFETY.md) and [limitations](docs/LIMITATIONS.md).

Built on [sunnypilot](https://github.com/sunnypilot/sunnypilot), [comma.ai openpilot](https://github.com/commaai/openpilot), and [Zoompilot JetLink](https://github.com/zoompilot/jetlink), including the accelerator integration from sunnypilot [PR #2001](https://github.com/sunnypilot/sunnypilot/pull/2001). See [LICENSE](LICENSE) and [LICENSE.md](LICENSE.md) for the applicable notices.
