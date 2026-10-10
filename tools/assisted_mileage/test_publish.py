from datetime import datetime
import unittest
from publish import nightly_bucket, public_summary, ZONE

class PublicationTests(unittest.TestCase):
  DEVICES = [{'name': 'comma 3', 'miles': 49220, 'drives': 2673, 'hours': 1313,
              'verified_date': '2026-10-10', 'source': 'comma Connect display'}]
  STATS = {'all': {'distance': 11584.522297826737, 'minutes': 20912, 'routes': 726}}

  def test_nightly_cutoff_and_dst(self):
    for month, day in ((10, 10), (11, 1)):
      before = nightly_bucket(datetime(2026, month, day, 22, 59, tzinfo=ZONE))
      after = nightly_bucket(datetime(2026, month, day, 23, 0, tzinfo=ZONE))
      self.assertNotEqual(before, after)
      self.assertEqual(after, f'2026-{month:02d}-{day:02d}')

  def test_only_connect_totals(self):
    stats = dict(self.STATS, reported_totals={'miles': 999999}, assisted_miles=999999,
                 route_id='private', latitude=1)
    result = public_summary(stats, '2026-10-10', self.DEVICES)
    self.assertEqual((result['driving_miles'], result['drives'], result['hours']), (60805, 3399, 1662))
    self.assertEqual(set(result), {'schema_version', 'driving_miles', 'drives', 'hours',
                                  'updated_date', 'devices', 'method', 'coverage', 'schedule'})
    self.assertNotIn('private', str(result))
    self.assertNotIn('historical_baseline', result)

  def test_repeated_snapshot_does_not_accumulate(self):
    self.assertEqual(public_summary(self.STATS, '2026-10-10', self.DEVICES),
                     public_summary(self.STATS, '2026-10-10', self.DEVICES))
    self.assertEqual(len(self.DEVICES), 1)

  def test_duplicate_or_unverified_devices_rejected(self):
    for devices in (self.DEVICES * 2, [dict(self.DEVICES[0], name='comma 4')],
                    [dict(self.DEVICES[0], source='Owner reported')]):
      with self.assertRaises(ValueError): public_summary(self.STATS, '2026-10-10', devices)

  def test_invalid_totals_rejected(self):
    for key in ('distance', 'minutes', 'routes'):
      for value in (-1, float('nan'), float('inf'), True, '10'):
        with self.assertRaises(ValueError):
          public_summary({'all': dict(self.STATS['all'], **{key: value})}, '2026-10-10', self.DEVICES)
    with self.assertRaises(ValueError):
      public_summary({'all': dict(self.STATS['all'], routes=1.5)}, '2026-10-10', self.DEVICES)

if __name__ == '__main__': unittest.main()
