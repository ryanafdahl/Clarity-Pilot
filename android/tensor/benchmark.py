"""Bounded synthetic JetLink benchmark. Run with upstream JetLink on PYTHONPATH.

ADB forwarding is a desk transport, not the comma's direct USB protocol.
The optional ADB thermal monitor stops at Android severe or battery 43 C.
"""
import argparse
import datetime
import json
from pathlib import Path
import re
import subprocess
import threading
import time
import numpy as np
from validation import TimingGuard, device_health, first_health
from jetlink.client import JetlinkClient
from scripts.verify_parity import make_inputs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=5599)
    p.add_argument('--source-sha256', required=True)
    p.add_argument('--source-bytes', type=int, required=True)
    p.add_argument('--frames', type=int, default=1200)
    p.add_argument('--warmup', type=int, default=20)
    p.add_argument('--period-ms', type=float, default=50)
    p.add_argument('--transport', required=True)
    p.add_argument('--adb', help='ADB executable for bounded thermal sampling')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists(): p.error('output already exists; choose a new filename')
    if not 10 <= a.frames <= 36000 or not 0 <= a.warmup <= 100 or not 0 <= a.period_ms <= 1000:
        p.error('frames 10..36000, warmup 0..100, period 0..1000 ms required')
    samples, rows = [], []
    phone_samples = []
    guard = TimingGuard()
    stop = threading.Event()
    unsafe = threading.Event()
    failures = []

    def thermal():
        while not stop.is_set():
            try:
                def dump(service):
                    return subprocess.run([a.adb, 'shell', 'dumpsys', service], check=True,
                        capture_output=True, text=True, timeout=5).stdout
                t = re.search(r'Thermal Status: (\d+)', dump('thermalservice'))
                b = re.search(r'temperature:\s*(\d+)', dump('battery'))
                if not t or not b:
                    raise RuntimeError('Thermal readings unavailable')
                sample = {'elapsed_s': round(time.monotonic()-started, 1), 'status': int(t[1]), 'battery_c': int(b[1])/10}
                samples.append(sample)
                if sample['status'] >= 3 or sample['battery_c'] >= 43:
                    failures.append('Thermal stop threshold reached'); unsafe.set(); return
            except Exception as e:
                failures.append(f'Thermal monitor: {e}'); unsafe.set(); return
            stop.wait(10)

    started = time.monotonic()
    monitor = threading.Thread(target=thermal, daemon=True) if a.adb else None
    c = None
    result = {'date_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'transport': a.transport, 'source_sha256': a.source_sha256, 'warmup_frames': a.warmup,
              'requested_frames': a.frames, 'period_ms': a.period_ms}
    try:
        c = JetlinkClient.open_tcp(a.host, a.port, want_hidden=True)
        hello = c.hello()
        result.update(backend=hello.get('backend'), device=hello.get('device'))
        phone_samples.append(dict(first_health(c), elapsed_s=round(time.monotonic()-started,3)))
        spec = c.ensure_engine(a.source_sha256, a.source_bytes)
        frames = make_inputs(spec, 32, seed=17)
        if monitor: monitor.start()
        first_health(c)
        due = time.perf_counter()
        for i in range(a.frames+a.warmup):
            if unsafe.is_set(): break
            time.sleep(max(0, due-time.perf_counter()))
            begin = time.perf_counter()
            output = c.infer(*frames[i % len(frames)], frame_id=i, reset=(i == 0), want_state=True)
            elapsed = (time.perf_counter()-begin)*1000
            if not np.isfinite(output).all(): raise RuntimeError(f'Non-finite frame {i}')
            health = device_health(c.last_state)
            if i % 20 == 0: phone_samples.append(dict(health, elapsed_s=round(time.monotonic()-started,3), frame=i))
            if i >= a.warmup:
                row = [elapsed]+[v/1000 for v in c.last_timings]
                rows.append(row)
                guard.observe(row, time.monotonic()-started)
            due = max(due+a.period_ms/1000, time.perf_counter())
            if i and i % 1200 == 0: print(f'{len(rows)} measured frames, last server {c.last_timings[2]/1000:.2f} ms', flush=True)
    except Exception as e:
        failures.append(str(e))
        if c:
            try: result['health_at_stop'] = c.state(timeout=1).get('device_health')
            except Exception as health_error: result['health_at_stop_error'] = str(health_error)
    finally:
        if c:
            try: c.close()
            except Exception as e: failures.append(f'Cleanup: {e}')
        stop.set()
        if monitor and monitor.is_alive(): monitor.join(12)
        result.update(measured_frames=len(rows), finite_frames=len(rows), failures=failures,
                      elapsed_s=time.monotonic()-started, thermal_samples=samples, phone_thermal_samples=phone_samples,
                      blocks_100=guard.blocks, driving_ready=False,
                      server_guard='100-frame server p95 <50 ms and each server time <100 ms')
        data = np.asarray(rows)
        if len(rows):
            for i, name in enumerate(['round_trip','inference','queues','server_total']):
                v = data[:,i]
                result[name] = {'mean_ms':float(v.mean()),'p50_ms':float(np.percentile(v,50)),
                    'p95_ms':float(np.percentile(v,95)),'p99_ms':float(np.percentile(v,99)),
                    'max_ms':float(v.max()),'over_50ms':int((v>50).sum())}
            result['blocks_1200'] = [{'start_frame':i, 'frames':len(data[i:i+1200]),
                'round_trip_p95_ms':float(np.percentile(data[i:i+1200,0],95)),
                'server_p95_ms':float(np.percentile(data[i:i+1200,3],95))} for i in range(0,len(rows),1200)]
        result['protocol_pass']=len(rows)==a.frames and not failures
        result['server_timing_pass']=result['protocol_pass'] and result.get('server_total',{}).get('p95_ms',float('inf'))<50 and result.get('server_total',{}).get('max_ms',float('inf'))<100
        result['round_trip_timing_pass']=result['protocol_pass'] and result.get('round_trip',{}).get('p95_ms',float('inf'))<50 and result.get('round_trip',{}).get('max_ms',float('inf'))<100
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(result,indent=2)+'\n', encoding='utf-8')
        print(json.dumps(result,indent=2), flush=True)
    return 0 if result['server_timing_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())