"""Conservative model/accelerator attribution from recorded outputs and handshakes."""
import math
import re

from core import MAX_SAMPLE_GAP, CONTROL_FRESHNESS, METERS_PER_MILE

VERSION = 1
ATTRIBUTION_REVISION = 4
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
  def __init__(self, peer='unknown', peer_since=None, model_freshness=MODEL_FRESHNESS):
    self.model_freshness = model_freshness
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
    freshness = {'control': CONTROL_FRESHNESS, 'model': self.model_freshness}.get(kind, math.inf)
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
              expiry = t + (CONTROL_FRESHNESS if kind == 'control' else self.model_freshness)
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


def forward_summary(records, tracking, updated_date):
  """Count only recordings started after the explicit activation timestamp.

  Use logged wall time, not file mtime or when a backfill was processed. Missing
  clocks and recordings already underway at activation cannot enter this total.
  """
  start = tracking['started_at_ns']
  if type(start) is not int or start < 1767225600000000000:
    raise ValueError('Invalid tracking activation timestamp')
  meters = 0.
  for row in records:
    wall = row.get('wall_time_ns')
    if type(wall) is not int or wall < start:
      continue
    for peer in ('pixel', 'jetson'):
      value = row['buckets'][peer]['assisted_meters']
      if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid model distance')
      meters += value
  return {'schema_version': 1, 'assisted_miles': round(meters / METERS_PER_MILE, 4),
          'started_date': tracking['started_date'], 'updated_date': updated_date,
          'method': 'Combined Pixel and Jetson big-model miles with active lateral or longitudinal assistance, counted once.',
          'coverage': 'Recordings started after tracking activation only; logged model and HELLO identity required. Missing logs or unknown identities excluded.'}


def sampled_model_events(rows, maximum_gap=.75):
  """Confirm a state only between two matching valid compact-log samples.

  Do not extrapolate a final sample, bridge a missing model sample, or assume
  that a transition occurred at the later timestamp. These remain estimates:
  brief transitions between the logged samples cannot be recovered.
  """
  result = []
  for index, (t, big, valid) in enumerate(rows):
    next_row = rows[index+1] if index+1 < len(rows) else None
    confirmed = bool(valid and next_row and next_row[2] and
                     0 < next_row[0]-t <= maximum_gap and big == next_row[1])
    result.append((t, 2, big, confirmed))
  return result


def history_summary(records, updated_date):
  """All available deduplicated model evidence, including unidentified peers."""
  rows = list(records)
  device_meters = {'pixel': 0., 'jetson': 0.}
  identified = unattributed = sampled = full = 0.
  wall_times = []
  for row in rows:
    meters = 0.
    for peer in ('pixel', 'jetson', 'large_unknown'):
      value = row['buckets'][peer]['assisted_meters']
      if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid model distance')
      meters += value
      if peer == 'large_unknown': unattributed += value
      else:
        identified += value
        device_meters[peer] += value
    if row.get('source_kind') == 'qlog': sampled += meters
    else: full += meters
    wall = row.get('wall_time_ns')
    if type(wall) is int and wall >= 946684800000000000 and meters > 0:
      wall_times.append(wall)
  from datetime import datetime, timezone
  from zoneinfo import ZoneInfo
  return {'schema_version': 3, 'assisted_miles': round((identified+unattributed)/METERS_PER_MILE, 4),
          'device_assisted_miles': {name: round(meters/METERS_PER_MILE, 4) for name, meters in device_meters.items()},
          'identified_assisted_miles': round(identified/METERS_PER_MILE, 4),
          'unattributed_assisted_miles': round(unattributed/METERS_PER_MILE, 4),
          'full_rate_assisted_miles': round(full/METERS_PER_MILE, 4),
          'sampled_assisted_miles': round(sampled/METERS_PER_MILE, 4),
          'earliest_date': datetime.fromtimestamp(min(wall_times)/1e9, timezone.utc).astimezone(ZoneInfo('America/Los_Angeles')).date().isoformat() if wall_times else None,
          'updated_date': updated_date, 'segments': len(rows),
          'recordings': len({row['route_key'] for row in rows}),
          'full_rate_segments': sum(row.get('source_kind') != 'qlog' for row in rows),
          'sampled_segments': sum(row.get('source_kind') == 'qlog' for row in rows),
          'method': 'Logged big-model execution plus active lateral or longitudinal control, counted once. Full-rate logs preferred over compact logs for each segment.',
          'coverage': 'Recovered available logs, not lifetime mileage. Compact-log miles are sampled estimates between matching valid model samples at most 0.75 seconds apart; brief hidden transitions cannot be recovered. Unidentified accelerator miles remain unattributed.'}
