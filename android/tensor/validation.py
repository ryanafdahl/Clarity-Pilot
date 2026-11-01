"""Shared fail-closed health and timing checks for synthetic Tensor tests."""
import math
import time
import numpy as np


def device_health(state):
    h = state.get('device_health') if isinstance(state, dict) else None
    if not isinstance(h, dict):
        raise RuntimeError('Phone thermal telemetry is unavailable')
    def number(key):
        v = h.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise RuntimeError(f'Invalid phone telemetry: {key}')
        return v
    age, status, battery = number('sample_age_s'), number('thermal_status'), number('battery_c')
    if not 0 <= age < 5: raise RuntimeError('Phone thermal telemetry is stale')
    if status not in range(7): raise RuntimeError('Invalid phone thermal status')
    if status >= 3: raise RuntimeError('Android severe thermal status; test stopped')
    if battery >= 43: raise RuntimeError('Battery reached the 43 C test limit; test stopped')
    return dict(h)


def first_health(client, timeout=3):
    """Allow the asynchronous telemetry sampler to populate before loading."""
    end = time.monotonic() + timeout
    while True:
        state = client.state(timeout=1)
        if state.get('device_health'):
            return device_health(state)
        if time.monotonic() >= end:
            raise RuntimeError('Phone thermal telemetry did not become available')
        time.sleep(0.1)


def metrics(values):
    v = np.asarray(values)
    return {'mean_ms': float(v.mean()), 'p95_ms': float(np.percentile(v, 95)),
            'p99_ms': float(np.percentile(v, 99)), 'max_ms': float(v.max()),
            'over_50ms': int((v > 50).sum())}


class TimingGuard:
    """Stop on a 100 ms exchange or a failing 100-frame p95 block.

    ADB desk tests guard server time. Direct USB also guards full exchange
    time. This distinction prevents a desk transport result from passing USB.
    Optional desk-only record mode retains the same violations without
    raising, so a full measurement can finish without becoming a timing pass.
    """
    def __init__(self, direct_usb=False, record_overruns=False):
        if direct_usb and record_overruns:
            raise ValueError('Recording timing overruns without stopping is for desk tests only')
        self.direct_usb = direct_usb
        self.record_overruns = record_overruns
        self.pending = []
        self.blocks = []
        self.frames = 0
        self.overruns = []

    def _overrun(self, reason, elapsed, **values):
        self.overruns.append(dict(reason=reason, end_frame=self.frames,
                                  elapsed_s=round(elapsed, 3), **values))
        if not self.record_overruns:
            raise RuntimeError(reason + '; test stopped')

    def observe(self, row, elapsed):
        self.pending.append(row)
        self.frames += 1
        if row[3] >= 100 or (self.direct_usb and row[0] >= 100):
            self._overrun('100 ms timing limit reached', elapsed,
                          server_total_ms=row[3], round_trip_ms=row[0], threshold_ms=100)
        if len(self.pending) == 100:
            data = np.asarray(self.pending)
            block = {'end_frame': self.frames, 'elapsed_s': round(elapsed, 3),
                     'round_trip': metrics(data[:, 0]), 'inference': metrics(data[:, 1]),
                     'server_total': metrics(data[:, 3])}
            self.blocks.append(block)
            self.pending.clear()
            if block['server_total']['p95_ms'] >= 50 or (self.direct_usb and block['round_trip']['p95_ms'] >= 50):
                self._overrun('100-frame p95 timing limit reached', elapsed,
                              server_p95_ms=block['server_total']['p95_ms'],
                              round_trip_p95_ms=block['round_trip']['p95_ms'], threshold_ms=50)
