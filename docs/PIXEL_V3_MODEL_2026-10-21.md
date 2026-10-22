# Pixel V3 model update: accuracy gate remains open

On October 21, 2026, the comma selected **Cinque Terre V3 Model (September 17, 2026)**. The matching Tensor G6 model was compiled and tested on the Pixel 11 Pro XL, but **was not accepted for use**. The existing `0.8.7-clarity-tensor.10` APK, LiteRT 2.3.0 runtime and previously validated V2 model remain selected.

The initial V3 compilation corrupted the image-history queue. An exact-weight layout rewrite repaired that error and passed the initial 32-frame comparison. Extending validation to 160 recurrent frames revealed one remaining `lead` failure at frame 56: correlation **0.9988897096**, below the unchanged **0.999** limit. Two further graph controls produced exactly the same outputs and failure. All 15 pooled slices passed, but that does not override the per-frame failure. No sustained timing or physical USB qualification followed.

[Sanitized results and handoff](../android/tensor/v3-2026-10-21/results.json) · [Reproduction tools and candidate manifests](../android/tensor/v3-2026-10-21/README.md)

## Matching the comma

The active Chestnut bundle was `CTV3M`, ref `bf3e3631b3f91d92a1020a5e0dd4298b93ff4244`. Its ONNX source SHA-256 was `404a18cfd86d29637d20c697dfde245bb47c666ae016730ab674c65f4d1e1aa4`, **766,354,845 bytes**. The source download independently matched both values. Its checkpoint is `b9facbcc-4d47-410e-b3ce-dfcbad12ba92/56320/f78ed37d-afad-4dbc-8050-40ea885eedde/12864`.

The live adapter uses `ModelManager_ActiveBundleChestnut` for JetLink selection. The legacy `JetlinkModel` parameter still said V2, and `JetlinkSpec` described the last prepared V2 engine; neither meant that the selected Chestnut model was V2. The comma configuration was not changed and no connection window was armed. The Pixel therefore does **not** yet match the comma's active model for acceleration.

## Isolated compiler failure and repair

The original conversion had 2,447 operators, all compiled into one NPU partition. CPU LiteRT closely matched the original ONNX across 32 frames, but the phone diverged after the first frame, especially when historical images entered the vision pair at frame 4.

A native control allocated independent input/output buffers and copied recurrent state through host memory. It reproduced the app's outputs exactly on all 32 frames, ruling out the app's direct buffer swapping as the cause in this test. Integer state snapshots isolated the image queue: the compiled slice returned the flat first eight frame blocks instead of shifting each camera's five-frame queue. That exact faulty mapping reproduced every captured corrupted queue at frames 1–5. The desire queue was exact.

The hash-gated workaround keeps the queue in `[2,30,128,256]` views. It slices at `[0,6,0,0]` with size `[2,24,128,256]`, appends the current image along axis 1, and restores the original joined view for existing consumers. Graph signatures and all weight bits remain unchanged. The rewritten CPU model produced **32/32 bit-identical outputs** to the original CPU conversion. Native Tensor image/desire states then matched exactly at all six captured checkpoints, and the production app passed all 15 output slices and columns over 32 frames.

## Extended results

The extended test used 160 consecutive frames, exceeding the image, desire and feature history lengths of 5, 132 and 128. Each implementation fed back its own state after the initial reset. Source identity, shapes, 18,452 output values per frame and finiteness were checked explicitly. The reference copy replaced only the export's one identity-only `org.tinygrad::Contiguous` marker with standard ONNX `Identity`; weights, dtypes and other operations were unchanged.

| Tensor candidate | Full NPU placement | Extended result |
| --- | --- | --- |
| Original conversion | 2,447 / 2,447 operators | Rejected: image-history corruption; initial 32-frame comparison failed |
| Queue-only 4D rewrite | 2,448 / 2,448 operators | Initial 32 passed; 160-frame check failed `lead` at frame 56 |
| Full 4D image path | 2,442 / 2,442 operators | Same outputs as queue-only on all 160 frames; same failure |
| Queue rewrite plus 116 MatMul-to-FC representations | 2,564 / 2,564 operators | Same outputs as queue-only on all 160 frames; same failure |

All compilations used SDK **2.1**, LiteRT **2.3.0**, target **Tensor_G6**, precision **half**, sharding **minimal**. No precision, accuracy threshold, app performance mode or thermal protection was changed. The final two controls establish no improvement and are not promoted.

At the failed frame, lead maximum absolute error was **0.4033203**, mean absolute error **0.0335137**. The error was concentrated in the predicted position column and grew with horizon. Its remaining cause is unresolved. Passing aggregate metrics or a shorter capture is insufficient evidence to accept this artifact. Candidate timing from short correctness captures is not a performance qualification.

## Final phone state

V2 was restored and reproduced **32/32 outputs exactly** against the previous validated installation. V3's prepared engine was removed through the app and its import pair renamed with `.unqualified-20261021` suffixes. A fresh V3 request was rejected for lack of a usable Tensor import; V3 was absent from the ready-engine catalog. This matters because removing only an import does not reliably remove an existing prepared cache.

After a fresh app restart, the phone displayed **Waiting for Comma · Cinque Terre Model V2**. The developer listener was off, ADB forwarding was removed, native diagnostic files were removed, and the temporary host compiler swap was removed. V2 imports, the rollback APK, alarms, Android security and comma driving configuration were preserved.

The next work is to resolve the remaining V3 numerical discrepancy under the same precision and criteria, then repeat extended accuracy and sustained timing before a parked physical USB test. No V3 driving-readiness claim is made.
