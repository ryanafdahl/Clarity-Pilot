from datetime import datetime
import unittest
from publish import nightly_bucket, public_summary, ZONE


class PublicationTests(unittest.TestCase):
  BASELINE = {'reported_totals': {'miles': 60791, 'drives': 3395, 'hours': 1661},
              'recorded_anchor': {'assisted_miles': 10, 'assisted_hours': 1, 'assisted_recordings': 2}}
  def test_nightly_cutoff_and_catchup(self):
    self.assertEqual(nightly_bucket(datetime(2026, 10, 10, 22, 59, tzinfo=ZONE)), '2026-10-09')
    self.assertEqual(nightly_bucket(datetime(2026, 10, 10, 23, 0, tzinfo=ZONE)), '2026-10-10')
    self.assertEqual(nightly_bucket(datetime(2026, 10, 11, 9, 0, tzinfo=ZONE)), '2026-10-10')

  def test_dst_does_not_change_local_cutoff(self):
    self.assertEqual(nightly_bucket(datetime(2026, 11, 1, 22, 59, tzinfo=ZONE)), '2026-10-31')
    self.assertEqual(nightly_bucket(datetime(2026, 11, 1, 23, 0, tzinfo=ZONE)), '2026-11-01')

  def test_allowlist_excludes_private_fields(self):
    public = public_summary({'assisted_miles': 12.345, 'total_recorded_miles': 20,
                             'assisted_hours': 1.5, 'assisted_recordings': 3,
                             'route_id': 'private', 'latitude': 1, 'segments': 20}, '2026-10-10', self.BASELINE)
    self.assertEqual(public['assisted_miles'], 60793.3)
    self.assertEqual(public['drives'], 3396)
    self.assertEqual(public['hours'], 1661.5)
    self.assertEqual(set(public), {'schema_version', 'assisted_miles', 'updated_date',
                                  'drives', 'hours', 'historical_baseline', 'method', 'coverage', 'schedule'})

  def test_existing_logs_are_not_added_to_history_again(self):
    summary = {'assisted_miles': 10, 'total_recorded_miles': 20, 'assisted_hours': 1, 'assisted_recordings': 2}
    public = public_summary(summary, '2026-10-10', self.BASELINE)
    self.assertEqual((public['assisted_miles'], public['drives'], public['hours']), (60791, 3395, 1661))

  def test_lost_ledger_is_rejected(self):
    with self.assertRaises(ValueError):
      public_summary({'assisted_miles': 9, 'total_recorded_miles': 20, 'assisted_hours': 1,
                      'assisted_recordings': 2}, '2026-10-10', self.BASELINE)

  def test_invalid_totals_are_rejected(self):
    for value in (-1, float('nan'), float('inf'), 11):
      with self.assertRaises(ValueError):
        public_summary({'assisted_miles': value, 'total_recorded_miles': 10}, '2026-10-10', self.BASELINE)


if __name__ == '__main__':
  unittest.main()
