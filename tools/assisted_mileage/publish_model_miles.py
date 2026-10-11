"""Publish only the authorized forward-looking combined model-mile aggregate."""
from datetime import datetime
import json
import os
import subprocess
from zoneinfo import ZoneInfo

from collect import atomic_json, require_offroad
from model_usage import forward_summary

REPOSITORY = 'git@github.com:ryanafdahl/t3st.site.git'
PUBLIC_FILE = 'data/model-miles.json'


def publish(base):
  # Called while publish.py holds publisher.lock. Fail closed until activation
  # has explicitly been configured; no implicit reset after state loss.
  tracking_path = base / 'model-tracking.json'
  if not tracking_path.exists():
    print('Forward model-mile publication has not been activated.')
    return
  require_offroad()
  now = datetime.now(ZoneInfo('America/Los_Angeles'))
  if now.year < 2026:
    raise RuntimeError('Unsynchronized clock')
  ledger = json.loads((base / 'model-usage-ledger.json').read_text())
  public = forward_summary(ledger['segments'].values(), json.loads(tracking_path.read_text()), now.date().isoformat())
  checkout = base / 'model-site'
  env = dict(os.environ, GIT_TERMINAL_PROMPT='0',
             GIT_SSH_COMMAND=f'ssh -i {base}/site_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes '
                            f'-o StrictHostKeyChecking=yes -o UserKnownHostsFile={base}/known_hosts '
                            '-o ConnectTimeout=10 -o ServerAliveInterval=15')

  def git(*args):
    return subprocess.run(['git', '-C', str(checkout), *args], check=True, env=env,
                          text=True, capture_output=True, timeout=120).stdout.strip()

  if not checkout.exists():
    subprocess.run(['git', 'clone', '--depth=1', '--single-branch', '--branch', 'master',
                    REPOSITORY, str(checkout)], env=env, check=True, timeout=120)
  if git('remote', 'get-url', 'origin') != REPOSITORY or git('status', '--porcelain'):
    raise RuntimeError('Unexpected remote or dirty model-mile publication checkout')
  git('fetch', '--depth=1', 'origin', 'master')
  git('checkout', '--detach', 'origin/master')
  require_offroad()
  atomic_json(checkout / PUBLIC_FILE, public)
  git('add', '--', PUBLIC_FILE)
  paths = git('diff', '--cached', '--name-only').splitlines()
  if not paths:
    return
  if paths != [PUBLIC_FILE]:
    raise RuntimeError('Unexpected staged model-mile paths')
  git('-c', 'user.name=Clarity mileage tracker', '-c', 'user.email=ryanafdahl@users.noreply.github.com',
      '-c', 'commit.gpgsign=false', 'commit', '-m', 'Update combined big-model assisted miles')
  require_offroad()
  git('push', 'origin', 'HEAD:master')
  if git('rev-parse', 'HEAD') != git('ls-remote', 'origin', 'refs/heads/master').split()[0]:
    raise RuntimeError('Remote changed; verify on the next offroad update')
  print(json.dumps({'model_assisted_miles': public['assisted_miles']}))
