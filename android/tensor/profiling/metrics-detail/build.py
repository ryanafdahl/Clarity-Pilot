"""Build a separate native metrics-detail diagnostic from a pinned baseline.

No phone access. Only accepts BENCH_METRICS_DETAIL=0 or 1 (default 0).
The meaning/availability of a detail level remains vendor-dependent.
"""
import argparse,difflib,hashlib,json,pathlib,shutil,subprocess

# Pins describe source bytes after CRLF -> LF normalization only. Historical
# raw-byte provenance is retained separately in generated/captured manifests.
SOURCE_PINS = {
    'bridge':'126baa587df3c6c3a2603f7de423506b58edda7a139bd55df3796b404dd717c2',
    'profiler':'4bc9df3654d298791a5081968d77485f7c69531fc096ea56c1f57595a221df7c',
    'metrics':'501734bae43a1064e21d0d7561ebf0d19117f5d9fbb895bb11365b3c58803f31',
}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def normalized_sha(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()

def validate_source_pins(paths):
    observed={}
    for role,expected in SOURCE_PINS.items():
        path=paths[role]
        if not path.is_file() or normalized_sha(path)!=expected:
            raise ValueError(f'Baseline source differs from the tested diagnostic: {path.name}')
        observed[role]={'raw_sha256':sha(path),'lf_normalized_sha256':normalized_sha(path)}
    return observed


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=pathlib.Path,required=True,help='Existing native baseline build directory')
    p.add_argument('--profiler',type=pathlib.Path,required=True,help='Directory with native_profile.c and metrics.inc')
    p.add_argument('--ndk',type=pathlib.Path,required=True)
    p.add_argument('--output',type=pathlib.Path,required=True,help='New output directory')
    a=p.parse_args()
    source=a.baseline.resolve()/'CLiteRt';profiler=a.profiler.resolve();out=a.output.resolve()
    compiler=a.ndk.resolve()/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android31-clang'
    if not compiler.is_file() or not (source/'jl_litert.c').is_file():
        p.error('NDK compiler or native baseline bridge is missing')
    if out.exists():
        p.error('Refusing output overwrite')
    paths={'bridge':source/'jl_litert.c','profiler':profiler/'native_profile.c','metrics':profiler/'metrics.inc'}
    try:
        source_hashes=validate_source_pins(paths)
    except ValueError as error:
        p.error(str(error))

    native_before=(profiler/'native_profile.c').read_text()
    metrics_before=(profiler/'metrics.inc').read_text()
    native=native_before;metrics=metrics_before
    anchor='int jl_bench_mode = 5;'
    if native.count(anchor)!=1:
        p.error('Native profiler anchor mismatch')
    native=native.replace(anchor,anchor+'\nint jl_bench_metrics_detail = 0;')
    anchor='int main(int argc,char **argv) {'
    if native.count(anchor)!=1:
        p.error('Native profiler anchor mismatch')
    native=native.replace(anchor,anchor+r'''
  const char *metrics_detail = getenv("BENCH_METRICS_DETAIL");
  if (metrics_detail && strcmp(metrics_detail,"0") && strcmp(metrics_detail,"1")) {
    fprintf(stderr,"BENCH_METRICS_DETAIL must be exactly 0 or 1\n");
    return 2;
  }
  jl_bench_metrics_detail = metrics_detail && !strcmp(metrics_detail,"1");
  fprintf(stderr,"METRICS requested detail_level=%d (vendor-dependent)\n",jl_bench_metrics_detail);
''')
    anchor='fn_LiteRtCompiledModelStartMetricsCollection(model->compiled,0)'
    if metrics.count(anchor)!=1:
        p.error('Metrics source anchor mismatch')
    metrics='extern int jl_bench_metrics_detail;\n'+metrics.replace(anchor,'fn_LiteRtCompiledModelStartMetricsCollection(model->compiled,jl_bench_metrics_detail)')
    out.mkdir(parents=True,exist_ok=False)
    shutil.copytree(source,out/'CLiteRt')
    (out/'native_profile.c').write_text(native)
    (out/'metrics.inc').write_text(metrics)
    patch=''.join(difflib.unified_diff(native_before.splitlines(keepends=True),native.splitlines(keepends=True),fromfile='a/native_profile.c',tofile='b/native_profile.c'))
    patch+=''.join(difflib.unified_diff(metrics_before.splitlines(keepends=True),metrics.splitlines(keepends=True),fromfile='a/metrics.inc',tofile='b/metrics.inc'))
    (out/'metrics-detail.patch').write_text(patch)
    command=[str(compiler),'-O2','-std=gnu11','-Wall','-Wextra','-I',str(out/'CLiteRt/include'),
     '-I',str(out/'CLiteRt/vendor'),'-I',str(out),str(out/'native_profile.c'),str(out/'CLiteRt/jl_litert.c'),
     '-ldl','-lm','-o',str(out/'tensor-bench')]
    subprocess.run(command,check=True)
    manifest={'purpose':'isolated vendor-dependent metrics detail 0/1 diagnostic; not app/runtime replacement',
     'source_bridge_sha256':sha(source/'jl_litert.c'),'source_profiler_sha256':sha(profiler/'native_profile.c'),
     'source_metrics_sha256':sha(profiler/'metrics.inc'),
     'source_lf_normalized_sha256':{role:values['lf_normalized_sha256'] for role,values in source_hashes.items()},'diagnostic_profiler_sha256':sha(out/'native_profile.c'),
     'diagnostic_metrics_sha256':sha(out/'metrics.inc'),'patch_sha256':sha(out/'metrics-detail.patch'),
     'binary_sha256':sha(out/'tensor-bench'),'binary_bytes':(out/'tensor-bench').stat().st_size,
     'command':command,'default_detail_level':0,'allowed_detail_levels':[0,1],
     'detail1_semantics':'vendor-dependent and unverified; may reject or return same metrics',
     'model_precision_changed':False,'model_runtime_calls_changed':False}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))


if __name__ == "__main__":
    main()
