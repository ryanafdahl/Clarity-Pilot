"""Bounded desk-only native TPU comparisons; never changes the installed app."""
import argparse, hashlib, json, pathlib, re, statistics, subprocess, time

ROOT = None
ADB = None
SERIAL = None
REMOTE = None

def adb(*args, timeout=20):
    return subprocess.run([ADB, '-s', SERIAL, *args], capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=timeout, check=True).stdout

def health():
    battery = adb('shell', 'dumpsys battery')
    thermal = adb('shell', 'dumpsys thermalservice')
    b = re.search(r'^\s*temperature:\s*(\d+)', battery, re.M)
    t = re.search(r'Thermal Status:\s*(\d+)', thermal)
    if not b or not t:
        raise RuntimeError('Cannot read phone health; refusing benchmark')
    state = {'time': time.time(), 'battery_c': int(b[1])/10, 'thermal_status': int(t[1])}
    if state['battery_c'] >= 43 or state['thermal_status'] >= 3:
        raise RuntimeError(f'Thermal guard: {state}')
    return state

def percentile(values, p):
    values = sorted(values)
    at = (len(values)-1)*p
    lo = int(at)
    return values[lo] + (values[min(lo+1,len(values)-1)]-values[lo])*(at-lo)

def summarize(path):
    rows = []
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if '{' not in line:
            continue
        row = json.loads(line[line.index('{'):])
        if row.get('frame', -1) >= 0:
            rows.append(row)
    result = {'frames': len(rows)}
    for key in ['input_ms','invoke_ms','output_ms','total_ms','input_cpu_ms','invoke_cpu_ms','output_cpu_ms']:
        v = [r[key] for r in rows]
        result[key] = {'mean': statistics.mean(v), 'p50': percentile(v,.5), 'p95': percentile(v,.95),
                       'p99': percentile(v,.99), 'max': max(v), 'over_46': sum(x>46 for x in v), 'over_50':sum(x>50 for x in v)}
    result['slowest'] = sorted(rows,key=lambda r:r['total_ms'],reverse=True)[:5]
    return result

def stop_owned(proc, name):
    """Stop only a still-running benchmark whose recorded PID has our comm."""
    if proc.poll() is not None:
        return
    try:
        pid = adb('shell','cat',f'{REMOTE}/{name}/bench.pid').strip()
        if pid.isdigit() and int(pid)>1:
            comm = adb('shell','cat',f'/proc/{pid}/comm').strip()
            if comm == 'tensor-bench':
                adb('shell','kill','-TERM',pid)
    except Exception as cleanup_error:
        print(f'Could not stop owned benchmark: {cleanup_error}; remote timeout remains active',flush=True)
    if proc.poll() is None:
        proc.terminate()
        proc.wait(timeout=10)

def run(name, model, mode, frames, copy_inputs, metrics=False, nice=None):
    target = ROOT / name
    target.mkdir(exist_ok=False)
    states = [health()]
    adb('shell', f'mkdir -p {REMOTE}/{name}')
    command = (f'cd {REMOTE} && BENCH_PID_FILE={REMOTE}/{name}/bench.pid {"BENCH_METRICS=1 " if metrics else ""}{"BENCH_NICE="+str(nice)+" " if nice is not None else ""}LD_LIBRARY_PATH=runtime timeout {int(frames*.05)+30} '
               f'./tensor-bench runtime {model} {mode} {frames} 50000 {name} {copy_inputs}')
    with (target/'samples.jsonl').open('w',encoding='utf-8') as out, (target/'stderr.txt').open('w',encoding='utf-8') as err:
        proc = subprocess.Popen([ADB,'-s',SERIAL,'shell',command],stdout=out,stderr=err)
        deadline = time.monotonic()+frames*.05+45
        try:
            while proc.poll() is None:
                if time.monotonic()>deadline:
                    raise RuntimeError('Benchmark timeout')
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    states.append(health())
            if proc.returncode:
                raise RuntimeError(f'Benchmark failed: {proc.returncode}; see {target}')
        except BaseException:
            stop_owned(proc,name)
            raise
        finally:
            (target/'health.json').write_text(json.dumps(states,indent=2)+'\n')
    states.append(health())
    (target/'health.json').write_text(json.dumps(states,indent=2)+'\n')
    adb('pull',f'{REMOTE}/{name}/.',str(target),timeout=30)
    result = summarize(target/'samples.jsonl')
    if result['frames'] != frames:
        raise RuntimeError(f'Incomplete frames: {result["frames"]}/{frames}')
    stderr=(target/'stderr.txt').read_text(encoding='utf-8')
    hw=re.search(r'METRIC hardware_execution_time_us=(\d+)',stderr)
    executions=re.search(r'METRIC number_of_graph_executions=(\d+)',stderr)
    result['hardware_mean_ms']=(int(hw[1])/int(executions[1])/1000
        if hw and executions and int(executions[1])==frames else None)
    result.update(name=name, model=model, mode=mode, copy_inputs=copy_inputs,nice=nice,metrics_requested=metrics,
                  health=states, output_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in target.glob('output-*.bin')})
    (target/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['name','mode','frames','input_ms','invoke_ms','total_ms','output_sha256']}),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adb',default='adb',help='ADB executable')
    p.add_argument('--serial',required=True,help='Explicit desk-connected device')
    p.add_argument('--remote-dir',required=True,help='Prepared /data/local/tmp directory')
    p.add_argument('--output',type=pathlib.Path,required=True,help='Local result directory')
    p.add_argument('--model',default='model-minimal.tflite')
    p.add_argument('--prefix',required=True)
    p.add_argument('--modes',default='5,3,4,5')
    p.add_argument('--frames',type=int,default=600)
    p.add_argument('--copy-inputs',type=int,choices=[0,1],default=1)
    p.add_argument('--metrics',action='store_true')
    p.add_argument('--nice',type=int,choices=[0,-4,-10])
    a=p.parse_args()
    if not re.fullmatch(r'/data/local/tmp/[a-zA-Z0-9][a-zA-Z0-9_-]{0,80}',a.remote_dir):
        p.error('remote-dir must be one named directory inside /data/local/tmp')
    ROOT=a.output.resolve(); ADB=a.adb; SERIAL=a.serial; REMOTE=a.remote_dir
    ROOT.mkdir(parents=True,exist_ok=True)
    if not re.fullmatch(r'[a-zA-Z0-9_.-]+',a.model+a.prefix) or not 10<=a.frames<=12000:
        p.error('Invalid model, prefix or frame count')
    modes=[int(m) for m in a.modes.split(',')]
    if any(m not in [3,4,5] for m in modes): p.error('Invalid mode')
    for i,mode in enumerate(modes):
        run(f'{a.prefix}-{i}-mode{mode}',a.model,mode,a.frames,a.copy_inputs,a.metrics,a.nice)
