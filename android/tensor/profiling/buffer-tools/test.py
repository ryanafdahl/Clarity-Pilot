"""Compile and run local diagnostic fixtures using a previously generated bridge."""
import argparse
import hashlib
import json
import os
import pathlib
import shlex
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=pathlib.Path, required=True)
    parser.add_argument('--cc', default=os.environ.get('CC', 'cc'), help='Host C compiler command (default: CC or cc)')
    args = parser.parse_args()
    here, build = pathlib.Path(__file__).resolve().parent, args.build_dir.resolve()
    shim = build/'CLiteRt'
    if not (shim/'jl_litert.c').is_file() or not (build/'io_profile.inc').is_file():
        parser.error('First prepare a diagnostic with build.py')
    for name in ['io_profile.h', 'io_profile.inc']:
        if (build/name).read_bytes() != (here/name).read_bytes():
            parser.error('Generated instrumentation differs from the fixture source: ' + name)
    suites = [('io', 'test_io_profile.c')]
    if '#include "ahwb_allocation.inc"' in (shim/'jl_litert.c').read_text():
        if (build/'ahwb_allocation.inc').read_bytes() != (here/'ahwb_allocation.inc').read_bytes():
            parser.error('Generated AHWB implementation differs from fixture source')
        suites.append(('ahwb', 'test_ahwb.c'))
    out = build/'offline-tests'
    out.mkdir(exist_ok=True)
    records=[]
    for kind, source in suites:
        binary = out/('test-'+kind)
        command = shlex.split(args.cc) + ['-O2','-std=gnu11','-Wall','-Wextra','-Werror',
                  '-I',str(here/'mock'),'-I',str(build),'-I',str(shim),'-I',str(shim/'include'),'-I',str(shim/'vendor'),
                  str(here/source),'-ldl','-lpthread','-o',str(binary)]
        subprocess.run(command, check=True)
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=60)
        (out/(kind+'.stdout.jsonl')).write_text(result.stdout)
        (out/(kind+'.stderr.txt')).write_text(result.stderr)
        records.append({'suite':kind,'exit_code':result.returncode,'source_sha256':hashlib.sha256((here/source).read_bytes()).hexdigest(),'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest()})
        (out/'results.json').write_text(json.dumps(records,indent=2)+'\n')
        print(result.stdout.splitlines()[-1] if result.stdout else result.stderr)
        result.check_returncode()


if __name__ == '__main__':
    main()
