"""Reproduce a bounded native A/B compiler comparison using profiling/profile.py.

Desk only. Uses already staged files; never installs or selects an app model.
All raw captures stay under a new local output directory. No phone access on import.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import pathlib
import random
import re
import time

SAFE_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z')
SAFE_REMOTE = re.compile(r'/data/local/tmp/[A-Za-z0-9][A-Za-z0-9_-]{0,80}\Z')
SHA256 = re.compile(r'[0-9a-fA-F]{64}\Z')


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adb', default='adb', help='ADB executable')
    p.add_argument('--serial', required=True, help='Explicit desk-connected device serial')
    p.add_argument('--remote-dir', required=True, help='Prepared directory inside /data/local/tmp')
    p.add_argument('--model-a', required=True, help='Already staged model basename')
    p.add_argument('--sha-a', required=True, help='Expected complete model SHA-256')
    p.add_argument('--model-b', required=True)
    p.add_argument('--sha-b', required=True)
    p.add_argument('--output', required=True, type=pathlib.Path, help='New local result directory')
    p.add_argument('--profile', type=pathlib.Path,
                   default=pathlib.Path(__file__).resolve().parent.parent / 'profile.py')
    p.add_argument('--prefix', default='model-pairs', help='Unique remote result prefix')
    p.add_argument('--pairs', type=int, default=6, help='Even count; half AB, half BA')
    p.add_argument('--frames', type=int, default=600, help='Measured frames per run')
    p.add_argument('--warmup', type=int, choices=[20], default=20,
                   help='The existing native profiler has exactly 20 warmups')
    p.add_argument('--mode', type=int, choices=[3, 4, 5], default=5)
    p.add_argument('--seed', type=int, default=20261017,
                   help='Pair-order randomization seed, not the fixed native input seed')
    p.add_argument('--plan-only', action='store_true', help='Write plan without contacting ADB')
    return p


def validate(a):
    if not a.serial or a.serial.startswith('-') or any(c.isspace() or ord(c) < 32 for c in a.serial):
        raise ValueError('serial must be a nonempty explicit ADB serial without whitespace')
    if not SAFE_REMOTE.fullmatch(a.remote_dir):
        raise ValueError('remote-dir must be one named directory inside /data/local/tmp')
    for name in (a.model_a, a.model_b, a.prefix):
        if not SAFE_NAME.fullmatch(name) or name in ('.', '..'):
            raise ValueError('model names and prefix must be safe basenames starting with a letter or digit')
    if len(a.prefix) > 48:
        raise ValueError('prefix must be at most 48 characters')
    if not SHA256.fullmatch(a.sha_a) or not SHA256.fullmatch(a.sha_b):
        raise ValueError('Both expected SHA-256 values must contain exactly 64 hex characters')
    if a.pairs < 2 or a.pairs > 24 or a.pairs % 2:
        raise ValueError('pairs must be an even number from 2 through 24')
    if not 10 <= a.frames <= 12000:
        raise ValueError('frames must be between 10 and 12000')
    if a.warmup != 20 or a.mode not in (3, 4, 5):
        raise ValueError('Unsupported warmup or mode')
    if a.output.exists():
        raise ValueError('Refusing an existing local output path')
    if not a.profile.is_file():
        raise ValueError('profile.py is missing; pass --profile explicitly')


def make_plan(a):
    order = ['AB'] * (a.pairs // 2) + ['BA'] * (a.pairs // 2)
    random.Random(a.seed).shuffle(order)
    return {
        'schema': 1, 'scope': 'native fixed-input desk comparison; not recurrent or vehicle USB qualification',
        'seed': a.seed, 'order': order, 'frames': a.frames, 'warmups': a.warmup,
        'period_ms': 50, 'mode': a.mode, 'copy_inputs': 1, 'metrics_requested': True,
        'native_input_seed': 17, 'A': a.model_a, 'B': a.model_b,
        'model_sha256': {'A': a.sha_a.lower(), 'B': a.sha_b.lower()},
        'profile_py_sha256': hashlib.sha256(a.profile.read_bytes()).hexdigest(),
        'primary': 'paired mean total native frame time; lower is faster',
        'runs': [{'pair': pair, 'variant': variant,
                  'name': f'{a.prefix}-{pair:02d}-{variant}'}
                 for pair, sequence in enumerate(order) for variant in sequence],
        'assumptions': [
            'Staged tensor-bench was built from the documented native_profile.c (20 warmups, input seed 17).',
            'Both models have the same I/O contract and precision.',
            'No other benchmark/app inference load is active; this runner does not stop other processes.',
        ],
    }


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def parse_remote_hash(text, path):
    lines = text.strip().splitlines()
    if len(lines) != 1:
        raise RuntimeError('Unexpected sha256sum output')
    parts = lines[0].split()
    if len(parts) != 2 or not SHA256.fullmatch(parts[0]) or parts[1].lstrip('*') != path:
        raise RuntimeError('Unexpected sha256sum filename or digest')
    return parts[0].lower()


def complete_hardware_metric(result):
    value = result.get('hardware_mean_ms')
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def matching_outputs(results):
    if not results or not results[0].get('output_sha256'):
        return False
    expected = results[0]['output_sha256']
    return all(r.get('output_sha256') == expected for r in results)


def execute(a, plan):
    root = a.output.resolve()
    spec = importlib.util.spec_from_file_location('jetlink_native_profile', a.profile.resolve())
    profile = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(profile)
    profile.ROOT, profile.ADB, profile.SERIAL, profile.REMOTE = root, a.adb, a.serial, a.remote_dir
    original_adb = profile.adb

    def recorded_adb(*args, **kwargs):
        # Preserve telemetry including an observation that triggers the existing guard.
        try:
            value = original_adb(*args, **kwargs)
        except BaseException as exc:
            if args in (('shell', 'dumpsys battery'), ('shell', 'dumpsys thermalservice')):
                with (root / 'raw-health.jsonl').open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps({'time': time.time(), 'command': args[-1],
                                             'error': str(exc)}) + '\n')
            raise
        if args in (('shell', 'dumpsys battery'), ('shell', 'dumpsys thermalservice')):
            with (root / 'raw-health.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'time': time.time(), 'command': args[-1],
                                         'stdout': value}) + '\n')
        return value

    profile.adb = recorded_adb
    remote = a.remote_dir
    models = {'A': a.model_a, 'B': a.model_b}

    def verify_models():
        found = {}
        for variant, model in models.items():
            path = f'{remote}/{model}'
            found[variant] = parse_remote_hash(profile.adb('shell', f'sha256sum {path}', timeout=90), path)
            if found[variant] != plan['model_sha256'][variant]:
                raise RuntimeError(f'Remote model {variant} SHA-256 differs from the supplied digest')
        return found

    results, current, locked = [], None, False
    lock = f'{remote}/.native-model-pairs-lock'
    try:
        if profile.adb('get-state').strip() != 'device':
            raise RuntimeError('Explicit ADB device is not ready')
        resolved = profile.adb('shell', f'readlink -f {remote}').strip()
        if resolved != remote:
            raise RuntimeError('Remote directory is missing or resolves outside the requested directory')
        profile.adb('shell', f'test -d {remote}/runtime && test -x {remote}/tensor-bench')
        # Atomic exclusion among invocations of this paired runner.
        profile.adb('shell', f'mkdir {lock}')
        locked = True
        for run in plan['runs']:
            profile.adb('shell', f'test ! -e {remote}/{run["name"]} && test ! -L {remote}/{run["name"]}')
        before = verify_models()
        bench_path = f'{remote}/tensor-bench'
        bench_sha = parse_remote_hash(profile.adb('shell', f'sha256sum {bench_path}'), bench_path)
        write_json(root / 'preflight.json', {'model_sha256': before, 'native_binary_sha256': bench_sha,
                   'remote_results_absent': True, 'exclusive_runner_lock_acquired': True})
        for run in plan['runs']:
            current = run
            result = profile.run(run['name'], models[run['variant']], a.mode, a.frames, 1, True)
            result.update(pair=run['pair'], variant=run['variant'])
            results.append(result)
            write_json(root / 'checkpoint.json', results)
            if not matching_outputs(results):
                raise RuntimeError('Final output hash mismatch or missing output; comparison stopped')
            if not complete_hardware_metric(result):
                raise RuntimeError('Requested hardware metrics are unavailable or do not cover exactly the measured frames')
        after = verify_models()
        after_bench_sha = parse_remote_hash(profile.adb('shell', f'sha256sum {bench_path}'), bench_path)
        if after_bench_sha != bench_sha:
            raise RuntimeError('Native benchmark binary changed during comparison')
        write_json(root / 'postflight.json', {'model_sha256': after,
                   'native_binary_sha256': after_bench_sha, 'final_outputs_match': True})
        profile.adb('shell', f'rmdir {lock}')
        locked = False
        write_json(root / 'results.json', results)
        write_json(root / 'completion.json', {'status': 'complete', 'runs': len(results),
                   'frames_per_run': a.frames, 'final_outputs_match': True,
                   'remote_runner_lock_retained': False})
    except BaseException as exc:
        # profile.run already preserves stdout/stderr/health and stops only its owned PID.
        # Pull any diagnostic artifacts left by an interrupted benchmark.
        pull_error = None
        if current is not None:
            try:
                profile.adb('pull', f'{remote}/{current["name"]}/.',
                            str(root / current['name']), timeout=30)
            except Exception as capture_error:
                pull_error = str(capture_error)
        write_json(root / 'checkpoint.json', results)
        write_json(root / 'failure.json', {'error': str(exc), 'type': type(exc).__name__,
                   'current_run': current, 'completed_runs': len(results),
                   'remote_runner_lock_retained': locked, 'artifact_pull_error': pull_error})
        # On failure retain the lock until the owned process and remote timeout are inspected.
        raise


def main(argv=None):
    p = parser()
    a = p.parse_args(argv)
    try:
        validate(a)
    except ValueError as exc:
        p.error(str(exc))
    plan = make_plan(a)
    a.output.resolve().mkdir(parents=True, exist_ok=False)
    write_json(a.output / 'plan.json', plan)
    if a.plan_only:
        print('Plan written; no ADB access performed.')
        return 0
    execute(a, plan)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

