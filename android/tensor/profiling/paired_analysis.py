"""Analyze interleaved app controls using runs, not individual frames, as repeats.

Positive differences mean the candidate B is faster than control A. The paired
bootstrap interval describes observed run variability, not driving qualification.
With only eight pairs its tail estimates remain imprecise.
"""
import argparse
import itertools
import json
from pathlib import Path
import numpy as np


def paired_stats(differences):
    d = np.asarray(differences, dtype=float)
    if len(d) < 2 or not np.isfinite(d).all():
        raise ValueError('At least two finite paired differences are required')
    rng = np.random.default_rng(20261011)
    bootstrap = d[rng.integers(0, len(d), size=(50000, len(d)))].mean(axis=1)
    # Two-sided sign-flip test. Exact for at most 16 pairs; bounded above that.
    if len(d) <= 16:
        null = np.asarray(list(itertools.product((-1, 1), repeat=len(d)))) @ d / len(d)
        p = float(np.mean(np.abs(null) >= abs(d.mean()) - 1e-12))
    else:
        null = (rng.choice((-1, 1), size=(50000, len(d))) * d).mean(axis=1)
        p = float((np.count_nonzero(np.abs(null) >= abs(d.mean())) + 1) / (len(null) + 1))
    return {'pairs': len(d), 'control_minus_candidate_ms': float(d.mean()),
            'paired_differences_ms': d.tolist(), 'candidate_faster_pairs': int((d > 0).sum()),
            'bootstrap_95pct_interval_ms': np.percentile(bootstrap, [2.5, 97.5]).tolist(),
            'two_sided_sign_flip_p': p}


def analyze(directory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    runs = manifest['runs']
    if manifest.get('failures') or len(runs) != len(manifest['order']) or len(runs) % 2:
        raise ValueError('Incomplete or failed comparison; do not report it as a completed experiment')
    data = []
    outputs = None
    for position, run in enumerate(runs):
        if run['variant'] != manifest['order'][position]: raise ValueError('Run order mismatch')
        row = json.loads((directory / run['result']).read_text())
        if not row['protocol_pass'] or row['measured_frames'] != manifest['frames_per_run']:
            raise ValueError('Incomplete run')
        frames = json.loads((directory / (Path(run['result']).stem + '-frames.json')).read_text())['frames']
        measured = [f for f in frames if not f['warmup']]
        if len(measured) != row['measured_frames']: raise ValueError('Frame file count mismatch')
        hashes = [(f['frame_id'], f['output_sha256']) for f in frames]
        if outputs is None: outputs = hashes
        elif outputs != hashes: raise ValueError('Output bytes differ between runs; investigate before comparing gains')
        data.append((run['variant'], row))
    result = {'complete_pairs': len(runs)//2, 'measured_frames': sum(r['measured_frames'] for _, r in data),
              'output_bytes_match_all_runs': True, 'positive_difference': 'candidate B faster',
              'unit_of_replication': 'adjacent paired runs, not frames',
              'interval': 'seeded paired percentile bootstrap, 50000 resamples',
              'caveat': 'Exploratory secondary tail metrics; multiple comparisons are not corrected. Desk TCP only.',
              'metrics': {}}
    for metric in ('server_total', 'inference', 'queues', 'round_trip'):
        result['metrics'][metric] = {}
        for stat in ('mean_ms', 'p95_ms', 'p99_ms', 'max_ms'):
            differences = []
            for i in range(0, len(data), 2):
                pair = dict(data[i:i+2])
                if set(pair) != {'A', 'B'}: raise ValueError('Every adjacent pair must contain one A and one B')
                differences.append(pair['A'][metric][stat] - pair['B'][metric][stat])
            values = paired_stats(differences)
            values.update(control_ms=float(np.mean([r[metric][stat] for v,r in data if v=='A'])),
                          candidate_ms=float(np.mean([r[metric][stat] for v,r in data if v=='B'])))
            result['metrics'][metric][stat] = values
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): parser.error('output already exists')
    args.output.write_text(json.dumps(analyze(args.directory), indent=2)+'\n')
