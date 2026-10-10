"""Private, deduplicated Connect engagement ledger; publish aggregates only."""
from datetime import datetime, timezone
import json
import time
import urllib.parse
import urllib.request
from collect import atomic_json, require_offroad


def integrate(events, duration):
  """Connect enabled intervals, with unknown prefix retained as unknown."""
  changes = sorted((e for e in events if e.get('type') in ('state', 'engage', 'disengage')),
                   key=lambda e: (e['route_offset_millis'], e.get('route_offset_nanos', 0)))
  enabled = None
  previous = 0
  engaged = known = 0
  for e in changes:
    stamp = min(duration, max(0, e['route_offset_millis']))
    delta = max(0, stamp - previous)
    if enabled is not None: known += delta
    if enabled: engaged += delta
    enabled = bool(e.get('data', {}).get('enabled')) if e['type'] == 'state' else e['type'] == 'engage'
    previous = stamp
  if enabled is not None: known += max(0, duration - previous)
  if enabled: engaged += max(0, duration - previous)
  return engaged / 1000, known / 1000


def fetch_events(route, segment):
  u = urllib.parse.urlsplit(route['url'])
  if u.scheme != 'https' or u.hostname not in ('chffrprivate.blob.core.windows.net', 'chffrprivate.azureedge.net'):
    raise ValueError('Unrecognized event storage host')
  url = urllib.parse.urlunsplit((u.scheme, u.netloc, u.path.rstrip('/') + f'/{segment}/events.json', u.query, ''))
  with urllib.request.urlopen(url, timeout=12) as response:
    raw = response.read(5 * 1024 * 1024 + 1)
  if len(raw) > 5 * 1024 * 1024: raise ValueError('Oversized event file')
  result = json.loads(raw)
  if not isinstance(result, list): raise ValueError('Invalid event data')
  return result


def refresh(base, api, identity, today, deadline_seconds=240):
  """Bounded offroad refresh. IDs and signed URLs never enter public output."""
  config = json.loads((base / 'connect-private-devices.json').read_text())
  ledger_path = base / 'engagement-ledger.json'
  ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {'routes': {}}
  deadline = time.monotonic() + deadline_seconds
  statuses = []
  stats = {}
  for device in config:
    require_offroad()
    name = device['name']; did = identity if device.get('current') else device['id']
    status = {'name': name, 'checked_date': today, 'route_list_ok': False}
    try:
      response = api.get(f'v1.1/devices/{did}/stats', access_token=api.get_token(), timeout=20)
      if response.status_code == 200: stats[name] = response.json()
      end = int(time.time() * 1000)
      rows = {}
      for page in range(20):
        if time.monotonic() >= deadline: break
        require_offroad()
        response = api.get(f'v1/devices/{did}/routes_segments', access_token=api.get_token(), timeout=20,
                           start=0, end=end, limit=1000)
        if response.status_code != 200: raise RuntimeError('Route list unavailable')
        batch = response.json()
        before = len(rows)
        for r in batch: rows[r['fullname']] = r
        if len(batch) < 1000 or len(rows) == before:
          status['route_list_ok'] = True
          break
        end = min(r['start_time_utc_millis'] for r in batch) - 1
      status['api_routes'] = len(rows)
      for key, route in rows.items():
        old = ledger['routes'].get(key, {})
        if old.get('complete') and old.get('source') == 'Connect events': continue
        if old.get('attempt_date') == today: continue
        if time.monotonic() >= deadline: break
        require_offroad()
        start, finish = route['segment_start_times'][0], route['segment_end_times'][-1]
        if abs(route['start_time_utc_millis'] - start) > 86400000 and abs(route['end_time_utc_millis'] - finish) < 10000:
          start, finish = route['start_time_utc_millis'], route['end_time_utc_millis']
        duration = finish - start
        if duration <= 0: continue
        row = {'device': name, 'date': datetime.fromtimestamp(start/1000, timezone.utc).date().isoformat(),
               'duration_seconds': duration/1000, 'source': 'Connect events', 'attempt_date': today}
        events = []
        try:
          for segment in range(route['maxqlog'] + 1):
            if time.monotonic() >= deadline: raise TimeoutError()
            require_offroad()
            events.extend(fetch_events(route, segment))
          processed_end = duration
          if route['procqlog'] < route['maxqlog']:
            processed_end = route['segment_end_times'][route['segment_numbers'].index(route['procqlog'])] - start
          engaged, known = integrate(events, processed_end)
          row.update(engaged_seconds=engaged, known_seconds=known, available=True,
                     complete=route['procqlog'] == route['maxqlog'])
          ledger['routes'][key] = row
        except (OSError, ValueError, KeyError, TimeoutError):
          if old.get('available'):
            old['attempt_date'] = today  # Never erase previously recovered evidence.
          else:
            row.update(available=False, complete=False)
            ledger['routes'][key] = row
    except (OSError, ValueError, RuntimeError, KeyError):
      status['error'] = 'Connect refresh incomplete; retained previous evidence'
    statuses.append(status)
  ledger['last_check_date'] = today
  atomic_json(ledger_path, ledger)
  return aggregate(ledger, statuses, today), stats


def aggregate(ledger, statuses, today):
  devices = []
  for name in ('comma 4', 'comma 3'):
    rows = [r for r in ledger['routes'].values() if r['device'] == name]
    available = [r for r in rows if r.get('available')]
    devices.append({'name': name, 'observed_engaged_seconds': round(sum(r.get('engaged_seconds', 0) for r in available), 3),
                    'reviewed_routes': len(available), 'unavailable_routes': sum(not r.get('available') for r in rows),
                    'recorded_seconds': round(sum(r['duration_seconds'] for r in available), 3),
                    'timeline_routes': sum(r['source'] == 'Connect timeline' for r in available),
                    'event_routes': sum(r['source'] == 'Connect events' for r in available),
                    'first_date': min((r['date'] for r in available), default=None),
                    'last_date': max((r['date'] for r in available), default=None)})
  # Month-level aggregates deliberately omit trip times and identifiers.
  periods = {}
  for r in ledger['routes'].values():
    if not r.get('available'): continue
    key = (r['date'][:7], r['device'])
    period = periods.setdefault(key, {'month': key[0], 'device': key[1], 'engaged_seconds': 0, 'routes': 0})
    period['engaged_seconds'] += r.get('engaged_seconds', 0); period['routes'] += 1
  for p in periods.values(): p['engaged_seconds'] = round(p['engaged_seconds'], 3)
  return {'schema_version': 1, 'updated_date': today,
          'observed_engaged_seconds': round(sum(d['observed_engaged_seconds'] for d in devices), 3),
          'devices': devices, 'periods': sorted(periods.values(), key=lambda p: (p['month'], p['device'])),
          'refresh': statuses, 'coverage': 'Partial retained Connect history; not lifetime or model-specific engagement.',
          'method': 'Connect enabled events plus dated, approximate Connect timeline observations. Routes deduplicated privately; missing data is unknown.'}
