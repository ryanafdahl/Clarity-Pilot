import unittest
from validation import TimingGuard, device_health

class HealthTests(unittest.TestCase):
    def health(self, **fields):
        return {'device_health':dict(sample_age_s=0.2, thermal_status=0, battery_c=25.0, **fields)}
    def test_missing_malformed_stale_and_hot_fail_closed(self):
        for state in [None, {}, {'device_health':{}},
            {'device_health':{'sample_age_s':5, 'thermal_status':0,'battery_c':25}},
            {'device_health':{'sample_age_s':0, 'thermal_status':3,'battery_c':25}},
            {'device_health':{'sample_age_s':0, 'thermal_status':0,'battery_c':43}},
            {'device_health':{'sample_age_s':0, 'thermal_status':0,'battery_c':float('nan')}},
            {'device_health':{'sample_age_s':0, 'thermal_status':True,'battery_c':25}}]:
            with self.subTest(state=state), self.assertRaises(RuntimeError): device_health(state)
    def test_charging_and_plugged_are_distinct(self):
        h=device_health(self.health(charging=False,plugged=True))
        self.assertTrue(h['plugged']); self.assertFalse(h['charging'])

class TimingTests(unittest.TestCase):
    def test_sustained_phone_slowdown_stops(self):
        g=TimingGuard()
        for i in range(99): g.observe([80,60,1,61],i*.08)
        with self.assertRaisesRegex(RuntimeError,'p95'): g.observe([80,60,1,61],8)
        self.assertEqual(len(g.blocks),1)
        self.assertEqual(g.blocks[0]['server_total']['p95_ms'],61)
    def test_adb_and_direct_usb_are_distinct(self):
        adb,usb=TimingGuard(),TimingGuard(direct_usb=True)
        for i in range(99):
            adb.observe([60,33,1,34],i*.06); usb.observe([60,33,1,34],i*.06)
        adb.observe([60,33,1,34],6)
        with self.assertRaisesRegex(RuntimeError,'p95'): usb.observe([60,33,1,34],6)
    def test_single_100_ms_server_stall_stops(self):
        with self.assertRaisesRegex(RuntimeError,'100 ms'): TimingGuard().observe([105,99,1,100],0)
    def test_good_windows_pass(self):
        g=TimingGuard(direct_usb=True)
        for i in range(200): g.observe([40,33,1,34],i*.05)
        self.assertEqual(len(g.blocks),2); self.assertEqual(g.blocks[-1]['end_frame'],200)
        self.assertEqual(g.overruns,[])
    def test_record_mode_preserves_blocks_after_stalls_and_slowdowns(self):
        g=TimingGuard(record_overruns=True)
        for i in range(300):
            # A stall exactly at a block boundary must not prevent that block
            # being completed, or prevent subsequent p95 windows being checked.
            row=[130,119,1,120] if i == 99 else ([80,60,1,61] if i < 200 else [40,33,1,34])
            g.observe(row,i*.08)
        self.assertEqual(g.frames,300)
        self.assertEqual([b['end_frame'] for b in g.blocks],[100,200,300])
        self.assertEqual(g.pending,[])
        self.assertEqual(len(g.overruns),3)
        self.assertEqual([v['end_frame'] for v in g.overruns],[100,100,200])
        self.assertEqual(g.overruns[0]['server_total_ms'],120)
        self.assertEqual(g.overruns[1]['server_p95_ms'],61)
        self.assertEqual(g.blocks[-1]['server_total']['p95_ms'],34)
    def test_record_mode_keeps_exact_thresholds(self):
        g=TimingGuard(record_overruns=True)
        for i in range(100): g.observe([70,49,1,50],i*.07)
        self.assertEqual(len(g.overruns),1)
        self.assertEqual(g.overruns[0]['threshold_ms'],50)
        g.observe([110,99,1,100],7.1)
        self.assertEqual(g.overruns[-1]['threshold_ms'],100)
    def test_record_mode_is_unavailable_for_direct_usb(self):
        with self.assertRaisesRegex(ValueError,'desk tests only'):
            TimingGuard(direct_usb=True,record_overruns=True)

if __name__=='__main__': unittest.main()
