"""Isolated Store tests. Synthetic facts never enter a production backend."""
import copy
from dataclasses import replace
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile
from researchlib.common import canonical, digest, ContractError
from researchlib import conditional_review as cr
from researchlib import formal_review as fr
from researchlib import funding_review as waiting
from researchlib.snapshot import publish_snapshot
from researchlib.archive import export_backup
import test_conditional_review as fixture
from test_conditional_review import REFS, PRIVATE_NUMBER, old_waiting_material
from test_formal_funding import resolution, END, INFO


class FormalReviewTests(unittest.TestCase):
    setUp=fixture.ConditionalReviewTests.setUp
    source=fixture.ConditionalReviewTests.source
    millis=staticmethod(fixture.ConditionalReviewTests.millis)
    inputs=fixture.ConditionalReviewTests.inputs
    reviews=fixture.ConditionalReviewTests.reviews
    commit=fixture.ConditionalReviewTests.commit
    private=fixture.ConditionalReviewTests.private
    retained=fixture.ConditionalReviewTests.retained
    reseal=staticmethod(fixture.ConditionalReviewTests.reseal)

    def prepare(self, ident='f1', sources=None, cutoff='2026-09-23T12:00:00Z', manifest=None):
        return fr.prepare_bundle(self.store,ident,manifest or self.inputs(sources),cutoff)

    def fixture_resolver(self, store, plan, requests, records, metadata, at, cutoff, context):
        # No request chooses this; unit tests explicitly patch the module binding.
        return resolution(plan,cutoff,info=at)

    def assert_ok(self,b):
        self.assertTrue(all(r['evaluation_stage']!='TECHNICAL_FAILURE' for r in self.reviews(b)),b['records'][0])

    def test_real_decode_path_from_legacy_has_no_granted_business_capabilities(self):
        b=self.prepare();self.assert_ok(b)
        self.assertEqual(b['records'][0]['coverage']['new_economic_computations'],0)
        for r in self.reviews(b):
            self.assertEqual(r['evaluation_stage'],'WAITING_DATA')
            self.assertTrue(all(v is None for v in r['metrics'].values()))
            self.assertIsNone(r['simulation_state']['inventory'])
            self.assertEqual(len(r['results']['scenarios']),12)
            self.assertEqual(self.private(b,r)['formal_result']['capabilities'],[])
        self.commit(b)

    def test_deployed_7db_complete_chain_migrates_without_reset(self):
        old=cr.prepare_bundle(self.store,'old7db',self.inputs(),'2026-09-23T12:00:00Z');self.commit(old)
        self.now='2026-09-23T19:00:00Z'
        b=self.prepare();self.assert_ok(b)
        for r in self.reviews(b):
            prior=next(x for x in self.reviews(old) if x['plan_ref']==r['plan_ref'])
            self.assertEqual(r['opening_state_hash'],digest(canonical(prior['simulation_state'])))
            self.assertEqual(self.private(b,r)['kernel_result']['opening_state_hash'],digest(canonical(self.private(old,prior)['kernel_result']['simulation_state'])))
        self.commit(b);self.now='2026-09-23T20:00:00Z'
        self.assert_ok(self.prepare('f2'))

    def test_both_waiting_profiles_bridge_and_wrong_runtime_rejects(self):
        with patch.object(waiting,'method_material',side_effect=old_waiting_material):
            old=waiting.prepare_bundle(self.store,'old-waiting','2026-09-23T12:00:00Z')
        self.commit(old);self.now='2026-09-23T19:00:00Z'
        self.assert_ok(self.prepare())
        with patch('platform.python_version',return_value='3.12.99'),self.assertRaises(ContractError):self.prepare('runtime')

    def test_changed_old_closure_cannot_be_relabelled_current(self):
        with patch.object(fr,'APPROVED_CONDITIONAL_HASH','0'*64),self.assertRaises(ContractError):self.prepare()

    def test_full_chain_once_and_split_inventory_metrics(self):
        with patch.object(fr,'_resolve_sources',side_effect=self.fixture_resolver):
            first=self.prepare(sources=[],cutoff='2026-09-23T16:00:00Z');self.assert_ok(first);self.commit(first)
            self.now=INFO
            second=self.prepare('f2',sources=[],cutoff=END);self.assert_ok(second)
            for r in self.reviews(second):
                self.assertEqual(r['evaluation_stage'],'FINAL');self.assertEqual(r['metrics']['trade_count'],2)
                self.assertEqual(r['simulation_state']['inventory'],'0')
                plan=self.store.load()[0][r['plan_ref']]
                from researchlib.formal_funding import _compute
                once=_compute(plan,resolution(plan,info=self.now))
                self.assertEqual(r['metrics']['gross_price_pnl'],once['metrics']['gross_price_pnl'])
                self.assertEqual(r['results']['scenarios'],once['scenarios'])
            self.commit(second)

    def test_final_reuse_carriers_preserve_economic_time_and_generic_exports(self):
        self.now=INFO
        with patch.object(fr,'_resolve_sources',side_effect=self.fixture_resolver):
            final=self.prepare(sources=[],cutoff=END);self.assert_ok(final);self.commit(final)
            original={r['plan_ref']:r for r in self.reviews(final)}
            self.now='2026-09-25T01:00:00Z'
            reused=self.prepare('reuse',sources=[],cutoff=END);self.assert_ok(reused)
            self.assertEqual(reused['records'][0]['coverage']['reused'],2)
            self.assertEqual(reused['records'][0]['coverage']['reviewed'],2)
            self.assertEqual(reused['records'][0]['coverage']['new_economic_computations'],0)
            for r in self.reviews(reused):
                parent=original[r['plan_ref']]
                self.assertEqual(r['disposition'],'REUSED_FINAL')
                self.assertEqual(r['results']['economic_computation_information_as_of'],INFO)
                self.assertFalse(r['results']['economic_recomputed'])
                self.assertEqual(r['available_at'],self.now)
                self.assertEqual(r['opening_state_hash'],fr.sha(parent['simulation_state']))
                self.assertEqual(self.private(reused,r)['kernel_result'],self.private(final,parent)['kernel_result'])
            self.commit(reused)
            public=self.root/'reuse-public';published=publish_snapshot(self.store,public,self.now)
            catalog=json.loads((public/published['catalog_url']).read_text())
            batch=next(b for b in catalog['review_batches'] if b['batch_id']=='reuse')
            self.assertEqual(batch['coverage']['reviewed'],2);self.assertEqual(batch['coverage']['missing'],[])
            for ref in ['reuse',self.reviews(reused)[0]['review_id']]:
                path=self.root/(ref+'-archive.zip');export_backup(self.store,path,record_refs=[ref])
                with zipfile.ZipFile(path) as z:
                    expected=list(original.values()) if ref=='reuse' else [original[self.reviews(reused)[0]['plan_ref']]]
                    for old in expected:self.assertIn('records/'+old['review_id']+'.json',z.namelist())
                    self.assertFalse(any('/PRIVATE/' in n for n in z.namelist()))
            self.now='2026-09-25T02:00:00Z'
            again=self.prepare('reuse-again',sources=[],cutoff=END);self.assert_ok(again)
            self.assertEqual(again['records'][0]['coverage']['reused'],2)
            for r in self.reviews(again):self.assertEqual(r['results']['economic_computation_information_as_of'],INFO)

    def test_final_cannot_reuse_with_capabilities_revoked(self):
        self.now=INFO
        with patch.object(fr,'_resolve_sources',side_effect=self.fixture_resolver):
            final=self.prepare(sources=[],cutoff=END);self.commit(final)
        self.now='2026-09-25T01:00:00Z'
        # Lost historical capability evidence makes the public FINAL unsafe to reference.
        with self.assertRaisesRegex(ContractError,'PUBLIC_ANCESTOR_PUBLIC_RECONSTRUCTION_REJECTED'):
            self.prepare('not-reuse',sources=[],cutoff=END)

    def test_forged_source_claims_and_unknown_backend_rejected(self):
        for field,value in [('events',[]),('verified',True),('coverage',True),('backend','test')]:
            manifest=self.inputs();manifest['plans'][REFS[0]][field]=value
            b=self.prepare('claim-'+field,manifest=manifest)
            self.assertEqual(b['records'][0]['coverage']['technical_failures'],1)
        request=copy.deepcopy(self.trade1);request['adapter']='TEST_VERIFIED'
        b=self.prepare('backend',sources=[request])
        self.assertTrue(all(r['evaluation_stage']=='TECHNICAL_FAILURE' for r in self.reviews(b)))

    def test_bad_latest_not_skipped_and_other_plan_survives(self):
        b=self.prepare();r=self.reviews(b)[0];r['simulation_state']['inventory']='0'
        self.commit(b);self.now='2026-09-23T19:00:00Z'
        next_b=self.prepare('f2')
        failed=[x for x in self.reviews(next_b) if x['evaluation_stage']=='TECHNICAL_FAILURE']
        self.assertEqual(len(failed),1);self.assertEqual(failed[0]['previous_review_ref'],r['review_id'])
        self.assertTrue(next_b['records'][0]['complete'])

    def test_missing_private_attachment_is_not_empty_state(self):
        b=self.prepare();r=self.reviews(b)[0];del b['attachments']['PRIVATE/'+r['review_id']+'.json']
        self.commit(b);self.now='2026-09-23T19:00:00Z'
        # The public projection cannot be fully proven without its private evidence.
        with self.assertRaisesRegex(ContractError,'PREVIOUS_ATTACHMENT_INVALID'):
            self.prepare('f2')

    def test_changed_private_or_public_capabilities_do_not_grant_metrics(self):
        b=self.prepare();r=self.reviews(b)[0];name='PRIVATE/'+r['review_id']+'.json'
        private=json.loads(b['attachments'][name]);private['formal_result']['capabilities']=['COST_SCHEDULE']
        raw=canonical(private);b['attachments'][name]=raw.decode();r['simulation_state']['private_computation_sha256']=digest(raw)
        self.commit(b);self.now='2026-09-23T19:00:00Z'
        self.assertEqual(self.prepare('f2')['records'][0]['coverage']['technical_failures'],1)

    def test_late_source_requires_bound_correction_then_continues(self):
        first=self.prepare();self.commit(first)
        revised=self.source('revised','2026-09-23','2026-09-24T17:00:00Z',[('1','2026-09-23T00:05:01Z','999')])
        self.now=INFO
        manifest=self.inputs([revised,self.funding1])
        ordinary=self.prepare('ordinary',manifest=manifest)
        self.assertTrue(all(r['coverage']['reason_codes']==['EXPLICIT_CORRECTION_REQUIRED'] for r in self.reviews(ordinary)))
        for ref in REFS:
            manifest['plans'][ref]['correction']=fr.correction_proposal(self.store,ref,[revised,self.funding1],'2026-09-23T12:00:00Z','PRIVATE_CORRECTION_CANARY')
        fixed=self.prepare('fixed',manifest=manifest);self.assert_ok(fixed)
        self.assertTrue(all('supersedes' in r for r in self.reviews(fixed)))
        self.assertNotIn('PRIVATE_CORRECTION_CANARY',canonical(fixed['records']).decode())
        self.commit(fixed);self.now='2026-09-25T01:00:00Z'
        self.assert_ok(self.prepare('next',sources=[revised,self.funding1]))
        self.assert_public_safe(fixed)

    def assert_public_safe(self,b):
        public=self.root/'public';publish_snapshot(self.store,public,self.now)
        blobs=[p.read_bytes() for p in public.rglob('*') if p.is_file()]
        for ref in (self.reviews(b)[0]['review_id'],b['records'][0]['batch_id'],self.reviews(b)[0]['feedback_refs'][0]):
            target=self.root/(ref+'.zip');export_backup(self.store,target,record_refs=[ref])
            with zipfile.ZipFile(target) as z:
                self.assertFalse(any('/PRIVATE/' in name for name in z.namelist()))
                contents=[z.read(name) for name in z.namelist()];blobs+=contents
                self.assertTrue(any(b'funding-formal-review-v1' in x for x in contents))
        for blob in blobs:
            self.assertNotIn(PRIVATE_NUMBER.encode(),blob)
            self.assertNotIn(b'PRIVATE_CORRECTION_CANARY',blob)
            self.assertNotIn(b'"private_equity_paths"',blob) if not blob.startswith(b'"""') else None

    def test_outbox_retry_freezes_time_and_whole_bundle_and_committed_original(self):
        path=fr.prepare_outbox(self.store,'out',self.inputs(),'out.json','2026-09-23T12:00:00Z')
        original=path.read_bytes();self.now='2026-09-23T19:00:00Z'
        recovered=fr.prepare_outbox(self.store,'out',self.inputs(),'unused.json','2026-09-23T12:00:00Z')
        self.assertEqual(recovered.read_bytes(),original)
        self.commit(json.loads(original));self.now='2026-09-23T20:00:00Z'
        self.assertEqual(fr.prepare_outbox(self.store,'out',self.inputs(),'unused2.json','2026-09-23T12:00:00Z').read_bytes(),original)

    def test_outbox_self_hash_does_not_authorize_private_public_license(self):
        fr.prepare_outbox(self.store,'out',self.inputs(),'out.json','2026-09-23T12:00:00Z')
        retained=self.retained('out');saved=json.loads(retained.read_text())
        name=next(n for n in saved['attachments'] if n.startswith('PRIVATE/'))
        saved['records'][-1]['disclosure']['public_attachments'].append('attachments/'+name)
        self.reseal(retained,saved)
        with self.assertRaises(ContractError):fr.prepare_outbox(self.store,'out',self.inputs(),'retry.json','2026-09-23T12:00:00Z')

    def test_old_outbox_cannot_be_reinterpreted_as_new_method(self):
        old=cr.prepare_outbox(self.store,'old-out',self.inputs(),'old.json','2026-09-23T12:00:00Z')
        original=old.read_bytes()
        with self.assertRaises(ContractError):fr.prepare_outbox(self.store,'old-out',self.inputs(),'new.json','2026-09-23T12:00:00Z')
        self.assertEqual(old.read_bytes(),original)
        self.assertEqual(cr.prepare_outbox(self.store,'old-out',self.inputs(),'retry.json','2026-09-23T12:00:00Z').read_bytes(),original)

    def test_chain_limits_and_deadline_fail_per_item(self):
        b=self.prepare();self.commit(b);self.now='2026-09-23T19:00:00Z'
        with patch.object(fr,'MAX_HISTORY_REVIEWS',1):
            bad=self.prepare('limit')
        self.assertTrue(all(r['evaluation_stage']=='TECHNICAL_FAILURE' for r in self.reviews(bad)))
        # Exhausted budget before public ancestry is proven produces no bundle.
        with patch.object(cr,'MAX_VALIDATION_SECONDS',-1),self.assertRaises(ContractError):
            self.prepare('deadline')

    def test_after_effective_historical_cutoff_inventory_stays_unknown(self):
        b=self.prepare(sources=[],cutoff='2026-09-22T20:00:00Z');self.assert_ok(b)
        for r in self.reviews(b):
            self.assertEqual(r['evaluation_stage'],'WAITING_DATA');self.assertIsNone(r['simulation_state']['inventory'])

    def test_unknown_plan_still_gets_complete_batch_disposition(self):
        records,_,_=self.store.load();p=copy.deepcopy(records[REFS[0]])
        p['plan_id']='unimplemented-plan';p['plan_ref']=p['plan_id']+'@1'
        self.store.commit_bundle('unsupported','research',[p])
        b=self.prepare();self.assertEqual(b['records'][0]['coverage']['registered'],3)
        self.assertTrue(b['records'][0]['complete'])
        self.assertTrue(any(r['evaluation_stage']=='RULES_INCOMPLETE' for r in self.reviews(b)))

    def test_public_method_provenance_mismatch_is_single_plan_failure(self):
        b=self.prepare();r=self.reviews(b)[0];r['provenance']=dict(r['provenance'],method_code_sha256='0'*64)
        self.commit(b);self.now='2026-09-23T19:00:00Z'
        next_b=self.prepare('next')
        failed=[x for x in self.reviews(next_b) if x['evaluation_stage']=='TECHNICAL_FAILURE']
        self.assertEqual(len(failed),1)
        self.assertEqual(failed[0]['coverage']['reason_codes'],['PREVIOUS_PROVENANCE_BINDING_INVALID'])

    def test_unknown_evaluator_cannot_bypass_ancestor_private_permissions(self):
        old=cr.prepare_bundle(self.store,'old7db',self.inputs(),'2026-09-23T12:00:00Z')
        for r in self.reviews(old):r['evaluator_version']='UNKNOWN_METHOD'
        private=next(n for n in old['attachments'] if n.startswith('PRIVATE/'))
        old['records'][-1]['disclosure']=copy.deepcopy(old['records'][-1]['disclosure'])
        old['records'][-1]['disclosure']['public_attachments'].append('attachments/'+private)
        self.commit(old);self.now='2026-09-23T19:00:00Z'
        refs_before=set(self.store.load()[0])
        with self.assertRaisesRegex(ContractError,'PUBLIC_ANCESTOR_POLICY_REJECTED'):
            fr.prepare_outbox(self.store,'unsafe',self.inputs(),'unsafe.json','2026-09-23T12:00:00Z')
        self.assertEqual(set(self.store.load()[0]),refs_before)
        self.assertFalse(self.retained('unsafe').exists())
        self.assertFalse((self.root/'unsafe.json').exists())

    def test_renamed_unknown_layout_is_rejected_before_new_public_root(self):
        old=cr.prepare_bundle(self.store,'old-renamed',self.inputs(),'2026-09-23T12:00:00Z')
        renamed={name: name.replace('SOURCE/','renamed-code/').replace('PRIVATE/','renamed-input/')
                 for name in old['attachments']}
        old['attachments']={renamed[name]: value for name,value in old['attachments'].items()}
        for record in old['records']:
            record['disclosure']=copy.deepcopy(record['disclosure'])
            record['disclosure']['public_attachments']=['attachments/'+renamed[name[len('attachments/'):]]
                for name in record['disclosure']['public_attachments']]
        for r in self.reviews(old):r['evaluator_version']='UNKNOWN_METHOD'
        for record in old['records']:
            record['disclosure']['public_attachments'].append(
                'attachments/'+next(name for name in old['attachments'] if name.startswith('renamed-input/')))
        self.commit(old);self.now='2026-09-23T19:00:00Z'
        # Establish that the attack is real through the unchanged generic
        # exporters; both are isolated temporary artifacts, never production.
        archive=self.root/'unsafe-ancestor.zip'
        export_backup(self.store,archive,record_refs=['old-renamed'])
        with zipfile.ZipFile(archive) as z:
            self.assertTrue(any(PRIVATE_NUMBER.encode() in z.read(name) for name in z.namelist()))
        public=self.root/'unsafe-ancestor-public'
        publish_snapshot(self.store,public,self.now)
        self.assertTrue(any(PRIVATE_NUMBER.encode() in p.read_bytes() for p in public.rglob('*') if p.is_file()))
        before=set(self.store.load()[0])
        with self.assertRaises(ContractError):
            fr.prepare_outbox(self.store,'unsafe-renamed',self.inputs(),'unsafe-renamed.json','2026-09-23T12:00:00Z')
        self.assertEqual(before,set(self.store.load()[0]))
        self.assertFalse(self.retained('unsafe-renamed').exists())

    def test_nested_public_extra_is_rejected_by_full_reconstruction(self):
        old=cr.prepare_bundle(self.store,'old-extra',self.inputs(),'2026-09-23T12:00:00Z')
        r=self.reviews(old)[0]
        r['coverage']['raw_prices']={'renamed':[PRIVATE_NUMBER]}
        self.commit(old);self.now='2026-09-23T19:00:00Z'
        archive=self.root/'unsafe-extra.zip'
        export_backup(self.store,archive,record_refs=[r['review_id']])
        with zipfile.ZipFile(archive) as z:
            self.assertTrue(any(PRIVATE_NUMBER.encode() in z.read(name) for name in z.namelist()))
        public=self.root/'unsafe-extra-public'
        publish_snapshot(self.store,public,self.now)
        self.assertTrue(any(PRIVATE_NUMBER.encode() in p.read_bytes() for p in public.rglob('*') if p.is_file()))
        before=set(self.store.load()[0])
        with self.assertRaisesRegex(ContractError,'PUBLIC_ANCESTOR_PUBLIC_RECONSTRUCTION_REJECTED'):
            fr.prepare_outbox(self.store,'unsafe-extra',self.inputs(),'unsafe-extra.json','2026-09-23T12:00:00Z')
        self.assertEqual(before,set(self.store.load()[0]))
        self.assertFalse(self.retained('unsafe-extra').exists())

    def test_bad_identity_cannot_bypass_feedback_text_gate(self):
        old=cr.prepare_bundle(self.store,'old7db',self.inputs(),'2026-09-23T12:00:00Z')
        r=self.reviews(old)[0];r['provenance']=dict(r['provenance'],method_code_sha256='0'*64)
        feedback=next(f for f in old['records'] if f.get('feedback_id')==r['feedback_refs'][0])
        feedback['supported_facts'].append(PRIVATE_NUMBER)
        self.commit(old);self.now='2026-09-23T19:00:00Z'
        with self.assertRaisesRegex(ContractError,'PUBLIC_ANCESTOR_DERIVED_TEXT_REJECTED'):
            self.prepare('unsafe')

    def test_combined_old_and_new_cached_bytes_budget_is_enforced(self):
        old=cr.prepare_bundle(self.store,'old7db',self.inputs(),'2026-09-23T12:00:00Z');self.commit(old)
        self.now='2026-09-23T19:00:00Z';first=self.prepare();self.commit(first)
        self.now='2026-09-23T20:00:00Z';second=self.prepare('second');self.commit(second)
        self.now='2026-09-23T21:00:00Z'
        records,metadata,_=self.store.load();method,_=fr.method_material(self.now);context=fr._context()
        r=self.reviews(second)[0];fr._previous(self.store,records[r['review_id']],records[r['plan_ref']],records,metadata,method,context)
        total=context['encoded_bytes']+context['old_context']['encoded_bytes']
        self.assertGreater(total,max(context['encoded_bytes'],context['old_context']['encoded_bytes']))
        with patch.object(cr,'MAX_CONTEXT_BYTES',total-1):
            with self.assertRaisesRegex(ContractError,'COMBINED_HISTORY_RESOURCE_LIMIT_EXCEEDED'):
                fr._previous(self.store,records[r['review_id']],records[r['plan_ref']],records,metadata,method,fr._context())

    def test_mixed_final_reuse_and_new_missing_item_stays_in_public_batch(self):
        def mixed(store,plan,requests,records,metadata,at,cutoff,context):
            value=self.fixture_resolver(store,plan,requests,records,metadata,at,cutoff,context)
            return replace(value,capabilities=value.capabilities-{'MARK_PATH'}) if plan['plan_id'].endswith('short-20260923') else value
        self.now=INFO
        with patch.object(fr,'_resolve_sources',side_effect=mixed):
            first=self.prepare(sources=[],cutoff=END);self.commit(first)
            self.now='2026-09-25T01:00:00Z'
            second=self.prepare('mixed',sources=[],cutoff=END);self.assert_ok(second)
            self.assertEqual(second['records'][0]['coverage']['reused'],1)
            self.assertEqual(second['records'][0]['coverage']['reviewed'],2)
            self.commit(second)
            public=self.root/'mixed-public';latest=publish_snapshot(self.store,public,self.now)
            catalog=json.loads((public/latest['catalog_url']).read_text())
            batch=next(b for b in catalog['review_batches'] if b['batch_id']=='mixed')
            self.assertEqual(batch['coverage']['missing'],[])
            path=self.root/'mixed.zip';export_backup(self.store,path,record_refs=['mixed'])
            with zipfile.ZipFile(path) as z:
                for r in self.reviews(first)+self.reviews(second):self.assertIn('records/'+r['review_id']+'.json',z.namelist())
                self.assertFalse(any('/PRIVATE/' in n for n in z.namelist()))

    def test_cost_fact_revision_is_explicit_bound_correction_not_silent_recompute(self):
        changed_at='2026-09-25T01:00:00Z'
        def revised(store,plan,requests,records,metadata,at,cutoff,context):
            value=self.fixture_resolver(store,plan,requests,records,metadata,at,cutoff,context)
            return replace(value,actual_costs=dict(value.actual_costs,entry_fee='0.004')) if at>=changed_at else value
        self.now=INFO
        with patch.object(fr,'_resolve_sources',side_effect=revised):
            first=self.prepare(sources=[],cutoff=END);self.commit(first)
            self.now=changed_at
            ordinary=self.prepare('ordinary',sources=[],cutoff=END)
            self.assertTrue(all(r['coverage']['reason_codes']==['EXPLICIT_FACT_CORRECTION_REQUIRED'] for r in self.reviews(ordinary)))
            inputs=self.inputs([])
            for ref in REFS:
                inputs['plans'][ref]['correction']=fr.correction_proposal(self.store,ref,[],END,'PRIVATE_CORRECTION_CANARY')
                self.assertEqual(inputs['plans'][ref]['correction']['event_diff'],{'added':[],'removed':[],'changed':[]})
                self.assertEqual(set(inputs['plans'][ref]['correction']['fact_diff']),{'cost_allocation'})
            bad=copy.deepcopy(inputs);bad['plans'][REFS[0]]['correction']['old_fact_fingerprint']='0'*64
            self.assertEqual(self.prepare('bad',manifest=bad,cutoff=END)['records'][0]['coverage']['technical_failures'],1)
            fixed=self.prepare('fixed',manifest=inputs,cutoff=END);self.assert_ok(fixed)
            self.assertTrue(all(r.get('supersedes') for r in self.reviews(fixed)))
            self.commit(fixed);self.assert_public_safe(fixed)
            self.now='2026-09-25T02:00:00Z'
            follow=self.prepare('follow',sources=[],cutoff=END);self.assert_ok(follow)
            self.assertEqual(follow['records'][0]['coverage']['reused'],2)

    def test_capability_fact_change_requires_explicit_correction(self):
        changed_at='2026-09-25T01:00:00Z'
        def revised(store,plan,requests,records,metadata,at,cutoff,context):
            value=self.fixture_resolver(store,plan,requests,records,metadata,at,cutoff,context)
            return replace(value,capabilities=value.capabilities-{'MARK_PATH'}) if at>=changed_at else value
        self.now=INFO
        with patch.object(fr,'_resolve_sources',side_effect=revised):
            self.commit(self.prepare(sources=[],cutoff=END));self.now=changed_at
            inputs=self.inputs([])
            for ref in REFS:inputs['plans'][ref]['correction']=fr.correction_proposal(self.store,ref,[],END,'Authority corrected')
            fixed=self.prepare('fixed',manifest=inputs,cutoff=END);self.assert_ok(fixed)
            self.assertTrue(all(r['evaluation_stage']=='MISSING_DATA' for r in self.reviews(fixed)))
            self.assertTrue(all(r['metrics']['gross_price_pnl'] is not None for r in self.reviews(fixed)))
            self.commit(fixed)

    def test_ancestor_batch_mutations_cannot_authorize_public_derived_claims(self):
        b=self.prepare();b['records'][0]['items'][0]['reason_codes']=['ARBITRARY_PRIVATE_TEXT']
        self.commit(b);self.now='2026-09-23T19:00:00Z'
        with self.assertRaisesRegex(ContractError,'PUBLIC_ANCESTOR_FROZEN_BATCH_REJECTED'):
            self.prepare('next')

    def test_middle_formal_self_consistent_reset_does_not_erase_prefix(self):
        first=self.prepare();self.commit(first);self.now='2026-09-23T19:00:00Z'
        second=self.prepare('second');r=self.reviews(second)[0];p=self.private(second,r)
        records,metadata,_=self.store.load();plan=records[r['plan_ref']]
        resolved=fr._resolve_sources(self.store,plan,[],records,metadata,self.now,r['data_cutoff'],fr._context())
        p.update(requests=[],source_bindings=[],decode_audits=[],kernel_result=fr._compute(plan,resolved)['kernel_result'],formal_result=fr._compute(plan,resolved))
        raw=canonical(p);second['attachments']['PRIVATE/'+r['review_id']+'.json']=raw.decode()
        r['simulation_state']=fr._summary(plan,p['formal_result'],digest(raw))
        r['metrics'],r['results']=fr._public_result(p['formal_result']);r['input_fingerprint']=fr.sha(resolved.payload)
        r['coverage']=fr._coverage(plan,p['formal_result'],resolved)
        self.commit(second);self.now='2026-09-23T20:00:00Z'
        with self.assertRaisesRegex(ContractError,'PUBLIC_ANCESTOR_PUBLIC_RECONSTRUCTION_REJECTED'):
            self.prepare('third')

    def test_safe_failed_input_can_continue_without_blocking_other_plan(self):
        manifest=self.inputs();manifest['plans'][REFS[0]]['backend']='not-allowed'
        first=self.prepare('failed-input',manifest=manifest)
        self.assertEqual(first['records'][0]['coverage']['technical_failures'],1)
        self.commit(first);self.now='2026-09-23T19:00:00Z'
        second=self.prepare('after-failure')
        self.assertEqual(second['records'][0]['coverage']['technical_failures'],1)
        self.assertTrue(second['records'][0]['complete'])
        self.commit(second)
        output=self.root/'failure-closure.zip'
        export_backup(self.store,output,record_refs=['after-failure'])
        with zipfile.ZipFile(output) as z:
            self.assertFalse(any(PRIVATE_NUMBER.encode() in z.read(name) for name in z.namelist()))

    def test_unsupported_registered_plan_does_not_block_later_safe_batch(self):
        records,_,_=self.store.load();plan=copy.deepcopy(records[REFS[0]])
        plan['plan_id']='unsupported-continuation';plan['plan_ref']='unsupported-continuation@1'
        self.store.commit_bundle('unsupported-continuation','research',[plan])
        manifest=self.inputs();manifest['plans'][plan['plan_ref']]={'sources':[],'correction':None}
        first=self.prepare('with-unsupported',manifest=manifest)
        self.assertEqual(next(r for r in self.reviews(first) if r['plan_ref']==plan['plan_ref'])['evaluation_stage'],'RULES_INCOMPLETE')
        self.commit(first);self.now='2026-09-23T19:00:00Z'
        second=self.prepare('unsupported-next')
        self.assertTrue(second['records'][0]['complete'])
        self.assertEqual(second['records'][0]['coverage']['registered'],3)
        self.assertEqual(next(r for r in self.reviews(second) if r['plan_ref']==plan['plan_ref'])['evaluation_stage'],'RULES_INCOMPLETE')
        self.assertFalse(any(r['evaluation_stage']=='TECHNICAL_FAILURE' for r in self.reviews(second)))

    def test_129_plans_with_two_historical_reviews_receive_full_batch(self):
        records,_,_=self.store.load()
        self.assertEqual(sum(r['record_type']=='review' for r in records.values()),2)
        added=[]
        for index in range(127):
            plan=copy.deepcopy(records[REFS[0]])
            plan['plan_id']='extra-plan-'+str(index)
            plan['plan_ref']=plan['plan_id']+'@1'
            added.append(plan)
        self.store.commit_bundle('extra-127-plans','research',added)
        result=self.prepare('batch-129-plans')
        self.assertEqual(result['records'][0]['coverage']['registered'],129)
        self.assertEqual(len(self.reviews(result)),129)
        self.assertEqual(sum(r['evaluation_stage']=='RULES_INCOMPLETE' for r in self.reviews(result)),127)
        self.assertEqual(sum(r['evaluation_stage']=='WAITING_DATA' for r in self.reviews(result)),2)
        self.assertEqual(result['records'][0]['coverage']['missing'],[])
        self.assertTrue(result['records'][0]['complete'])
        self.commit(result)

    def test_real_semantic_closure_bound_4096_and_4097(self):
        self.assertEqual(fr.MAX_SEMANTIC_ANCESTORS,4096)
        entries=[dict(schema_version='1.0',record_type='evidence',evidence_id='closure-'+str(i),
            created_at=self.now,available_at=self.now,synthetic=False,
            disclosure={'visibility':'PUBLIC','license':'OWN_ANALYSIS'}) for i in range(4097)]
        self.store.commit_bundle('closure-boundary','review',entries)
        records,metadata,_=self.store.load()
        refs=[r['evidence_id'] for r in entries]
        # Both actual passes inspect real committed canonical records. No
        # limit is reduced or validator replaced for these boundary checks.
        for count in (4095,4096):
            fr._ancestor_public_policy(self.store,records,metadata,refs[:count],fr._context())
        with self.assertRaisesRegex(ContractError,'PUBLIC_ANCESTOR_CLOSURE_LIMIT_EXCEEDED'):
            fr._ancestor_public_policy(self.store,records,metadata,refs,fr._context())

    def test_review_node_and_depth_bounds_remain_128_and_64(self):
        self.assertEqual(fr.MAX_HISTORY_NODES,128)
        self.assertEqual(fr.MAX_HISTORY_REVIEWS,64)
        plan=self.store.load()[0][REFS[0]]
        method,_=fr.method_material(self.now)
        # Isolate only the recursive budget guard: expensive source/private
        # validation is covered by full Store tests, not claimed by this stub.
        def node(store,previous,plan,records,metadata,method,context):
            successor=previous.get('next')
            if successor is not None:
                return fr._previous(store,successor,plan,records,metadata,method,context)
            return None,None,'BOUNDARY_GUARD_ONLY'
        def chain(prefix,count):
            result=None
            for i in range(count):
                result={'review_id':prefix+str(i),'plan_hash':fr.sha(plan),'next':result}
            return result
        with patch.object(fr,'_previous_node',side_effect=node):
            context=fr._context()
            fr._previous(None,chain('a',64),plan,{}, {},method,context)
            fr._previous(None,chain('b',64),plan,{}, {},method,context)
            self.assertEqual(len(context['nodes']),128)
            with self.assertRaisesRegex(ContractError,'PREVIOUS_REVIEW_NODE_LIMIT_EXCEEDED'):
                fr._previous(None,chain('c',1),plan,{}, {},method,context)
            with self.assertRaisesRegex(ContractError,'PREVIOUS_REVIEW_CHAIN_LIMIT_EXCEEDED'):
                fr._previous(None,chain('depth',65),plan,{}, {},method,fr._context())

    def test_outbox_ignores_newly_registered_plan_but_rejects_rewritten_frozen_list(self):
        path=fr.prepare_outbox(self.store,'out',self.inputs(),'out.json','2026-09-23T12:00:00Z')
        original=path.read_bytes();self.now='2026-09-23T19:00:00Z'
        records,_,_=self.store.load();p=copy.deepcopy(records[REFS[0]])
        p['plan_id']='later-plan';p['plan_ref']='later-plan@1';p['created_at']=p['available_at']=self.now
        self.store.commit_bundle('later-plan','research',[p])
        self.assertEqual(fr.prepare_outbox(self.store,'out',self.inputs(),'retry.json','2026-09-23T12:00:00Z').read_bytes(),original)
        retained=self.retained('out');saved=json.loads(retained.read_text())
        saved['records'][0]['plan_refs'].append('later-plan@1');self.reseal(retained,saved)
        with self.assertRaises(ContractError):fr.prepare_outbox(self.store,'out',self.inputs(),'again.json','2026-09-23T12:00:00Z')

    def test_raw_symlink_or_physical_store_damage_never_produces_batch(self):
        identity=self.store.load()[0][self.trade1['dataset_ref']]['sha256']
        source=self.store.data_root/'objects'/identity;outside=self.root/'read-only-original'
        source.rename(outside);source.symlink_to(outside)
        b=self.prepare();self.assertEqual(b['records'][0]['coverage']['technical_failures'],2)
        source.unlink();outside.rename(source)
        good=self.prepare('good');self.commit(good)
        target=self.store.root/'bundles'/good['bundle_id']/'attachments'/'METHOD.json'
        target.write_text('{}')
        with self.assertRaises(ContractError):self.prepare('damaged')

    def test_nested_provenance_cannot_carry_private_text_through_failed_ancestor(self):
        old=cr.prepare_bundle(self.store,'old7db',self.inputs(),'2026-09-23T12:00:00Z')
        r=self.reviews(old)[0]
        # Shared provenance is deliberately changed in both review and feedback.
        r['provenance']['state_migration']=PRIVATE_NUMBER
        self.commit(old);self.now='2026-09-23T19:00:00Z'
        with self.assertRaisesRegex(ContractError,'PUBLIC_ANCESTOR_DERIVED_TEXT_REJECTED'):
            self.prepare('unsafe')
