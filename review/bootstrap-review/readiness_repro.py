"""Isolated adversarial regression. Fixture claims are never production evidence."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from researchlib.readiness import assess, REQUIRED_CHECKS
from researchlib.common import canonical, now_iso


def run():
    plan = {'schema_version':'1.0','record_type':'plan','synthetic':False,'plan_id':'broken','version':1,'replay_eligibility':'INCOMPLETE_DATA','rules':{},'instrument_ref':'UNVERIFIED','effective_from':'2026-09-22T18:00:00Z','entry_valid_until':'2026-09-22T19:00:00Z'}
    evidence = {'schema_version':'1.0','record_type':'evidence','synthetic':False,'evidence_id':'e','plan_ref':'broken@1','evidence_status':'VERIFIED','source_refs':['does-not-exist'],'available_at':'2026-09-22T18:00:00Z','observed_at':'2026-09-22T18:00:00Z','valid_until':'2026-09-22T19:00:00Z'}
    assessment = {'schema_version':'1.0','synthetic':False,'assessment_id':'a','plan_ref':'broken@1','as_of':'2026-09-22T18:00:00Z','valid_until':'2026-09-22T18:30:00Z','effective_from':plan['effective_from'],'checks':{k:{'status':'PASS','observed_at':'2026-09-22T18:00:00Z','valid_until':'2026-09-22T19:00:00Z','evidence_refs':['e']} for k in REQUIRED_CHECKS},'trigger_status':'MET','trigger_evidence_refs':['e']}
    class MockStore:
        def resolve_evidence(self, ref, records):
            return {'kind':'record','record':records[ref]}
    observed = assess(MockStore(), assessment, {'broken@1':plan,'e':evidence}, '2026-09-22T18:10:00Z')
    result = {'test_only':True,'fixture_claims_not_real':True,'production_writes':False,'checked_at':now_iso(),'expected':'not EXECUTION_READY_AS_OF','observed':observed['state'],'reason':observed['reason'],'passed':observed['state'] != 'EXECUTION_READY_AS_OF'}
    Path(__file__).with_name('readiness-recheck.json').write_bytes(canonical(result))
    print(result)
    if not result['passed']:
        raise SystemExit(1)

if __name__ == '__main__':
    run()
