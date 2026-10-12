"""Analyze fixed wake windows; preserve failures and refuse uncensored gains."""
import argparse,json,pathlib
import numpy as np
from paired_analysis import paired_stats

def summary(frames):
    if not frames:return None
    values=np.asarray([f['server_total_ms'] for f in frames])
    return {'frames':len(frames),'mean_ms':float(values.mean()),
            'p95_ms':float(np.percentile(values,95)),'max_ms':float(values.max()),
            'over_50ms':int((values>50).sum())}

def analyze(path):
    manifest=json.loads((path/'manifest.json').read_text())
    if manifest['traced']:raise ValueError('Traced runs are diagnostic, not primary latency controls')
    if manifest['failures'] or len(manifest['runs'])!=len(manifest['order']):raise ValueError('Experiment incomplete')
    runs=[];reference={};matches=True
    for index,item in enumerate(manifest['runs']):
        if item['variant']!=manifest['order'][index]:raise ValueError('Order mismatch')
        result=json.loads((path/item['result']).read_text())
        frames=json.loads((path/(pathlib.Path(item['result']).stem+'-frames.json')).read_text())['frames']
        ids=[f['frame_id'] for f in frames]
        if ids!=list(range(len(frames))):raise ValueError('Missing or duplicated frame IDs')
        if not result.get('wake_stimulus',{}).get('command_completed'):raise ValueError('Missing wake stimulus')
        if result['measured_frames']!=len([f for f in frames if not f['warmup']]):raise ValueError('Measured frame count mismatch')
        for frame in frames:
            old=reference.setdefault(frame['frame_id'],frame['output_sha256'])
            matches=matches and old==frame['output_sha256']
        baseline=summary([f for f in frames if 100<=f['frame_id']<200])
        wake=summary([f for f in frames if 200<=f['frame_id']<300])
        runs.append({'run':item['run'],'variant':item['variant'],'baseline':baseline,'wake':wake,
                     'censored':wake is None or wake['frames']!=100,
                     'failures':result['failures'],'before':item['before'],'after':item['after'],
                     'wake_command_duration_ms':1000*(result['wake_stimulus']['command_end_monotonic_s']-result['wake_stimulus']['command_start_monotonic_s'])})
    if not matches:raise ValueError('Output hashes differ; investigate before attributing timing gains')
    out={'order':manifest['order'],'runs':runs,'all_common_output_bytes_match':matches,
         'apk_sha256':manifest['apk_sha256'],'rollback':manifest.get('rollback'),
         'primary':'mean phone-processing latency in fixed frame IDs 200..299',
         'unit_of_replication':'wake trial pair, not frames','traced':False,
         'censored_trials':sum(r['censored'] for r in runs),'paired':{},
         'caveat':'Exploratory single-device desk ADB/TCP; not driving qualification. Secondary comparisons uncorrected.'}
    for variant in ('A','B'):
        cases=[r for r in runs if r['variant']==variant]
        out[variant]={'trials':len(cases),'timing_stops':sum(bool(r['failures']) for r in cases),
                      'censored':sum(r['censored'] for r in cases)}
    if len(runs)>=4 and all(r['baseline'] and r['baseline']['frames']==100 for r in runs):
        differences=[]
        for i in range(0,len(runs),2):
            pair={r['variant']:r for r in runs[i:i+2]}
            if set(pair)!={'A','B'}:raise ValueError('Unpaired sequence')
            differences.append(pair['A']['baseline']['mean_ms']-pair['B']['baseline']['mean_ms'])
        out['baseline_only_mean']=paired_stats(differences)
        out['baseline_only_note']='Secondary screen-off baseline comparison; does not estimate wake-stall improvement'
    if not out['censored_trials']:
        for metric in ('mean_ms','p95_ms','max_ms','over_50ms','baseline_adjusted_mean_ms'):
            differences=[]
            for i in range(0,len(runs),2):
                pair={r['variant']:r for r in runs[i:i+2]}
                if set(pair)!={'A','B'}:raise ValueError('Unpaired sequence')
                def value(r):
                    return r['wake']['mean_ms']-r['baseline']['mean_ms'] if metric=='baseline_adjusted_mean_ms' else r['wake'][metric]
                differences.append(value(pair['A'])-value(pair['B']))
            if len(differences)>=2:out['paired'][metric]=paired_stats(differences)
    else:out['primary_unavailable']='At least one wake window is censored; do not report an uncensored overall gain'
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path,required=True)
    a=p.parse_args()
    if a.output.exists():p.error('Output already exists')
    a.output.write_text(json.dumps(analyze(a.directory),indent=2)+'\n')
