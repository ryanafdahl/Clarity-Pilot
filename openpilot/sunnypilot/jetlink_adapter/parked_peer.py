"""Keep Clarity's experimental Tensor APK outside normal driving sessions.

The private APK advertises validation=parked_only in HELLO. Upstream has no
such extension. Guard the shared client before either provisioning or modeld
can call ensure_engine. The resident upstream owner keeps ep0 across failed
borrowers, so this refusal does not cause the old USB reconnect loop.
"""
from functools import wraps


class ParkedOnlyPeer(RuntimeError):
  pass


def install_guard():
  # Installed lazily: manager imports the adapter without importing numpy.
  from jetlink.client import JetlinkClient
  original = JetlinkClient.hello
  if getattr(original, '_clarity_parked_guard', False) is True:
    return

  @wraps(original)
  def hello(self, *args, **kwargs):
    reply = original(self, *args, **kwargs)
    if reply.get('validation') == 'parked_only':
      raise ParkedOnlyPeer('Pixel connected for parked testing; normal model loading is blocked')
    return reply

  hello._clarity_parked_guard = True
  JetlinkClient.hello = hello
