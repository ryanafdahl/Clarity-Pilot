"""Build the isolated ARM64 profiler with the Linux Android NDK, without editing JetLink."""
import argparse, hashlib, pathlib, shutil, subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=pathlib.Path,required=True,help='Upstream checkout with this repository\'s Tensor patch applied')
p.add_argument('--ndk',type=pathlib.Path,required=True,help='Linux Android NDK root')
p.add_argument('--output',type=pathlib.Path,required=True,help='New build directory; refuses an existing directory')
a=p.parse_args()
here=pathlib.Path(__file__).resolve().parent
source=a.source.resolve()/'JetlinkKit/Sources/CLiteRt'
compiler=a.ndk.resolve()/'toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android31-clang'
if not compiler.is_file() or not (source/'jl_litert.c').is_file():
    p.error('Compiler or patched CLiteRt source missing')
metrics=here/'litert_metrics.h'
if hashlib.sha256(metrics.read_bytes()).hexdigest()!='fa9f0057830c58cf7b57e0f8ccb75dd034294132f5c4c8f44b2e886e72be3a3c':
    p.error('Pinned LiteRT 2.3.0 metrics header changed')
out=a.output.resolve()
out.mkdir(parents=True,exist_ok=False)
shim=out/'CLiteRt'
shutil.copytree(source,shim)
shutil.copy2(metrics,shim/'vendor/litert/c/litert_metrics.h')
path=shim/'jl_litert.c'
text=path.read_text()
needle='5 /* Burst in LiteRT 2.2.0 */'
if text.count(needle)!=1:
    p.error('Unexpected bridge version; refusing to alter a different performance-mode expression')
text=text.replace(needle,'jl_bench_mode')
text='extern int jl_bench_mode;\n#include "litert/c/litert_metrics.h"\n'+text
text+='\n#include "metrics.inc"\n'
path.write_text(text)
subprocess.run([str(compiler),'-O2','-std=gnu11','-Wall','-Wextra',
    '-I',str(shim/'include'),'-I',str(shim/'vendor'),'-I',str(here),
    str(here/'native_profile.c'),str(path),'-ldl','-lm','-o',str(out/'tensor-bench')],check=True)
print(out/'tensor-bench')
