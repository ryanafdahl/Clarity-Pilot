import unittest
from model_usage import ModelUsageCounter, carried_peer, peer_from_message, summarize
from core import DistanceCounter


class ModelUsageTests(unittest.TestCase):
  def test_attribution_preserves_existing_assistance_integral(self):
    old, new = DistanceCounter(), ModelUsageCounter('pixel')
    for i in range(200):
      t = i / 100
      if i % 3 == 0:
        active = i % 41 < 29
        old.control(t, active, False)
        new.event(t, 'control', active)
      if i % 5 == 0:
        new.event(t, 'model', i % 37 < 30, valid=i % 29 != 0)
      speed = 10 + i / 20
      old.speed(t, speed)
      new.speed(t, speed)
    self.assertAlmostEqual(sum(b['assisted_meters'] for b in new.buckets.values()), old.assisted_meters)
    self.assertAlmostEqual(sum(b['assisted_seconds'] for b in new.buckets.values()), old.assisted_seconds)
    self.assertAlmostEqual(sum(b['observed_meters'] for b in new.buckets.values()), old.total_meters)

  def test_segment_boundary_ordering_and_missing_segments(self):
    previous = {'peer_end': 'pixel', 'peer_since': 5., 'last_monotonic': 60.}
    self.assertEqual(carried_peer(previous, True, 59.985), ('pixel', 5.))
    self.assertEqual(carried_peer(previous, True, 60.01), ('pixel', 5.))
    self.assertEqual(carried_peer(previous, False, 60.01), ('unknown', None))
    self.assertEqual(carried_peer(previous, True, 62.), ('unknown', None))
    self.assertEqual(carried_peer(dict(previous, peer_since=60.), True, 59.985), ('unknown', None))

  def test_identity_requires_hardware_evidence(self):
    self.assertEqual(peer_from_message('jetlink: tensor-Tensor_G6 trt None, engine none, loaded abc'), 'pixel')
    self.assertEqual(peer_from_message('jetlink: Orin trt 10.0, engine ready, loaded abc'), 'jetson')
    self.assertIsNone(peer_from_message('jetlink: jetson attached'))
    self.assertEqual(peer_from_message('jetlink: unknown trt 10.0, engine ready, loaded abc'), 'unknown')
    self.assertEqual(peer_from_message('jetlink: lost jetlink'), 'unknown')

  def test_model_fallback_splits_assisted_distance(self):
    c = ModelUsageCounter('pixel')
    c.event(0, 'control', True)
    c.event(0, 'model', True)
    c.speed(0, 10)
    c.event(.1, 'model', False)
    c.speed(.2, 20)
    self.assertAlmostEqual(c.buckets['pixel']['assisted_meters'], 1.25)
    self.assertAlmostEqual(c.buckets['small']['assisted_meters'], 1.75)

  def test_model_expiry_and_control_expiry(self):
    c = ModelUsageCounter('jetson')
    c.event(0, 'control', True)
    c.event(0, 'model', True)
    for i in range(6): c.speed(i / 10, 10)
    self.assertAlmostEqual(c.buckets['jetson']['assisted_meters'], 2.5)
    self.assertAlmostEqual(c.buckets['unknown']['observed_meters'], 2.5)
    self.assertAlmostEqual(c.buckets['unknown']['assisted_meters'], 0)

  def test_disconnected_peer_cannot_leak_to_reconnection(self):
    c = ModelUsageCounter('pixel')
    c.event(0, 'control', True)
    c.event(0, 'model', True)
    c.speed(0, 10)
    c.event(.05, 'peer', 'unknown')
    c.event(.1, 'peer', 'jetson')
    c.speed(.2, 10)
    self.assertAlmostEqual(c.buckets['pixel']['assisted_meters'], .5)
    self.assertAlmostEqual(c.buckets['large_unknown']['assisted_meters'], .5)
    self.assertAlmostEqual(c.buckets['jetson']['assisted_meters'], 1)

  def test_active_union_and_invalid_gap(self):
    c = ModelUsageCounter()
    c.event(0, 'control', True)
    c.event(0, 'model', True)
    c.speed(0, 10)
    c.speed(.1, 10)
    c.speed(1, 10)
    c.speed(1.1, 10, valid=False)
    self.assertAlmostEqual(c.buckets['large_unknown']['assisted_meters'], 1)
    self.assertEqual(c.skipped_intervals, 2)
    self.assertNotIn('peer_end', str(summarize([c.result()])))


if __name__ == '__main__': unittest.main()
