"""Isolated synthetic engineering fixtures; no real economics or production writes."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from researchlib import Store
from researchlib.common import canonical, digest, ContractError
from researchlib import conditional_review as cr
from researchlib import funding_review as waiting
from researchlib.snapshot import publish_snapshot
from researchlib.archive import export_backup

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = json.loads((ROOT / 'research/bootstrap-v1/research_bundle.json').read_text())
LEGACY = json.loads((ROOT / 'review/bootstrap-review/review_bundle.json').read_text())
REFS = sorted(cr.PLAN_HASHES)
PRIVATE_NUMBER = '98765.432198765432109876'
OLD_WAITING_HASH = 'd21b004a0efe4295f391a3f82ccba05f6a967b9205d370eabd807a8692f91f65'
COMBINED_WAITING_HASH = '7718ec0e6f94d2c71a8cd66b0baf6b7a77b39c99312b81e744d8095ae34d3115'


def old_waiting_material(at):
    """Real old source bytes; synthetic availability only in temporary Store tests."""
    fixture = ROOT / 'tests/fixtures/waiting-d21'
    method = json.loads((fixture / 'METHOD.template.json').read_text())
    assert method['method_code_sha256'] == OLD_WAITING_HASH
    assert cr.sha({'sources': method['source_sha256'], 'runtime': method['runtime']}) == OLD_WAITING_HASH
    attachments = {}
    for name, relative in cr.WAITING_SOURCE_ATTACHMENTS.items():
        raw = (fixture / 'contracts.py.txt').read_bytes() if name == 'contracts.py' else (ROOT / relative).read_bytes()
        assert digest(raw) == method['source_sha256'][relative], 'Old approved source fixture changed: ' + name
        attachments[name] = raw.decode()
    method.update(available_at=at, created_at=at)
    attachments['METHOD.json'] = canonical(method).decode()
    return method, attachments


class FutureFixtureClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 9, 30, tzinfo=timezone.utc)


class ConditionalReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # Explicit approved-runtime fixture; never widens the production allowlist.
        runtime = patch('platform.python_version', return_value='3.9.6')
        runtime.start(); self.addCleanup(runtime.stop)
        self.root = Path(self.temp.name).resolve()
        self.now = '2026-09-22T18:07:00Z'
        self.store = Store(self.root, clock=lambda: self.now)
        self.store.commit_bundle('research-fixture', 'research', copy.deepcopy(RESEARCH['records']))
        self.now = '2026-09-22T18:14:00Z'
        self.store.commit_bundle('review-fixture', 'review', copy.deepcopy(LEGACY['records']))
        for module in ('researchlib.okx_trade_file.datetime', 'researchlib.okx_funding_file.datetime'):
            p = patch(module, FutureFixtureClock); p.start(); self.addCleanup(p.stop)
        self.trade1 = self.source('trade1', '2026-09-23', '2026-09-23T17:00:00Z',
            [('1', '2026-09-23T00:05:01Z', PRIVATE_NUMBER)])
        self.funding1 = self.source('funding1', '2026-09-23', '2026-09-23T17:00:00Z',
            [('0.00001', '2026-09-23T08:00:00Z')], funding=True)
        self.trade2 = self.source('trade2', '2026-09-24', '2026-09-24T17:00:00Z',
            [('2', '2026-09-24T00:05:01Z', '98760.1')])
        self.now = '2026-09-23T18:00:00Z'

    def source(self, name, day, acquired, rows, funding=False, **changes):
        if funding:
            header = 'instrument_name,funding_rate,funding_time'
            lines = ['BTC-USDT-SWAP,%s,%s' % (rate, self.millis(at)) for rate, at in rows]
            filename = 'allswap-fundingrates-' + day + '.csv'
            adapter, role = cr.FUNDING_ADAPTER, 'TARGET_REALIZED_FUNDING'
        else:
            header = 'instrument_name,trade_id,side,price,size,created_time,source'
            lines = ['BTC-USDT-SWAP,%s,buy,%s,0.01,%s,0' % (ident, price, self.millis(at)) for ident, at, price in rows]
            filename = 'BTC-USDT-SWAP-trades-' + day + '.csv'
            adapter, role = cr.TRADE_ADAPTER, 'TARGET_TRADE_HISTORY'
        raw = (header + '\r\n' + '\r\n'.join(lines) + '\r\n').encode()
        previous_now = self.now; self.now = acquired
        identity = digest(raw)
        self.store.put_data(raw, {'source_url': 'https://www.okx.com/historical-data', 'acquired_at': acquired,
                                  'license': 'LOCAL_ONLY', 'data_role': role}, 'review')
        dataset = dict(schema_version='1.0', record_type='dataset', dataset_id=name, version=1, synthetic=False,
                       created_at=acquired, available_at=acquired, acquired_at=acquired,
                       instrument_ref='BTC-USDT-SWAP', data_role=role, data_ref='sha256:' + identity,
                       sha256=identity, bytes=len(raw), source_url='https://www.okx.com/historical-data',
                       disclosure={'visibility': 'LOCAL_ONLY', 'license': 'LOCAL_ONLY'})
        dataset.update(changes)
        self.store.commit_bundle('data-' + name, 'review', [dataset])
        self.now = previous_now
        return {'dataset_ref': name + '@1', 'adapter': adapter, 'filename': filename,
                'declared_partition': {'date': day, 'timezone': 'UTC+08:00'},
                'window': None if funding else {'start_inclusive': rows[0][1][0:11] + '00:05:00Z',
                                               'end_exclusive': rows[0][1][0:11] + '00:06:00Z'}}

    @staticmethod
    def millis(at):
        return int(datetime.fromisoformat(at.replace('Z', '+00:00')).timestamp()) * 1000

    def inputs(self, sources=None):
        return {'schema_version': 1, 'plans': {ref: {'sources': copy.deepcopy(sources if sources is not None else [self.trade1, self.funding1]),
                                                   'correction': None} for ref in REFS}}

    def prepare(self, ident='c1', sources=None, cutoff='2026-09-23T12:00:00Z', manifest=None):
        return cr.prepare_bundle(self.store, ident, manifest or self.inputs(sources), cutoff)

    def reviews(self, bundle):
        return [r for r in bundle['records'] if r['record_type'] == 'review']

    def commit(self, bundle):
        self.store.commit_bundle(bundle['bundle_id'], bundle['role'], bundle['records'], bundle['attachments'], request_key=bundle['request_key'])

    def private(self, bundle, review=None):
        review = review or self.reviews(bundle)[0]
        return json.loads(bundle['attachments']['PRIVATE/' + review['review_id'] + '.json'])

    def replace_private(self, bundle, review, private):
        records, _, _ = self.store.load(strict=True)
        raw = canonical(private)
        bundle['attachments']['PRIVATE/' + review['review_id'] + '.json'] = raw.decode()
        review['simulation_state'] = cr._summary(records[review['plan_ref']], private['kernel_result'], digest(raw))
        review['input_fingerprint'] = cr.sha(private['kernel_result']['input_payload'])

    def assert_one_failed(self, bundle, previous_ref, code=None):
        failed = [r for r in self.reviews(bundle) if r['evaluation_stage'] == 'TECHNICAL_FAILURE']
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]['previous_review_ref'], previous_ref)
        if code:
            self.assertEqual(failed[0]['coverage']['reason_codes'], [code])
        self.assertTrue(bundle['records'][0]['complete'])
        self.assertEqual(bundle['records'][0]['coverage']['evaluable_results'], 0)

    def retained(self, batch_id):
        return self.root / '.local/review-outbox/.prepared-batches' / (digest(batch_id.encode()) + '.json')

    @staticmethod
    def reseal(path, saved):
        saved['preparation'].pop('content_sha256', None)
        saved['preparation']['content_sha256'] = cr.sha(saved)
        path.write_bytes(canonical(saved))

    def test_decoded_legacy_migration_preserves_formal_hash_and_unknown_actuals(self):
        records, _, _ = self.store.load(strict=True)
        b = self.prepare()
        for r in self.reviews(b):
            self.assertEqual(r['evaluation_stage'], 'WAITING_DATA', r['coverage'])
            self.assertEqual(r['opening_state_hash'], digest(canonical(records[r['previous_review_ref']]['simulation_state'])))
            self.assertTrue(all(v is None for v in r['metrics'].values()))
            self.assertIsNone(r['simulation_state']['inventory'])
            self.assertEqual(r['provenance']['method_available_at'], self.now)
            private = self.private(b, r)
            self.assertEqual(private['kernel_result']['simulation_state']['state'], 'CONDITIONAL_OPEN')
            self.assertIsNone(private['kernel_result']['scenarios'][0]['conditional_net_pnl'])
        self.commit(b)

    def test_full_and_cross_day_conditional_results_equal_no_reentry_or_recount(self):
        first = self.prepare(); self.commit(first)
        self.now = '2026-09-25T00:00:00Z'
        next_bundle = self.prepare('c2', [self.trade1, self.funding1, self.trade2], '2026-09-24T00:06:00Z')
        for review in self.reviews(next_bundle):
            self.assertEqual(review['evaluation_stage'], 'WAITING_DATA', review['coverage'])
            private = self.private(next_bundle, review)
            records, _, _ = self.store.load(strict=True)
            result = private['kernel_result']
            from researchlib.funding_forward import evaluate
            once = evaluate(records[review['plan_ref']], result['input_payload'], self.now, result['market_event_cutoff'])
            self.assertEqual(result['simulation_state'], once['simulation_state'])
            self.assertEqual(result['scenarios'], once['scenarios'])
            self.assertEqual(result['conditional_observed_input_metrics']['trade_count'], 2)
            self.assertEqual(len(result['simulation_state']['funding_observations']), 1)
            self.assertIsNone(review['metrics']['trade_count'])
            self.assertIsNone(review['simulation_state']['inventory'])
        self.commit(next_bundle)

    def test_empty_post_effective_input_is_unknown_not_zero_inventory(self):
        for r in self.reviews(self.prepare(sources=[])):
            self.assertEqual(r['evaluation_stage'], 'WAITING_DATA')
            self.assertIsNone(r['simulation_state']['inventory'])
            self.assertIsNone(r['coverage']['actually_evaluated_market_cutoff'])
            self.assertFalse(r['coverage']['trade_partitions']['declared_partition_union_covers_requested_interval'])
            self.assertIsNone(r['metrics']['trade_count'])

    def test_approved_waiting_bridge_only_and_real_method_time(self):
        first = waiting.prepare_bundle(self.store, 'waiting1', '2026-09-23T12:00:00Z'); self.commit(first)
        self.now = '2026-09-23T19:00:00Z'
        b = self.prepare()
        self.assertTrue(all(r['evaluation_stage'] == 'WAITING_DATA' for r in self.reviews(b)))
        self.assertTrue(all(r['provenance']['state_migration'].startswith('APPROVED_WAITING') for r in self.reviews(b)))
        with patch.dict(cr.APPROVED_WAITING_PROFILES, {}, clear=True):
            bad = self.prepare('bad')
        self.assertTrue(all(r['evaluation_stage'] == 'TECHNICAL_FAILURE' for r in self.reviews(bad)))

    def test_real_old_waiting_profile_and_six_original_sources_bridge_to_combined(self):
        with patch.object(waiting, 'method_material', side_effect=old_waiting_material):
            first = waiting.prepare_bundle(self.store, 'old-waiting', '2026-09-23T12:00:00Z')
        method = json.loads(first['attachments']['METHOD.json'])
        self.assertEqual(method['method_code_sha256'], OLD_WAITING_HASH)
        self.assertEqual(len(method['source_sha256']), 11)
        self.assertEqual(len(first['attachments']), 7)
        self.assertNotEqual(first['attachments']['contracts.py'], (ROOT / 'researchlib/contracts.py').read_text())
        self.commit(first); self.now = '2026-09-23T19:00:00Z'
        next_bundle = self.prepare('combined-after-old')
        self.assertEqual(next_bundle['records'][0]['coverage']['technical_failures'], 0)
        self.assertTrue(all(r['evaluation_stage'] == 'WAITING_DATA' for r in self.reviews(next_bundle)))
        self.commit(next_bundle); self.now = '2026-09-23T20:00:00Z'
        continued = self.prepare('continued-after-old')
        self.assertEqual(continued['records'][0]['coverage']['technical_failures'], 0)

    def test_combined_waiting_profile_matches_frozen_full_template(self):
        method, _ = waiting.method_material(self.now)
        self.assertEqual(method['method_code_sha256'], COMBINED_WAITING_HASH)
        self.assertEqual(method, dict(cr.APPROVED_WAITING_PROFILES[COMBINED_WAITING_HASH],
                                     created_at=self.now, available_at=self.now))
        self.assertEqual(method['source_sha256']['researchlib/public.py'], cr.PUBLIC_SCANNER_SOURCE_HASH)

    def test_old_waiting_bridge_then_conditional_correction_and_recovery_preserve_chain(self):
        with patch.object(waiting, 'method_material', side_effect=old_waiting_material):
            first = waiting.prepare_bundle(self.store, 'old-before-correction', '2026-09-23T12:00:00Z')
        self.commit(first); self.now = '2026-09-23T19:00:00Z'
        current = self.prepare('accepted-after-old'); self.commit(current)
        revised = self.source('revision-after-old', '2026-09-23', '2026-09-24T17:00:00Z',
                              [('1', '2026-09-23T00:05:01Z', '999')])
        self.now = '2026-09-25T00:00:00Z'
        manifest = self.inputs([revised, self.funding1])
        for ref in REFS:
            manifest['plans'][ref]['correction'] = cr.correction_proposal(self.store, ref,
                [revised, self.funding1], '2026-09-23T12:00:00Z', 'SYNTHETIC private reason')['correction']
        output = cr.prepare_outbox(self.store, 'corrected-after-old', manifest, 'correction.json', '2026-09-23T12:00:00Z')
        original = output.read_bytes(); bundle = json.loads(original)
        self.assertTrue(all(r['supersedes'] in {p['review_id'] for p in self.reviews(current)} for r in self.reviews(bundle)))
        self.commit(bundle); self.now = '2026-09-25T01:00:00Z'
        recovered = cr.prepare_outbox(self.store, 'corrected-after-old', manifest, 'unused.json', '2026-09-23T12:00:00Z')
        self.assertEqual(recovered.read_bytes(), original)
        continued = self.prepare('after-correction', [revised, self.funding1])
        self.assertEqual(continued['records'][0]['coverage']['technical_failures'], 0)

    def test_source_locator_binds_real_combined_git_ref_without_publication_claim(self):
        method, _ = cr.method_material(self.now)
        excluded = method['public_archive']['excluded_source_attachments']
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded[0]['sha256'], digest((ROOT / 'researchlib/public.py').read_bytes()))
        self.assertIn('/e65bb32e162ddc21b2513ee4edfd4d90829c5b5b/', excluded[0]['git_source_locator'])
        self.assertNotIn('published_git_source', excluded[0])
        self.assertEqual(excluded[0]['locator_scope'], 'IMMUTABLE_GIT_REF_NOT_NETWORK_AVAILABILITY_ATTESTATION')

    def test_waiting_profiles_reject_hash_runtime_map_template_source_and_time_changes(self):
        attacks = ('hash', 'runtime', 'map', 'template', 'source', 'substitute-current-contracts',
                   'missing-source', 'method-time', 'provenance-hash')
        for profile in ('old', 'combined'):
            for attack in attacks:
                with self.subTest(profile=profile, attack=attack):
                    if profile == 'old':
                        with patch.object(waiting, 'method_material', side_effect=old_waiting_material):
                            first = waiting.prepare_bundle(self.store, profile + '-' + attack, '2026-09-23T12:00:00Z')
                    else:
                        first = waiting.prepare_bundle(self.store, profile + '-' + attack, '2026-09-23T12:00:00Z')
                    material = json.loads(first['attachments']['METHOD.json'])
                    if attack == 'hash': material['method_code_sha256'] = 'e' * 64
                    elif attack == 'runtime': material['runtime']['python_version'] = '3.12.99'
                    elif attack == 'map': material['source_sha256']['researchlib/public.py'] = 'e' * 64
                    elif attack == 'template': material['scope'] = 'EXPANDED_SCOPE'
                    elif attack == 'source': first['attachments']['store.py'] += '\n# forged original\n'
                    elif attack == 'substitute-current-contracts':
                        first['attachments']['contracts.py'] = ((ROOT / 'researchlib/contracts.py').read_text()
                            if profile == 'old' else (ROOT / 'tests/fixtures/waiting-d21/contracts.py.txt').read_text())
                    elif attack == 'missing-source': del first['attachments']['contracts.py']
                    elif attack == 'method-time': material['available_at'] = '2026-09-23T17:59:00Z'
                    else:
                        for r in self.reviews(first): r['provenance']['method_code_sha256'] = 'e' * 64
                    first['attachments']['METHOD.json'] = canonical(material).decode()
                    # Independent fresh temporary Store: no earlier bad predecessor can mask this attack.
                    with tempfile.TemporaryDirectory() as root:
                        isolated = Store(Path(root).resolve(), clock=lambda: self.now)
                        records, metadata, _ = self.store.load(strict=True)
                        for bundle_id in ('research-fixture', 'review-fixture'):
                            selected = [r for ref, r in records.items() if metadata[ref]['bundle_id'] == bundle_id]
                            isolated.commit_bundle(bundle_id, 'research' if bundle_id == 'research-fixture' else 'review', selected)
                        isolated.commit_bundle(first['bundle_id'], 'review', first['records'], first['attachments'])
                        with patch.object(isolated, 'clock', return_value='2026-09-23T19:00:00Z'):
                            result = cr.prepare_bundle(isolated, 'next', self.inputs([]), '2026-09-23T12:00:00Z')
                        self.assertTrue(all(r['evaluation_stage'] == 'TECHNICAL_FAILURE' for r in self.reviews(result)))
                        expected = ('PREVIOUS_ATTACHMENT_INVALID' if attack == 'missing-source' else
                                    'WAITING_METHOD_SOURCE_BYTES_MISMATCH' if attack in ('source', 'substitute-current-contracts') else
                                    'PREVIOUS_METHOD_BINDING_OR_TIME_INVALID' if attack == 'method-time' else
                                    'WAITING_METHOD_NOT_APPROVED_IDENTITY')
                        self.assertTrue(all(r['coverage']['reason_codes'] == [expected] for r in self.reviews(result)), result['records'][0])

    def test_uninstalled_fourth_conditional_identity_is_explicitly_unsupported(self):
        first = self.prepare(); method = json.loads(first['attachments']['METHOD.json'])
        method['method_code_sha256'] = 'a1f6f384e885176dbc1680ca4b720ec13c96e2361b84b3f4512ff721cd0c88ae'
        first['attachments']['METHOD.json'] = canonical(method).decode()
        for review in self.reviews(first):
            review['evaluator_version'] = cr.VERSION + '@sha256:' + method['method_code_sha256']
        self.commit(first); self.now = '2026-09-23T19:00:00Z'
        result = self.prepare('reject-uninstalled')
        self.assertTrue(all(r['coverage']['reason_codes'] == ['PREVIOUS_CONDITIONAL_METHOD_NOT_SUPPORTED'] for r in self.reviews(result)))

    def test_different_waiting_runtime_is_not_approved_by_version_label(self):
        with patch('platform.python_version', return_value='3.12.99'):
            first = waiting.prepare_bundle(self.store, 'different-runtime', '2026-09-23T12:00:00Z')
        self.commit(first); self.now = '2026-09-23T19:00:00Z'
        reviews = self.reviews(self.prepare())
        self.assertTrue(all(r['coverage']['reason_codes'] == ['WAITING_METHOD_NOT_APPROVED_IDENTITY'] for r in reviews))

    def test_historical_cutoff_after_effective_preserves_unknown_across_bridge(self):
        first = waiting.prepare_bundle(self.store, 'historic-waiting', '2026-09-22T19:00:00Z')
        self.commit(first); self.now = '2026-09-23T19:00:00Z'
        second = self.prepare('historic-conditional', [], '2026-09-22T20:00:00Z')
        for review in self.reviews(second):
            self.assertEqual(review['evaluation_stage'], 'WAITING_DATA')
            self.assertEqual(review['simulation_state']['state'], 'HISTORICAL_PRE_EFFECTIVE_INPUTS_ONLY')
            self.assertIsNone(review['simulation_state']['inventory'])
            self.assertTrue(review['simulation_state']['historical_pre_effective_cutoff'])
            self.assertEqual(self.private(second, review)['kernel_result']['evaluation_stage'], 'NOT_YET_EFFECTIVE')
        self.commit(second); self.now = '2026-09-23T20:00:00Z'
        third = self.prepare('historic-third', [], '2026-09-22T21:00:00Z')
        self.assertTrue(all(r['evaluation_stage'] == 'WAITING_DATA' and r['simulation_state']['inventory'] is None
                            for r in self.reviews(third)))

    def test_middle_review_cannot_drop_prefix_and_recompute_as_new_empty_state(self):
        first = self.prepare(); self.commit(first)
        self.now = '2026-09-23T19:00:00Z'
        middle = self.prepare('middle'); review = self.reviews(middle)[0]
        private = self.private(middle, review)
        records, metadata, _ = self.store.load(strict=True)
        payload, bindings, audits = cr.decode_sources(self.store, [], records, metadata, self.now, review['data_cutoff'])
        private.update(requests=[], source_bindings=bindings, decode_audits=audits)
        private['kernel_result'] = cr.evaluate(records[review['plan_ref']], payload, self.now, review['data_cutoff'])
        self.replace_private(middle, review, private)
        self.commit(middle); self.now = '2026-09-23T20:00:00Z'
        request = self.inputs(); request['plans'][review['plan_ref']]['sources'] = []
        self.assert_one_failed(self.prepare('last', manifest=request), review['review_id'])

    def test_private_opening_hash_cannot_be_erased_while_public_hash_matches(self):
        first = self.prepare(); self.commit(first); self.now = '2026-09-23T19:00:00Z'
        middle = self.prepare('middle'); review = self.reviews(middle)[0]
        private = self.private(middle, review)
        self.assertIsNotNone(private['kernel_result']['opening_state_hash'])
        private['kernel_result']['opening_state_hash'] = None
        self.replace_private(middle, review, private)
        self.commit(middle); self.now = '2026-09-23T20:00:00Z'
        self.assert_one_failed(self.prepare('last'), review['review_id'], 'PREVIOUS_KERNEL_TRANSITION_NOT_REPRODUCIBLE')

    def test_historical_hop_cannot_skip_already_committed_latest(self):
        first = self.prepare(); self.commit(first); self.now = '2026-09-23T19:00:00Z'
        second = self.prepare('second'); self.commit(second); self.now = '2026-09-23T20:00:00Z'
        third = self.prepare('third'); review = self.reviews(third)[0]
        parent = next(r for r in self.reviews(first) if r['plan_ref'] == review['plan_ref'])
        private = self.private(third, review)
        records, _, _ = self.store.load(strict=True)
        private['kernel_result'] = cr.evaluate(records[review['plan_ref']], private['kernel_result']['input_payload'],
            self.now, review['data_cutoff'], previous=self.private(first, parent)['kernel_result'])
        review.update(previous_review_ref=parent['review_id'], opening_state_hash=cr.sha(parent['simulation_state']),
                      revision=parent['revision'] + 1)
        review['provenance']['prior_state_preserved_in'] = parent['review_id']
        self.replace_private(third, review, private)
        self.commit(third); self.now = '2026-09-23T21:00:00Z'
        self.assert_one_failed(self.prepare('fourth'), review['review_id'], 'HISTORICAL_LATEST_PREDECESSOR_SKIPPED')

    def test_same_time_latest_reviews_are_ambiguous_not_revision_tiebroken(self):
        first = self.prepare('same-time-one'); second = self.prepare('same-time-two')
        self.commit(first); self.commit(second); self.now = '2026-09-23T19:00:00Z'
        result = self.prepare('third')
        self.assertTrue(all(r['coverage']['reason_codes'] == ['LATEST_FORMAL_PREDECESSOR_AMBIGUOUS'] for r in self.reviews(result)))

    def test_bounded_chain_and_cycle_fail_closed_and_decode_is_memoized(self):
        for hour in range(18, 24):
            self.now = '2026-09-23T%02d:00:00Z' % hour
            bundle = self.prepare('chain-' + str(hour)); self.commit(bundle)
        self.now = '2026-09-24T01:00:00Z'
        with patch.object(cr, 'decode_sources', wraps=cr.decode_sources) as decode:
            valid = self.prepare('chain-valid')
        self.assertEqual(valid['records'][0]['coverage']['technical_failures'], 0)
        # Six historical information cutoffs plus current; shared by both plans.
        self.assertEqual(decode.call_count, 7)
        with patch.object(cr, 'MAX_HISTORY_REVIEWS', 3):
            invalid = self.prepare('chain-limit')
        self.assertTrue(all(r['coverage']['reason_codes'] == ['PREVIOUS_REVIEW_CHAIN_LIMIT_EXCEEDED'] for r in self.reviews(invalid)))
        records, metadata, _ = self.store.load(strict=True)
        review = copy.deepcopy(self.reviews(bundle)[0]); review['previous_review_ref'] = review['review_id']
        records[review['review_id']] = review
        method, _ = cr.method_material(self.now)
        with self.assertRaisesRegex(ContractError, 'PREVIOUS_REVIEW_CHAIN_CYCLE'):
            cr._previous(self.store, review, records[review['plan_ref']], records, metadata, method)

    def test_validation_resource_limits_do_not_return_partial_success(self):
        first = self.prepare(); self.commit(first); self.now = '2026-09-23T19:00:00Z'
        for name, limit, code in (
                ('MAX_HISTORY_NODES', 1, 'PREVIOUS_REVIEW_NODE_LIMIT_EXCEEDED'),
                ('MAX_CONTEXT_BYTES', 1, 'VALIDATION_CONTEXT_SIZE_LIMIT_EXCEEDED'),
                ('MAX_VALIDATION_SECONDS', 0, 'VALIDATION_TIME_LIMIT_EXCEEDED')):
            with self.subTest(limit=name), patch.object(cr, name, limit):
                result = self.prepare('limited-' + name.lower())
                self.assertTrue(all(r['evaluation_stage'] == 'TECHNICAL_FAILURE' for r in self.reviews(result)))
                self.assertTrue(any(r['coverage']['reason_codes'] == [code] for r in self.reviews(result)))
                self.assertEqual(result['records'][0]['coverage']['evaluable_results'], 0)

    def test_late_commit_is_not_visible_to_earlier_historical_hop(self):
        first = self.prepare(); self.commit(first); self.now = '2026-09-23T19:00:00Z'
        late = self.prepare('late-commit')
        self.now = '2026-09-23T20:00:00Z'
        ordinary = self.prepare('ordinary-before-late-commit'); self.commit(ordinary)
        self.now = '2026-09-23T21:00:00Z'; self.commit(late)
        self.now = '2026-09-23T22:00:00Z'
        result = self.prepare('after-late-commit')
        self.assertEqual(result['records'][0]['coverage']['technical_failures'], 0)
        self.assertEqual({r['previous_review_ref'] for r in self.reviews(result)},
                         {r['review_id'] for r in self.reviews(ordinary)})

    def test_dataset_registration_role_target_synthetic_and_time_checked(self):
        mutations = [{'synthetic': True}, {'instrument_ref': 'ETH-USDT-SWAP'}, {'data_role': 'TARGET_TRADE_CANDLES_NOT_MARK'},
                     {'data_ref': None}, {'sha256': 'a' * 64}]
        for i, mutation in enumerate(mutations):
            request = self.source('bad' + str(i), '2026-09-23', '2026-09-23T17:00:00Z',
                                  [('1', '2026-09-23T00:05:01Z', '100')], **mutation)
            manifest = self.inputs(); manifest['plans'][REFS[0]]['sources'] = [request]
            reviews = self.reviews(self.prepare('b' + str(i), manifest=manifest))
            self.assertEqual([r['evaluation_stage'] for r in reviews].count('TECHNICAL_FAILURE'), 1)
        future = self.inputs([self.trade2])
        self.assertTrue(all(r['evaluation_stage'] == 'TECHNICAL_FAILURE' for r in self.reviews(self.prepare('future', manifest=future))))

    def test_caller_cannot_override_rows_urls_availability_marks_or_coverage(self):
        for field, value in [('events', []), ('coverage', True), ('obtained_at', '2020-01-01T00:00:00Z'),
                             ('source_url', 'https://evil.test'), ('sequence', 1), ('mark', '999')]:
            manifest = self.inputs(); manifest['plans'][REFS[0]]['sources'][0][field] = value
            reviews = self.reviews(self.prepare('reject-' + field, manifest=manifest))
            self.assertEqual([r['evaluation_stage'] for r in reviews].count('TECHNICAL_FAILURE'), 1)

    def test_bad_source_bytes_do_not_fall_back_to_fixture_or_other_plan(self):
        request = self.source('badbytes', '2026-09-23', '2026-09-23T17:00:00Z', [('1', '2026-09-23T00:05:01Z', '101')])
        records, _, _ = self.store.load(strict=True)
        (self.store.data_root / 'objects' / records['badbytes@1']['sha256']).write_bytes(b'private invalid bytes')
        manifest = self.inputs(); manifest['plans'][REFS[0]]['sources'] = [request]
        b = self.prepare(manifest=manifest)
        self.assertEqual(b['records'][0]['coverage']['technical_failures'], 1)
        self.assertTrue(b['records'][0]['complete'])
        self.assertNotIn('private invalid bytes', canonical(b['records']).decode())

    def test_method_and_private_payload_mismatch_is_plan_failure_not_fallback(self):
        b = self.prepare()
        r = self.reviews(b)[0]
        del b['attachments']['PRIVATE/' + r['review_id'] + '.json']
        # Manifest is valid but expected private material is absent: other plan survives.
        self.commit(b); self.now = '2026-09-23T19:00:00Z'
        second = self.prepare('c2')
        failed = next(x for x in self.reviews(second) if x['plan_ref'] == r['plan_ref'])
        self.assertEqual(failed['evaluation_stage'], 'TECHNICAL_FAILURE')
        self.assertEqual(failed['previous_review_ref'], r['review_id'])
        self.assertEqual(second['records'][0]['coverage']['technical_failures'], 1)

    def test_forged_private_state_with_valid_manifest_is_rejected(self):
        b = self.prepare(); r = self.reviews(b)[0]
        name = 'PRIVATE/' + r['review_id'] + '.json'; p = json.loads(b['attachments'][name])
        p['kernel_result']['simulation_state']['inventory'] = '999'
        raw = canonical(p); b['attachments'][name] = raw.decode()
        r['simulation_state']['private_computation_sha256'] = digest(raw)
        self.commit(b); self.now = '2026-09-23T19:00:00Z'
        second = self.prepare('c2')
        self.assertEqual(second['records'][0]['coverage']['technical_failures'], 1)

    def test_unknown_latest_state_is_not_skipped_for_older_good_review(self):
        b = self.prepare(); r = self.reviews(b)[0]
        r['simulation_state']['state'] = 'UNRECOGNIZED'
        self.commit(b); self.now = '2026-09-23T19:00:00Z'
        second = self.prepare('c2')
        bad = next(x for x in self.reviews(second) if x['plan_ref'] == r['plan_ref'])
        self.assertEqual(bad['previous_review_ref'], r['review_id'])
        self.assertEqual(bad['evaluation_stage'], 'TECHNICAL_FAILURE')

    def test_late_and_same_id_new_provenance_require_exact_correction(self):
        first = self.prepare(); self.commit(first)
        revised = self.source('revised', '2026-09-23', '2026-09-24T17:00:00Z',
            [('0', '2026-09-23T00:05:00Z', '99'), ('1', '2026-09-23T00:05:01Z', PRIVATE_NUMBER)])
        self.now = '2026-09-25T00:00:00Z'
        manifest = self.inputs([revised, self.funding1])
        ordinary = self.prepare('ordinary', manifest=manifest)
        self.assertTrue(all(r['coverage']['reason_codes'] == ['EXPLICIT_CORRECTION_REQUIRED'] for r in self.reviews(ordinary)))
        records, metadata, _ = self.store.load(strict=True)
        payload, _, _ = cr.decode_sources(self.store, [revised, self.funding1], records, metadata, self.now, '2026-09-23T12:00:00Z')
        for previous in self.reviews(first):
            old = self.private(first, previous)['kernel_result']['input_payload']
            manifest['plans'][previous['plan_ref']]['correction'] = {'previous_review_ref': previous['review_id'],
                'old_input_fingerprint': cr.sha(old), 'new_input_fingerprint': cr.sha(payload),
                'event_diff': cr._event_diff(old, payload), 'reason': 'PRIVATE_REASON_CANARY_FOR_TEST_ONLY'}
        fixed = self.prepare('corrected', manifest=manifest)
        self.assertTrue(all(r['evaluation_stage'] == 'WAITING_DATA' for r in self.reviews(fixed)))
        self.assertTrue(all('supersedes' in r and r['revision'] == 3 for r in self.reviews(fixed)))
        self.assertNotIn('PRIVATE_REASON_CANARY', canonical(fixed['records']).decode())
        self.commit(fixed)
        public_dir = self.root / 'corrected-public'
        publish_snapshot(self.store, public_dir, self.now)
        exported = [p.read_bytes() for p in public_dir.rglob('*') if p.is_file()]
        for ident in (self.reviews(fixed)[0]['review_id'], 'corrected', self.reviews(fixed)[0]['feedback_refs'][0]):
            target = self.root / (ident + '.zip')
            export_backup(self.store, target, record_refs=[ident])
            with zipfile.ZipFile(target) as archive:
                self.assertFalse(any('/PRIVATE/' in name for name in archive.namelist()))
                exported.extend(archive.read(name) for name in archive.namelist())
        for content in exported:
            self.assertNotIn(PRIVATE_NUMBER.encode(), content)
            self.assertNotIn(b'PRIVATE_REASON_CANARY', content)
        self.now = '2026-09-25T01:00:00Z'
        manifest['plans'][REFS[0]]['correction']['event_diff'] = {'added': [], 'changed': [], 'removed': []}
        bad = self.prepare('bad-correction', manifest=manifest)
        self.assertTrue(any(r['evaluation_stage'] == 'TECHNICAL_FAILURE' for r in self.reviews(bad)))

    def test_private_correction_requires_matching_public_supersedes_and_summary(self):
        first = self.prepare(); self.commit(first)
        revised = self.source('corrected-source', '2026-09-23', '2026-09-24T17:00:00Z',
                              [('1', '2026-09-23T00:05:01Z', '999')])
        self.now = '2026-09-25T00:00:00Z'
        manifest = self.inputs([revised, self.funding1])
        for ref in REFS:
            manifest['plans'][ref]['correction'] = cr.correction_proposal(self.store, ref,
                [revised, self.funding1], '2026-09-23T12:00:00Z', 'SYNTHETIC private correction')['correction']
        corrected = self.prepare('corrected', manifest=manifest)
        review = self.reviews(corrected)[0]
        del review['supersedes']
        self.commit(corrected); self.now = '2026-09-25T01:00:00Z'
        self.assert_one_failed(self.prepare('next', [revised, self.funding1]), review['review_id'],
                               'PUBLIC_PRIVATE_CORRECTION_MISMATCH')

    def test_correction_proposal_binds_exact_diff_without_writing(self):
        first = self.prepare(); self.commit(first)
        revised = self.source('proposal', '2026-09-23', '2026-09-24T17:00:00Z',
                              [('1', '2026-09-23T00:05:01Z', '999')])
        self.now = '2026-09-25T00:00:00Z'
        before = self.store.load(strict=True)[0]
        proposal = cr.correction_proposal(self.store, REFS[0], [revised, self.funding1],
                                          '2026-09-23T12:00:00Z', 'PRIVATE source revision reason')
        self.assertEqual(proposal['scope'], 'LOCAL_ONLY_PROPOSAL_NOT_PREPARED_OR_COMMITTED')
        self.assertTrue(proposal['correction']['event_diff']['changed'])
        manifest = self.inputs(); manifest['plans'][REFS[0]] = {'sources': [revised, self.funding1], 'correction': proposal['correction']}
        result = self.prepare('proposal-applied', manifest=manifest)
        review = next(r for r in self.reviews(result) if r['plan_ref'] == REFS[0])
        self.assertIn('supersedes', review)
        self.assertEqual(self.store.load(strict=True)[0], before)

    def test_same_ms_stays_ambiguous(self):
        tied = self.source('tied', '2026-09-23', '2026-09-23T17:00:00Z',
                           [('1', '2026-09-23T00:05:01Z', '100'), ('2', '2026-09-23T00:05:01Z', '100')])
        self.assertTrue(all(r['evaluation_stage'] == 'PATH_AMBIGUOUS' for r in self.reviews(self.prepare(sources=[tied]))))

    def test_all_registered_plans_disposed_even_unknown_missing_endpoint(self):
        records, _, _ = self.store.load(strict=True)
        plan = copy.deepcopy(records[REFS[0]])
        plan.update(plan_id='unknown-plan'); plan.pop('plan_ref', None); plan.pop('evaluation_end')
        self.store.commit_bundle('unknown-plan', 'research', [plan])
        b = self.prepare()
        self.assertEqual(b['records'][0]['coverage']['registered'], 3)
        self.assertEqual([r['evaluation_stage'] for r in self.reviews(b)].count('RULES_INCOMPLETE'), 1)

    def test_cutoff_method_time_and_partition_layers_never_final(self):
        b = self.prepare()
        for r in self.reviews(b):
            cov = r['coverage']
            self.assertTrue(cov['trade_partitions']['declared_partition_union_covers_requested_interval'])
            self.assertEqual(cov['source_event_completeness'], 'UNKNOWN')
            self.assertEqual(cov['exact_settlement_mark'], 'MISSING')
            self.assertEqual(cov['exchange_chronology'], 'UNKNOWN')
            self.assertFalse(r['data_complete'])
        for cutoff in ('2026-09-30T00:00:00Z', '2026-09-23T12:00:00'):
            with self.assertRaises(ContractError): self.prepare(cutoff=cutoff)

    def test_isolated_old_observation_does_not_claim_evaluation_to_later_cutoff(self):
        old = self.source('old-observation', '2026-09-22', '2026-09-22T17:00:00Z',
                          [('1', '2026-09-22T00:05:01Z', '100')])
        result = self.prepare('old-only', [old])
        for review in self.reviews(result):
            coverage = review['coverage']
            self.assertIsNone(coverage['actually_evaluated_market_cutoff'])
            self.assertEqual(coverage['conditional_computation_market_cutoff'], '2026-09-23T12:00:00Z')
            self.assertEqual(cr.utc(coverage['observed_event_max_at']), cr.utc('2026-09-22T00:05:01Z'))
            self.assertEqual(coverage['source_event_completeness'], 'UNKNOWN')
            self.assertFalse(coverage['result_is_evaluable'])
            self.assertTrue(all(value is None for value in review['metrics'].values()))

    def test_batch_retry_reuses_immutable_preparation_and_rejects_changed_request(self):
        inputs = self.inputs()
        output = cr.prepare_outbox(self.store, 'idempotent', inputs, 'first.json', '2026-09-23T12:00:00Z')
        raw = output.read_bytes(); self.now = '2026-09-23T19:00:00Z'
        retry = cr.prepare_outbox(self.store, 'idempotent', inputs, 'second.json', '2026-09-23T12:00:00Z')
        self.assertEqual(retry.read_bytes(), raw)
        self.assertFalse((output.parent / 'second.json').exists())
        with self.assertRaises(ContractError):
            cr.prepare_outbox(self.store, 'idempotent', self.inputs([]), 'third.json', '2026-09-23T12:00:00Z')

    def test_recovery_excludes_new_and_late_committed_records_and_reuses_committed_original(self):
        output = cr.prepare_outbox(self.store, 'frozen', self.inputs(), 'frozen.json', '2026-09-23T12:00:00Z')
        original = output.read_bytes(); saved = json.loads(original)
        self.now = '2026-09-23T19:00:00Z'; self.commit(saved)
        records, _, _ = self.store.load(strict=True)
        new_plan = copy.deepcopy(records[REFS[0]]); new_plan['plan_id'] = 'late-committed-plan'
        new_plan.pop('plan_ref', None)
        # Old availability cannot hide a genuinely later commit.
        self.store.commit_bundle('late-plan', 'research', [new_plan])
        later = self.prepare('later-review'); self.commit(later)
        self.now = '2026-09-23T20:00:00Z'
        retry = cr.prepare_outbox(self.store, 'frozen', self.inputs(), 'unused.json', '2026-09-23T12:00:00Z')
        self.assertEqual(retry.read_bytes(), original)
        self.assertEqual(json.loads(retry.read_text())['records'][0]['coverage']['registered'], 2)
        self.assertFalse((output.parent / 'unused.json').exists())

    def test_recovery_rejects_actual_committed_bundle_conflict(self):
        output = cr.prepare_outbox(self.store, 'commit-conflict', self.inputs(), 'first.json', '2026-09-23T12:00:00Z')
        committed = json.loads(output.read_text())
        committed['attachments']['EXTRA_LOCAL.txt'] = 'Different real committed bytes'
        self.now = '2026-09-23T19:00:00Z'; self.commit(committed)
        with self.assertRaisesRegex(ContractError, 'PREPARED_BATCH_DIFFERS_FROM_COMMITTED_ORIGINAL'):
            cr.prepare_outbox(self.store, 'commit-conflict', self.inputs(), 'second.json', '2026-09-23T12:00:00Z')

    def test_recovery_self_hash_cannot_authorize_private_export_or_forged_output(self):
        attacks = ('feedback-permission', 'batch-permission', 'batch-items', 'formal-metrics',
                   'private-request', 'method', 'source')
        for attack in attacks:
            with self.subTest(attack=attack):
                ident = 'recover-' + attack
                output = cr.prepare_outbox(self.store, ident, self.inputs(), ident + '.json', '2026-09-23T12:00:00Z')
                retained = self.retained(ident); saved = json.loads(retained.read_text())
                review = self.reviews(saved)[0]
                private_name = 'PRIVATE/' + review['review_id'] + '.json'
                if attack.endswith('permission'):
                    kind = 'feedback' if attack.startswith('feedback') else 'review_batch'
                    record = next(r for r in saved['records'] if r['record_type'] == kind)
                    record['disclosure']['public_attachments'].append('attachments/' + private_name)
                elif attack == 'batch-items':
                    saved['records'][0]['items'].pop()
                elif attack == 'formal-metrics':
                    review['metrics']['trade_count'] = 0
                elif attack == 'private-request':
                    private = self.private(saved, review); private['requests'] = []
                    self.replace_private(saved, review, private)
                elif attack == 'method':
                    method = json.loads(saved['attachments']['METHOD.json']); method['scope'] = 'FORGED'
                    saved['attachments']['METHOD.json'] = canonical(method).decode()
                else:
                    name = next(name for name in saved['attachments'] if name.startswith('SOURCE/'))
                    saved['attachments'][name] += '\n# altered source\n'
                self.reseal(retained, saved)
                before = retained.read_bytes()
                with self.assertRaises(ContractError):
                    cr.prepare_outbox(self.store, ident, self.inputs(), 'should-not-export.json', '2026-09-23T12:00:00Z')
                self.assertEqual(retained.read_bytes(), before)
                self.assertFalse((output.parent / 'should-not-export.json').exists())

    def test_public_snapshot_and_exact_archive_exclude_private_rows_and_reason(self):
        b = self.prepare(); self.commit(b)
        self.now = '2026-09-23T19:00:00Z'
        public_dir = self.root / 'site-data'
        publish_snapshot(self.store, public_dir, self.now)
        for path in public_dir.rglob('*'):
            if path.is_file():
                self.assertNotIn(PRIVATE_NUMBER.encode(), path.read_bytes(), str(path))
                self.assertNotIn(b'attachments/PRIVATE/', path.read_bytes(), str(path))
        metadata_text = b''.join(p.read_bytes() for p in public_dir.rglob('*') if p.is_file())
        self.assertIn(b'attachments/METHOD.json', metadata_text)
        self.assertIn(b'attachments/SOURCE/researchlib/conditional_review.py', metadata_text)
        self.assertNotIn(b'attachments/SOURCE/researchlib/public.py', metadata_text)
        for ident in (self.reviews(b)[0]['review_id'], 'c1', self.reviews(b)[0]['feedback_refs'][0]):
            target = self.root / (ident + '.zip')
            export_backup(self.store, target, record_refs=[ident])
            with zipfile.ZipFile(target) as archive:
                self.assertFalse(any('/PRIVATE/' in name for name in archive.namelist()))
                self.assertTrue(any('/attachments/METHOD.json' in name for name in archive.namelist()))
                self.assertTrue(any('/SOURCE/researchlib/conditional_review.py' in name for name in archive.namelist()))
                self.assertFalse(any('/SOURCE/researchlib/public.py' in name for name in archive.namelist()))
                for name in archive.namelist():
                    self.assertNotIn(PRIVATE_NUMBER.encode(), archive.read(name), name)

    def test_public_error_uses_code_not_exception_text_or_raw_path(self):
        with patch.object(cr, 'decode_sources', side_effect=OSError('/' + 'home/private/raw-price-' + PRIVATE_NUMBER)):
            b = self.prepare()
        text = canonical(b['records']).decode()
        self.assertNotIn(PRIVATE_NUMBER, text)
        self.assertNotIn('/' + 'home/private/', text)
        self.assertTrue(all(r['coverage']['reason_codes'] == ['CONDITIONAL_INPUT_OR_STATE_REJECTED'] for r in self.reviews(b)))

    def test_method_ref_cannot_borrow_other_committed_bundle(self):
        first = self.prepare()
        review = self.reviews(first)[0]
        review['review_method_ref'] = 'bundle:review-fixture/attachments/METHOD.json'
        self.commit(first); self.now = '2026-09-23T19:00:00Z'
        second = self.prepare('second')
        self.assertEqual(second['records'][0]['coverage']['technical_failures'], 1)

    def test_changed_method_source_even_with_valid_manifest_is_rejected(self):
        first = self.prepare()
        source_name = next(k for k in first['attachments'] if k.startswith('SOURCE/'))
        first['attachments'][source_name] += '\n# changed after method identity\n'
        self.commit(first); self.now = '2026-09-23T19:00:00Z'
        second = self.prepare('second')
        self.assertEqual(second['records'][0]['coverage']['technical_failures'], 2)

    def test_forged_private_event_with_recomputed_kernel_must_redecode_source(self):
        first = self.prepare(); review = self.reviews(first)[0]
        private = self.private(first, review)
        private['kernel_result']['input_payload']['events'][0]['price'] = '1234'
        records, _, _ = self.store.load(strict=True)
        from researchlib.funding_forward import evaluate
        private['kernel_result'] = evaluate(records[review['plan_ref']], private['kernel_result']['input_payload'],
            private['information_as_of'], private['market_event_cutoff'])
        raw = canonical(private)
        first['attachments']['PRIVATE/' + review['review_id'] + '.json'] = raw.decode()
        review['simulation_state'] = cr._summary(records[review['plan_ref']], private['kernel_result'], digest(raw))
        review['input_fingerprint'] = cr.sha(private['kernel_result']['input_payload'])
        self.commit(first); self.now = '2026-09-23T19:00:00Z'
        second = self.prepare('second')
        bad = next(r for r in self.reviews(second) if r['plan_ref'] == review['plan_ref'])
        self.assertEqual(bad['coverage']['reason_codes'], ['PREVIOUS_DECODE_NOT_REPRODUCIBLE'])

    def test_duplicate_input_conflicts_and_backward_cursor_do_not_reset(self):
        manifest = self.inputs([self.trade1, self.trade1])
        self.assertTrue(all(r['evaluation_stage'] == 'TECHNICAL_FAILURE' for r in self.reviews(self.prepare(manifest=manifest))))
        first = self.prepare(); self.commit(first); self.now = '2026-09-23T19:00:00Z'
        second = self.prepare('second', cutoff='2026-09-23T10:00:00Z')
        self.assertTrue(all(r['evaluation_stage'] == 'TECHNICAL_FAILURE' for r in self.reviews(second)))
        self.assertTrue(all(r['data_cutoff'] == '2026-09-23T12:00:00Z' for r in self.reviews(second)))

    def test_interrupted_export_retains_private_original_for_recovery(self):
        original_publish = waiting._publish_exclusive
        calls = [0]
        def fail_second(*args):
            calls[0] += 1
            if calls[0] == 2:
                raise InterruptedError('SYNTHETIC interruption before export')
            return original_publish(*args)
        with patch.object(waiting, '_publish_exclusive', side_effect=fail_second):
            with self.assertRaises(InterruptedError):
                cr.prepare_outbox(self.store, 'interrupted', self.inputs(), 'failed.json', '2026-09-23T12:00:00Z')
        self.assertFalse((self.root / '.local/review-outbox/failed.json').exists())
        recovered = cr.prepare_outbox(self.store, 'interrupted', self.inputs(), 'new.json', '2026-09-23T12:00:00Z')
        saved = json.loads(recovered.read_text())
        self.assertTrue(any(k.startswith('PRIVATE/') for k in saved['attachments']))
        self.assertEqual(saved['preparation']['prepared_at'], self.now)
        self.assertEqual(saved['records'][0]['coverage']['technical_failures'], 0)

    def test_outbox_tamper_and_symlink_are_rejected(self):
        path = cr.prepare_outbox(self.store, 'retained', self.inputs(), 'first.json', '2026-09-23T12:00:00Z')
        retained = self.root / '.local/review-outbox/.prepared-batches' / (digest(b'retained') + '.json')
        saved = json.loads(retained.read_text()); saved['records'][0]['complete'] = False
        retained.write_bytes(canonical(saved))
        with self.assertRaises(ContractError):
            cr.prepare_outbox(self.store, 'retained', self.inputs(), 'second.json', '2026-09-23T12:00:00Z')
        (path.parent / 'alias').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises((ContractError, OSError)):
            cr.prepare_outbox(self.store, 'new-id', self.inputs(), 'alias/escape.json', '2026-09-23T12:00:00Z')

    def test_retry_revalidates_original_registered_source_bytes(self):
        cr.prepare_outbox(self.store, 'retained-source', self.inputs(), 'first.json', '2026-09-23T12:00:00Z')
        records, _, _ = self.store.load(strict=True)
        path = self.store.data_root / 'objects' / records['trade1@1']['sha256']
        path.write_bytes(b'changed immutable source')
        with self.assertRaises(ContractError):
            cr.prepare_outbox(self.store, 'retained-source', self.inputs(), 'second.json', '2026-09-23T12:00:00Z')

    def test_complete_source_closure_stays_bound_despite_public_scanner_self_match(self):
        from researchlib.public import scan_bytes
        method, attachments = cr.method_material(self.now)
        self.assertIn('researchlib/__init__.py', method['source_sha256'])
        self.assertIn('researchlib/public.py', method['source_sha256'])
        for name, expected in method['source_sha256'].items():
            self.assertEqual(digest(attachments['SOURCE/' + name].encode()), expected)
        with self.assertRaisesRegex(ContractError, 'PRIVATE_LOCAL_PATH'):
            scan_bytes('SOURCE/researchlib/public.py', attachments['SOURCE/researchlib/public.py'].encode())

    def test_manifest_flags_and_mark_decoder_cannot_be_injected(self):
        for manifest in ({'schema_version': True, 'plans': {}}, {'schema_version': 1, 'plans': {}, 'complete': True}):
            with self.assertRaises(ContractError): self.prepare(manifest=manifest)
        manifest = self.inputs(); manifest['plans'][REFS[0]]['sources'][0]['adapter'] = 'invented-mark-adapter'
        self.assertEqual(self.prepare(manifest=manifest)['records'][0]['coverage']['technical_failures'], 1)

    def test_physical_manifest_corruption_still_blocks_entire_store(self):
        b = self.prepare(); self.commit(b)
        name = next(n for n in b['attachments'] if n.startswith('PRIVATE/'))
        (self.store.root / 'bundles' / b['bundle_id'] / 'attachments' / name).unlink()
        self.now = '2026-09-23T19:00:00Z'
        with self.assertRaises(ContractError): self.prepare('second')


if __name__ == '__main__':
    unittest.main()
