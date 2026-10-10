import unittest
from unittest.mock import patch
import tempfile,json
from pathlib import Path
from engagement import integrate, aggregate, refresh


class EngagementTests(unittest.TestCase):
  def test_unknown_prefix_and_alert_overlay(self):
    events = [{'type': 'state', 'route_offset_millis': 2000, 'data': {'enabled': True}},
              {'type': 'alert', 'route_offset_millis': 3000},
              {'type': 'state', 'route_offset_millis': 5000, 'data': {'enabled': False}}]
    self.assertEqual(integrate(events, 10000), (3, 8))

  def test_empty_is_unknown_and_legacy_pairs(self):
    self.assertEqual(integrate([], 10000), (0, 0))
    self.assertEqual(integrate([{'type':'engage','route_offset_millis':1000},
                                {'type':'disengage','route_offset_millis':4000}], 5000), (3,4))

  def test_clip_open_interval_to_processed_end(self):
    self.assertEqual(integrate([{'type':'state','route_offset_millis':1000,'data':{'enabled':True}}],3000),(2,2))

  def test_aggregate_privacy_and_missing_data(self):
    row = {'device':'comma 4','date':'2026-10-10','duration_seconds':100,'available':True,
           'source':'Connect timeline','engaged_seconds':42, 'url':'secret'}
    result=aggregate({'routes':{'private-id':row,'missing':dict(row,available=False)}},[],'2026-10-10')
    self.assertEqual(result['observed_engaged_seconds'],42)
    self.assertEqual(result['devices'][0]['unavailable_routes'],1)
    self.assertNotIn('secret',str(result));self.assertNotIn('private-id',str(result))

  def test_failed_download_preserves_prior_route_and_deduplicates(self):
    route={'fullname':'private','segment_start_times':[0],'segment_end_times':[10000],
           'start_time_utc_millis':0,'end_time_utc_millis':10000,'maxqlog':0,'procqlog':0}
    class Response:
      status_code=200
      def json(self): return [route]
    class Api:
      def get_token(self): return 'unused'
      def get(self,*a,**kw): return Response()
    with tempfile.TemporaryDirectory() as tmp:
      base=Path(tmp)
      (base/'connect-private-devices.json').write_text(json.dumps([{'name':'comma 4','current':True}]))
      row={'device':'comma 4','date':'2026-10-10','duration_seconds':10,'available':True,
           'source':'Connect timeline','engaged_seconds':5,'complete':False}
      (base/'engagement-ledger.json').write_text(json.dumps({'routes':{'private':row}}))
      with patch('engagement.require_offroad'),patch('engagement.fetch_events',side_effect=OSError('missing')):
        result,_=refresh(base,Api(),'unused','2026-10-11')
        again,_=refresh(base,Api(),'unused','2026-10-11')
      self.assertEqual(result['observed_engaged_seconds'],5)
      self.assertEqual(again['devices'][0]['reviewed_routes'],1)

  def test_recovered_sources_separate_and_api_replacement_not_additive(self):
    row={'device':'comma 4','date':'2026-09-28','duration_seconds':100,'available':True,
         'source':'Recovered device logs','engaged_seconds':42}
    ledger={'routes':{'same-route':row}}
    result=aggregate(ledger,[],'2026-10-10')
    self.assertEqual(result['sources'][1]['engaged_seconds'],42)
    self.assertEqual(result['devices'][0]['recovered_log_routes'],1)
    ledger['routes']['same-route']=dict(row,source='Connect events',engaged_seconds=43)
    result=aggregate(ledger,[],'2026-10-10')
    self.assertEqual(result['observed_engaged_seconds'],43)
    self.assertEqual(result['sources'][1]['engaged_seconds'],0)

if __name__=='__main__': unittest.main()
