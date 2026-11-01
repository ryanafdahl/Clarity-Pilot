# Pixel JetLink update — November 1, 2026

The Pixel 11 Pro XL was updated in place from `.10` to **`0.8.12-clarity-tensor.11`**. Its outputs matched the prior app exactly across 160 frames. **A timing stall remains unresolved:** the first run stopped after 490 measured frames when phone processing reached 275.406 ms. A repeat completed 1,200 frames with a 37.261 ms maximum, but does not erase the earlier failure. The app is left at Waiting for Comma with V2 and the temporary test listener disabled. [APK and rebuild instructions](../android/README.md) · [Sanitized evidence](../android/tensor/update-2026-11-01.json).

The validated Tensor model remains Cinque Terre V2. **V3 is still unqualified:** the October 21 compile failed one extended accuracy criterion and its candidates remain quarantined. This maintenance release does not repair that numerical failure. The comma was not contacted for this app update, so this report makes no claim about its current model selection. [V3 evidence](PIXEL_V3_MODEL_2026-10-21.md).

The later [two longer Pixel 11 tests](PIXEL_LONG_TESTS_2026-11-01.md) completed 24,000 measured frames under 50 ms on the phone. Their successful sustained timing does not erase the first failed attempt recorded here.

## What changed

The app advances from upstream v0.8.7 to stable [v0.8.12](https://github.com/zoompilot/jetlink/releases/tag/v0.8.12), source `a863c3801da6fd925d14eb1f5b1e250f8efcc649`. Upstream adds model-choice sharing and model downloads by ONNX hash, alongside its intervening maintenance fixes. This is an app maintenance update; no speed improvement is claimed.

The Tensor support patch was rebased onto that source. Its sole merge conflict was in engine requests: the resolution retains upstream's new `fetch` and `ref` fields together with the existing phone-health check and recovery state. Static comparison found all custom patch additions/deletions unchanged apart from the `.11` version fields. The previously reviewed compiler provenance helper also remains included; it does not change inference.

The precompiled Tensor path, explicit FP16 precision, LiteRT 2.3.0, V2 model, CPU hints, USB recovery and thermal protections remain unchanged. Four packaged runtime libraries were checked against `.10` and are byte-identical: LiteRT core, its GPU accelerator, the Tensor compiler plugin and Tensor dispatch. Protocol remains v3 with unchanged packet and inference layouts.

## Model-choice behavior

The new upstream PickStore remembers the newest explicit model choice from either phone or comma. **Use Model** on the phone records a local choice that can replace an older comma choice at the next HELLO; a newer comma choice can take precedence in turn.

On an upgrade with no prior `pick.json`, the pick is empty. Startup still preloads the previously loaded engine, but does not turn it into a new explicit model choice. A normal desk `ensure_engine` request also does not create a pick. No model selection change is needed for this app update.

Downloading V3's ONNX does not supply its required precompiled Tensor import. Its rejected prepared cache and active import filenames must both remain absent: removing imports alone would not prevent an existing prepared engine from loading. The update retains that distinction and does not add an automatic GPU fallback to the precompiled path.

## Build and device evidence

| Item | Result |
| --- | --- |
| Version / code | `0.8.12-clarity-tensor.11` / `81211` |
| APK bytes | `104224964` |
| APK SHA-256 | `30880b942fbc44b8d09f4c54ba25321e60df7f5c0dce235d50b8e74f6f9e6f3e` |
| Signer certificate SHA-256 | `50e670489a4ba19aec5e9fbad6f06074556d4d07be629ba012b3ca78f1eabb4e` |
| Android unit tests | 59 passed; no failures, errors or skips |
| Native regressions | 226 passed across three selected runs: 11, 162 and 53 tests |
| Installation | In-place update to `.11` / `81211` |
| Recurrent outputs | 160/160 full outputs exactly match `.10`; all finite |
| Reference comparison | First 32 frames passed all 15 output slices |
| First timing attempt | Failed 100 ms guard at 490 measured frames; maximum phone processing 275.406 ms |
| Repeat timing attempt | 1,200 frames completed; phone guard passed, PC round-trip timing failed |
| Final listener/forwarding cleanup | Listener disabled after restart; owned ADB forwarding removed |

The installed `.10` baseline and updated `.11` each produced 160 finite full-output frames, with exact equality between versions. Both first-32-frame reference comparisons passed all 15 output slices. The updated HELLO identifies protocol 3, LiteRT 2.3.0 and Tensor G6, with V2 loaded, V3 absent from the prepared inventory and `pick: null`.

The initial host-native test attempts had missing or mismatched ONNX Runtime libraries. After supplying the matching host runtime, all 226 selected tests passed. This host-test setup repair did not change the APK or its runtime libraries.

## Desk timing

All three runs requested 20 warmup frames and 1,200 measured frames at a 50 ms period. The first updated run stopped at its existing guard; it did not complete the requested duration. The unchanged app then completed a repeat. Runs were sequential and not a balanced performance experiment.

| Metric, milliseconds unless noted | Previous `.10` | First `.11` attempt | `.11` repeat |
| --- | ---: | ---: | ---: |
| Measured frames | 1,200 | 490 | 1,200 |
| Phone processing mean | 31.884 | 31.668 | 32.137 |
| Phone processing p95 | 33.484 | 33.183 | 33.638 |
| Phone processing maximum | 37.502 | 275.406 | 37.261 |
| Phone frames over 50 ms | 0 | 1 | 0 |
| PC round-trip p95 | 50.124 | 49.535 | 50.605 |
| PC round-trip maximum | 69.717 | 287.883 | 66.938 |
| Phone timing guard | Passed | Failed | Passed |
| PC round-trip timing check | Failed | Failed | Failed |

The updated outlier was predominantly inference: 275.057 ms. Sampled battery temperatures were 24.5–25.0°C for the baseline, 25.7°C for the first updated run and 26.7°C for the repeat, with normal thermal status. The phone was already awake during the tested period; no wake event establishes a cause for this stall. Its cause remains unknown. Neither the app update nor screen activity is established as the cause, and the repeat does not resolve the earlier failure or establish a speed improvement.

Timing is measured with synthetic recurrent inputs through PC ADB/TCP forwarding. Phone processing, PC round trip and direct comma USB are different measurements; a desk result does not establish physical USB reliability or driving readiness. Rare wake stalls and the earlier USB resets remain unresolved.

## Handoff and rollback

The final installed APK hash and version match the release file. The unchanged V2 compiled model and manifest were checked, and the phone was left at **Waiting for Comma · Cinque Terre Model V2**, using **Tensor TPU (precompiled)**. Battery temperature was 27.5°C with normal Android thermal status.

V3 remained absent from the prepared-engine inventory, its external imports remained quarantined, and a fresh V3 engine request was rejected for missing active Tensor imports. V2 was restored after that negative check. The temporary Developer listener was disabled and checked after an app restart, owned ADB forwarding was removed, and the temporary UI file was deleted.

The comma was not contacted or reconfigured, no connection window was armed, and no physical comma-to-Pixel USB test was performed. The completed app update does not establish driving readiness or resolve the timing stall.

The [previous `.10` APK and exact-source patch](../android/README-0.8.7-clarity-tensor.10.md) are retained. Android may reject installing its lower version code over `.11`; preserving app data can require rebuilding the archived source with a higher code and the same signing key. Do not uninstall to bypass signing or downgrade checks.

The [October 17 maintenance check](PIXEL_UPDATE_2026-10-17.md) and [compiler/runtime investigation](TENSOR_COMPILER_RUNTIME_2026-10-17.md) remain historical evidence. Their speed measurements are not attributed to this update.
