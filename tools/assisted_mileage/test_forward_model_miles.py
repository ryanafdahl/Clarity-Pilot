import unittest
from model_usage import ModelUsageCounter, forward_summary
from core import METERS_PER_MILE


class ForwardModelMilesTests(unittest.TestCase):
  def row(self, wall, pixel=0., jetson=0., unknown=0.):
    row = ModelUsageCounter().result()
    row['wall_time_ns'] = wall
    for name, value in [('pixel', pixel), ('jetson', jetson), ('large_unknown', unknown)]:
      row['buckets'][name]['assisted_meters'] = value * METERS_PER_MILE
    return row

  def test_backfill_and_unknown_identity_cannot_inflate_forward_total(self):
    start = 1791686400000000000
    rows = [self.row(start-1, 99), self.row(None, 99), self.row(start, 2, 3, 100)]
    result = forward_summary(rows, {'started_at_ns': start, 'started_date': '2026-10-10'}, '2026-10-11')
    self.assertEqual(result['assisted_miles'], 5)
    self.assertNotIn('buckets', result)
    self.assertNotIn('started_at_ns', result)

  def test_negative_nonfinite_and_boolean_distances_rejected(self):
    start = 1791686400000000000
    for bad in (-1, float('nan'), float('inf'), True):
      row = self.row(start)
      row['buckets']['pixel']['assisted_meters'] = bad
      with self.assertRaises(ValueError):
        forward_summary([row], {'started_at_ns': start, 'started_date': '2026-10-10'}, '2026-10-11')
