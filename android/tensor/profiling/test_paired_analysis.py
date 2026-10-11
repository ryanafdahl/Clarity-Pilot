import unittest
from paired_analysis import paired_stats


class PairedAnalysisTests(unittest.TestCase):
    def test_consistent_small_gain(self):
        stats = paired_stats([0.1]*8)
        self.assertAlmostEqual(stats['control_minus_candidate_ms'], 0.1)
        self.assertEqual(stats['candidate_faster_pairs'], 8)
        self.assertAlmostEqual(stats['two_sided_sign_flip_p'], 2/256)
        self.assertTrue(all(abs(x-0.1)<1e-10 for x in stats['bootstrap_95pct_interval_ms']))

    def test_mixed_noise_spans_zero(self):
        stats = paired_stats([-0.1, 0.1]*4)
        self.assertAlmostEqual(stats['control_minus_candidate_ms'], 0)
        self.assertLess(stats['bootstrap_95pct_interval_ms'][0], 0)
        self.assertGreater(stats['bootstrap_95pct_interval_ms'][1], 0)
        self.assertEqual(stats['two_sided_sign_flip_p'], 1)

    def test_missing_or_invalid_replicates(self):
        for values in ([0.1], [0.1, float('nan')]):
            with self.assertRaises(ValueError): paired_stats(values)


if __name__ == '__main__': unittest.main()
