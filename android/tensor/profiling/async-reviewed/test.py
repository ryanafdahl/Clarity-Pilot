"""Run the 15 local ownership fixtures against an applied reviewed async patch."""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shlex
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge-dir', type=pathlib.Path, required=True, help='CLiteRt in either reviewed patched checkout')
    parser.add_argument('--build-dir', type=pathlib.Path, required=True, help='Fresh host-test output directory')
    parser.add_argument('--cc', default=os.environ.get('CC', 'cc'))
    args = parser.parse_args()
    source, out = args.bridge_dir.resolve(), args.build_dir.resolve()
    here = pathlib.Path(__file__).resolve().parent
    for name in ['jl_litert.c','experiment_safety.inc','wake_async.inc','wake_metrics.inc']:
        if not (source/name).is_file():
            parser.error('Apply one complete reviewed source patch first; missing ' + name)
    text = (source/'jl_litert.c').read_text()
    if len(re.findall(r'#define JL_WAKE_ASYNC [01]', text)) != 1:
        parser.error('Unexpected async experiment bridge')
    if out.is_relative_to(source) or out.is_relative_to(here):
        parser.error('Keep --build-dir outside the source and package')
    out.mkdir(parents=True, exist_ok=False)
    records=[]
    for variant, expected in [(0,3),(1,12)]:
        branch=out/str(variant)
        branch.mkdir()
        # Test the actual bridge; only the existing compile-time switch changes.
        (branch/'jl_litert.c').write_text(re.sub(r'#define JL_WAKE_ASYNC [01]', f'#define JL_WAKE_ASYNC {variant}', text))
        command=shlex.split(args.cc)+['-std=gnu11','-O2','-Wall','-Wextra','-Werror',
                '-I',str(branch),'-I',str(source),'-I',str(source/'include'),'-I',str(source/'vendor'),
                str(here/'test_async.c'),'-ldl','-lpthread','-o',str(branch/'test-async')]
        subprocess.run(command,check=True)
        result=subprocess.run([str(branch/'test-async')],capture_output=True,text=True,timeout=60)
        (branch/'stdout.txt').write_text(result.stdout)
        (branch/'stderr.txt').write_text(result.stderr)
        result.check_returncode()
        if f'PASS async={variant} cases={expected}:' not in result.stdout:
            raise RuntimeError('Unexpected ownership test coverage')
        records.append({'async':variant,'passed':expected,'test_source_sha256':hashlib.sha256((here/'test_async.c').read_bytes()).hexdigest()})
        print(result.stdout.strip())
    (out/'results.json').write_text(json.dumps({'cases':records,'total_passed':15,'mocked_apis':True,'no_device_access':True},indent=2)+'\n')


if __name__ == '__main__':
    main()
