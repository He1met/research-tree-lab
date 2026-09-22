"""Independent adversarial mutations on an isolated engineering fixture.

The positive control below is explicitly a synthetic test claim in memory,
not evidence for any production plan or execution condition.
"""
import copy
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'tests'))
from test_storage_contracts import ReadinessTests, T2, T3
from researchlib.readiness import assess
from researchlib.common import canonical, now_iso


def main():
    fixture = ReadinessTests()
    fixture.setUp()
    cases = {}
    try:
        baseline = assess(fixture.store,fixture.assessment,fixture.records,T2)['state']
        assert baseline == 'EXECUTION_READY_AS_OF'
        mutations = {
            'missing_policy': lambda a,r:a.pop('policy_ref'),
            'incomplete_data_plan': lambda a,r:r['P1@1'].update(replay_eligibility='INCOMPLETE_DATA'),
            'empty_rules': lambda a,r:r['P1@1'].update(rules={}),
            'missing_source': lambda a,r:r['E1'].update(source_refs=['absent']),
            'source_lacks_capture': lambda a,r:r['S1'].update(artifact_refs=[]),
            'source_future_available': lambda a,r:r['S1'].update(available_at=T3),
            'source_private_origin': lambda a,r:r['S1'].update(source_url='https://localhost/private'),
            'evidence_wrong_plan': lambda a,r:r['E1'].update(plan_ref='P1@2'),
            'evidence_no_attested_checks': lambda a,r:r['E1'].update(check_names=[]),
            'evidence_no_verification_method': lambda a,r:r['E1'].pop('verification_method'),
            'source_cycle': lambda a,r:r['S1'].update(source_url=None,artifact_refs=[],source_refs=['E1']),
            'missing_method_reference': lambda a,r:r['P1@1'].update(method_ref='absent'),
            'reference_instead_of_target_data': lambda a,r:r['DATA'].update(data_role='REFERENCE'),
            'missing_target_data_bytes': lambda a,r:r['DATA'].update(data_ref='sha256:'+'f'*64),
            'target_contract_absent': lambda a,r:r.pop('TARGET'),
            'synthetic_assessment': lambda a,r:a.update(synthetic=True),
            'unknown_schema': lambda a,r:a.update(schema_version='99'),
            'invalidated_assessment': lambda a,r:a.update(invalidated=True),
        }
        for name,mutate in mutations.items():
            a=copy.deepcopy(fixture.assessment); r=copy.deepcopy(fixture.records)
            mutate(a,r)
            observed=assess(fixture.store,a,r,T2)['state']
            cases[name]={'observed':observed,'passed':observed!='EXECUTION_READY_AS_OF'}
        expired=assess(fixture.store,fixture.assessment,fixture.records,T3)['state']
        cases['validity_endpoint_expires']={'observed':expired,'passed':expired=='EXPIRED'}
    finally:
        fixture.tearDown()
    result={'schema_version':'1.0','checked_at':now_iso(),'test_only':True,'fixture_not_economic_evidence':True,'production_writes':False,'positive_control':baseline,'cases':cases,'all_passed':all(v['passed'] for v in cases.values())}
    Path(__file__).with_name('readiness-matrix.json').write_bytes(canonical(result))
    print({'cases':len(cases),'all_passed':result['all_passed']})
    if not result['all_passed']:
        raise SystemExit(1)

if __name__=='__main__':
    main()
