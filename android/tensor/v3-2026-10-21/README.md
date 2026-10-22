# Unqualified Cinque Terre V3 Tensor candidates

**Do not install these candidate manifests as a qualified model.** The phone was restored to V2. Every repaired V3 candidate still failed one per-frame accuracy check in the 160-frame comparison. [Findings and final handoff](../../../docs/PIXEL_V3_MODEL_2026-10-21.md) · [Results](results.json).

This directory preserves a reproducible image-queue compiler workaround, the unsuccessful follow-up controls, manifest hashes and sanitized comparison summaries. Model weights, compiled models and the private Tensor SDK are not distributed.

## Reproduce the queue repair

Use the pinned upstream checkout and Tensor patch from [the Tensor guide](../README.md). Obtain the V3 ONNX from the comma model ref `bf3e3631b3f91d92a1020a5e0dd4298b93ff4244`; verify SHA-256 `404a18cfd86d29637d20c697dfde245bb47c666ae016730ab674c65f4d1e1aa4` and 766,354,845 bytes. Convert it with `tensor-convert`. The original conversion must hash to `a60ff14e699827da4f2416c9853f5018403d1b8b5700b7dae5fbdfba065d721a`; the script refuses a different graph.

Use an environment containing `ai-edge-litert==2.3.0`, NumPy and FlatBuffers:

```sh
python rewrite_image_queue.py \
  --source /path/to/converted/model.tflite \
  --output /path/to/queue4d.tflite --report /path/to/queue4d-rewrite.json
python /path/to/patched-jetlink/android/scripts/compile-tensor.py \
  --source /path/to/source.onnx --model /path/to/queue4d.tflite \
  --sdk /path/to/google_tensor_ml_sdk --output /path/to/compiled-v3 \
  --soc Tensor_G6 --precision half --sharding minimal
```

The rewritten TFLite hash is `948c8abd44a05900f8367ba3d485d17f2e29de5140def594b8b5c5b14811a223`. Its tested compilation is recorded in [candidate-queue4d.json](candidate-queue4d.json). The helper validates the exact operations and consumers, preserves external weight bytes, relocates their offsets and rehashes every external buffer. Default without `--output` is a dry run; existing output/report files are not overwritten. The usual converter output alone retains the demonstrated V3 queue bug on this compiler.

The full-image-path control uses `rewrite_image_path_4d.py` against the same original conversion and imports the adjacent queue script. The matrix control uses the reviewed [rewrite_matmul_fc.py](../compiler-tools/rewrite_matmul_fc.py) with the queue-repaired file as `--source`, `--write`, a new `--output` and `--report`. Its transposed FP16 weight bits remain exact. Neither control fixed the remaining numerical miss.

## Validation requirements

Run captures through the normal installed app with the source hash/size above. A compiled import needs the original ONNX for first-time spec preparation. Stop the app before replacing a model/manifest pair, verify staged hashes, then relaunch; a live engine can reuse the old same-source artifact. Follow [import instructions](../README.md#import-into-the-pixel) only for controlled desk investigation and retain V2 rollback.

Create a separate CPU-reference ONNX that replaces only the one validated `org.tinygrad::Contiguous` node (one input, one output, no attributes) with `Identity`, retaining its tensor names, weights and dtypes. [Reference hashes](reference-provenance.json). Capture at least 160 recurrent frames with reset on the first frame. Use independent state feedback in the CPU reference. Verify exact source identity and shapes, every array finite, and both output lengths exactly 18,452 before the unchanged upstream slice/column comparison; its generic comparator otherwise truncates to the shorter output length.

Keep individual-frame failures as well as pooled results. The repaired 32-frame pass did not predict the 160-frame failure. Accuracy must pass before sustained timing or a physical USB handoff. Keep the benchmark listener disabled outside desk tests. Removing unqualified artifacts requires both the prepared engine and its import pair to be unavailable; verify a fresh model request is rejected afterward.
