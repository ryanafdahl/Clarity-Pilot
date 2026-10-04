#!/usr/bin/env python3
"""Supervised Tensor USB test. Ignition-off by default; --ignition-on pre-arms isolation.

Uses the JetLink loan API by default. --legacy-owner temporarily disables
Accelerator Link, waits for its older daemon to exit, and restores the setting
after closing USB. --ignition-on must start with the car off, then waits for
fresh stationary vehicle data after ignition starts. Never changes engine
readiness or publishes model/control outputs. Run only while at the car.
"""
import argparse
import datetime
import json
import fcntl
from pathlib import Path
import signal
import sys
import time
import numpy as np
from validation import TimingGuard, device_health, first_health

sys.path.insert(0, '/data/openpilot')
sys.path.insert(0, '/data/openpilot/jetlink_repo')
from openpilot.common.params import Params
from jetlink import protocol as P
from jetlink.client import JetlinkClient
from jetlink.comma.lending import borrow

SOURCE = '09d080f36965bb2a0790500452bd328aa03c484d0222aa79d1ad9f021a522aec'
SOURCE_BYTES = 766040736


def active_processes():
    for entry in Path('/proc').glob('[0-9]*/cmdline'):
        try: yield entry.read_bytes().split(b'\0')
        except OSError: continue


def wait_legacy_release(parked, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        parked()
        running = any(b'openpilot.sunnypilot.accelerators.jetlink.jetlinkd' in argv
                      for argv in active_processes())
        bound = Path('/sys/kernel/config/usb_gadget/jetlink/UDC').read_text().strip()
        if not running and not bound: return
        time.sleep(0.2)
    raise RuntimeError('Legacy USB owner did not release the gadget; test refused')


def wait_usb_host(client, parked, timeout):
    if client.t.link_info().get('kind') != 'usb':
        raise RuntimeError('This test requires direct USB, not a network loan')
    udc = client.t.bound_udc
    if not udc: raise RuntimeError('USB controller is not bound')
    state = Path('/sys/class/udc') / udc / 'state'
    end = time.monotonic() + timeout
    print(f'Waiting up to {timeout}s for the Pixel USB connection; accept any phone prompt.', flush=True)
    while time.monotonic() < end:
        parked()
        if state.read_text().strip() == 'configured':
            return
        time.sleep(0.2)
    raise RuntimeError('Pixel did not configure USB within the connection window')


def acquire_test_lock():
    handle = open('/dev/shm/clarity-pixel-test.lock', 'a')
    try: fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        handle.close()
        raise RuntimeError('Another Pixel USB test is already running')
    return handle


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--frames', type=int, default=1200)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--connect-timeout', type=int, default=60, help='seconds to reconnect USB (10..120)')
    p.add_argument('--legacy-owner', action='store_true',
                   help='temporarily release the older offroad daemon and restore Accelerator Link afterward')
    p.add_argument('--ignition-on', action='store_true', help='arm while offroad, then test in Park with ignition/A/C on')
    p.add_argument('--ignition-timeout', type=int, default=180, help='seconds to start the car and obtain stationary state (30..300)')
    a = p.parse_args()
    if Path('/data/openpilot/openpilot/sunnypilot/jetlink_adapter').is_dir():
        p.error('This Pixel test requires a new startup/USB ownership review for the updated comma; no test was armed')
    if a.ignition_on and not a.legacy_owner: p.error('--ignition-on requires --legacy-owner for this deployment')
    if not 30 <= a.ignition_timeout <= 300: p.error('ignition-timeout must be 30..300')
    if not 20 <= a.frames <= 6000: p.error('frames must be 20..6000')
    if not 10 <= a.connect_timeout <= 120: p.error('connect-timeout must be 10..120')
    if a.output.exists(): p.error('output already exists; choose a new filename')
    params = Params()
    ignition = None
    if a.ignition_on:
        from stationary import IgnitionGuard
        ignition = IgnitionGuard(params)
        try: ignition.prepare()
        except BaseException:
            ignition.close()
            raise
    def parked():
        if ignition:
            ignition.check()
            return
        if not params.get_bool('IsOffroad'):
            raise RuntimeError('Ignition must stay off; test stopped')
    try:
        parked()
        if not params.get_bool('JetlinkEnabled'):
            raise RuntimeError('Enable Accelerator Link while parked before this test')
    except BaseException:
        if ignition: ignition.close()
        raise
    for argv in active_processes():
        if any(Path(v.decode(errors='replace')).name in ('modeld', 'camerad') or v == b'openpilot.selfdrive.modeld.modeld' for v in argv):
            if ignition: ignition.close()
            raise RuntimeError('Camera/model processes are active; test refused')
    def interrupted(*_): raise RuntimeError('Test interrupted or timed out')
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGALRM, signal.SIGHUP): signal.signal(sig, interrupted)
    signal.alarm(max(180, a.frames // 10) + a.connect_timeout + 60 + (a.ignition_timeout if ignition else 0))
    client = loan = test_lock = None
    restore_link = False
    peer_ready = False
    rows = []
    samples = []
    started = time.monotonic()
    guard = TimingGuard(direct_usb=True)
    report = {'date_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'source_sha256':SOURCE, 'transport':'direct comma USB', 'driving_ready':False,
              'requested_frames':a.frames, 'warmup_frames':20, 'failures':[],
              'usb_ownership':'legacy exclusive' if a.legacy_owner else 'loan',
              'ignition_mode':'on_stationary' if ignition else 'off',
              'phase':'usb_isolation','warmup_completed':0,'warmup_timings':[],
              'warmup_transport_deadline_s':2,'measured_transport_deadline_s':0.2 if ignition else 2}
    try:
        test_lock = acquire_test_lock()
        parked()
        if a.legacy_owner:
            restore_link = True
            params.put_bool('JetlinkEnabled', False, block=True)
            wait_legacy_release(parked)
            if ignition: ignition.require_disabled()
            client = JetlinkClient.open_ffs('/dev/ffs-jetlink',
                gadget='/sys/kernel/config/usb_gadget/jetlink',
                name='clarity-parked-test', want_hidden=True, deadline=2)
        else:
            loan = borrow(name='clarity-parked-test', timeout=10)
            if loan is None: raise RuntimeError('JetLink owner could not lend USB; no settings were changed')
            parked()
            client = JetlinkClient.open_loan(loan, name='clarity-parked-test', want_hidden=True, deadline=2)
        report['phase']='waiting_for_stationary_vehicle'
        if ignition: ignition.wait_until_ready(a.ignition_timeout)
        report['phase']='waiting_for_phone'
        wait_usb_host(client, parked, a.connect_timeout)
        report['link'] = client.t.link_info()
        report['phase']='hello'
        hello = client.hello(timeout=20)
        parked()
        if hello.get('validation') != 'parked_only' or hello.get('device') != 'tensor-Tensor_G6':
            raise RuntimeError('Expected the Tensor G6 parked-only app; peer did not match')
        peer_ready = True
        report['runtime'] = hello.get('runtime_version')
        report['link'] = client.t.link_info()
        if report['link'].get('usb_speed') not in ('super-speed', 'super-speed-plus'):
            raise RuntimeError('USB SuperSpeed is required for this validation')
        samples.append(dict(first_health(client), elapsed_s=round(time.monotonic()-started,3)))
        parked()
        send_json = client.t.send_json
        def parked_request(kind, seq, data, flags=0):
            if kind == P.Msg.ENGINE_REQ: data = dict(data, validation_mode='parked')
            return send_json(kind, seq, data, flags)
        client.t.send_json = parked_request
        report['phase']='engine_setup'
        spec = client.ensure_engine(SOURCE, SOURCE_BYTES, frame_skip=4, build_timeout=30)
        if spec.output_nelem != 18452: raise RuntimeError('Unexpected output shape')
        # Deterministic synthetic image; features/desires are queued by the server.
        warped = np.arange(spec.warped_nbytes, dtype=np.uint8).reshape(spec.warped_shape)
        packed = np.zeros(spec.packed_nelem,np.float32)
        for name,(at,_) in spec.packed_layout.items():
            if name == 'traffic_convention': packed[at] = [1,0]
            if name == 'action_t': packed[at] = [0.25,0.35]
        first_health(client)
        due = time.monotonic()
        for i in range(a.frames+20):
            parked()
            time.sleep(max(0,due-time.monotonic()))
            parked()
            report['phase']='warmup' if i<20 else 'measured'
            report['attempted_frame_id']=i
            start = time.monotonic()
            out = client.infer(warped,packed,frame_id=i,reset=(i==0),want_state=True,deadline=0.2 if ignition and i>=20 else 2)
            elapsed=(time.monotonic()-start)*1000
            parked()
            if not np.isfinite(out).all(): raise RuntimeError('Non-finite output')
            health = device_health(client.last_state)
            if i % 20 == 0: samples.append(dict(health, elapsed_s=round(time.monotonic()-started,3), frame=i))
            if i<20:
                report['warmup_completed']+=1
                report['warmup_timings'].append({'frame_id':i,'round_trip_ms':elapsed,'server_total_ms':client.last_timings[2]/1000})
            if i>=20:
                row = [elapsed]+[v/1000 for v in client.last_timings]
                rows.append(row)
                guard.observe(row, time.monotonic()-started)
            if i==19: print('20 warm-up frames completed; starting measured frames with the unchanged timing limits.',flush=True)
            due=max(due+0.05,time.monotonic())
            if i and i%200==0: print(f'{len(rows)} measured frames; latest exchange {elapsed:.2f} ms',flush=True)
    except Exception as e:
        report['failures'].append(str(e))
        if client and peer_ready:
            try: report['health_at_stop'] = client.state(timeout=1).get('device_health')
            except Exception as health_error: report['health_at_stop_error'] = str(health_error)
    finally:
        signal.alarm(0)
        for resource in (client, loan):
            if resource:
                try: resource.close()
                except Exception as e: report['failures'].append(f'Cleanup: {e}')
        if ignition:
            try: report['vehicle_gate'] = ignition.summary()
            except Exception as e: report['failures'].append(f'Vehicle summary: {e}')
            try: ignition.close()
            except Exception as e: report['failures'].append(f'Vehicle monitor cleanup: {e}')
        if restore_link:
            try:
                params.put_bool('JetlinkEnabled', True, block=True)
                report['accelerator_link_restored'] = params.get_bool('JetlinkEnabled')
                if not report['accelerator_link_restored']:
                    raise RuntimeError('Accelerator Link did not restore')
            except Exception as e: report['failures'].append(f'Restore: {e}')
        if test_lock:
            try: test_lock.close()
            except Exception as e: report['failures'].append(f'Test lock cleanup: {e}')
        report['elapsed_s']=round(time.monotonic()-started,3)
        report['thermal_samples']=samples
        report['blocks_100']=guard.blocks
        report['timing_guard']='100-frame p95 <50 ms and each exchange/server <100 ms'
        report['measured_frames']=len(rows)
        report['protocol_pass']=len(rows)==a.frames and not report['failures']
        if rows:
            data=np.asarray(rows)
            for i,name in enumerate(['round_trip','inference','queues','server_total']):
                v=data[:,i]
                report[name]={'mean_ms':float(v.mean()),'p95_ms':float(np.percentile(v,95)),
                    'p99_ms':float(np.percentile(v,99)),'max_ms':float(v.max()),'over_50ms':int((v>50).sum())}
            report['timing_pass']=report['protocol_pass'] and report['round_trip']['p95_ms']<50 and report['round_trip']['max_ms']<100
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2),flush=True)
        print('USB test ended. Turn off Parked USB Test on the Pixel. Driving remains blocked.',flush=True)
        if ignition: print('Turn ignition off before another test or normal use; modeld keeps its small-model startup choice for this ignition cycle.',flush=True)
    return 0 if report['protocol_pass'] and report.get('timing_pass') else 1


if __name__=='__main__': raise SystemExit(main())