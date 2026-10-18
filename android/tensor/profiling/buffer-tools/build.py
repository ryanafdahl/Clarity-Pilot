"""Build isolated I/O or AHWB diagnostics; no device access or SDK/model bundling."""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess

METRICS_SHA256 = 'fa9f0057830c58cf7b57e0f8ccb75dd034294132f5c4c8f44b2e886e72be3a3c'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def normalized_sha(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def replace_once(text, old, new, count=1):
    if count != 1 or text.count(old) != 1:
        raise ValueError('Unexpected source shape for replacement: ' + repr(old))
    return text.replace(old, new, 1)


def prepare_base(text):
    plain = '5 /* Burst in LiteRT 2.2.0 */'
    prefix = 'extern int jl_bench_mode;\n#include "litert/c/litert_metrics.h"\n'
    suffix = '\n#include "metrics.inc"\n'
    if 'io_profile.inc' in text or 'ahwb_allocation.inc' in text or 'wake_async.inc' in text:
        raise ValueError('Supply a plain or native-baseline bridge, not an existing experiment')
    if text.count(plain) == 1 and 'jl_bench_mode' not in text and 'metrics.inc' not in text and 'litert_metrics.h' not in text:
        return prefix + replace_once(text, plain, 'jl_bench_mode') + suffix, 'plain_bridge'
    expected = 'format("performance_mode = %d\\n", jl_bench_mode)'
    if text.startswith(prefix) and text.endswith(suffix) and text.count('jl_bench_mode') == 2 and text.count('metrics.inc') == 1 and text.count('litert_metrics.h') == 1 and text.count(expected) == 1:
        return text, 'prepared_native_baseline'
    raise ValueError('Partial or unsupported native-profiler bridge instrumentation')


def instrument_io(build, profiler):
    shim = build / 'CLiteRt'
    bridge = shim / 'jl_litert.c'
    text = bridge.read_text()
    anchor = 'char *jl_litert_buffer_write(jl_litert_buffer *buffer, const void *data, size_t nbytes) {'
    assert text.count(anchor) == 1
    text = replace_once(text, anchor, '#include "io_profile.inc"\n\n' + anchor + '\n  if (io_active) return io_measured_write(buffer, data, nbytes);')
    anchor = 'char *jl_litert_buffer_read(jl_litert_buffer *buffer, void *data, size_t nbytes) {'
    assert text.count(anchor) == 1
    text = replace_once(text, anchor, anchor + '\n  if (io_active) return io_measured_read(buffer, data, nbytes);')
    bridge.write_text(text)

    text = (profiler / 'native_profile.c').read_text()
    text = replace_once(text, '#include "jl_litert.h"', '#include "jl_litert.h"\n#include "io_profile.h"')
    text = replace_once(text, '  return t;\n}', '  jl_io_profile_register(t.device, output, i, t.name, t.bytes);\n  return t;\n}', 1)
    anchor = '  for(int frame=-20;frame<frames;frame++) {'
    assert text.count(anchor) == 1
    text = replace_once(text, anchor, r'''  int io_enabled = !getenv("BENCH_IO_PROFILE") || strcmp(getenv("BENCH_IO_PROFILE"), "0");
      if (!copy_inputs) { fprintf(stderr,"I/O diagnostic requires copy_inputs=1\n"); return 2; }
      printf("{\"diagnostic\":\"io_profile\",\"enabled\":%d,\"warmup_frames\":20,\"finite_output_check\":true,\"byte_identical_output_check\":true}\n", io_enabled);
      void *reference[32] = {0};
      for (size_t i=0;i<no;i++) { reference[i]=malloc(outputs[i].bytes); if(!reference[i])return 2; }
    ''' + anchor + '\n    if(frame==0) jl_io_profile_begin(io_enabled);')
    anchor = '    printf("{\\"frame\\":%d,'
    assert text.count(anchor) == 1
    text = replace_once(text, anchor, r'''    for (size_t i=0;i<no;i++) {
          if(frame==-20) memcpy(reference[i],outputs[i].host,outputs[i].bytes);
          else if(memcmp(reference[i],outputs[i].host,outputs[i].bytes)) {
            fprintf(stderr,"Deterministic output changed at frame %d output %zu\n",frame,i); return 6;
          }
        }
    ''' + anchor)
    anchor = '  if(getenv("BENCH_METRICS"))jl_bench_metrics(model,0);'
    assert text.count(anchor) == 1
    text = replace_once(text, anchor, '  jl_io_profile_end();\n' + anchor + r'''
      jl_io_profile_report();
      printf("{\"diagnostic\":\"output_consistency\",\"byte_identical_frames\":%d,\"measured_frames\":%d}\n", frames+20, frames);''')
    text = replace_once(text, 'jl_litert_buffer_release(out[i]);free(outputs[i].host);', 'jl_litert_buffer_release(out[i]);free(outputs[i].host);free(reference[i]);')
    native = build / 'native_profile.c'
    native.write_text(text)


def instrument_ahwb(build):
    shim = build / 'CLiteRt'
    bridge=shim/'jl_litert.c'
    text=bridge.read_text()
    anchor='  X(LiteRtGetTensorBufferPackedSize)'
    assert text.count(anchor)==1
    symbols=['LiteRtGetTensorBufferRequirementsBufferSize','LiteRtGetTensorBufferRequirementsStrides',
             'LiteRtGetTensorBufferRequirementsAlignment','LiteRtCreateTensorBufferFromAhwb',
             'LiteRtGetTensorBufferType','LiteRtGetTensorBufferAhwb','LiteRtGetTensorBufferSize']
    text=replace_once(text, anchor,''.join('  X('+s+') \\\n' for s in symbols)+anchor)
    start=text.index('char *jl_litert_buffer_create(')
    end=text.index('\n// Maps a buffer',start)
    text=text[:start]+'''#include "ahwb_allocation.inc"
    char *jl_litert_buffer_create(jl_litert_model *model, int output, size_t index, jl_litert_buffer **out) {
      return ahwb_create(model,output,index,out);
    }
    '''+text[end:]
    start=text.index('void jl_litert_buffer_release(')
    end=text.index('\nchar *jl_litert_run(',start)
    text=text[:start]+'''void jl_litert_buffer_release(jl_litert_buffer *buffer) {
      ahwb_release(buffer);
    }
    '''+text[end:]
    bridge.write_text(text)
    native=build/'native_profile.c'
    text=native.read_text()
    anchor='  check(jl_litert_open(argv[1]));'
    assert text.count(anchor)==1
    text=replace_once(text, anchor,'''  const char *usage=getenv("BENCH_AHWB_USAGE");
      if(!usage||(strcmp(usage,"rarely")&&strcmp(usage,"often"))){fprintf(stderr,"Set BENCH_AHWB_USAGE=rarely or often\\\\n");return 2;}
      printf("{\\\\"diagnostic\\\\":\\\\"ahwb_usage_experiment\\\\",\\\\"mode\\\\":\\\\"%s\\\\",\\\\"all_copies_preserved\\\\":true,\\\\"all_litert_locks_preserved\\\\":true}\\\\n",usage);
    '''.replace('\\\\','\\')+anchor)
    text=replace_once(text, 'extern void jl_bench_metrics', 'extern void jl_ahwb_release_after_model(void);\nextern void jl_bench_metrics',1)
    assert text.count('jl_litert_model_release(model);return 0;')==1
    text=replace_once(text, 'jl_litert_model_release(model);return 0;',
                      'jl_litert_model_release(model);jl_ahwb_release_after_model();return 0;')
    native.write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=['io', 'ahwb'], default='io')
    parser.add_argument('--bridge-dir', type=pathlib.Path, required=True)
    parser.add_argument('--profiler-dir', type=pathlib.Path, required=True)
    parser.add_argument('--ndk-root', type=pathlib.Path, required=True)
    parser.add_argument('--api', type=int, default=31)
    parser.add_argument('--build-dir', type=pathlib.Path, required=True)
    args = parser.parse_args()
    here = pathlib.Path(__file__).resolve().parent
    source, profiler = args.bridge_dir.resolve(), args.profiler_dir.resolve()
    build = args.build_dir.resolve()
    compiler = args.ndk_root.resolve() / f'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android{args.api}-clang'
    if args.api < 31:
        parser.error('Use Android API 31 or later')
    for path in [compiler, source/'jl_litert.c', profiler/'native_profile.c', profiler/'metrics.inc', profiler/'litert_metrics.h']:
        if not path.is_file():
            parser.error('Required source or compiler is missing: ' + str(path))
    if normalized_sha(profiler/'litert_metrics.h') != METRICS_SHA256:
        parser.error('Pinned public LiteRT 2.3.0 metrics header differs')
    try:
        text, preparation = prepare_base((source/'jl_litert.c').read_text())
    except ValueError as error:
        parser.error(str(error))
    for protected in (source, profiler, here):
        if build.is_relative_to(protected):
            parser.error('--build-dir must be outside the source, profiler and package directories')
    build.mkdir(parents=True, exist_ok=False)
    shim = build/'CLiteRt'
    shutil.copytree(source, shim)
    shutil.copy2(profiler/'litert_metrics.h', shim/'vendor/litert/c/litert_metrics.h')
    (shim/'jl_litert.c').write_text(text)
    shutil.copy2(profiler/'metrics.inc', build/'metrics.inc')
    for name in ['io_profile.h', 'io_profile.inc'] + (['ahwb_allocation.inc'] if args.kind == 'ahwb' else []):
        shutil.copy2(here/name, build/name)
    instrument_io(build, profiler)
    if args.kind == 'ahwb':
        instrument_ahwb(build)
    binary = build/'tensor-bench'
    command = [str(compiler), '-O2', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
               '-I', str(shim/'include'), '-I', str(shim/'vendor'), '-I', str(build),
               str(build/'native_profile.c'), str(shim/'jl_litert.c'), '-ldl', '-lm']
    if args.kind == 'ahwb':
        command.append('-landroid')
    command += ['-o', str(binary)]
    subprocess.run(command, check=True)
    manifest = {
        'kind': args.kind, 'bridge_preparation': preparation, 'android_api': args.api,
        'source_bridge_sha256': sha(source/'jl_litert.c'),
        'source_profiler_sha256': sha(profiler/'native_profile.c'),
        'source_metrics_sha256': sha(profiler/'metrics.inc'),
        'source_metrics_header_sha256': sha(profiler/'litert_metrics.h'),
        'source_metrics_header_lf_normalized_sha256': normalized_sha(profiler/'litert_metrics.h'),
        'diagnostic_bridge_sha256': sha(shim/'jl_litert.c'),
        'diagnostic_profiler_sha256': sha(build/'native_profile.c'),
        'source_instrumentation_sha256': {p.name: sha(p) for p in [here/'io_profile.h', here/'io_profile.inc'] + ([here/'ahwb_allocation.inc'] if args.kind == 'ahwb' else [])},
        'binary_sha256': sha(binary), 'compiler_target': f'aarch64-linux-android{args.api}',
        'compiler_flags': ['-O2', '-std=gnu11', '-Wall', '-Wextra', '-Werror'],
        'parameter_roles': {'bridge_dir': 'matching CLiteRt source', 'profiler_dir': 'native profiler and pinned metrics header', 'ndk_root': 'Linux Android NDK', 'build_dir': 'fresh isolated generated output'},
        'retains_all_io': True, 'warmup_frames_excluded': 20,
        'instrumentation_control': 'BENCH_IO_PROFILE=0', 'no_device_execution': True,
    }
    (build/'build-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (build/'build-command.local.json').write_text(json.dumps({'local_only_do_not_publish': True, 'command': command}, indent=2)+'\n')
    print(binary)


if __name__ == '__main__':
    main()
