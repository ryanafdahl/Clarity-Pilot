"""Local desk experiment: eight predeclared pairs, then restore the original APK.

Requires the exact Pixel already connected, healthy, with JetLink's desk listener
enabled. It never enables a listener, changes thermal policy or uses the comma.
Trace collection is deliberately OFF for this latency comparison.
"""
import argparse, datetime, hashlib, json, os, pathlib, random, re, subprocess, sys, time

ROOT=pathlib.Path(__file__).resolve().parent
PACKAGE='io.zoompilot.jetlink.android'
ACTIVITY=PACKAGE+'/io.zoompilot.jetlink.MainActivity'
PAIRS=['AB']*4+['BA']*4
random.Random(20261011).shuffle(PAIRS)
ORDER=''.join(PAIRS)
def health(adb):
    b=re.search(r'temperature:\s*(\d+)',adb('shell','dumpsys','battery'))
    t=re.search(r'Thermal Status: (\d+)',adb('shell','dumpsys','thermalservice'))
    if not b or not t: raise RuntimeError('Phone health unavailable')
    result={'battery_c':int(b[1])/10,'thermal_status':int(t[1])}
    if result['battery_c']>=43 or result['thermal_status']>=3: raise RuntimeError('Phone thermal stop')
    return result

def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adb',default='adb')
    p.add_argument('--serial',required=True)
    p.add_argument('--control-apk',type=pathlib.Path,required=True)
    p.add_argument('--candidate-apk',type=pathlib.Path,required=True)
    p.add_argument('--rollback-apk',type=pathlib.Path,required=True)
    p.add_argument('--rollback-sha256',required=True)
    p.add_argument('--client-path',type=pathlib.Path,required=True,help='Compatible JetLink Python source checkout')
    p.add_argument('--source-sha256',required=True)
    p.add_argument('--source-bytes',type=int,required=True)
    p.add_argument('--output',type=pathlib.Path,required=True)
    a=p.parse_args()
    if sha(a.rollback_apk)!=a.rollback_sha256.lower(): p.error('Rollback APK hash mismatch')
    if not re.fullmatch('[0-9a-f]{64}',a.source_sha256) or a.source_bytes<=0: p.error('Invalid source identity')
    apks={'A':a.control_apk,'B':a.candidate_apk}
    hashes={k:sha(v) for k,v in apks.items()}
    a.output.mkdir(parents=True,exist_ok=False)
    def adb(*args, timeout=30):
        return subprocess.run([a.adb,'-s',a.serial,*args],capture_output=True,text=True,
            check=True,timeout=timeout).stdout.strip()
    manifest={'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'order':ORDER,'pairs':8,'frames_per_run':600,'warmup_frames':100,
        'order_design':'four AB and four BA pairs, shuffled once before testing with seed 20261011',
        'variant_A':'trace-only nice 0 control','variant_B':'same trace points, session nice -4',
        'comparison':'paired run means and quantiles; frames are not independent replicates',
        'apk_sha256':hashes,'rollback_sha256':a.rollback_sha256,
        'source_sha256':a.source_sha256,
        'transport':'desk ADB/TCP; not direct comma USB','runs':[],'failures':[]}
    def save(): (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    save()
    env=dict(os.environ,PYTHONPATH=str(a.client_path.resolve()))
    changed=False
    forwarded=False
    try:
        if adb('get-state')!='device': raise RuntimeError('Requested device unavailable')
        health(adb)
        if ':5599' not in adb('shell','ss','-ltn'): raise RuntimeError('JetLink desk listener is not enabled')
        if any('tcp:5599' in line.split()[1:2] for line in adb('forward','--list').splitlines()):
            raise RuntimeError('Local port 5599 already forwarded; preserve it and choose a clean test setup')
        adb('forward','tcp:5599','tcp:5599')
        forwarded=True
        for index,variant in enumerate(ORDER):
            before=health(adb)
            # Every run reinstalls/restarts, including repeated same-variant runs.
            changed=True
            adb('install','-r',str(apks[variant]),timeout=120)
            adb('shell','am','start','-n',ACTIVITY)
            adb('shell','input','keyevent','223')  # same screen-off condition in every run
            deadline=time.monotonic()+30
            while ':5599' not in adb('shell','ss','-ltn'):
                if time.monotonic()>deadline: raise RuntimeError('Listener did not return after app restart')
                time.sleep(1)
            name=f'{index+1:02d}-{variant}'
            result=a.output/(name+'.json')
            command=[sys.executable,'-X','utf8',str(ROOT.parent/'benchmark.py'),
                '--port','5599','--source-sha256',a.source_sha256,
                '--source-bytes',str(a.source_bytes),'--frames','600','--warmup','100',
                '--transport',manifest['transport']+f'; repeated scheduling variant {variant}',
                '--adb',a.adb,'--serial',a.serial,'--output',str(result),
                '--frame-output',str(a.output/(name+'-frames.json'))]
            with (a.output/(name+'.log')).open('w',encoding='utf-8') as log:
                proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=env)
                try:
                    # One bounded process snapshot after warmup starts, outside phone work.
                    time.sleep(12)
                    pid=adb('shell','pidof',PACKAGE)
                    if not re.fullmatch(r'\d+',pid): raise RuntimeError('App PID unavailable')
                    (a.output/(name+'-threads.txt')).write_text(adb('shell','ps','-T','-p',pid,'-o','PID,TID,NI,NAME'))
                    code=proc.wait(timeout=100)
                finally:
                    if proc.poll() is None: proc.terminate(); proc.wait(timeout=10)
            row=json.loads(result.read_text())
            item={'run':index+1,'variant':variant,'before':before,'after':health(adb),
                'returncode':code,'result':result.name,'server_total':row.get('server_total')}
            manifest['runs'].append(item);save()
            print(json.dumps(item),flush=True)
            if code or not row['protocol_pass']: raise RuntimeError('Benchmark failed its existing guard')
    except Exception as e:
        manifest['failures'].append(str(e));raise
    finally:
        if changed:
            try:
                adb('install','-r',str(a.rollback_apk),timeout=120)
                adb('shell','am','start','-n',ACTIVITY)
                manifest['rollback']='provided rollback APK reinstalled and launched'
            except Exception as e: manifest['rollback']='FAILED: '+str(e)
        if forwarded:
            try: adb('forward','--remove','tcp:5599')
            except Exception as e: manifest['forward_cleanup']=str(e)
        save()
        if manifest.get('rollback','').startswith('FAILED:'):
            raise RuntimeError(manifest['rollback'])

if __name__=='__main__': main()
