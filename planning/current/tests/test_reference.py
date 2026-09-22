import copy
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reference.contracts import make_snapshot, validate_fixture, readiness, REQUIRED_CHECKS

class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'examples/records.json').read_text())
        self.now='2026-09-23T03:10:00Z'
        self.assessment={'synthetic':False,'plan_ref':'isolated-test-plan@1','invalidated':False,
                         'replay_eligible':True,'as_of':'2026-09-23T03:00:00Z',
                         'valid_until':'2026-09-23T03:30:00Z','effective_from':'2026-09-23T02:00:00Z',
                         'trigger_status':'MET','trigger_evidence_refs':['isolated-test-only'],
                         'checks':{k:{'status':'PASS','evidence_refs':['unit-test-not-real-evidence'],
                                       'observed_at':'2026-09-23T03:00:00Z','valid_until':'2026-09-23T03:30:00Z'}
                                   for k in REQUIRED_CHECKS}}
    def test_01_fixture_valid(self): validate_fixture(self.data)
    def test_02_no_synthetic_production_fallback(self):
        self.assertEqual(make_snapshot(self.data,self.now)['round_count'],0)
    def test_03_hierarchy_and_internal_reviews(self):
        s=make_snapshot(self.data,self.now,demo=True)
        n={x['id']:x for x in s['nodes']}
        self.assertEqual(n['round-btc-2']['generation'],2)
        self.assertEqual(len(n['round-btc-2']['review_refs']),2)
        self.assertEqual(len(s['nodes']),4)
    def test_04_future_round_hidden(self):
        s=make_snapshot(self.data,'2026-09-02T12:00:00Z',demo=True)
        self.assertNotIn('round-btc-2',[x['id'] for x in s['nodes']])
    def test_05_correction_not_leaked_into_past(self):
        s=make_snapshot(self.data,'2026-09-04T12:00:00Z',demo=True)
        n=next(x for x in s['nodes'] if x['id']=='round-btc-2')
        self.assertEqual(n['latest_review_ref'],'review-2')
        self.assertEqual(n['net_return_fraction'],0.0032)
    def test_06_corrected_result_current(self):
        s=make_snapshot(self.data,self.now,demo=True)
        n=next(x for x in s['nodes'] if x['id']=='round-btc-2')
        self.assertEqual(n['net_return_fraction'],-0.0012)
    def test_07_duplicate_rejected(self):
        self.data['rounds'].append(copy.deepcopy(self.data['rounds'][0]))
        with self.assertRaises(ValueError): validate_fixture(self.data)
    def test_08_cycles_rejected(self):
        self.data['rounds'][0]['parent_round_id']='round-btc-2'
        with self.assertRaises(ValueError): validate_fixture(self.data)
    def test_09_mismatched_review_rejected(self):
        self.data['reviews'][0]['plan_ref']='missing@1'
        with self.assertRaises(ValueError): validate_fixture(self.data)
    def test_10_unknown_schema_rejected(self):
        self.data['schema_version']='999'
        with self.assertRaises(ValueError): validate_fixture(self.data)
    def test_11_deterministic_nonmutating_projection(self):
        old=copy.deepcopy(self.data)
        self.assertEqual(make_snapshot(self.data,self.now,demo=True),make_snapshot(self.data,self.now,demo=True))
        self.assertEqual(self.data,old)
    def test_12_no_zero_imputation(self):
        s=make_snapshot(self.data,self.now,demo=True)
        self.assertIsNone(next(x for x in s['nodes'] if x['id']=='round-btc-2b')['net_return_fraction'])
    def test_13_ready_does_not_authorize_trade(self):
        r=readiness(self.assessment,self.now)
        self.assertEqual(r['state'],'EXECUTION_READY_AS_OF')
        self.assertFalse(r['automatic_trade_authorized'])
        self.assertEqual(r['account_eligibility'],'NOT_ASSESSED')
    def test_14_expired_badge(self):
        self.assertEqual(readiness(self.assessment,'2026-09-23T03:30:00Z')['state'],'EXPIRED')
    def test_15_unknown_time_not_ready(self):
        self.assessment['valid_until']=None
        self.assertEqual(readiness(self.assessment,self.now)['state'],'UNKNOWN')
    def test_16_synthetic_not_ready(self):
        self.assessment['synthetic']=True
        self.assertEqual(readiness(self.assessment,self.now)['state'],'DEMO_ONLY')
    def test_17_missing_market_evidence_replay_only(self):
        del self.assessment['checks']['target_data_current']
        self.assertEqual(readiness(self.assessment,self.now)['state'],'REPLAYABLE_ONLY')
    def test_18_trigger_not_met(self):
        self.assessment['trigger_status']='NOT_MET'
        self.assertEqual(readiness(self.assessment,self.now)['state'],'RULES_READY_WAITING_TRIGGER')
    def test_19_invalidated(self):
        self.assessment['invalidated']=True
        self.assertEqual(readiness(self.assessment,self.now)['state'],'INVALIDATED')
    def test_20_evidence_window_not_extended_by_new_publication(self):
        self.assessment['checks']['target_data_current']['valid_until']='2026-09-23T03:05:00Z'
        self.assertEqual(readiness(self.assessment,self.now)['state'],'UNKNOWN')
    def test_21_profit_is_not_readiness_test(self):
        self.assessment['historical_profit']=0.9
        self.assessment['checks']['references_intact']['status']='UNKNOWN'
        self.assertNotEqual(readiness(self.assessment,self.now)['state'],'EXECUTION_READY_AS_OF')
    def test_22_task_manifest_not_install_receipt(self):
        config=json.loads((ROOT/'config/task_intents.json').read_text())
        self.assertEqual(len(config['tasks']),4)
        for task in config['tasks']:
            self.assertIsNone(task['native_task_id'])
            self.assertFalse(task['registered'])
            self.assertTrue((ROOT/task['prompt_file']).is_file())
            self.assertTrue((ROOT/'.agents/skills'/task['skill_name']/'SKILL.md').is_file())
    def test_23_products_are_intents(self):
        p=json.loads((ROOT/'config/products.json').read_text())
        self.assertEqual({x['ticker'] for x in p['products']},{'AAPL','QQQ','BTC','ETH'})
        self.assertTrue(all(x['instrument_refs']==[] for x in p['products']))
        self.assertFalse(p['extension_example_only']['enabled'])
    def test_24_file_projection_matches_explicit_selection(self):
        self.data['plans'].append({'plan_ref':'unselected-best@1','round_id':'round-btc-1','synthetic':True,'available_at':'2026-09-01T00:00:00Z'})
        self.data['reviews'].append({'review_id':'unselected-best-review','plan_ref':'unselected-best@1','revision':1,'supersedes':None,'stage':'FINAL','net_return_fraction':1.0,'data_cutoff':'2026-09-02T00:00:00Z','available_at':'2026-09-02T01:00:00Z','synthetic':True})
        s=make_snapshot(self.data,self.now,demo=True)
        self.assertEqual(next(x for x in s['nodes'] if x['id']=='round-btc-1')['net_return_fraction'],-0.0025)

if __name__=='__main__': unittest.main()
