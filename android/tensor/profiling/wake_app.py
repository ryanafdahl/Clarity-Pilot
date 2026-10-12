"""Repeated desk-only wake trials. Each timing stop is retained as an outcome.

Every trial keeps the existing timing/thermal guard and a fixed 100-frame
pre-wake and 100-frame wake window. A timing stop ends that trial; the next
predeclared trial starts a fresh app/session after a health check and cooldown.
An early stop censors its window and must never be reported as a complete pass.
"""
import argparse, datetime, json, os, pathlib, re, subprocess, sys, time, uuid
from paired_app import health, sha, PACKAGE, ACTIVITY

ROOT=pathlib.Path(__file__).resolve().parent
ORDER='ABBABAABBAABABBA'
TIMING_STOPS={'100 ms timing limit reached; test stopped',
              '100-frame p95 timing limit reached; test stopped'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adb',required=True);p.add_argument('--serial',required=True)
    for name in ('control-apk','candidate-apk','rollback-apk','client-path','output'):
        p.add_argument('--'+name,type=pathlib.Path,required=True)
    p.add_argument('--rollback-sha256',required=True)
    p.add_argument('--source-sha256',required=True);p.add_argument('--source-bytes',type=int,required=True)
    p.add_argument('--order',default=ORDER)
    p.add_argument('--trace',action='store_true',help='Diagnostic only; exclude traced runs from latency comparison')
    a=p.parse_args()
    if not re.fullmatch(r'(?:AB|BA){1,16}',a.order):p.error('Expected complete AB/BA pairs')
    if sha(a.rollback_apk)!=a.rollback_sha256:p.error('Rollback hash mismatch')
    if not re.fullmatch(r'[0-9a-f]{64}',a.source_sha256) or a.source_bytes<=0:p.error('Invalid source identity')
    apks={'A':a.control_apk,'B':a.candidate_apk}
    hashes={k:sha(v) for k,v in apks.items()}
    a.output.mkdir(parents=True,exist_ok=False)
    def adb(*args,timeout=30):
        return subprocess.run([a.adb,'-s',a.serial,*args],check=True,capture_output=True,text=True,timeout=timeout).stdout.strip()
    remote_prefix='jetlink-wake-'+uuid.uuid4().hex[:12]
    manifest={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'order':a.order,'variant_A':'burst 5','variant_B':'high performance 3',
        'apk_sha256':hashes,'rollback_sha256':a.rollback_sha256,'traced':a.trace,
        'warmup_frames':100,'baseline_frames':100,'wake_frame':200,'wake_window_frames':100,
        'primary':'mean phone latency in fixed frame IDs 200..299; incomplete windows are censored',
        'secondary':['wake maximum','wake p95','frames >50 ms','timing stops','baseline mean'],
        'transport':'desk ADB/TCP; not direct comma USB','runs':[],'failures':[]}
    def save():(a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    save();changed=False;forwarded=False
    env=dict(os.environ,PYTHONPATH=str(a.client_path.resolve()))
    try:
        if adb('get-state')!='device':raise RuntimeError('Device unavailable')
        health(adb)
        if ':5599' not in adb('shell','ss','-ltn'):raise RuntimeError('Listener must be enabled in JetLink')
        if any('tcp:5599' in line.split()[1:2] for line in adb('forward','--list').splitlines()):raise RuntimeError('Port 5599 already forwarded')
        adb('forward','tcp:5599','tcp:5599');forwarded=True
        for index,variant in enumerate(a.order):
            before=health(adb);changed=True
            adb('install','-r',str(apks[variant]),timeout=120)
            adb('shell','am','start','-n',ACTIVITY)
            adb('shell','input','keyevent','223')
            time.sleep(10)
            if ':5599' not in adb('shell','ss','-ltn'):raise RuntimeError('Listener unavailable after restart')
            name=f'{index+1:02d}-{variant}'
            trace=None
            if a.trace:
                config=a.output/(name+'.pbtxt')
                config.write_text((ROOT/'app-scheduler.pbtxt').read_text().replace('120000','35000'))
                remote=f'/data/local/tmp/{remote_prefix}-{name}.pbtxt'
                trace=f'/data/misc/perfetto-traces/{remote_prefix}-{name}.pftrace'
                adb('push',str(config),remote)
                adb('shell',f'cat {remote} | perfetto --txt -c - -o {trace} --background-wait')
                trace_started=time.monotonic()
            result=a.output/(name+'.json')
            cmd=[sys.executable,'-X','utf8',str(ROOT.parent/'benchmark.py'),'--port','5599',
                '--source-sha256',a.source_sha256,'--source-bytes',str(a.source_bytes),
                '--frames','200','--warmup','100','--wake-frame','200',
                '--transport',manifest['transport']+'; controlled wake '+variant,
                '--adb',a.adb,'--serial',a.serial,'--output',str(result),
                '--frame-output',str(a.output/(name+'-frames.json'))]
            with (a.output/(name+'.log')).open('w',encoding='utf-8') as log:
                run=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=100)
            if trace:
                time.sleep(max(0,trace_started+38-time.monotonic()))
                adb('pull',trace,str(a.output/(name+'.pftrace')))
                adb('shell','rm','-f',remote,trace)
            row=json.loads(result.read_text())
            item={'run':index+1,'variant':variant,'before':before,'after':health(adb),
                  'returncode':run.returncode,'result':result.name,'measured_frames':row['measured_frames'],
                  'failures':row['failures'],'server_total':row.get('server_total')}
            manifest['runs'].append(item);save();print(json.dumps(item),flush=True)
            if any(f not in TIMING_STOPS for f in row['failures']):raise RuntimeError('Non-timing failure; stopping experiment')
            if not row['failures'] and (not row['protocol_pass'] or row['measured_frames']!=200):raise RuntimeError('Incomplete trial without a recorded timing stop')
            if not row.get('wake_stimulus',{}).get('command_completed'):raise RuntimeError('Wake stimulus missing or failed')
            if run.returncode not in (0,1):raise RuntimeError('Unexpected benchmark exit')
    except Exception as error:
        manifest['failures'].append(str(error));raise
    finally:
        if changed:
            try:
                adb('install','-r',str(a.rollback_apk),timeout=120)
                adb('shell','am','start','-n',ACTIVITY)
                manifest['rollback']='original APK reinstalled and launched'
            except Exception as error:manifest['rollback']='FAILED: '+str(error)
        if forwarded:
            try:adb('forward','--remove','tcp:5599')
            except Exception as error:manifest['forward_cleanup']=str(error)
        save()
        if manifest.get('rollback','').startswith('FAILED:'):raise RuntimeError(manifest['rollback'])

if __name__=='__main__':main()
