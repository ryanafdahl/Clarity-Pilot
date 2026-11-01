# Compile Cinque Terre V2 for Pixel 10 Pro XL

This is the recipe behind the **50.62 ms average phone-processing result** on a Pixel 10 Pro XL with Tensor G5. It converts the original ONNX through JetLink's converter, compiles that output on a Linux workstation with Google's Tensor SDK, and imports the compiled model into JetLink's **Tensor TPU (precompiled)** backend. Installing stock JetLink or choosing its separate **Tensor NPU (on-device)** backend does not reproduce this setup.

The measured run completed 12,000 frames, but 76.1% exceeded 50 ms. Reproducing the configuration does not guarantee identical timing or establish driving readiness. [Full results](../../docs/PIXEL10_TESTS_2026-11-01.md) · [Comparison chart and text](../../docs/images/pixel-comparison-2026-11-01/README.md).

## What you need

- A Pixel 10 Pro XL with Tensor G5, USB debugging authorized, and a USB data cable. The recorded device ran Android 17. Other Pixel 10 variants have not been measured here.
- An x86-64 Linux workstation. Compilation was performed under Ubuntu 24.04 in WSL, with Python 3.12.3 and Swift 6.4.0. Install a release Swift toolchain using the [official Linux instructions](https://www.swift.org/install/linux/) and confirm `swift --version` works in your shell. The pinned Swift package requires at least Swift 6.2.
- **Google Tensor SDK v2.1**, obtained through your own approved SDK access. Google's [SDK access and prerequisites page](https://developers.google.com/edge/litert/next/tensor-sdk) links the beta application. Keep the downloaded compiler library and its executable worker together. Neither the private SDK nor compiled model weights are included in this repository.
- Enough memory for this large model. Google recommends at least 64 GB RAM for substantial models; earlier local builds exhausted WSL's default memory allocation. Check `free -h`, allow adequate RAM/swap, and compile alone rather than alongside an Android build. The minimum sufficient memory for this model has not been established.
- Git, curl, Python venv support, and Android platform-tools (`adb`). TensorFlow, a generic ONNX-to-TFLite converter, and an Android APK rebuild are not needed for this recipe.

The commands below are **Bash**, run in order in the same shell. Use a new working directory. For the phone steps, ADB and the Python client must run on the same host and reach the same forwarded localhost port. Native Linux can run the whole procedure; under WSL, first make the phone visible to that Linux ADB instance, or run the phone/client steps together on Windows. Do not assume WSL Python's `127.0.0.1` reaches a forwarding port created by Windows ADB. The published timing run used Windows Python and Windows ADB; host round-trip timings can differ on Linux.

## 1. Get the exact app converter and compiler helper

```bash
set -euo pipefail
mkdir pixel10-jetlink-repro
cd pixel10-jetlink-repro
export PIXEL_REPRO="$PWD"
export CLARITY_ROOT="$PIXEL_REPRO/Clarity-Pilot"
export JETLINK_ROOT="$PIXEL_REPRO/jetlink"

# Skip unrelated upstream LFS assets; this APK and patch are ordinary Git files.
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://github.com/ryanafdahl/Clarity-Pilot.git "$CLARITY_ROOT"
git clone https://github.com/zoompilot/jetlink.git "$JETLINK_ROOT"
git -C "$JETLINK_ROOT" checkout a863c3801da6fd925d14eb1f5b1e250f8efcc649
git -C "$JETLINK_ROOT" apply --check "$CLARITY_ROOT/android/tensor/tensor-support.patch"
git -C "$JETLINK_ROOT" apply "$CLARITY_ROOT/android/tensor/tensor-support.patch"

python3.12 -m venv "$PIXEL_REPRO/compiler-env"
source "$PIXEL_REPRO/compiler-env/bin/activate"
python -m pip install 'ai-edge-litert==2.3.0' 'numpy==2.5.4'
python -m pip freeze > "$PIXEL_REPRO/compiler-packages.txt"
```

The patch is tied to upstream **v0.8.12 / `a863c380`** and the published **`0.8.12-clarity-tensor.11`** APK. Stop if it does not apply cleanly; do not substitute a newer converter while claiming the same experiment. The helper needs Python 3.11+ because it uses `hashlib.file_digest`; the client project's lower minimum is not the compiler helper's minimum. LiteRT **2.3.0** is required on both compiler and app sides.

## 2. Download and identify the original V2 ONNX

Use this pinned source, not a similarly named export or a V3 model. The filename and display name are insufficient to establish identity.

```bash
export SOURCE_SHA=09d080f36965bb2a0790500452bd328aa03c484d0222aa79d1ad9f021a522aec
export SOURCE_ONNX="$PIXEL_REPRO/cinque-terre-v2.onnx"

curl --fail --location \
  'https://media.githubusercontent.com/media/commaai/openpilot/37bfa1413edcdc2e8844984b83727c33f81d8f46/openpilot/selfdrive/modeld/models/big_driving_supercombo.onnx' \
  --output "$SOURCE_ONNX"
printf '%s  %s\n' "$SOURCE_SHA" "$SOURCE_ONNX" | sha256sum --check --strict
test "$(stat -c %s "$SOURCE_ONNX")" = 766040736
```

Both checks must succeed. If the URL is unavailable, an existing copy is usable only when its **SHA-256 and 766,040,736-byte size** match. The original weights remain subject to their upstream terms.

## 3. Convert with JetLink's model layout

```bash
cd "$JETLINK_ROOT/JetlinkKit"
swift build -c release --product tensor-convert
.build/release/tensor-convert "$SOURCE_ONNX" "$PIXEL_REPRO/converted-v2"

printf '%s  %s\n' \
  60c74bc8ce8bc111b110571b40bc6bfae86483f3857a8e052fe7a670de2af897 \
  "$PIXEL_REPRO/converted-v2/model.tflite" | sha256sum --check --strict
```

The recorded converted input was **766,883,008 bytes**, with 2,424 operators. The converter applies JetLink's image layout and recurrent queue contract; a generic conversion is not an equivalent input. There are no additional layout flags for `tensor-convert`. If this digest differs, stop and investigate the source/patch/toolchain rather than replacing the expected hash. The current converter's executable source was compared with the historical conversion source; no semantic conversion changes were found, but this guide-writing pass did not perform a new full conversion or compilation.

## 4. Compile for Tensor G5 on the workstation

Set `TENSOR_SDK_DIR` to the extracted directory containing **both** files below. Keep the compiler worker executable; extract on the Linux filesystem when possible.

```bash
export TENSOR_SDK_DIR="/absolute/path/to/google_tensor_ml_sdk"
test -f "$TENSOR_SDK_DIR/liblitert_plugin_compiler.so"
test -x "$TENSOR_SDK_DIR/compiler_worker"

printf '%s  %s\n' \
  14e84153cbcf60463d011ba739fc15ff222188c6448a283c0abea639fa19cb68 \
  "$TENSOR_SDK_DIR/liblitert_plugin_compiler.so" | sha256sum --check --strict
printf '%s  %s\n' \
  e6a8f7c0bdfebbb754e18f82b7bcde83b22c526c1297ce555a1797a2cd099294 \
  "$TENSOR_SDK_DIR/compiler_worker" | sha256sum --check --strict

python "$JETLINK_ROOT/android/scripts/compile-tensor.py" \
  --source "$SOURCE_ONNX" \
  --model "$PIXEL_REPRO/converted-v2/model.tflite" \
  --sdk "$TENSOR_SDK_DIR" --sdk-worker compiler_worker \
  --output "$PIXEL_REPRO/compiled-g5" \
  --soc Tensor_G5 --precision half --sharding minimal \
  2>&1 | tee "$PIXEL_REPRO/compile-g5.log"
```

The SDK hashes identify the **v2.1 build used here**. Different hashes mean a different compiler experiment, not an equivalent reproduction. Obtain the matching release from Google if available; do not use another person's private SDK download link.

The helper sets `GOOGLE_TENSOR_BACKEND_ENABLED=1` and `GOOGLE_TENSOR_COMPILER_LIB` before importing LiteRT. Its flags map to Google's `google_tensor_truncation_type="half"` and `google_tensor_sharding_intensity="minimal"`. `half` means FP16; do not substitute `auto`, BF16, or quantization. [Google's compilation flag definitions](https://developers.google.com/edge/tensor-sdk/compilation-flags).

A matching compile reports:

```text
Google_Tensor_G5
Subgraph 0 fully compiled: 2424 / 2424 ops offloaded to 1 partitions.
```

The two files to deploy are:

```text
compiled-g5/09d080f36965bb2a0790500452bd328aa03c484d0222aa79d1ad9f021a522aec/model.tflite
compiled-g5/09d080f36965bb2a0790500452bd328aa03c484d0222aa79d1ad9f021a522aec/manifest.json
```

The recorded G5 compiled model was **777,647,632 bytes**, SHA-256 **`9a4481fde9229db6362778c218eae8b28e97774e46d73ad2358ff91bde823ca2`**. Compare your generated manifest with the [recorded G5 manifest](validated-model-g5.json). A different compiled digest must be recorded and investigated, and needs its own numerical validation; do not edit the manifest to pretend that different bytes match. A compile report alone does not prove on-phone NPU execution or numerical correctness. **Do not import the Tensor G6 / Pixel 11 artifact.**

## 5. Install the matching app and import your artifact

The released APK already contains the matching LiteRT runtime and precompiled Tensor support. Use the [APK installation and signature guidance](../README.md#install-or-update); no private compiler is installed on the phone.

```bash
export PIXEL_SERIAL='YOUR_DEVICE_SERIAL'
export ADB_BIN="$(command -v adb)"
export APP_ID=io.zoompilot.jetlink.android
export COMPILED_DIR="$PIXEL_REPRO/compiled-g5/$SOURCE_SHA"
export PHONE_MODEL_DIR="/sdcard/Android/data/$APP_ID/files/tensor-models"
export APK_PATH="$CLARITY_ROOT/android/jetlink-0.8.12-clarity-tensor.11-pixel.apk"

printf '%s  %s\n' \
  30880b942fbc44b8d09f4c54ba25321e60df7f5c0dce235d50b8e74f6f9e6f3e \
  "$APK_PATH" | sha256sum --check --strict
"$ADB_BIN" devices
"$ADB_BIN" -s "$PIXEL_SERIAL" install -r "$APK_PATH"
"$ADB_BIN" -s "$PIXEL_SERIAL" shell am start -n "$APP_ID/io.zoompilot.jetlink.MainActivity"
```

Unlock the phone, allow JetLink notifications, and open the app once so it creates its model directory. In Settings, select **Tensor TPU (precompiled)** and enable **Keep CPU Awake** and **Keep Screen On**, matching the recorded foreground test. Leave Android's thermal controls unchanged. Before replacing an existing model, pull its `.tflite` and `.json` to a separate local backup directory and retain the prior APK. A signing mismatch is not a reason to uninstall and erase existing app data.

```bash
"$ADB_BIN" -s "$PIXEL_SERIAL" shell am force-stop "$APP_ID"
"$ADB_BIN" -s "$PIXEL_SERIAL" push "$COMPILED_DIR/model.tflite" "$PHONE_MODEL_DIR/$SOURCE_SHA.tflite.pending"
"$ADB_BIN" -s "$PIXEL_SERIAL" push "$COMPILED_DIR/manifest.json" "$PHONE_MODEL_DIR/$SOURCE_SHA.json.pending"
sha256sum "$COMPILED_DIR/model.tflite"
"$ADB_BIN" -s "$PIXEL_SERIAL" shell sha256sum "$PHONE_MODEL_DIR/$SOURCE_SHA.tflite.pending"
```

Confirm that the local digest, phone digest, and your generated manifest's `compiled_sha256` all agree before running the next block. Keep the app stopped while replacing the pair; do not create a nested shell-owned directory under `tensor-models`.

```bash
"$ADB_BIN" -s "$PIXEL_SERIAL" shell mv "$PHONE_MODEL_DIR/$SOURCE_SHA.tflite.pending" "$PHONE_MODEL_DIR/$SOURCE_SHA.tflite"
"$ADB_BIN" -s "$PIXEL_SERIAL" shell mv "$PHONE_MODEL_DIR/$SOURCE_SHA.json.pending" "$PHONE_MODEL_DIR/$SOURCE_SHA.json"
"$ADB_BIN" -s "$PIXEL_SERIAL" shell am start -n "$APP_ID/io.zoompilot.jetlink.MainActivity"
```

## 6. Prepare the fresh model cache and verify the backend

Create a separate Python environment for the desk client and reference check. These NumPy/ONNX Runtime versions match the retained reference environment; they are distinct from the compiler environment. Put the **patched checkout root** on `PYTHONPATH`, because the benchmark imports both `jetlink` and `scripts.verify_parity`.

```bash
python3.12 -m venv "$PIXEL_REPRO/client-env"
source "$PIXEL_REPRO/client-env/bin/activate"
python -m pip install 'numpy==2.2.6' 'onnx==1.20.1' 'onnxruntime==1.26.0'
export PYTHONPATH="$JETLINK_ROOT"
python -m pip freeze > "$PIXEL_REPRO/client-packages.txt"
```

In JetLink Settings, scroll to About and tap **Version seven times**. This reveals the Developer section and enables its **Port 5599** listener. It is separate from Android's USB-debugging setting. Keep the phone unlocked and JetLink visible throughout the test; do not run another benchmark concurrently.

```bash
"$ADB_BIN" -s "$PIXEL_SERIAL" forward tcp:5599 tcp:5599
python - <<'PY'
import hashlib, json, os
from pathlib import Path
from jetlink.client import JetlinkClient

source = Path(os.environ['SOURCE_ONNX'])
sha = os.environ['SOURCE_SHA']
assert source.stat().st_size == 766040736
with source.open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == sha
client = JetlinkClient.open_tcp('127.0.0.1', 5599, want_hidden=True)
try:
    hello = client.hello()
    assert hello['protocol'] == 3, hello
    assert hello['device'] == 'tensor-Tensor_G5', hello
    assert hello['runtime_version'] == '2.3.0', hello
    spec = client.ensure_engine(sha, 766040736, onnx_path=source, build_timeout=900)
    assert spec.sha256 == sha
    print(json.dumps({'hello': hello, 'state': client.state()}, indent=2))
finally:
    client.close()
PY
```

This uploads the **original ONNX** if the app lacks its source cache and prepares the imported compiled artifact through the ordinary engine request. It does not create an explicit phone-side model choice. `verify_parity capture` and `benchmark.py` do **not** upload the ONNX; skip this step on a fresh phone and they may fail with a missing-model error. `capture --onnx` is not an upload shortcut.

Inspect JetLink's logs after preparation. Require **`NPU(Tensor G5)`** and the correct source hash; the precompiled backend rejects partial/CPU/GPU execution. A label containing `npu`, or a successful workstation compile, is insufficient. `GPU(fp16)` is a different execution path. For a private diagnostic capture:

```bash
"$ADB_BIN" -s "$PIXEL_SERIAL" logcat -d -s jetlink > "$PIXEL_REPRO/backend.log"
```

## 7. Check numerical output before timing

Use a new directory. The following checks **32 recurrent frames against the original ONNX**, matching the extent of the retained reference-accuracy result. Our update also captured 160 finite frames and matched the first 32 against its prior G5 installation; those are separate checks. Do not claim 160 reference frames from the 32-frame command below.

```bash
export PARITY_DIR="$PIXEL_REPRO/parity-32"
test ! -e "$PARITY_DIR"
python -m scripts.verify_parity capture \
  --host 127.0.0.1 --port 5599 --sha256 "$SOURCE_SHA" --nbytes 766040736 \
  --n 32 --seed 0 --dir "$PARITY_DIR"
python -m scripts.verify_parity reference --onnx "$SOURCE_ONNX" --dir "$PARITY_DIR"
python - <<'PY'
import os
from pathlib import Path
import numpy as np
p = Path(os.environ['PARITY_DIR'])
for prefix in ('out_link', 'out_ref'):
    files = list(p.glob(prefix + '_*.npy'))
    assert len(files) == 32, (prefix, len(files))
    for i in range(32):
        values = np.load(p / f'{prefix}_{i}.npy')
        assert values.size == 18452 and np.isfinite(values).all(), (prefix, i)
print('32 complete, finite output vectors on each side')
PY
python -m scripts.verify_parity compare --dir "$PARITY_DIR"
```

Require successful exit codes and all **15 output slices** passing. Do not loosen tolerances to get a pass. Capture uses `--n`, not `--frames`; reference/compare consume every saved frame in the directory, and their `--n` does not restrict that count. Never reuse a directory with stale frames. For an extended 160-frame reference experiment, choose another new directory and change the capture count **and** the independent count check to 160; report that as a new validation.

## 8. Repeat the full timing measurement

Let the phone cool to approximately the recorded starting battery temperature of **27°C** and normal Android thermal status. The measured setup used USB power, no wireless charging, JetLink in the foreground, Keep CPU Awake and Keep Screen On enabled. Room temperature and case configuration were not recorded, so they are not controlled equivalences. Keep the PC awake and record your OS, battery temperature, app settings and cooling conditions.

The next command runs **20 warmup + 12,000 measured frames**, cycling 32 synthetic inputs with seed 17 and continuous recurrent state. `--record-timing-overruns` retains slow frames and continues; health and protocol failures still stop it. A Pixel 10 run can take approximately 14 minutes because the requested 50 ms interval is not an achieved full-exchange rate.

```bash
if python "$CLARITY_ROOT/android/tensor/benchmark.py" \
  --source-sha256 "$SOURCE_SHA" --source-bytes 766040736 \
  --frames 12000 --warmup 20 --period-ms 50 --record-timing-overruns \
  --transport 'desk ADB TCP forwarding over USB, Pixel 10 Tensor G5' \
  --adb "$ADB_BIN" --serial "$PIXEL_SERIAL" \
  --frame-output "$PIXEL_REPRO/pixel10-run-frames.json" \
  --output "$PIXEL_REPRO/pixel10-run.json"; then
  printf 'Phone timing passed; inspect the complete result.\n'
else
  BENCHMARK_EXIT=$?
  printf 'Benchmark exit %s; inspect the saved result before any further run.\n' "$BENCHMARK_EXIT"
fi
```

**Exit code 1 is expected if timing fails, even when all 12,000 frames completed.** Read `measured_frames`, `failures`, `protocol_pass`, `server_timing_pass`, `timing_overruns` and `server_total` in the saved JSON. Use new output filenames for another run. The unchanged health stops include battery temperature at 43°C, Android severe thermal status (3), and missing/invalid/stale telemetry.

Compare **`server_total`**, not `round_trip`, with the recorded result:

| Metric, warmup excluded | Recorded Pixel 10 Pro XL |
| --- | ---: |
| Measured frames | 12,000 |
| Phone mean / p95 / maximum | 50.625 / 52.165 / 58.077 ms |
| Phone frames over 50 ms | 9,127 (76.1%) |
| Battery before → after | 27.0 → 34.4°C |
| Highest Android thermal status | 0 (normal) |
| Phone timing qualification | Failed |

PC round-trip timing includes transport and was slower; it is not the phone-processing number. Neither metric here measures the complete vehicle pipeline. Preserve the full distribution and failures rather than reporting only the fastest frames.

## 9. Close the temporary test connection

Perform this cleanup even if preparation, numerical checks or benchmarking fail. If the fail-fast shell exited, set `PIXEL_SERIAL`, `ADB_BIN` and `APP_ID` again as in step 5 before running the cleanup commands.

Tap Version seven times again to disable the Developer listener, wait for its section to disappear and allow a few seconds for settings to save, then remove only your forwarding:

```bash
"$ADB_BIN" -s "$PIXEL_SERIAL" forward --remove tcp:5599
"$ADB_BIN" -s "$PIXEL_SERIAL" shell am force-stop "$APP_ID"
"$ADB_BIN" -s "$PIXEL_SERIAL" shell am start -n "$APP_ID/io.zoompilot.jetlink.MainActivity"
"$ADB_BIN" -s "$PIXEL_SERIAL" shell ss -ltn
```

Verify port 5599 stays closed after restarting JetLink. Leave the original APK/model backups intact. No comma configuration, model choice or connection window needs to be changed to reproduce this desk measurement.

## SDK access, app allowlisting, and common failures

**Is an allowlist involved?** SDK download approval and phone-side application access are separate questions. In the earlier Pixel 10 **on-device compiler** experiment, the actual service error was `Compile failed, error code 16` with `Current application should not be allowed to access EdgeTPU.` The runtime subsequently reported `GPU(fp16)`. That attempt involved V3; it is not a controlled same-model comparison with today's V2 timing.

The precompiled G5 V2 path subsequently executed as **`NPU(Tensor G5)`** on our tested Pixel/APK. This is evidence for that combination, not proof that SDK acceptance automatically allowlists every package/signature or that precompilation universally avoids application access restrictions. This guide does not bypass an allowlist. If another phone/build reports access denied, preserve the exact error, package/signing identity, Android build and execution backend, and ask Google about the supported access requirements. Do not label a CPU/GPU fallback as a TPU result.

| Symptom | Check |
| --- | --- |
| SDK unavailable | Apply through Google's SDK page; the public APK does not include the private compiler. |
| `compiler_worker` missing or not executable | Extract the complete matching SDK on Linux and preserve its worker beside the library. |
| Compile killed / out of memory | Review Linux/WSL RAM and swap, and stop concurrent builds; do not change precision just to finish. |
| Source or converted hash mismatch | Verify the pinned ONNX and patched converter; similarly named exports can differ. |
| G6 artifact or chipset mismatch | Recompile with explicit `--soc Tensor_G5`; the helper's default is G6. |
| Import present but source model missing | Perform the explicit ONNX upload/engine-preparation step. |
| `GPU(fp16)` despite selecting an NPU option | Inspect which backend was selected and its access/compilation errors; require the precompiled backend's NPU check. |
| Parity mismatch or non-finite output | Stop and preserve results; do not promote the artifact or relax checks. |
| Benchmark exits 1 after 12,000 frames | Inspect timing flags and `failures`; full measurement completion is distinct from passing 50 ms. |
| A 200+ ms result elsewhere | Match source model, compiled target, runtime/backend, thermal state and timing definition before attributing the gap to compilation. |

Keep private SDK files, model weights, device identifiers and raw device logs out of public reports. Share versions, hashes, compiler partition counts, numerical-validation outcomes and sanitized timing distributions instead.
