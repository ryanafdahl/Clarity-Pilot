"""Publish only aggregate mileage from a private ledger to the website repo."""
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


def public_summary(summary, today, baseline):
  miles = summary['assisted_miles']
  if not math.isfinite(miles) or miles < 0 or miles > summary['total_recorded_miles'] + 0.001:
    raise ValueError('Invalid assisted-distance summary')
  anchor = baseline['recorded_anchor']
  added_miles = miles - anchor['assisted_miles']
  added_hours = summary['assisted_hours'] - anchor['assisted_hours']
  added_drives = summary['assisted_recordings'] - anchor['assisted_recordings']
  if min(added_miles, added_hours, added_drives) < -0.000001:
    raise ValueError('Private ledger is smaller than its historical anchor; restore the ledger')
  history = baseline['reported_totals']
  return {
    'schema_version': 1,
    'assisted_miles': round(history['miles'] + max(0, added_miles), 1),
    'drives': history['drives'] + max(0, added_drives),
    'hours': round(history['hours'] + max(0, added_hours), 1),
    'updated_date': today,
    'historical_baseline': {'miles': history['miles'], 'drives': history['drives'], 'hours': history['hours'],
                            'source': 'Owner-reported historical totals, updated on 2026-10-10.'},
    'method': 'Owner-reported historical totals plus new logged distance with lateral or longitudinal AI control active.',
    'coverage': 'Logs present at setup are treated as included in the historical baseline and are not added again.',
    'schedule': 'Nightly at 11 p.m. Pacific, or when next powered, offroad and online.',
  }


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
    summary = json.loads((base / 'summary.json').read_text())
    baseline = json.loads((base / 'baseline.json').read_text())
    public = public_summary(summary, now.date().isoformat(), baseline)
    target = checkout / PUBLIC_FILE
    previous = json.loads(target.read_text()) if target.exists() else {}
    if previous.get('assisted_miles', 0) > public['assisted_miles']:
      raise RuntimeError('Mileage would decrease; recover the private ledger before publishing')
    require_offroad()
    atomic_json(target, public)
    if git('diff', '--name-only') or git('ls-files', '--others', '--exclude-standard'):
      git('add', '--', PUBLIC_FILE)
      if git('diff', '--cached', '--name-only') != PUBLIC_FILE:
        raise RuntimeError('Unexpected staged publication paths')
      git('-c', 'user.name=Clarity mileage tracker', '-c', 'user.email=ryanafdahl@users.noreply.github.com',
          '-c', 'commit.gpgsign=false', 'commit', '-m', 'Update recorded AI-assisted mileage')
      require_offroad()
      git('push', 'origin', f'HEAD:{BRANCH}')
    sha = git('rev-parse', 'HEAD')
    remote_sha = git('ls-remote', 'origin', f'refs/heads/{BRANCH}').split()[0]
    if sha != remote_sha:
      raise RuntimeError('Remote changed during verification; retry on the next check')
    atomic_json(receipt_path, {'nightly_bucket': bucket, 'commit': sha, 'assisted_miles': public['assisted_miles']})
    print(json.dumps({'published_miles': public['assisted_miles'], 'commit': sha}))


if __name__ == '__main__':
  main()
