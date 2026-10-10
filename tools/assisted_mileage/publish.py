"""Publish verified Connect totals; retain local assistance logs separately."""
import argparse
from datetime import datetime, timedelta
import fcntl
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo

from collect import atomic_json, require_offroad

REPOSITORY = 'git@github.com:ryanafdahl/t3st.site.git'
BRANCH = 'master'
PUBLIC_FILE = 'data/assisted-miles.json'
ZONE = ZoneInfo('America/Los_Angeles')


def nightly_bucket(now):
  return (now.astimezone(ZONE) - timedelta(hours=23)).date().isoformat()


def public_summary(stats, today, verified_devices):
  """Only Connect observations; never add a manual baseline or local routes."""
  current = stats['all']
  for key in ('distance', 'minutes', 'routes'):
    value = current[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
      raise ValueError('Invalid Connect statistics')
  if int(current['routes']) != current['routes']:
    raise ValueError('Invalid route count')
  devices = []
  for device in verified_devices:
    if device['source'] != 'comma Connect display':
      raise ValueError('Historical device must be verified from Connect')
    row = {key: device[key] for key in ('name', 'miles', 'drives', 'hours', 'verified_date', 'source')}
    if any(type(row[key]) is not int or row[key] < 0 for key in ('miles', 'drives', 'hours')):
      raise ValueError('Invalid verified device totals')
    if row['name'] == 'comma 4' or any(d['name'] == row['name'] for d in devices):
      raise ValueError('Duplicate device')
    devices.append(row)
  # Match Connect's whole-number display. The older offline device is a dated
  # browser observation, not an API refresh or an owner-supplied estimate.
  devices.append({'name': 'comma 4', 'miles': math.floor(current['distance'] + .5),
                  'drives': int(current['routes']), 'hours': math.floor(current['minutes'] / 60 + .5),
                  'verified_date': today, 'source': 'comma Connect API'})
  return {'schema_version': 2, 'driving_miles': sum(d['miles'] for d in devices),
          'drives': sum(d['drives'] for d in devices), 'hours': sum(d['hours'] for d in devices),
          'updated_date': today, 'devices': devices,
          'method': 'Sum of verified comma Connect device statistics; whole-number display precision.',
          'coverage': 'Driving totals, not independently verified active-assistance miles. No manual additions or local-log increments.',
          'schedule': 'Current device refreshed nightly offroad and online; older device retains its dated Connect observation.'}


def connect_statistics():
  from openpilot.common.params import Params
  from openpilot.common.api import Api
  identity = Params().get('DongleId')
  if isinstance(identity, bytes): identity = identity.decode()
  if not identity: raise RuntimeError('Device identity unavailable')
  api = Api(identity)
  response = api.get(f'v1.1/devices/{identity}/stats', access_token=api.get_token(), timeout=20)
  if response.status_code != 200:
    raise RuntimeError(f'Connect statistics unavailable: HTTP {response.status_code}')
  return response.json()


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--base', type=Path, default=Path(__file__).resolve().parent)
  parser.add_argument('--force-publish', action='store_true')
  args = parser.parse_args()
  base = args.base.resolve()
  try:
    require_offroad()
  except (OSError, RuntimeError):
    print('Deferred: comma is onroad or its state is unavailable.')
    return
  with (base / 'publisher.lock').open('w') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    subprocess.run([sys.executable, str(base / 'collect.py'), '--state', str(base / 'ledger.json'),
                    '--summary', str(base / 'summary.json')], check=True, timeout=1800)
    require_offroad()
    now = datetime.now(ZONE)
    if now.year < 2026:
      raise RuntimeError('Clock is not synchronized; retaining private counts without publication')
    bucket = nightly_bucket(now)
    receipt_path = base / 'published.json'
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    if receipt.get('nightly_bucket') == bucket and not args.force_publish:
      print('Mileage ledger refreshed; this nightly publication is already complete.')
      return
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0',
               GIT_SSH_COMMAND=f'ssh -i {base}/site_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes '
                               f'-o StrictHostKeyChecking=yes -o UserKnownHostsFile={base}/known_hosts '
                               '-o ConnectTimeout=10 -o ServerAliveInterval=15')
    checkout = base / 'site'

    def git(*arguments, timeout=120):
      return subprocess.run(['git', '-C', str(checkout), *arguments], check=True, env=env,
                            text=True, capture_output=True, timeout=timeout).stdout.strip()

    if not checkout.exists():
      subprocess.run(['git', 'clone', '--depth=1', '--single-branch', '--branch', BRANCH,
                      REPOSITORY, str(checkout)], env=env, check=True, timeout=120)
    if git('remote', 'get-url', 'origin') != REPOSITORY:
      raise RuntimeError('Unexpected website remote; refusing to publish')
    if git('status', '--porcelain'):
      raise RuntimeError('Website checkout has uncommitted changes; refusing to overwrite them')
    git('fetch', '--depth=1', 'origin', BRANCH)
    # This dedicated cache always starts from the current remote commit. A rejected
    # previous push is recomputed from the durable ledger without a force push.
    git('checkout', '--detach', f'origin/{BRANCH}')
    verified_devices = json.loads((base / 'connect-devices.json').read_text())
    public = public_summary(connect_statistics(), now.date().isoformat(), verified_devices)
    target = checkout / PUBLIC_FILE
    require_offroad()
    atomic_json(target, public)
    if git('diff', '--name-only') or git('ls-files', '--others', '--exclude-standard'):
      git('add', '--', PUBLIC_FILE)
      if git('diff', '--cached', '--name-only') != PUBLIC_FILE:
        raise RuntimeError('Unexpected staged publication paths')
      git('-c', 'user.name=Clarity mileage tracker', '-c', 'user.email=ryanafdahl@users.noreply.github.com',
          '-c', 'commit.gpgsign=false', 'commit', '-m', 'Update verified Connect driving history')
      require_offroad()
      git('push', 'origin', f'HEAD:{BRANCH}')
    sha = git('rev-parse', 'HEAD')
    remote_sha = git('ls-remote', 'origin', f'refs/heads/{BRANCH}').split()[0]
    if sha != remote_sha:
      raise RuntimeError('Remote changed during verification; retry on the next check')
    atomic_json(receipt_path, {'nightly_bucket': bucket, 'commit': sha, 'driving_miles': public['driving_miles']})
    print(json.dumps({'published_miles': public['driving_miles'], 'commit': sha}))


if __name__ == '__main__':
  main()
