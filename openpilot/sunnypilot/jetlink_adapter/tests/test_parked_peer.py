import unittest
from unittest.mock import patch

from jetlink.client import JetlinkClient
from openpilot.sunnypilot.jetlink_adapter.parked_peer import ParkedOnlyPeer, install_guard


class TestParkedPeer(unittest.TestCase):
  def test_reject_before_model_request(self):
    with patch.object(JetlinkClient, 'hello', return_value={'validation': 'parked_only'}), \
         patch.object(JetlinkClient, 'ensure_engine') as ensure:
      install_guard()
      client = object.__new__(JetlinkClient)
      with self.assertRaises(ParkedOnlyPeer):
        client.hello()
        client.ensure_engine('unused', 0)
      ensure.assert_not_called()

  def test_normal_jetson_is_unchanged_and_install_is_idempotent(self):
    reply = {'device': 'Orin-sm87', 'version': '0.8.3'}
    with patch.object(JetlinkClient, 'hello', return_value=reply):
      install_guard()
      guarded = JetlinkClient.hello
      install_guard()
      self.assertIs(JetlinkClient.hello, guarded)
      self.assertIs(object.__new__(JetlinkClient).hello(timeout=2), reply)
