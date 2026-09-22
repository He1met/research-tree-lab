"""Independent adversarial mutations in temporary synthetic stores only.

Uses the author's fixture factory to seed exact plan/legacy records and synthetic
files; assertions and mutations below are independent of the author's test cases.
"""
import argparse
import copy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch
import zipfile


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--code-root',required=True,type=Path)
    args=parser.parse_args();sys.path.insert(0,str(args.code_root))
    from tests.test_conditional_review import ConditionalReviewTests, REFS, PRIVATE_NUMBER
    from researchlib import conditional_review as cr, funding_review as waiting
    from researchlib.common import ContractError,canonical,digest
    from researchlib.snapshot import publish_snapshot
    from researchlib.archive import export_backup,inspect_backup
    checks=[]
    @contextmanager
    def fixture():
        case=ConditionalReviewTests();case.setUp()
        try:yield case
        finally:case.doCleanups()
    def target(case,bundle,ref):
        return next(r for r in case.reviews(bundle) if r['plan_ref']==ref)
    def rejected(call):
        try:call()
        except ContractError:return
        raise AssertionError('Mutation accepted')
    def invariants(case,bundle):
        assert bundle['records'][0]['coverage']['evaluable_results']==0
        assert bundle['records'][0]['coverage']['final_results']==0
        for r in case.reviews(bundle):
            assert r['evaluation_stage'] not in {'FINAL','NOT_TRIGGERED'}
            assert r['data_complete'] is False and all(v is None for v in r['metrics'].values())
            assert r['coverage']['actually_evaluated_market_cutoff'] is None
    with fixture() as t:
        first=t.prepare('a1');t.commit(first);t.now='2026-09-23T19:00:00Z'
        middle=t.prepare('a2');r=t.reviews(middle)[0];ref=r['plan_ref'];p=t.private(middle,r)
        records,meta,_=t.store.load(strict=True)
        payload,bindings,audits=cr.decode_sources(t.store,[],records,meta,t.now,r['data_cutoff'])
        p.update(requests=[],source_bindings=bindings,decode_audits=audits,correction=None)
        p['kernel_result']=cr.evaluate(records[ref],payload,t.now,r['data_cutoff'])
        t.replace_private(middle,r,p)
        r['coverage']=cr._coverage(records[ref],r['data_cutoff'],audits,payload['events'])
        r['coverage'].update(information_as_of=t.now,reason_codes=['CONDITIONAL_OBSERVATIONS_ONLY','SOURCE_COVERAGE_UNKNOWN','EXACT_MARK_MISSING','ACTUAL_COSTS_UNKNOWN'])
        t.commit(middle);t.now='2026-09-23T20:00:00Z'
        request=t.inputs();request['plans'][ref]['sources']=[]
        last=t.prepare('a3',manifest=request)
        assert target(t,last,ref)['evaluation_stage']=='TECHNICAL_FAILURE'
        assert target(t,last,ref)['previous_review_ref']==r['review_id']
        assert last['records'][0]['coverage']['technical_failures']==1
        invariants(t,last);checks.append('original_P1_middle_prefix_reset_rejected_without_skipping_bad_latest')
    with fixture() as t:
        first=t.prepare('b1');t.commit(first);t.now='2026-09-23T19:00:00Z'
        second=t.prepare('b2');t.commit(second);t.now='2026-09-23T20:00:00Z'
        third=t.prepare('b3');r=t.reviews(third)[0];ref=r['plan_ref'];p=t.private(third,r)
        ancestor=target(t,first,ref);records,_,_=t.store.load(strict=True)
        p['kernel_result']=cr.evaluate(records[ref],p['kernel_result']['input_payload'],t.now,r['data_cutoff'],previous=t.private(first,ancestor)['kernel_result'])
        r.update(previous_review_ref=ancestor['review_id'],opening_state_hash=cr.sha(ancestor['simulation_state']),revision=ancestor['revision']+1)
        r['provenance']['prior_state_preserved_in']=ancestor['review_id'];t.replace_private(third,r,p)
        t.commit(third);t.now='2026-09-23T21:00:00Z'
        last=t.prepare('b4');bad=target(t,last,ref)
        assert bad['coverage']['reason_codes']==['HISTORICAL_LATEST_PREDECESSOR_SKIPPED']
        assert last['records'][0]['coverage']['technical_failures']==1
        checks.append('self_consistent_historical_hop_skipping_committed_latest_rejected')
    with fixture() as t:
        first=t.prepare('c1');second=t.prepare('c2');t.commit(first);t.commit(second)
        t.now='2026-09-23T19:00:00Z';result=t.prepare('c3')
        assert all(r['coverage']['reason_codes']==['LATEST_FORMAL_PREDECESSOR_AMBIGUOUS'] for r in t.reviews(result))
        checks.append('same_time_siblings_are_ambiguous_not_arbitrarily_selected')
    with fixture() as t:
        for n in range(4):
            t.now=f'2026-09-23T{18+n:02d}:00:00Z';bundle=t.prepare('chain'+str(n));t.commit(bundle)
        t.now='2026-09-23T22:00:00Z'
        with patch.object(cr,'MAX_HISTORY_REVIEWS',2):
            result=t.prepare('bounded')
        assert all(r['evaluation_stage']=='TECHNICAL_FAILURE' for r in t.reviews(result))
        records,meta,_=t.store.load(strict=True);r=copy.deepcopy(t.reviews(bundle)[0]);r['previous_review_ref']=r['review_id'];records[r['review_id']]=r
        method,_=cr.method_material(t.now)
        rejected(lambda:cr._previous(t.store,r,records[r['plan_ref']],records,meta,method))
        checks.append('chain_depth_and_cycle_guards_fail_closed')
    with fixture() as t:
        old=waiting.prepare_bundle(t.store,'historical-waiting','2026-09-22T19:00:00Z');t.commit(old)
        assert all(r['simulation_state']['inventory'] is None for r in t.reviews(old))
        t.now='2026-09-23T19:00:00Z';new=t.prepare('historical-condition',[],cutoff='2026-09-22T20:00:00Z')
        for r in t.reviews(new):
            assert r['evaluation_stage']=='WAITING_DATA' and r['simulation_state']['inventory'] is None
            assert r['simulation_state']['state']=='HISTORICAL_PRE_EFFECTIVE_INPUTS_ONLY'
            assert t.private(new,r)['kernel_result']['evaluation_stage']=='NOT_YET_EFFECTIVE'
        invariants(t,new);checks.append('original_P2_historical_cutoff_keeps_after_effective_public_inventory_unknown')
    with fixture() as t:
        with patch('platform.python_version',return_value='3.12.99'):
            old=waiting.prepare_bundle(t.store,'wrong-runtime','2026-09-23T12:00:00Z')
        t.commit(old);t.now='2026-09-23T19:00:00Z';new=t.prepare('no-runtime-migration')
        assert all(r['coverage']['reason_codes']==['WAITING_METHOD_NOT_APPROVED_IDENTITY'] for r in t.reviews(new))
        checks.append('waiting_VERSION_label_does_not_authorize_different_runtime')
    with fixture() as t:
        old=t.source('historical-only','2026-09-22','2026-09-22T17:00:00Z',[('7','2026-09-22T00:05:01Z','123')])
        result=t.prepare('isolated-old',[old],cutoff='2026-09-23T12:00:00Z')
        for r in t.reviews(result):
            assert r['coverage']['actually_evaluated_market_cutoff'] is None
            assert r['coverage']['conditional_computation_market_cutoff']=='2026-09-23T12:00:00Z'
            assert r['coverage']['observed_event_max_at']=='2026-09-22T00:05:01.000Z'
        invariants(t,result);checks.append('isolated_old_event_does_not_promote_requested_cutoff_to_formal_evaluation')
    with fixture() as t:
        for kind in ('review','review_batch','feedback'):
            ident='disclosure-'+kind;inputs=t.inputs()
            path=cr.prepare_outbox(t.store,ident,inputs,ident+'.json','2026-09-23T12:00:00Z')
            retained=t.retained(ident);saved=json.loads(retained.read_text());r=t.reviews(saved)[0]
            record=next(r for r in saved['records'] if r['record_type']==kind)
            record['disclosure']['public_attachments'].append('attachments/PRIVATE/'+r['review_id']+'.json')
            t.reseal(retained,saved);before=retained.read_bytes()
            rejected(lambda:cr.prepare_outbox(t.store,ident,inputs,'must-not-write.json','2026-09-23T12:00:00Z'))
            assert retained.read_bytes()==before and not (path.parent/'must-not-write.json').exists()
        checks.append('original_P2_private_export_drift_rejected_for_every_public_record_type_even_rehashed')
        for mutation in ('method-restore-claim','excluded-source-deletion','batch-plan-list'):
            inputs=t.inputs();path=cr.prepare_outbox(t.store,mutation,inputs,mutation+'.json','2026-09-23T12:00:00Z')
            retained=t.retained(mutation);saved=json.loads(retained.read_text())
            if mutation=='method-restore-claim':
                method=json.loads(saved['attachments']['METHOD.json']);method['public_archive']['self_contained_method_restore']=True
                saved['attachments']['METHOD.json']=canonical(method).decode()
            elif mutation=='excluded-source-deletion':del saved['attachments']['SOURCE/researchlib/public.py']
            else:saved['records'][0]['plan_refs'].pop()
            t.reseal(retained,saved)
            rejected(lambda:cr.prepare_outbox(t.store,mutation,inputs,'must-not-write.json','2026-09-23T12:00:00Z'))
        checks.append('recovery_rejects_forged_METHOD_missing_local_SOURCE_and_incomplete_batch_even_rehashed')
    with fixture() as t:
        inputs=t.inputs();original=cr.prepare_outbox(t.store,'frozen-retry',inputs,'first.json','2026-09-23T12:00:00Z').read_bytes()
        saved=json.loads(original);t.now='2026-09-23T19:00:00Z';t.commit(saved)
        records,_,_=t.store.load(strict=True);new=copy.deepcopy(records[REFS[0]]);new.update(plan_id='late-plan');new.pop('plan_ref',None)
        t.store.commit_bundle('late-plan','research',[new]);t.now='2026-09-23T20:00:00Z'
        recovered=cr.prepare_outbox(t.store,'frozen-retry',inputs,'unused.json','2026-09-23T12:00:00Z')
        assert recovered.read_bytes()==original and len(json.loads(original)['records'][0]['plan_refs'])==2
        t.now='2026-09-23T17:59:59Z'
        rejected(lambda:cr.prepare_outbox(t.store,'frozen-retry',inputs,'rollback.json','2026-09-23T12:00:00Z'))
        checks.append('committed_retry_preserves_original_clock_and_plan_snapshot_and_rejects_clock_rollback')
    with fixture() as t:
        first=t.prepare('correct-before');t.commit(first)
        revised=t.source('revision','2026-09-23','2026-09-24T17:00:00Z',[('0','2026-09-23T00:05:00Z','12345.765432123456789'),('1','2026-09-23T00:05:01Z',PRIVATE_NUMBER)])
        t.now='2026-09-25T00:00:00Z';inputs=t.inputs([revised,t.funding1])
        secret='PRIVATE_CORRECTION_REASON_CANARY_DO_NOT_EXPORT'
        for ref in REFS:
            inputs['plans'][ref]['correction']=cr.correction_proposal(t.store,ref,[revised,t.funding1],'2026-09-23T12:00:00Z',secret)['correction']
        corrected=t.prepare('correct-after',manifest=inputs);invariants(t,corrected);t.commit(corrected)
        t.now='2026-09-25T01:00:00Z';continued=t.prepare('correct-next',[revised,t.funding1]);invariants(t,continued)
        assert continued['records'][0]['coverage']['technical_failures']==0
        site=t.root/'site';publish_snapshot(t.store,site,t.now)
        needles=[PRIVATE_NUMBER.encode(),b'12345.765432123456789',secret.encode(),b'attachments/PRIVATE/']
        for file in site.rglob('*'):
            if file.is_file():assert not any(n in file.read_bytes() for n in needles),file.name
        roots=[corrected['records'][0]['batch_id'],t.reviews(corrected)[0]['review_id'],t.reviews(corrected)[0]['feedback_refs'][0]]
        for n,root in enumerate(roots):
            archive=t.root/f'corrected-{n}.zip';export_backup(t.store,archive,[root]);inspect_backup(archive)
            with zipfile.ZipFile(archive) as z:
                assert any('/SOURCE/researchlib/conditional_review.py' in x for x in z.namelist())
                assert not any('/PRIVATE/' in x or '/SOURCE/researchlib/public.py' in x for x in z.namelist())
                for name in z.namelist():assert not any(v in z.read(name) for v in needles),name
        checks.append('explicit_correction_and_continuation_pass_actual_snapshot_and_three_archive_roots_without_private_data')
        # A committed correction that removes its public correction contract cannot be reused.
        wrong=t.prepare('wrong-correction',manifest=t.inputs([revised,t.funding1]))
        r=t.reviews(wrong)[0];p=t.private(wrong,r)
        p['correction']=copy.deepcopy(inputs['plans'][r['plan_ref']]['correction'])
        t.replace_private(wrong,r,p);t.commit(wrong);t.now='2026-09-25T02:00:00Z'
        next_result=t.prepare('reject-incorrect-correction',[revised,t.funding1])
        assert target(t,next_result,r['plan_ref'])['evaluation_stage']=='TECHNICAL_FAILURE'
        checks.append('private_correction_contract_cannot_disagree_with_actual_public_parent_transition')
    method,attachments=cr.method_material('2026-09-22T00:00:00Z')
    assert len(method['source_sha256'])==16 and method['public_archive']['self_contained_method_restore'] is False
    for name,expected in method['source_sha256'].items():assert digest(attachments['SOURCE/'+name].encode())==expected
    checks.append('all_16_exact_source_bytes_retained_locally_unique_public_exception_remains_explicit')
    print(json.dumps({'state':'PASS_INDEPENDENT_SYNTHETIC_CONDITIONAL_REVIEW_PROBES','groups':len(checks),'checks':checks,
        'module_sha256':hashlib.sha256((args.code_root/'researchlib/conditional_review.py').read_bytes()).hexdigest(),
        'method_code_sha256':method['method_code_sha256'],'runtime':method['runtime'],
        'real_economic_result':False,'production_modified':False},sort_keys=True))


if __name__=='__main__':main()
