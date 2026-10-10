import unittest

from core import DistanceCounter


class MileageTests(unittest.TestCase):
  def test_constant_speed_and_lateral_only(self):
    c = DistanceCounter()
    for i in range(101):
      c.control(i / 100, True, False)
      c.speed(i / 100, 10)
    self.assertAlmostEqual(c.total_meters, 10)
    self.assertAlmostEqual(c.assisted_meters, 10)

  def test_switch_inside_speed_interval(self):
    c = DistanceCounter()
    c.control(0, False, True)
    c.speed(0, 10)
    c.control(.1, False, False)
    c.speed(.2, 20)
    self.assertAlmostEqual(c.total_meters, 3)
    self.assertAlmostEqual(c.assisted_meters, 1.25)

  def test_stale_control_is_not_carried_indefinitely(self):
    c = DistanceCounter()
    c.control(0, True, False)
    for i in range(11):
      c.speed(i / 10, 10)
    self.assertAlmostEqual(c.total_meters, 10)
    self.assertAlmostEqual(c.assisted_meters, 2.5)

  def test_missing_invalid_and_stationary_data(self):
    c = DistanceCounter()
    c.control(0, True, True)
    c.speed(0, 10)
    c.speed(1, 10)  # Never bridge a missing second.
    c.speed(1.1, float('nan'))
    c.speed(1.2, 10)
    self.assertEqual(c.total_meters, 0)
    c.control(1.2, True, True, valid=False)
    c.speed(1.3, 10)
    self.assertAlmostEqual(c.total_meters, 1)
    self.assertEqual(c.assisted_meters, 0)
    parked = DistanceCounter()
    parked.control(0, True, True)
    parked.speed(0, .1, standstill=True)
    parked.speed(.1, .1, standstill=True)
    self.assertEqual(parked.assisted_meters, 0)

  def test_segment_reset_never_bridges_recordings(self):
    a, b = DistanceCounter(), DistanceCounter()
    a.control(0, True, False)
    a.speed(0, 10)
    b.speed(100, 10)
    b.speed(100.1, 10)
    self.assertEqual(a.assisted_meters + b.assisted_meters, 0)


if __name__ == '__main__':
  unittest.main()
