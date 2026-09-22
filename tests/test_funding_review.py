"""Status-only engineering fixtures in temporary stores, never production outcomes."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from researchlib import Store
from researchlib.common import ContractError, canonical, digest
from researchlib.contracts import record_ref, validate_relationships
from researchlib.funding_review import (LEGACY_KEYS, ORIGIN, PLAN_HASHES, VERSION,
                                       prepare_bundle, readonly_store, write_outbox)
from researchlib.public import public_record, scan_bytes

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = json.loads((ROOT / 'research/bootstrap-v1/research_bundle.json').read_text())
LEGACY = json.loads((ROOT / 'review/bootstrap-review/review_bundle.json').read_text())


class FundingReview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.now = '2026-09-22T18:07:00Z'
        self.store = Store(self.root, clock=lambda: self.now)
        self.store.commit_bundle('research-fixture', 'research', copy.deepcopy(RESEARCH['records']))
        self.now = '2026-09-22T18:14:00Z'
        self.legacy = copy.deepcopy(LEGACY['records'])
        self.store.commit_bundle('review-fixture', 'review', self.legacy)
        self.now = '2026-09-22T20:00:00Z'

    def tearDown(self):
        self.temp.cleanup()

    def bundle(self, ident='status-1', cutoff=None):
        return prepare_bundle(self.store, ident, cutoff)

    def reviews(self, bundle):
        return [r for r in bundle['records'] if r['record_type'] == 'review']

    def commit(self, bundle):
        return self.store.commit_bundle(bundle['bundle_id'], bundle['role'], bundle['records'], bundle['attachments'], request_key=bundle['request_key'])

    def altered_previous(self, change, ref=None):
        old = next(r for r in self.legacy if r['record_type'] == 'review' and (ref is None or r['plan_ref'] == ref))
        altered = copy.deepcopy(old)
        altered.update(review_id='altered-old', revision=2, supersedes=old['review_id'],
                       correction_reason='SYNTHETIC_TEST_ONLY', created_at='2026-09-22T18:30:00Z',
                       available_at='2026-09-22T18:30:00Z', feedback_refs=[])
        change(altered)
        self.store.commit_bundle('altered-fixture', 'review', [altered])
        return altered['plan_ref']

    def test_two_exact_real_shapes_pre_effective_no_numeric_outcomes(self):
        b = self.bundle()
        self.assertEqual(len(b['records']), 5)
        self.assertEqual(set(b['records'][0]['plan_refs']), set(PLAN_HASHES))
        self.assertTrue(b['records'][0]['complete'])
        for r in self.reviews(b):
            self.assertEqual(r['evaluation_stage'], 'NOT_YET_EFFECTIVE')
            self.assertEqual(r['simulation_state']['inventory'], '0')
            self.assertTrue(all(v is None for v in r['metrics'].values()))
            self.assertIn('ORIGINAL_ENTRY_EVENTS_NOT_YET_OCCURRED', r['coverage']['reason_codes'])
            self.assertIn('FORMAL_SOURCE_ADAPTER_NOT_BOUND_TO_STATUS_METHOD', r['coverage']['reason_codes'])
            self.assertEqual(r['provenance']['method_available_at'], self.now)
            self.assertEqual(r['provenance']['evaluation_information_as_of'], self.now)
        self.commit(b)
        records, _, _ = self.store.load(strict=True)
        validate_relationships(records)

    def test_post_effective_inventory_unknown_never_zero_trade(self):
        self.now = '2026-09-23T08:00:00Z'
        for r in self.reviews(self.bundle()):
            self.assertEqual(r['evaluation_stage'], 'WAITING_DATA')
            self.assertIsNone(r['simulation_state']['inventory'])
            self.assertIsNone(r['metrics']['trade_count'])
            self.assertIsNone(r['simulation_state']['initial_notional'])
            self.assertIn('REMAINING_ORIGINAL_WINDOW_EVENTS_NOT_YET_OCCURRED', r['coverage']['reason_codes'])

    def test_endpoint_elapsed_is_waiting_not_final_or_not_triggered(self):
        self.now = '2026-09-26T08:00:00Z'
        for r in self.reviews(self.bundle()):
            self.assertEqual(r['evaluation_stage'], 'WAITING_DATA')
            self.assertFalse(r['data_complete'])
            self.assertEqual(r['data_cutoff'], '2026-09-24T00:06:00+00:00')
            self.assertIn('ORIGINAL_WINDOW_ELAPSED_REQUIRED_INPUTS_NOT_ACCEPTED', r['coverage']['reason_codes'])

    def test_migration_preserves_previous_bytes_hash_and_new_method_attachment(self):
        before, meta, _ = self.store.load(strict=True)
        hashes = {k: digest(canonical(v)) for k, v in before.items()}
        b = self.bundle()
        self.commit(b)
        after, _, _ = self.store.load(strict=True)
        for r in self.reviews(b):
            old = before[r['previous_review_ref']]
            self.assertEqual(r['opening_state_hash'], digest(canonical(old['simulation_state'])))
            self.assertEqual(r['revision'], old['revision'] + 1)
            resolved = self.store.resolve_evidence(r['review_method_ref'])
            self.assertTrue(resolved)
        self.assertTrue(all(digest(canonical(after[k])) == v for k,v in hashes.items()))

    def test_second_and_third_day_waiting_state_continuity(self):
        first = self.bundle(); self.commit(first)
        self.now = '2026-09-23T08:00:00Z'
        second = self.bundle('status-2'); self.commit(second)
        self.now = '2026-09-24T08:00:00Z'
        third = self.bundle('status-3'); self.commit(third)
        prev = {r['plan_ref']:r for r in self.reviews(second)}
        for r in self.reviews(third):
            self.assertEqual(r['evaluation_stage'], 'WAITING_DATA')
            self.assertEqual(r['previous_review_ref'], prev[r['plan_ref']]['review_id'])
            self.assertEqual(r['opening_state_hash'], digest(canonical(prev[r['plan_ref']]['simulation_state'])))
            self.assertIsNone(r['simulation_state']['inventory'])

    def test_unknown_plan_is_included_and_does_not_block_known_versions(self):
        records, _, _ = self.store.load(strict=True)
        p = copy.deepcopy(next(r for r in records.values() if r['record_type']=='plan'))
        p['plan_id']='unknown-protocol'; p.pop('plan_ref',None)
        self.store.commit_bundle('unknown-fixture','research',[p])
        b = self.bundle()
        self.assertEqual(b['records'][0]['coverage']['registered'],3)
        self.assertEqual(b['records'][0]['coverage']['rules_incomplete'],1)
        self.assertEqual([r['evaluation_stage'] for r in self.reviews(b)].count('NOT_YET_EFFECTIVE'),2)
        self.commit(b)

    def test_modified_known_plan_hash_is_rules_incomplete(self):
        other = tempfile.TemporaryDirectory()
        try:
            s=Store(other.name,clock=lambda:self.now)
            changed=copy.deepcopy(RESEARCH['records'])
            for r in changed:
                if r['record_type']=='plan':r['rules']['quantity_or_inventory']['base_quantity_btc']='999'
            s.commit_bundle('changed','research',changed)
            self.assertTrue(all(r['evaluation_stage']=='RULES_INCOMPLETE' for r in self.reviews(prepare_bundle(s,'b'))))
        finally:other.cleanup()

    def test_unknown_old_state_is_item_failure_not_batch_crash(self):
        ref=self.altered_previous(lambda r:r['simulation_state'].update(state='UNRECOGNIZED'))
        b=self.bundle(); bad=next(r for r in self.reviews(b) if r['plan_ref']==ref)
        self.assertEqual(bad['evaluation_stage'],'TECHNICAL_FAILURE')
        self.assertIsNone(bad['simulation_state'])
        self.assertIsNone(bad['coverage']['actually_evaluated_market_cutoff'])
        self.assertEqual(b['records'][0]['coverage']['technical_failures'],1)
        self.assertEqual([r['evaluation_stage'] for r in self.reviews(b)].count('NOT_YET_EFFECTIVE'),1)
        self.commit(b)

    def test_legacy_positions_events_fills_costs_and_unknown_fields_rejected(self):
        # Validate original whole state, not an asserted opening hash or one field.
        original=next(r for r in self.legacy if r['record_type']=='review')
        self.assertEqual(set(original['simulation_state']),LEGACY_KEYS)
        from researchlib.funding_review import _validate_previous
        plan=next(r for r in RESEARCH['records'] if record_ref(r)==original['plan_ref'])
        mutations=[('inventory','1'),('inventory','NaN'),('inventory',False),('entry_fill',{}),
                   ('exit_fill',0),('processed_event_ids',['e']),('last_event_at','2026-09-22T18:00:00Z'),
                   ('funding_cashflow','0'),('entry_fee','0'),('slippage_cost','0'),('source_rows',[{'private':1}])]
        for key,value in mutations:
            with self.subTest(key=key,value=value):
                r=copy.deepcopy(original);r['simulation_state'][key]=value
                with self.assertRaises(ContractError):_validate_previous(r,plan,r['plan_hash'],'ignored')

    def test_unknown_method_and_kernel_positions_cannot_be_reset(self):
        ref=self.altered_previous(lambda r:r.update(evaluator_version='funding-forward-kernel-v1'))
        r=next(r for r in self.reviews(self.bundle()) if r['plan_ref']==ref)
        self.assertEqual(r['evaluation_stage'],'TECHNICAL_FAILURE')
        self.assertIn('PREVIOUS_METHOD_NOT_BOUND_TO_COMMITTED_REVIEW_BUNDLE',r['coverage']['reason_codes'])

    def test_new_waiting_state_cannot_smuggle_a_position(self):
        first=self.bundle();self.commit(first);self.now='2026-09-23T08:00:00Z'
        original=self.reviews(first)[0];r=copy.deepcopy(original)
        r.update(review_id='bad-waiting',revision=original['revision']+1,supersedes=original['review_id'],
                 correction_reason='SYNTHETIC_TEST_ONLY',created_at='2026-09-23T01:00:00Z',available_at='2026-09-23T01:00:00Z',feedback_refs=[])
        r['simulation_state']['inventory']='1';self.store.commit_bundle('bad-waiting','review',[r])
        second=self.bundle('status-2')
        self.assertEqual(next(x for x in self.reviews(second) if x['plan_ref']==r['plan_ref'])['evaluation_stage'],'TECHNICAL_FAILURE')

    def test_late_committed_review_is_not_known_at_earlier_clock(self):
        self.now='2026-09-23T08:00:00Z'
        self.altered_previous(lambda r:r['simulation_state'].update(state='BAD'))
        self.now='2026-09-22T20:00:00Z'
        self.assertTrue(all(r['evaluation_stage']=='NOT_YET_EFFECTIVE' for r in self.reviews(self.bundle())))

    def test_future_or_naive_market_time_rejected_and_past_market_separate(self):
        for cutoff in ['2026-09-26T00:00:00Z','2026-09-22T19:00:00']:
            with self.assertRaises(ContractError):self.bundle(cutoff=cutoff)
        self.now='2026-09-24T08:00:00Z'
        b=self.bundle(cutoff='2026-09-23T10:00:00Z')
        for r in self.reviews(b):
            self.assertEqual(r['coverage']['information_as_of'],self.now)
            self.assertEqual(r['data_cutoff'],'2026-09-23T10:00:00Z')
            self.assertEqual(r['provenance']['method_available_at'],self.now)

    def test_market_after_endpoint_is_explicit_item_failure_without_future_cursor(self):
        self.now='2026-09-26T08:00:00Z'
        b=self.bundle(cutoff='2026-09-25T00:00:00Z')
        for r in self.reviews(b):
            self.assertEqual(r['evaluation_stage'],'TECHNICAL_FAILURE')
            self.assertIn('MARKET_CUTOFF_AFTER_ORIGINAL_ENDPOINT',r['coverage']['reason_codes'])
            self.assertIsNone(r['coverage']['market_event_cutoff'])
        self.commit(b)

    def test_no_kernel_call_and_no_native_header_attestation(self):
        with patch('researchlib.funding_forward.evaluate',side_effect=AssertionError('kernel must not be called')):
            b=self.bundle()
        self.assertFalse(b['preparation']['natural_trigger'])
        for r in b['records']:
            self.assertEqual(r['provenance']['trigger_origin'],ORIGIN)
            self.assertIsNone(r['provenance']['native_task_ref'])
        with self.assertRaises(TypeError):prepare_bundle(self.store,'forged',native_task_ref='fake')
        with self.assertRaises(TypeError):prepare_bundle(self.store,'backdate',information_as_of='2020-01-01T00:00:00Z')

    def test_same_preparation_deterministic_committed_batch_refused(self):
        b=self.bundle();self.assertEqual(canonical(b),canonical(self.bundle()))
        self.commit(b)
        with self.assertRaises(ContractError):self.bundle()

    def test_outbox_exclusive_and_symlink_path_refusal(self):
        b=self.bundle();p=write_outbox(self.root,'new/result.json',b);before=p.read_bytes()
        with self.assertRaises(FileExistsError):write_outbox(self.root,'new/result.json',b)
        self.assertEqual(p.read_bytes(),before)
        for name in ['../../escape.json','/escape.json','a/../b.json','bad\\x.json']:
            with self.assertRaises(ContractError):write_outbox(self.root,name,b)
        (p.parent/'link').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(OSError):write_outbox(self.root,'new/link/x.json',b)
        p.parent.joinpath('final.json').symlink_to(p)
        with self.assertRaises(OSError):write_outbox(self.root,'new/final.json',b)

    def test_readonly_store_never_mkdir_and_no_source_rows_or_private_paths(self):
        with patch('pathlib.Path.mkdir',side_effect=AssertionError('read-only reader creates no directories')):
            s=readonly_store(self.root);s.load(strict=True)
        b=self.bundle()
        for r in b['records']:
            self.assertEqual(set(public_record(r)),set(r))
            scan_bytes('record.json',canonical(r))
        for name,text in b['attachments'].items():scan_bytes(name,text.encode())
        self.assertNotIn('source_rows',canonical(b).decode())

    def test_late_committed_plan_excluded_without_inventing_early_identity(self):
        records, _, _ = self.store.load(strict=True)
        plan=copy.deepcopy(next(r for r in records.values() if r['record_type']=='plan'))
        plan['plan_id']='late-plan';plan.pop('plan_ref',None)
        self.now='2026-09-23T08:00:00Z'
        self.store.commit_bundle('late-plan-fixture','research',[plan])
        self.now='2026-09-22T20:00:00Z'
        b=self.bundle()
        self.assertEqual(set(b['records'][0]['plan_refs']),set(PLAN_HASHES))

    def test_outbox_ancestor_symlink_and_invalid_payload_never_write(self):
        with tempfile.TemporaryDirectory() as other:
            root=Path(other); (root/'.local').symlink_to(self.root,target_is_directory=True)
            with self.assertRaises(OSError):write_outbox(root,'blocked.json',self.bundle())
        with self.assertRaises(ValueError):write_outbox(self.root,'nonfinite.json',{'value':float('nan')})
        self.assertFalse((self.root/'.local/review-outbox/nonfinite.json').exists())

    def test_cli_prepares_but_does_not_commit_temporary_store(self):
        before=self.store.load(strict=True)[0]
        p=subprocess.run([sys.executable,str(ROOT/'scripts/prepare_funding_review.py'),
            '--project-root',str(self.root),'--batch-id','cli-success','--output','cli.json'],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(before,self.store.load(strict=True)[0])
        bundle=json.loads((self.root/'.local/review-outbox/cli.json').read_text())
        self.assertEqual(bundle['preparation']['trigger_origin'],ORIGIN)
        self.assertFalse(bundle['preparation']['natural_trigger'])
        self.assertEqual(json.loads(p.stdout)['state'],'OUTBOX_PREPARED_NOT_COMMITTED')

    def test_batch_preparation_identity_is_independent_of_output_path(self):
        first=self.bundle('same-batch');path=write_outbox(self.root,'first.json',first)
        self.now='2026-09-22T20:01:00Z';second=self.bundle('same-batch')
        self.assertNotEqual(canonical(first),canonical(second))
        for candidate in (first,second):
            with self.assertRaisesRegex(ContractError,'BATCH_ALREADY_PREPARED'):
                write_outbox(self.root,'second.json',candidate)
        self.assertEqual(path.read_bytes(),canonical(first))
        self.assertFalse((path.parent/'second.json').exists())

    def test_interrupted_export_preserves_complete_prepared_original(self):
        from researchlib.funding_review import _publish_exclusive
        b=self.bundle();calls=[]
        def fail_export(fd,name,payload):
            calls.append(name)
            if len(calls)==2:raise OSError('SYNTHETIC_EXPORT_INTERRUPTION')
            return _publish_exclusive(fd,name,payload)
        with patch('researchlib.funding_review._publish_exclusive',side_effect=fail_export):
            with self.assertRaises(OSError):write_outbox(self.root,'interrupted.json',b)
        retained=list((self.root/'.local/review-outbox/.prepared-batches').glob('*.json'))
        self.assertEqual(len(retained),1);self.assertEqual(retained[0].read_bytes(),canonical(b))
        with self.assertRaisesRegex(ContractError,'BATCH_ALREADY_PREPARED'):
            write_outbox(self.root,'retry.json',b)

    def test_preparation_race_has_only_one_batch_original(self):
        from concurrent.futures import ThreadPoolExecutor
        b=self.bundle()
        def write(name):
            try:write_outbox(self.root,name,b);return 'created'
            except ContractError:return 'refused'
        with ThreadPoolExecutor(max_workers=2) as executor:
            results=list(executor.map(write,['a.json','b.json']))
        self.assertEqual(sorted(results),['created','refused'])
        self.assertEqual(len(list((self.root/'.local/review-outbox').glob('*.json'))),1)

    def test_dependency_closure_contains_package_initialization_and_runtime(self):
        from researchlib.funding_review import method_material
        method,_=method_material(self.now)
        for source in ['researchlib/__init__.py','researchlib/store.py','researchlib/snapshot.py',
                       'researchlib/public.py','researchlib/readiness.py','researchlib/novelty.py',
                       'scripts/prepare_funding_review.py']:
            self.assertIn(source,method['source_sha256'])
            self.assertEqual(method['source_sha256'][source],digest((ROOT/source).read_bytes()))
        self.assertTrue(method['runtime']['python_version'])

    def test_new_waiting_method_requires_resolvable_exact_committed_evidence(self):
        b=self.bundle();self.commit(b);old=self.reviews(b)[0]
        r=copy.deepcopy(old);r.update(review_id='forged-method-review',revision=old['revision']+1,
            supersedes=old['review_id'],correction_reason='SYNTHETIC_TEST_ONLY',feedback_refs=[],
            created_at='2026-09-22T21:00:00Z',available_at='2026-09-22T21:00:00Z',
            review_method_ref='unresolved-method')
        self.now='2026-09-22T22:00:00Z';self.store.commit_bundle('forged-method','review',[r])
        result=next(x for x in self.reviews(self.bundle('status-2')) if x['plan_ref']==r['plan_ref'])
        self.assertEqual(result['evaluation_stage'],'TECHNICAL_FAILURE')
        self.assertIn('PREVIOUS_METHOD_NOT_BOUND_TO_COMMITTED_REVIEW_BUNDLE',result['coverage']['reason_codes'])

    def test_legacy_cloned_id_is_not_an_original_bridge(self):
        self.altered_previous(lambda r:None)
        self.assertIn('LEGACY_REVIEW_NOT_ONE_OF_TWO_FROZEN_ORIGINALS',
            next(r for r in self.reviews(self.bundle()) if r['evaluation_stage']=='TECHNICAL_FAILURE')['coverage']['reason_codes'])

    def test_cli_has_no_backdating_or_native_identity_options(self):
        command=[sys.executable,str(ROOT/'scripts/prepare_funding_review.py'),'--project-root',str(self.root),'--batch-id','cli','--output','cli.json']
        for extra in [['--information-as-of','2020-01-01T00:00:00Z'],['--native-task-ref','fake'],['--trigger-origin','NATURAL']]:
            p=subprocess.run(command+extra,capture_output=True,text=True)
            self.assertEqual(p.returncode,2)
            self.assertFalse((self.root/'.local/review-outbox/cli.json').exists())


if __name__=='__main__':unittest.main()
