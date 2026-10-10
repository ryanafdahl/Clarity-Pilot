# Pixel USB stability and LiteRT 2.3 — October 10, 2026

**Subsequent road evidence:** the [later October 10 Pixel drive review](PIXEL_DRIVE_SCREEN_OFF_2026-10-10.md) records approximately 8.67 assisted miles on the large-model path, three early USB resets and an uninterrupted 11 min 45.7 s finish. This page preserves the earlier repair and desk-validation record; its proposed next test predates that drive. USB reliability and rare inference stalls remain unresolved.

The Pixel has **JetLink 0.8.5-clarity-tensor.8** with **LiteRT 2.3.0**, and the comma has a verified USB inference backpressure patch. Cinque Terre V2 remains fully on the Tensor G6 NPU. Numerical and desk timing checks passed. **The physical USB resets and the earlier isolated 124 ms inference spike are not yet proven eliminated.** The next check is parked, with Android Auto unplugged and the Pixel off the wireless charger.

## Evidence from the drive and parked comparison

The preceding drive still had USB failures with Android Auto unplugged throughout. One separate event reported 123.809 ms inference, 0.398 ms queue time and 0.465 ms response sending without a USB reset at that point. It exhausted the existing five-frame hold allowance, followed by failed proving attempts. An earlier long period on the small model included MADS remaining active; the normal rule preventing a model swap while steering is active is preserved.

The following parked session used a **direct USB-C cable**, initially with wireless charging as well. Two bounded 125-second samples, before and after removing wireless charging, each produced 2,500 large-model outputs without a fallback. However, full logs cover 500.732 seconds and reveal **one unexpected USB reset between those samples**, with about 0.455 seconds on the small model. Pixel USB endpoints reported status `-71` (EPROTO); its two sessions reported maximum processing times of 47 and 45 ms. This was a USB failure with normal inference timing. The final intentional unplug is excluded. Neither the charger nor the cable is proven to be the root cause. Raw routes and device logs remain private.

## Changes installed

1. **Bound USB inference requests to one outstanding frame.** Optional FunctionFS requests hold the last result while an earlier inference is pending, instead of queuing additional camera frames that are already old when executed. Replies are drained before new work is offered. The oldest request still expires normally and completed USB errors are still surfaced immediately. Blocking clients, TCP and UDP retain their policies. The injected 124 ms regression verifies that frames arriving at 50 and 100 ms do not become a backlog and that a new request succeeds after the reply.
2. **Use Android performance hints for Tensor when Keep CPU Awake is enabled.** The existing setting now reaches the precompiled Tensor backend. It requests a 35 ms work target for the inference thread; Android retains control of clocks and thermals. A live Android hint session was verified. The setting is enabled on this Pixel. It is not a fixed-frequency or busy-spin override.
3. **Measure slow inference stages.** Input copies, runtime invocation, output copies and calling-thread CPU time are captured. Slow-frame details are formatted and logged after the response is sent. These are host measurements, not NPU hardware counters, and can help distinguish a future CPU stall from waiting inside the runtime.
4. **Upgrade the complete LiteRT stack to 2.3.0.** The C headers, runtime, GPU library, Tensor dispatch/plugin and AOT Python package use the same release. Each Android AAR has a pinned SHA-256, and missing native libraries fail the build. The V2 model was recompiled using the existing private SDK, explicit `half` precision and minimal sharding. All 2,424 operators compiled into one NPU partition and reproduced the previous model bytes exactly. The matching runtime manifest was updated after recompilation. Runtime-mismatched imports remain rejected; there is no silent GPU fallback.

These changes retain the previous receive-reserve, attached-device wake lock and reconnect repairs. Protocol v3, normal Tensor requests, the 46 ms hold deadline, five consecutive holds, 20-frame proving, steering-active model-swap gate and phone thermal/telemetry stops remain in effect. No vehicle-control tuning changed. The Jetson was not changed in this repair.

## Applying the Google documentation

[LiteRT 2.3.0](https://github.com/google-ai-edge/LiteRT/releases/tag/v2.3.0), released October 7, is the latest stable release checked on October 10. Its Android GPU and vendor NPU runtimes moved to separate Maven artifacts; the build now follows that packaging. Its published LLM/Metal speedups are not evidence of faster V2 execution on Tensor.

The [Google Tensor SDK codelab](https://codelabs.developers.google.com/codelabs/google-tensor-ml-sdk#0) informs the AOT compilation, compilation-report review and validation workflow. Its stable-package route uses `GOOGLE_TENSOR_BACKEND_ENABLED=1` before importing LiteRT. We target the actual `Tensor_G6`, retain the supplied private SDK locally, and compare recurrent device outputs against the original ONNX reference. Google Play model delivery is unnecessary for this sideloaded app. This does not establish that the supplied private SDK is Google's newest private compiler.

The app already uses the CompiledModel C API and preallocated buffers. Its engine supports recurrent buffer loops, while host inputs and outputs still require copies when the runtime cannot use host memory directly. The measured result below determines whether the upgrade helps this workload; a newer version alone does not establish a speedup. Burst mode 5 is retained from the qualified model configuration; sustained-mode and further zero-copy changes were not part of this measurement.

## Validation and performance

| Check | Result |
| --- | --- |
| Android release build | Succeeded; 59 unit tests passed |
| Native USB, protocol, Tensor import and thermal checks | 53 tests in 9 suites passed, using simulated USB and native fixtures |
| Comma transport, joining, model state and client checks | 285 tests and 9 subtests passed |
| Guarded patch installer | Dry-run, apply/readback, idempotence and unexpected-source refusal passed |
| Numerical comparison | 32 recurrent frames, 64 byte-identical reference inputs, all 15 output slices passed |
| Installed identity | APK pulled back and matched byte for byte; original signer retained |

Desk results use **ADB/TCP**, not the direct comma USB path. Each short configuration contains 1,200 measured finite frames; the longer LiteRT 2.3 check contains 6,000. All runs completed without protocol or phone-health failures. [Numerical comparison details](../android/tensor/parity-litert23-32-seed0.txt).

| Configuration | Inference p95 | Phone processing p95 | Phone maximum | ADB round-trip p95 |
| --- | ---: | ---: | ---: | ---: |
| LiteRT 2.2, hints off | 36.325 ms | 37.642 ms | 42.963 ms | 58.466 ms |
| LiteRT 2.2, hints on | 35.200 ms | 36.393 ms | 38.089 ms | 54.436 ms |
| LiteRT 2.3, hints on | 35.416 ms | 36.563 ms | 38.831 ms | 53.736 ms |
| LiteRT 2.3, hints on, 6,000 frames | 35.507 ms | 36.580 ms | 38.989 ms | 55.087 ms |

The longer run lasted 306.8 seconds. Battery telemetry ranged from 28.2 to 32.4°C, with normal thermal status (0). LiteRT 2.3 performed similarly to 2.2 with hints enabled; no clear runtime-only speedup was established. The earlier hints-on sample lowered phone p95 from 37.642 to 36.393 ms. These sequential runs are a desk comparison, not randomized hardware benchmarking. No repetition of the 124 ms spike was observed in these samples; rare-event elimination is unproven. ADB round-trip results must not be treated as a direct-USB timing pass. [Aggregate results and identities](../android/tensor/usb-stability-litert23-2026-10-10.json).

After benchmarking, the Settings runtime label was corrected to display `LiteRT 2.3.0` instead of the hard-coded ONNX Runtime name. All 27 native libraries in the final APK matched the benchmarked APK byte for byte. The final installation then passed a further 120-frame smoke check, and the corrected label was verified on the phone. Both APK hashes are recorded in the aggregate evidence.

## Installed identities

- APK: `0.8.5-clarity-tensor.8`, code `80508`, 104,211,360 bytes; SHA-256 `a51d60b8445a5f89664d34658292e0d44cf946bbc5604045ffe3870690220df5`.
- Source: upstream `b079496816e617ffd891ea12e5bee5d116db1383` plus the [complete Android patch](../android/tensor/tensor-support.patch).
- Model: source `09d080f36965bb2a0790500452bd328aa03c484d0222aa79d1ad9f021a522aec`; compiled `fc393523c5c1ddba9774382db513a5c62fad50cb187968ea25bc96db5480b51b`. [Manifest](../android/tensor/qualified-model.json).
- Comma JetLink: pinned API-2 v0.8.5 base `4b747aebad3d8d96ab26d76f1668f2b2ecb1b667`, previous recovery patch, then the [new stability patch](../patches/jetlink-usb-stability/recovery.patch).

The comma update was applied with fresh offroad/ignition/process checks, exact before/after source hashes and a rollback backup, then its resident USB owner was restarted offroad. The phone is at the desk; stored engine readiness does not establish a new USB handshake. The temporary developer TCP listener and ADB port forwarding were disabled after testing.

## Reapply and roll back the comma patch

For a fresh copy of the pinned JetLink submodule, apply the two bundles in order from the Clarity-Pilot repository root:

```sh
python scripts/maintenance/apply_jetlink_usb_recovery.py --check
python scripts/maintenance/apply_jetlink_usb_recovery.py
python scripts/maintenance/apply_jetlink_usb_recovery.py --bundle patches/jetlink-usb-stability --check
python scripts/maintenance/apply_jetlink_usb_recovery.py --bundle patches/jetlink-usb-stability
```

The stability bundle is incremental: its input hashes are the previously repaired files, not unmodified upstream files. On a live comma, use its openpilot Python environment with ignition off. The deployed bundle is `/data/jetlink-usb-stability-20261010`; verification is:

```sh
PYTHONPATH=/data/openpilot /usr/local/venv/bin/python \
  /data/jetlink-usb-stability-20261010/apply.py \
  --root /data/openpilot/jetlink_repo \
  --bundle /data/jetlink-usb-stability-20261010 --check
```

The installer refuses unexpected or partially changed sources. Already-patched files are verified without rewriting. Restart the resident USB owner only offroad after applying a new patch. The rollback ZIP is `/data/jetlink-usb-stability-20261010/rollback-1791665395766901782.zip`. To undo only this increment, confirm ignition off and onroad processes stopped, restore its four listed files, verify the [manifest's before hashes](../patches/jetlink-usb-stability/manifest.json), then restart offroad. To undo both repairs, roll back this increment first, then the [earlier repair](PIXEL_USB_RECOVERY_2026-10-10.md#reapply-and-rollback-on-the-comma). A repository push alone does not update a comma or the separate installation branch.

## Next physical test

Keep Android Auto unplugged and the Pixel off the wireless charger. Use the direct USB data cable and cool the phone. The car may run for air conditioning while remaining in Park. Verify fresh protocol v3, V2 identity, SuperSpeed USB and live phone health. Start with 120 frames and extend to 1,200 only if transport and timing stay clean. Inspect both devices' logs and camera-derived output before considering a drive. Any reset, fallback burst or thermal stop requires investigation. There is no parked-only software restriction in the app; this is the remaining physical validation step.

The [previous `.6` APK and source](../android/README-0.8.5-clarity-tensor.6.md) and [LiteRT 2.2 model manifest](../android/tensor/qualified-model-litert22.json) are archived. Android may refuse a version-code downgrade; do not uninstall to bypass it and erase app data. Model weights and the private compiler are not published.
