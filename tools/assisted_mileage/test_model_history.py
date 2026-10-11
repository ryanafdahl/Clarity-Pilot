import unittest
from model_usage import ModelUsageCounter, sampled_model_events, history_summary
from core import METERS_PER_MILE


class ModelHistoryTests(unittest.TestCase):
  def test_history_includes_before_activation_without_guessing_device(self):
    rows = []
    for peer, miles, source in [('pixel', 2, 'rlog'), ('jetson', 3, 'rlog'), ('large_unknown', 4, 'qlog'), ('small', 99, 'rlog')]:
      row = ModelUsageCounter().result()
      row.update(wall_time_ns=1791000000000000000, route_key=peer, source_kind=source)
      row['buckets'][peer]['assisted_meters'] = miles*METERS_PER_MILE
      rows.append(row)
    summary = history_summary(rows, '2026-10-10')
    self.assertEqual(summary['assisted_miles'], 9)
    self.assertEqual(summary['identified_assisted_miles'], 5)
    self.assertEqual(summary['unattributed_assisted_miles'], 4)
    self.assertEqual(summary['sampled_assisted_miles'], 4)
    self.assertEqual(summary['full_rate_assisted_miles'], 5)
    self.assertNotIn('route_key', str(summary))
    self.assertNotIn('started_date', summary)

  def test_compact_logs_confirm_only_matching_neighbors_and_no_final_tail(self):
    events = sampled_model_events([(0, True, True), (.5, True, True), (1, False, True), (1.5, False, True), (3, False, True)])
    self.assertEqual([e[3] for e in events], [True, False, True, False, False])
    c = ModelUsageCounter(model_freshness=.75)
    for i in range(21):
      t=i/10
      for e in events:
        if abs(e[0]-t) < 1e-8: c.event(e[0], 'model', *e[2:])
      c.event(t, 'control', True)
      c.speed(t, 10)
    self.assertAlmostEqual(c.buckets['large_unknown']['assisted_meters'], 5)
    self.assertAlmostEqual(c.buckets['small']['assisted_meters'], 5)

  def test_bad_distance_fails_closed(self):
    row = ModelUsageCounter().result()
    row['route_key'] = 'private'
    row['buckets']['large_unknown']['assisted_meters'] = float('nan')
    with self.assertRaises(ValueError): history_summary([row], '2026-10-10')
