"""Conservative model/accelerator attribution from recorded outputs and handshakes."""
import math
import re

from core import MAX_SAMPLE_GAP, CONTROL_FRESHNESS, METERS_PER_MILE

VERSION = 1
ATTRIBUTION_REVISION = 2
MODEL_FRESHNESS = .25
BUCKETS = ('pixel', 'jetson', 'large_unknown', 'small', 'unknown')


def peer_from_message(message):
  """None means no identity event; unknown explicitly clears a previous peer.

  A generic 'jetson attached' message is not hardware identification. Existing
  JetLink versions log the device advertised in HELLO as 'jetlink: DEVICE trt ...'.
  """
  if not isinstance(message, str):
    return None
  if any(text in message for text in ('large model failed mid-drive', 'lost jetlink',
                                      'borrowed the gadget', 'handed the gadget back')):
    return 'unknown'
  match = re.search(r'jetlink: (.+?) trt \S+, engine ', message)
  if not match:
    return None
  device = match[1].lower()
  if re.fullmatch(r'tensor-tensor_g[0-9]+', device) or re.search(r'\bpixel\b', device):
    return 'pixel'
  if re.search(r'\b(?:jetson|orin)\b', device):
    return 'jetson'
  return 'unknown'


def carried_peer(previous, same_adjacent_route, first):
  # Different logging services can straddle segment boundaries by milliseconds.
  # Carry identity only if its actual handshake predates this segment's events.
  if previous and same_adjacent_route:
    since = previous.get('peer_since')
    if (since is not None and since <= first and
        -.25 <= first - previous['last_monotonic'] <= 1):
      return previous['peer_end'], since
  return 'unknown', None


class ModelUsageCounter:
  def __init__(self, peer='unknown', peer_since=None):
    self.peer = peer
    self.peer_since = peer_since
    self.events = {'control': [], 'model': [], 'peer': [(-math.inf, peer, True)]}
    self.previous = None
    self.buckets = {name: {'observed_seconds': 0., 'assisted_seconds': 0.,
                           'observed_meters': 0., 'assisted_meters': 0.} for name in BUCKETS}
    self.skipped_intervals = 0
    self.speed_samples = 0

  def event(self, timestamp, kind, value, valid=True):
    if kind == 'peer':
      if value not in ('pixel', 'jetson', 'unknown'):
        value = 'unknown'
      self.peer = value
      self.peer_since = timestamp
    self.events[kind].append((timestamp, value, bool(valid)))

  def _state(self, kind, timestamp):
    state = next((e for e in reversed(self.events[kind]) if e[0] <= timestamp), None)
    freshness = {'control': CONTROL_FRESHNESS, 'model': MODEL_FRESHNESS}.get(kind, math.inf)
    if not state or not state[2] or (kind != 'peer' and timestamp - state[0] > freshness):
      return None
    return state[1]

  def speed(self, timestamp, speed, valid=True, standstill=False):
    self.speed_samples += 1
    speed = 0. if standstill else speed
    good = valid and math.isfinite(speed) and 0 <= speed <= 80
    if self.previous:
      start, v0, previous_good = self.previous
      dt = timestamp - start
      if previous_good and good and 0 < dt <= MAX_SAMPLE_GAP:
        cuts = {start, timestamp}
        for kind, rows in self.events.items():
          for t, _, _ in rows:
            if start < t < timestamp:
              cuts.add(t)
            if kind in ('control', 'model'):
              expiry = t + (CONTROL_FRESHNESS if kind == 'control' else MODEL_FRESHNESS)
              if start < expiry < timestamp:
                cuts.add(expiry)
        cuts = sorted(cuts)
        for left, right in zip(cuts, cuts[1:]):
          middle = (left + right) / 2
          big = self._state('model', middle)
          peer = self._state('peer', middle)
          name = ('unknown' if big is None else 'small' if not big else
                  peer if peer in ('pixel', 'jetson') else 'large_unknown')
          meters = (v0 + (speed - v0) * (middle - start) / dt) * (right - left)
          bucket = self.buckets[name]
          bucket['observed_seconds'] += right - left
          bucket['observed_meters'] += meters
          if self._state('control', middle):
            bucket['assisted_seconds'] += right - left
            bucket['assisted_meters'] += meters
      else:
        self.skipped_intervals += 1
    self.previous = (timestamp, speed, good)
    self.events = {kind: rows[-1:] for kind, rows in self.events.items()}

  def result(self):
    return {'buckets': self.buckets, 'peer_end': self.peer, 'peer_since': self.peer_since,
            'skipped_intervals': self.skipped_intervals, 'speed_samples': self.speed_samples}


def summarize(records):
  totals = {name: {metric: sum(row['buckets'][name][metric] for row in records)
                   for metric in ('observed_seconds', 'assisted_seconds', 'observed_meters', 'assisted_meters')}
            for name in BUCKETS}
  for row in totals.values():
    row['assisted_miles'] = row.pop('assisted_meters') / METERS_PER_MILE
    row['observed_miles'] = row.pop('observed_meters') / METERS_PER_MILE
  return {'schema_version': VERSION, 'buckets': totals, 'segments': len(records),
          'method': 'Full-rate logged modelV2.big plus JetLink HELLO device identity; active lateral or longitudinal control counted once.',
          'coverage': 'Only retained logs analyzed. Unknown identities remain unknown. Model/control samples expire after 0.25 seconds. Separate from Connect lifetime totals.'}
