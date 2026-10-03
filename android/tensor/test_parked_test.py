"""The parked harness must release its loan and refuse onroad operation."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import numpy as np


class ParkedHarnessTests(unittest.TestCase):
    def run_harness(self, *, onroad=False, bad_peer=False, bad_output=False, close_error=False, legacy=False, release_error=False, open_error=False, connect_error=False, bad_health=False, health_lost=False, slow=False, ignition_on=False, readiness_error=False, motion_error=False, monitor_close_error=False, lock_error=False, slow_usb=False, interrupted=False):
        loan = types.SimpleNamespace(closed=False)
        loan.close = lambda: setattr(loan, 'closed', True)
        client = types.SimpleNamespace(closed=False)
        def close_client():
            client.closed = True
            if close_error: raise RuntimeError('close failed')
        client.close = close_client
        client.t = types.SimpleNamespace(send_json=lambda *args: None, link_info=lambda: {'kind':'usb','usb_speed':'high-speed' if slow_usb else 'super-speed'})
        client.hello = lambda **kw: {'validation':'parked_only','device':'wrong' if bad_peer else 'tensor-Tensor_G6'}
        spec = types.SimpleNamespace(output_nelem=18452,warped_nbytes=12,warped_shape=(2,6,1,1),packed_nelem=4,
                                     packed_layout={'traffic_convention':(slice(0,2),None),'action_t':(slice(2,4),None)})
        client.ensure_engine = lambda *a,**kw: spec
        good_health={'device_health': {'sample_age_s':0.1,'thermal_status':0,'battery_c':25.0}}
        state_reads=[]
        def read_state(**kw):
            state_reads.append(True)
            return {'device_health': {'sample_age_s':0.1,'thermal_status':3,'battery_c':25.0}} if bad_health else good_health
        client.state=read_state
        client.last_state = {} if health_lost else good_health
        client.last_timings = (110000,10,110010) if slow else (100,10,110)
        handlers={}
        infer_deadlines=[]
        def infer(*a,**kw):
            infer_deadlines.append(kw['deadline'])
            if interrupted: handlers[module.signal.SIGTERM]()
            return np.array([np.nan] if bad_output else [0.0],dtype=np.float32)
        client.infer=infer
        changes = []
        state = {'IsOffroad': not onroad, 'JetlinkEnabled': True}
        def put_bool(key, value, **kw):
            changes.append((key, value))
            state[key] = value
        events=[]
        test_lock=io.StringIO()
        guard=types.SimpleNamespace(active=False,closed=False,checks=0)
        def prepare():
            self.assertTrue(state['JetlinkEnabled'])
            events.append('prepare')
        def require_disabled():
            self.assertFalse(state['JetlinkEnabled'])
            events.append('disabled')
        def ready(timeout):
            self.assertFalse(state['JetlinkEnabled'])
            events.append('ready')
            if readiness_error: raise RuntimeError('not stationary')
            guard.active=True
        def check():
            if guard.active:
                guard.checks+=1
                if motion_error and guard.checks>=6: raise RuntimeError('Vehicle moved')
        def stop_guard():
            self.assertFalse(state['JetlinkEnabled'])
            guard.closed=True
            if monitor_close_error: raise RuntimeError('monitor close failed')
        guard.prepare=prepare;guard.require_disabled=require_disabled;guard.wait_until_ready=ready
        guard.check=check;guard.close=stop_guard;guard.summary=lambda: {'phase':'active'}
        modules = {
            'openpilot.common.params': types.SimpleNamespace(Params=lambda: types.SimpleNamespace(get_bool=lambda key: state[key], put_bool=put_bool)),
            'jetlink.comma.lending': types.SimpleNamespace(borrow=lambda **kw: loan),
        }
        with patch.dict(sys.modules,modules):
            descriptor=importlib.util.spec_from_file_location('parked_harness',Path(__file__).with_name('parked-test.py'))
            module=importlib.util.module_from_spec(descriptor);descriptor.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as d, patch.object(module.JetlinkClient,'open_loan',return_value=client), \
             patch.object(module.JetlinkClient,'open_ffs',return_value=client,side_effect=RuntimeError('open failed') if open_error else None), \
             patch.object(module,'wait_legacy_release',side_effect=RuntimeError('release failed') if release_error else None), \
             patch.object(module,'acquire_test_lock',return_value=test_lock,side_effect=RuntimeError('lock occupied') if lock_error else None), \
             patch.dict(sys.modules,{'stationary':types.SimpleNamespace(IgnitionGuard=lambda params:guard)}), \
             patch.object(module,'wait_usb_host',side_effect=RuntimeError('connect timed out') if connect_error else None), \
             patch.object(module.signal,'signal',side_effect=lambda sig,handler:handlers.__setitem__(sig,handler)),patch.object(module.signal,'alarm'),patch.object(module.time,'sleep'), \
             patch.object(sys,'argv',['parked-test.py','--frames','20','--output',str(Path(d)/'result.json')]+(['--legacy-owner'] if legacy else [])+(['--ignition-on'] if ignition_on else [])), \
             contextlib.redirect_stdout(io.StringIO()):
            if onroad:
                with self.assertRaisesRegex(RuntimeError,'Ignition'): module.main()
                self.assertFalse(loan.closed)
                self.assertEqual(changes, [])
                return
            status=module.main()
            report=json.loads((Path(d)/'result.json').read_text())
            if status==0:
                self.assertEqual(report['warmup_completed'],20)
                self.assertEqual(len(report['warmup_timings']),20)
                self.assertEqual(infer_deadlines[:20],[2]*20)
                self.assertEqual(infer_deadlines[20:],[0.2 if ignition_on else 2]*20)
            if readiness_error or connect_error or bad_peer:
                self.assertEqual(state_reads,[], 'Do not send a health request before a valid peer handshake')
            if bad_health:
                self.assertEqual(json.loads((Path(d)/'result.json').read_text())['health_at_stop']['thermal_status'],3)
            self.assertEqual(loan.closed, not legacy and not lock_error)
            self.assertEqual(client.closed, not release_error and not open_error and not lock_error)
            self.assertEqual(changes, [('JetlinkEnabled', False), ('JetlinkEnabled', True)] if legacy and not lock_error else [])
            if not lock_error: self.assertTrue(test_lock.closed)
            if ignition_on:
                self.assertTrue(guard.closed)
                if not release_error and not open_error and not lock_error: self.assertEqual(events,['prepare','disabled','ready'])
            self.assertTrue(state['JetlinkEnabled'])
            self.assertEqual(status,1 if bad_peer or bad_output or close_error or release_error or open_error or connect_error or bad_health or health_lost or slow or readiness_error or motion_error or monitor_close_error or lock_error or slow_usb or interrupted else 0)

    def test_signal_interrupt_closes_usb_and_restores(self): self.run_harness(legacy=True,ignition_on=True,interrupted=True)
    def test_stationary_ignition_sequence(self): self.run_harness(legacy=True,ignition_on=True)
    def test_stationary_readiness_failure_restores(self): self.run_harness(legacy=True,ignition_on=True,readiness_error=True)
    def test_motion_during_test_restores(self): self.run_harness(legacy=True,ignition_on=True,motion_error=True)
    def test_monitor_close_failure_still_restores(self): self.run_harness(legacy=True,ignition_on=True,monitor_close_error=True)
    def test_lock_failure_changes_nothing(self): self.run_harness(legacy=True,lock_error=True)
    def test_usb2_refuses_and_restores(self): self.run_harness(legacy=True,slow_usb=True)

    def test_initial_hot_phone_restores_enable(self): self.run_harness(legacy=True,bad_health=True)
    def test_lost_telemetry_restores_enable(self): self.run_harness(legacy=True,health_lost=True)
    def test_latency_stop_restores_enable(self): self.run_harness(legacy=True,slow=True)

    def test_ignition_on_refuses_before_borrowing(self): self.run_harness(onroad=True)
    def test_wrong_peer_releases_loan(self): self.run_harness(bad_peer=True)
    def test_nonfinite_output_releases_loan(self): self.run_harness(bad_output=True)
    def test_client_close_failure_still_releases_loan(self): self.run_harness(close_error=True)
    def test_success_releases_loan(self): self.run_harness()
    def test_legacy_success_restores_enable(self): self.run_harness(legacy=True)
    def test_legacy_wrong_peer_restores_enable(self): self.run_harness(legacy=True,bad_peer=True)
    def test_legacy_release_failure_restores_enable(self): self.run_harness(legacy=True,release_error=True)
    def test_legacy_open_failure_restores_enable(self): self.run_harness(legacy=True,open_error=True)
    def test_legacy_close_failure_restores_enable(self): self.run_harness(legacy=True,close_error=True)
    def test_legacy_connect_timeout_restores_enable(self): self.run_harness(legacy=True,connect_error=True)
    def test_legacy_ignition_on_refuses_before_disabling(self): self.run_harness(legacy=True,onroad=True)


class ConnectionWaitTests(unittest.TestCase):
    def setUp(self):
        modules={'openpilot.common.params': types.SimpleNamespace(Params=lambda: None),
                 'jetlink.comma.lending': types.SimpleNamespace(borrow=lambda **kw: None)}
        with patch.dict(sys.modules,modules):
            descriptor=importlib.util.spec_from_file_location('parked_connection_wait',Path(__file__).with_name('parked-test.py'))
            self.module=importlib.util.module_from_spec(descriptor);descriptor.loader.exec_module(self.module)
        self.client=types.SimpleNamespace(t=types.SimpleNamespace(bound_udc='fake-udc',link_info=lambda: {'kind':'usb'}))

    def test_exclusive_lock_is_released_by_close(self):
        with tempfile.TemporaryDirectory() as d:
            real_open=open
            with patch('builtins.open',side_effect=lambda *a,**k: real_open(Path(d)/'lock','a')):
                first=self.module.acquire_test_lock()
                try:
                    with self.assertRaisesRegex(RuntimeError,'already running'): self.module.acquire_test_lock()
                finally: first.close()
                self.module.acquire_test_lock().close()

    def test_waits_for_configuration_without_opening_endpoint_files(self):
        parked=unittest.mock.Mock()
        with patch.object(Path,'read_text',side_effect=['not attached','addressed','configured']), \
             patch.object(self.module.time,'sleep'), contextlib.redirect_stdout(io.StringIO()):
            self.module.wait_usb_host(self.client,parked,60)
        self.assertEqual(parked.call_count,3)

    def test_ignition_change_aborts_while_waiting(self):
        def onroad(): raise RuntimeError('Ignition on')
        with self.assertRaisesRegex(RuntimeError,'Ignition'), contextlib.redirect_stdout(io.StringIO()):
            self.module.wait_usb_host(self.client,onroad,60)

    def test_network_loan_is_not_reported_as_direct_usb(self):
        self.client.t.link_info=lambda: {'kind':'tcp'}
        with self.assertRaisesRegex(RuntimeError,'direct USB'):
            self.module.wait_usb_host(self.client,lambda: None,60)

    def test_missing_host_times_out(self):
        with patch.object(self.module.time,'monotonic',side_effect=[0,61]), \
             self.assertRaisesRegex(RuntimeError,'connection window'), contextlib.redirect_stdout(io.StringIO()):
            self.module.wait_usb_host(self.client,lambda: None,60)


if __name__=='__main__': unittest.main()