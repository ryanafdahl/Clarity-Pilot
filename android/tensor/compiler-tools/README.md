# Tensor model investigation tools

These scripts inspect or prepare local LiteRT models. They do not download an SDK, compile a model, access a phone, install an app, or change vehicle settings. No vendor SDK, model weights, compiled models, device logs, or private account information belong in this directory.

Use the same Python environment as the model compiler. The tested environment has `ai-edge-litert==2.3.0`, `flatbuffers`, and `numpy`.

## Static graph census

```sh
python graph_census.py --model converted.tflite --output graph-census.json
```

Counts operators, logical multiply-adds, constant weight ancestors, and layout-related tensor sizes. It supports both inline and external constant buffers. One multiply-add is one MAC. These are graph estimates, not measured NPU time, physical bandwidth, or proof of a bottleneck. Constant DEQUANTIZE operations can be folded by the compiler; reshape bytes do not imply memory copies.

Keep detailed reports private if their tensor names or shapes are not intended for publication. The script never includes weight values. It refuses to overwrite a report.

## Experimental constant MatMul to fully connected rewrite

Start with a dry run:

```sh
python rewrite_matmul_fc.py --source converted.tflite --report fc-plan.json
```

Create a separate experimental model:

```sh
python rewrite_matmul_fc.py --source converted.tflite --write --output fc-converted.tflite --report fc-transform.json
```

The transform requires a single static graph and eligible FP32 BATCH_MATMUL inputs whose constant two-dimensional right-hand matrix comes from FP16 DEQUANTIZE. It transposes the underlying FP16 uint16 bits into a new weight buffer and uses FULLY_CONNECTED version 5 with `keep_num_dims=true`. It preserves original tensors, signatures, constants, graph inputs/outputs, and subsequent ADD operations. No bias fusion or precision conversion is introduced. Unsupported cases stay unchanged; no eligible cases cause an error.

Original buffers deliberately remain in the new file. This can nearly double the temporary uncompiled file size. Compilation may remove unused buffers and conversions. Neither the source nor an existing output/report is overwritten.

Equivalent real arithmetic does not guarantee identical floating-point accumulation. The resulting artifact remains experimental until full recurrent output and performance comparisons pass. The tested JetLink model showed no practical gain from this representation change; the compiler produced nearly identical payloads.

Run the tiny CPU reference tests:

```sh
python test_rewrite_matmul_fc.py
```

Four tests cover 100 random cases across ranks two through four, exact FP16 bit preservation including negative zero, multiple transpose stripes, multiple external buffer relocation, signatures, separate ADD behavior, rejected preconditions, and overwrite protection. They do not replace real-model validation.

## Compiled payload comparison

```sh
python compare_compiled_payload.py --model-a compiled-a.tflite --model-b compiled-b.tflite --output payload-comparison.json
```

For models with one LiteRT DISPATCH_OP, this reads public dispatch offset/size metadata and compares the referenced payload with memory maps. It reports hashes, sizes, and differing byte ranges, never executable or weight bytes. If the payload is a nested TFLite model, it also reports buffer hashes and custom-option metadata. Unknown custom-option fields remain uninterpreted; equal buffers or a small byte difference do not establish equivalent execution.

All reports identify only the model basenames. Supply explicit paths to your own local artifacts. The comparison refuses to overwrite a report.

## Compiler manifest provenance

The current Tensor support patch records `source_converted_sha256`, `sdk_sha256` (the compiler library), and `sdk_executables_sha256`. A sole colocated executable helper is recorded as `sdk_worker` and `sdk_worker_sha256`. Discovery uses executable metadata; `--sdk-worker` selects a helper for ambiguous or nested layouts. Nested bundled toolchains are excluded from automatic discovery. Library-only SDK v2.0 needs no worker. This inventories the supplied files, not proof that every inventoried helper ran.

From the repository root, `python3 android/tensor/compiler-tools/test_compiler_provenance.py` runs nine Linux fixtures against the helper extracted from the actual support patch, without an SDK or model compilation.
