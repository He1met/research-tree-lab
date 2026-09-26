"""Store-only formal counterfactual review; no network, source claims or commit.

Approved 7db code remains unmodified. Its exact chain is reverified before
migration. All business capabilities are currently absent from production
resolutions. The same internal arithmetic admits independently tested facts,
but no CLI/request/backend may supply them.
"""
import ast
from copy import deepcopy
from pathlib import Path
import platform
from types import FunctionType

from . import conditional_review as legacy
from . import funding_review as waiting
from .common import canonical, digest, utc, under, read_json, safe_id
from .contracts import record_ref, validate_record, validate_relationships, semantic_refs
from .review import freeze_batch, verify_batch_coverage
from .public import public_record, scan_bytes
from .funding_forward import PLAN_HASHES
from .formal_funding import _Resolution, _compute, VERSION as ARITHMETIC_VERSION
from .conditional_review import (Rejected, fail, sha, _context, _reserve, _check_time,
    _bound_attachment_bytes, _attachment, _visible, _latest_review_ref,
    _event_diff, _correction_summary, _verify_transition)

VERSION = 'funding-formal-review-v1'
STATE_VERSION = 'formal-counterfactual-state-v1'
PRIVATE_VERSION = 'formal-private-computation-v1'
ORIGIN = 'OFFICIAL_APP_HELPER_NOT_NATIVE_ATTESTATION'
APPROVED_CONDITIONAL_HASH = '7dbdd186fd04ddca07dc3bfa933f9a0fae1ce66e1f1d91447e0bbeff5332d3ce'
PUBLIC_SCANNER_SOURCE_HASH = legacy.PUBLIC_SCANNER_SOURCE_HASH
PUBLIC_SCANNER_GIT_URL = legacy.PUBLIC_SCANNER_GIT_URL
MAX_PRIVATE_BYTES = legacy.MAX_PRIVATE_BYTES
MAX_HISTORY_REVIEWS = legacy.MAX_HISTORY_REVIEWS
MAX_HISTORY_NODES = legacy.MAX_HISTORY_NODES
MAX_SEMANTIC_ANCESTORS = 4096


def _old_method(at):
    material, _ = legacy.method_material(at)
    if material['method_code_sha256'] != APPROVED_CONDITIONAL_HASH:
        fail('DEPLOYED_7DB_IMPLEMENTATION_OR_RUNTIME_CHANGED')
    return material


def method_material(prepared_at):
    root = Path(__file__).resolve().parents[1]
    pending = ['researchlib/formal_review.py', 'scripts/prepare_formal_review.py'] + list(_old_method(prepared_at)['source_sha256'])
    sources, attachments = {}, {}
    def enqueue(module):
        for relative in ('/'.join(module) + '.py', '/'.join(module) + '/__init__.py'):
            if (root / relative).is_file():
                pending.append(relative)
                return
    while pending:
        relative = pending.pop()
        if relative in sources:
            continue
        content = (root / relative).read_text(encoding='utf-8')
        sources[relative] = digest(content.encode())
        attachments['SOURCE/' + relative] = content
        package = relative.split('/')[:-1]
        if package and package[0] == 'researchlib':
            pending.append('researchlib/__init__.py')
        for node in ast.walk(ast.parse(content)):
            if isinstance(node, ast.ImportFrom):
                module = (package[:len(package)-node.level+1] if node.level else []) + (node.module.split('.') if node.module else [])
                if module and module[0] == 'researchlib':
                    enqueue(module)
                    for alias in node.names:
                        enqueue(module + [alias.name])
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split('.')[0] == 'researchlib':
                        enqueue(alias.name.split('.'))
    runtime = {'implementation': platform.python_implementation(), 'python_version': platform.python_version(),
               'third_party_runtime_dependencies': []}
    identity = sha({'sources': dict(sorted(sources.items())), 'runtime': runtime})
    method = {'schema_version': '1.0', 'method_version': VERSION, 'method_code_sha256': identity,
              'source_sha256': dict(sorted(sources.items())), 'runtime': runtime,
              'available_at': prepared_at, 'created_at': prepared_at,
              'availability_basis': 'SOURCE_BYTES_OBSERVED_AT_PREPARATION_NOT_BACKDATED',
              'scope': 'FORMAL_COUNTERFACTUAL_ARITHMETIC_PRODUCTION_SOURCE_CAPABILITIES_UNPROVEN',
              'plan_hashes': PLAN_HASHES, 'private_schema': PRIVATE_VERSION, 'public_state_schema': STATE_VERSION}
    if sources.get('researchlib/public.py') != PUBLIC_SCANNER_SOURCE_HASH:
        fail('SOURCE_PUBLIC_EXPORT_EXCEPTION_REVIEW_REQUIRED')
    method['public_archive'] = {'self_contained_method_restore': False,
        'excluded_source_attachments': [{'path': 'SOURCE/researchlib/public.py', 'sha256': PUBLIC_SCANNER_SOURCE_HASH,
            'reason': 'SCANNER_SELF_MATCHES_OWN_PRIVATE_PATH_REGEX', 'git_source_locator': PUBLIC_SCANNER_GIT_URL,
            'locator_scope': 'IMMUTABLE_GIT_REF_NOT_NETWORK_AVAILABILITY_ATTESTATION'}],
        'full_source_closure_retained_locally': True}
    attachments['METHOD.json'] = canonical(method).decode()
    return method, attachments


def _check_time(context):
    legacy._check_time(context)
    old = context.get('old_context', {})
    if (context['encoded_bytes'] + old.get('encoded_bytes', 0) + context.get('public_replay_bytes', 0) > legacy.MAX_CONTEXT_BYTES
            or len(context['nodes'] | old.get('nodes', set())) > MAX_HISTORY_NODES):
        fail('COMBINED_HISTORY_RESOURCE_LIMIT_EXCEEDED')


def _ancestor_legacy_checks(store, records, metadata, roots, context):
    # Archive follows semantic references, including sibling reviews/feedback via
    # batches. A failed public review still references its predecessor: privacy
    # violations therefore stop preparation BEFORE any new bundle is produced.
    pending, seen, bundles = list(roots), set(), set()
    while pending:
        _check_time(context)
        ref = pending.pop()
        if ref in seen: continue
        if len(seen) >= MAX_SEMANTIC_ANCESTORS: fail('PUBLIC_ANCESTOR_CLOSURE_LIMIT_EXCEEDED')
        seen.add(ref)
        record = records[ref]
        pending.extend(semantic_refs(record))
        bundle = metadata[ref]['bundle_id']
        members = {key: r for key, r in records.items() if metadata[key]['bundle_id'] == bundle}
        # Permission safety is orthogonal to mutable evaluator/provenance labels.
        for member in members.values():
            for name in member.get('disclosure', {}).get('public_attachments', []):
                if 'private' in name.lower().split('/'):
                    fail('PUBLIC_ANCESTOR_POLICY_REJECTED')
        if record.get('record_type') != 'review': continue
        if bundle not in context['bundles']:
            manifest, _ = store._read_bundle(store.root / 'bundles' / bundle)
            context['bundles'][bundle] = {entry['path']: entry for entry in manifest['files']}
        files = context['bundles'][bundle]
        if 'attachments/SOURCE/researchlib/formal_review.py' in files:
            method_version = VERSION
        elif 'attachments/SOURCE/researchlib/conditional_review.py' in files:
            method_version = legacy.VERSION
        else:
            if any('/PRIVATE/' in name for name in files):
                fail('PUBLIC_ANCESTOR_METHOD_LAYOUT_REJECTED')
            continue
        if bundle in bundles: continue
        bundles.add(bundle)
        formal = method_version == VERSION
        at = record['available_at']
        if formal:
            material, attachments = method_material(at)
            policy = _disclosure(attachments)
        else:
            material, attachments = legacy.method_material(at)
            policy = {'visibility': 'PUBLIC', 'license': 'OWN_ANALYSIS',
                'public_attachments': ['attachments/' + name for name in sorted(attachments) if name != 'SOURCE/researchlib/public.py'],
                'scope': 'Authored summaries, method identity and explicitly scanned source. public.py remains local because its scanner matches its own regex; archive is not a self-contained method restore. Private computation never exported.'}
        members = {key: r for key, r in records.items() if metadata[key]['bundle_id'] == bundle}
        if any(r.get('disclosure') != policy for r in members.values()):
            fail('PUBLIC_ANCESTOR_POLICY_REJECTED')
        reason_codes = {'UNSUPPORTED_OR_MODIFIED_PLAN', 'FORMAL_INPUT_OR_STATE_REJECTED',
                        'CONDITIONAL_INPUT_OR_STATE_REJECTED'}
        for name, content in attachments.items():
            if name.startswith('SOURCE/') and name.endswith('.py'):
                for node in ast.walk(ast.parse(content)):
                    value = node.value if isinstance(node, ast.Constant) else None
                    if isinstance(value,str) and value and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789' for c in value):
                        reason_codes.add(value)
        reason_codes.update(name.upper() + '_UNPROVEN' for name in ('entry_first_trade','exit_first_trade',
            'position_at_cutoff','price_pnl','funding_cashflow','source_mark_path','verified_cost_schedule',
            'actual_cost','cost_terminal_interpretation'))
        reviews = [r for r in members.values() if r['record_type'] == 'review']
        for r in reviews:
            expected_summary = ('按封存规则逐指标复算；模拟与实际成本分开，缺项不补零。' if formal else
                                '条件输入复算与缺项处置；来源完整性未证，实际收益与交易状态未知。')
            expected_limitations = (['Counterfactual simulation is not an account fill or trading authority.',
                'No NOT_TRIGGERED branch is defined for these two already-triggered frozen plans.'] if formal else
                ['Conditional observations do not prove a first trade or complete funding/mark path.',
                 'No FINAL, NOT_TRIGGERED, readiness, actual return or natural execution claim.'])
            if r.get('summary') != expected_summary or r.get('limitations') != expected_limitations:
                fail('PUBLIC_ANCESTOR_DERIVED_TEXT_REJECTED')
            prov = r.get('provenance', {})
            provenance_keys = {'trigger_origin','natural_trigger','native_task_ref','method_available_at',
                'method_code_sha256','evaluation_information_as_of','state_migration','prior_state_preserved_in','correction_summary'}
            migrations = {'APPROVED_LEGACY_EMPTY_STATE_TO_CONDITIONAL',
                'APPROVED_WAITING_STATE_TO_CONDITIONAL_NOT_ZERO_INVENTORY','CONDITIONAL_PREFIX_CONTINUATION'}
            migrations |= {'VERIFIED_7DB_OR_APPROVED_WAITING_TO_FORMAL:' + name for name in migrations}
            migrations |= {None, 'FORMAL_PREFIX_CONTINUATION'}
            if set(prov) != provenance_keys or prov.get('state_migration') not in migrations:
                fail('PUBLIC_ANCESTOR_DERIVED_TEXT_REJECTED')
            correction = prov.get('correction_summary')
            if correction is not None:
                basic = {'diff_sha256','old_input_fingerprint','new_input_fingerprint','counts'}
                extra = {'old_fact_fingerprint','new_fact_fingerprint','changed_fact_groups'}
                if set(correction) not in (basic, basic | extra) or set(correction['counts']) != {'added','removed','changed'}:
                    fail('PUBLIC_ANCESTOR_DERIVED_TEXT_REJECTED')
                hashes = [v for k,v in correction.items() if k not in {'counts','changed_fact_groups'}]
                if (any(not isinstance(v,str) or len(v)!=64 or any(c not in '0123456789abcdef' for c in v) for v in hashes)
                        or any(type(v) is not int or not 0 <= v <= legacy.MAX_EVENTS for v in correction['counts'].values())
                        or set(correction.get('changed_fact_groups',[])) - {'capabilities','cost_allocation'}):
                    fail('PUBLIC_ANCESTOR_DERIVED_TEXT_REJECTED')
            # Unrestricted text or nested rows cannot ride a failed ancestor's
            # provenance/feedback; method identity errors alone remain per-plan.
            for reason in r['coverage']['reason_codes']:
                if reason not in reason_codes:
                    fail('PUBLIC_ANCESTOR_DERIVED_TEXT_REJECTED')
            feedback = members.get(r['feedback_refs'][0]) if len(r.get('feedback_refs', [])) == 1 else None
            if feedback is None: fail('PUBLIC_ANCESTOR_RELATIONS_REJECTED')
            common = {k: r[k] for k in ('schema_version','created_at','available_at','synthetic','disclosure')}
            expected_feedback = dict(common, record_type='feedback', feedback_id=r['feedback_refs'][0],review_ref=r['review_id'],
                status='AVAILABLE_FOR_RESEARCH_NOT_YET_ADOPTED', supported_facts=[r['evaluation_stage']] + r['coverage']['reason_codes'],
                interpretation='仅支持有证据资格的分项模拟指标；假设成本不代表实际费用。' if formal else '仅支持已声明条件与数据缺口；不支持策略盈利、无效或未触发结论。',
                proposed_question='依据明确缺项补充合法证据，保留原规则与已有状态链。' if formal else '保留原规则，补充合法来源的排序、覆盖和精确mark证据。',
                what_changes='复核方法与信息时点；旧原件不变。' if formal else '输入与复算版本；原计划和真实可得时点不改。',provenance=feedback.get('provenance'))
            # A mismatched method identity on the review is a per-plan failure.
            # Feedback cannot use that mismatch to admit arbitrary public text.
            feedback_prov = feedback.get('provenance', {})
            trusted_prov = dict(prov, trigger_origin=ORIGIN if formal else legacy.ORIGIN,
                natural_trigger=False, native_task_ref=None, method_available_at=r['available_at'],
                method_code_sha256=material['method_code_sha256'], prior_state_preserved_in=r['previous_review_ref'])
            if feedback_prov != trusted_prov:
                fail('PUBLIC_ANCESTOR_DERIVED_TEXT_REJECTED')
            if not formal: expected_feedback['required_data']=['Official event completeness, chronology and exact settlement mark evidence']
            if feedback != expected_feedback: fail('PUBLIC_ANCESTOR_DERIVED_TEXT_REJECTED')
        batches = [r for r in members.values() if r['record_type']=='review_batch']
        if len(batches) != 1: fail('PUBLIC_ANCESTOR_RELATIONS_REJECTED')
        b = batches[0]
        expected_batch_summary = ('全部登记方案逐项处置；新计算与已核验最终复用分别计数。' if formal else
                                  '全部登记方案逐项处置；条件计算不是完整经济评价。')
        if (b.get('trigger_origin') != (ORIGIN if formal else legacy.ORIGIN) or b.get('native_task_ref') is not None
                or b.get('complete') is not True or b.get('summary') != expected_batch_summary):
            fail('PUBLIC_ANCESTOR_BATCH_SUMMARY_REJECTED')
        visible = {key: value for key, value in records.items() if metadata[key]['bundle_id'] != bundle
                   and utc(value['available_at']) <= utc(b['frozen_at'])
                   and utc(metadata[key]['committed_at']) <= utc(b['frozen_at'])}
        class HistoricalStore:
            clock = staticmethod(lambda: b['available_at'])
            def load(self, strict=True):
                return visible, {key: metadata[key] for key in visible}, []
        frozen = freeze_batch(HistoricalStore(), b['batch_id'], b['frozen_at'], ORIGIN if formal else legacy.ORIGIN, None)
        if any(b.get(key) != frozen[key] for key in ('created_at','available_at','frozen_at','cutoff','plan_refs')):
            fail('PUBLIC_ANCESTOR_FROZEN_BATCH_REJECTED')
        if len(b['items']) != len(frozen['items']):
            fail('PUBLIC_ANCESTOR_FROZEN_BATCH_REJECTED')
        reviews_by_plan = {r['plan_ref']: r for r in reviews}
        for item, frozen_item in zip(b['items'], frozen['items']):
            r = reviews_by_plan.get(item['plan_ref'])
            if r is None or any(item.get(key) != value for key, value in frozen_item.items() if key != 'disposition'):
                fail('PUBLIC_ANCESTOR_FROZEN_BATCH_REJECTED')
            expected_item = dict(frozen_item, disposition=r.get('disposition',r['evaluation_stage']),
                review_ref=r['review_id'], result_is_evaluable=r['coverage']['result_is_evaluable'],
                reason_codes=r['coverage']['reason_codes'])
            if item != expected_item:
                fail('PUBLIC_ANCESTOR_FROZEN_BATCH_REJECTED')
        if formal:
            if sorted(b.get('input_record_refs', [])) != sorted(r['review_id'] for r in reviews):
                fail('PUBLIC_ANCESTOR_RELATIONS_REJECTED')
            expected_coverage = _batch_coverage(b, list(members.values()), records)
        else:
            expected_coverage = verify_batch_coverage(b, members)
            expected_coverage.update(evaluable_results=0, final_results=0,
                technical_failures=sum(i['disposition']=='TECHNICAL_FAILURE' for i in b['items']))
        if b.get('coverage') != expected_coverage:
            fail('PUBLIC_ANCESTOR_BATCH_SUMMARY_REJECTED')


def _ancestor_public_policy(store, records, metadata, roots, context):
    """Prove the public ancestor bytes, independently of their claimed layout.

    Re-run only the installed, hash-bound generators at the historical visible
    snapshot. Never execute bundled Python, accept a caller supplied backend, or
    infer permission from a file name. Whole-record equality closes every nested
    field, including fields the generic exporter intentionally permits.
    """
    _ancestor_legacy_checks(store, records, metadata, roots, context)
    pending, seen = list(roots), set()
    verified = context.setdefault('public_verified_bundles', set())
    while pending:
        _check_time(context)
        ref = pending.pop()
        if ref in seen:
            continue
        seen.add(ref)
        if len(seen) > MAX_SEMANTIC_ANCESTORS:
            fail('PUBLIC_ANCESTOR_CLOSURE_LIMIT_EXCEEDED')
        record = records[ref]
        pending.extend(semantic_refs(record))
        if record.get('record_type') != 'review':
            continue
        bundle_id = metadata[ref]['bundle_id']
        if bundle_id in verified:
            continue
        members = {k: r for k, r in records.items() if metadata[k]['bundle_id'] == bundle_id}
        manifest, _ = store._read_bundle(store.root / 'bundles' / bundle_id)
        files = {f['path']: f for f in manifest['files']}
        if record.get('evaluator_version') == waiting.LEGACY_METHOD:
            # Actual first-review originals, not regenerated or fixture-backed.
            original_hashes = dict(waiting.LEGACY_REVIEW_HASHES, **{
                'batch-manual-safe-review-20260923-v1': '00cb81af6c6e9a9f486de3693a2f8ebad041a426610064c2b0751b3891f41b3f',
                'feedback-btc-funding-long-control-manual-20260923-v1': '0bc04f617365b2b72f5100d992c2648e4c6b8e29c2f70311e2ed4b1a32530a2c',
                'feedback-btc-funding-short-manual-20260923-v1': '59fa17345b905be5e960a72d805ae843404d83dd69e6625f9b440c77af8370df'})
            allowed = {'attachments/REVIEW_METHOD.md': '0cf401a81d83fc989b84ea70339ddbb6ca68f71882ef79f9f889b64f2dca2455',
                'attachments/independent_arithmetic.json': 'ef1a571ec785f85767d40f8f4298f63b29e594857702175d1f15be0df0f79e99',
                'attachments/independent_audit.py': '1e698b6255620d1bb3fd9eea8d66a520ca637cb35bbb41c1d18eef9a27aaae44'}
            if {k: sha(v) for k, v in members.items()} != original_hashes:
                fail('PUBLIC_ANCESTOR_ORIGINAL_BYTES_REJECTED')
            for name in allowed.keys() & files.keys():
                if files[name]['sha256'] != allowed[name]:
                    fail('PUBLIC_ANCESTOR_ATTACHMENT_BYTES_REJECTED')
            verified.add(bundle_id)
            continue
        batches = [r for r in members.values() if r['record_type'] == 'review_batch']
        if len(batches) != 1 or 'attachments/METHOD.json' not in files:
            fail('PUBLIC_ANCESTOR_METHOD_LAYOUT_REJECTED')
        batch = batches[0]
        at = batch['available_at']
        material, _, method_ref = _attachment(store, metadata, record, 'METHOD.json', context, 1_000_000)
        version = material.get('method_version')
        visible = {k: r for k, r in records.items() if metadata[k]['bundle_id'] != bundle_id
            and utc(r['available_at']) <= utc(at) and utc(metadata[k]['committed_at']) <= utc(at)}
        class HistoricalStore:
            clock = staticmethod(lambda: at)
            def load(self, strict=True):
                return deepcopy(visible), {k: deepcopy(metadata[k]) for k in visible}, []
            def __getattr__(self, name):
                return getattr(store, name)
        historical = HistoricalStore()
        reviews = [r for r in members.values() if r['record_type'] == 'review']
        if not reviews:
            fail('PUBLIC_ANCESTOR_RELATIONS_REJECTED')
        if version == waiting.VERSION:
            profile = legacy.APPROVED_WAITING_PROFILES.get(material.get('method_code_sha256'))
            if profile is None or material != dict(profile, available_at=at, created_at=at):
                fail('PUBLIC_ANCESTOR_METHOD_IDENTITY_REJECTED')
            attachments = {}
            for name, source in legacy.WAITING_SOURCE_ATTACHMENTS.items():
                raw, _ = _bound_attachment_bytes(store, metadata, record, name, context)
                if digest(raw) != profile['source_sha256'][source]:
                    fail('PUBLIC_ANCESTOR_ATTACHMENT_BYTES_REJECTED')
                attachments[name] = raw.decode()
            attachments['METHOD.json'] = canonical(material).decode()
            # The local generator itself is pinned by _old_method. A private
            # globals copy binds only the two reviewed historical method records;
            # no attachment is evaluated and no shared module state is mutated.
            namespace = dict(waiting.prepare_bundle.__globals__)
            namespace['method_material'] = lambda _: (deepcopy(material), deepcopy(attachments))
            generator = FunctionType(waiting.prepare_bundle.__code__, namespace)
            requested = reviews[0]['coverage'].get('requested_market_event_cutoff')
            expected = generator(historical, batch['batch_id'], requested)
        elif version in {VERSION, legacy.VERSION}:
            approved, _ = method_material(at) if version == VERSION else legacy.method_material(at)
            if material != approved:
                fail('PUBLIC_ANCESTOR_METHOD_IDENTITY_REJECTED')
            inputs, cutoffs, failures = {}, set(), []
            for r in reviews:
                if r.get('evaluator_version') != version + '@sha256:' + approved['method_code_sha256']:
                    fail('PUBLIC_ANCESTOR_METHOD_IDENTITY_REJECTED')
                if r['evaluation_stage'] in {'TECHNICAL_FAILURE', 'RULES_INCOMPLETE'}:
                    failures.append(r)
                    continue
                private, _, _ = _attachment(store, metadata, r, 'PRIVATE/' + r['review_id'] + '.json', context)
                inputs[r['plan_ref']] = {'sources': private['requests'], 'correction': private['correction']}
                cutoffs.add(private['market_event_cutoff'])
            if len(cutoffs) > 1:
                fail('PUBLIC_ANCESTOR_REQUEST_RECONSTRUCTION_REQUIRED')
            requested = next(iter(cutoffs)) if cutoffs else None
            request = {'schema_version': 1, 'plans': inputs}
            if version == VERSION:
                child = _context()
                child['deadline'] = context['deadline']
                child['public_verified_bundles'] = verified
                expected = _prepare_bundle(historical, batch['batch_id'], request, requested, child)
                # Validation caches must not authorize a later economic replay
                # under different resource limits. Account for the temporary
                # work while keeping its predecessor cache private.
                context['public_replay_bytes'] = context.get('public_replay_bytes', 0) + child['encoded_bytes'] + child.get('public_replay_bytes', 0) + child.get('old_context', {}).get('encoded_bytes', 0)
                _check_time(context)
            else:
                expected = legacy.prepare_bundle(historical, batch['batch_id'], request, requested)
            for failed in failures:
                wanted = next(r for r in expected['records'] if r.get('review_id') == failed['review_id'])
                parent = records.get(failed['previous_review_ref'])
                if failed['evaluation_stage'] == 'RULES_INCOMPLETE':
                    if (wanted['evaluation_stage'] != 'RULES_INCOMPLETE'
                            or utc(failed['data_cutoff']) > utc(at)
                            or not _is_sha(failed.get('input_fingerprint'))
                            or parent and utc(failed['data_cutoff']) < utc(parent['data_cutoff'])):
                        fail('PUBLIC_ANCESTOR_PUBLIC_RECONSTRUCTION_REJECTED')
                    # Unsupported plans have no private request. Their bounded
                    # timestamp is not an economic evaluation or raw payload.
                    wanted['data_cutoff'] = failed['data_cutoff']
                    wanted['input_fingerprint'] = failed['input_fingerprint']
                    continue
                fingerprint = failed.get('input_fingerprint')
                if not _is_sha(fingerprint):
                    fail('PUBLIC_ANCESTOR_PUBLIC_RECONSTRUCTION_REJECTED')
                reasons = failed['coverage']['reason_codes']
                # The preliminary gate already proves finite method reason
                # literals and migration vocabulary; never echo exception text.
                provenance = dict(wanted['provenance'], state_migration=failed['provenance']['state_migration'],
                    correction_summary=None, evaluation_information_as_of=at)
                wanted.update(evaluation_stage=failed['evaluation_stage'], simulation_state=None,
                    data_complete=False, metrics={k: None for k in waiting.METRICS}, input_fingerprint=fingerprint,
                    data_cutoff=parent['data_cutoff'] if parent else records[failed['plan_ref']]['available_at'],
                    coverage={'source_coverage':'UNKNOWN','result_is_evaluable':False,
                        'actually_evaluated_market_cutoff':None,'information_as_of':at,'reason_codes':reasons},
                    provenance=provenance)
                wanted.pop('supersedes', None); wanted.pop('correction_reason', None)
                if version == VERSION:
                    wanted.update(disposition=failed['evaluation_stage'], input_record_refs=[],
                        results={'metric_scope':'FROZEN_RULE_COUNTERFACTUAL_NOT_ACCOUNT_EXECUTION'})
                feedback = next(r for r in expected['records'] if r.get('feedback_id') == wanted['feedback_refs'][0])
                feedback.update(provenance=provenance, supported_facts=[failed['evaluation_stage']] + reasons)
                item = next(i for i in expected['records'][0]['items'] if i['plan_ref'] == failed['plan_ref'])
                item.update(disposition=failed['evaluation_stage'], result_is_evaluable=False, reason_codes=reasons)
            if failures:
                eb = expected['records'][0]
                if version == VERSION:
                    eb['coverage'] = _batch_coverage(eb, expected['records'][1:], records)
                else:
                    eb['coverage'] = verify_batch_coverage(eb, {record_ref(r):r for r in expected['records']})
                    eb['coverage'].update(evaluable_results=0,final_results=0,
                        technical_failures=sum(i['disposition']=='TECHNICAL_FAILURE' for i in eb['items']))
        else:
            fail('PUBLIC_ANCESTOR_METHOD_IDENTITY_REJECTED')
        expected_records = {record_ref(r): r for r in expected['records']}
        if set(members) != set(expected_records):
            fail('PUBLIC_ANCESTOR_RECORD_SET_REJECTED')
        for key, actual in members.items():
            wanted = expected_records[key]
            comparable = deepcopy(actual)
            if actual['record_type'] == 'review':
                # These bounded scalar integrity faults contain no raw text or
                # rows. Keep the original bytes and let economic validation fail
                # only this plan, rather than suppress every other safe plan.
                prov = comparable.get('provenance', {})
                if _is_sha(prov.get('method_code_sha256')):
                    prov['method_code_sha256'] = wanted['provenance']['method_code_sha256']
                state, expected_state = comparable.get('simulation_state'), wanted.get('simulation_state')
                if isinstance(state,dict) and isinstance(expected_state,dict):
                    if state.get('inventory') in (None, '0', '0.01', '-0.01'):
                        state['inventory'] = expected_state['inventory']
                    if _is_sha(state.get('private_computation_sha256')):
                        state['private_computation_sha256'] = expected_state['private_computation_sha256']
            if canonical(comparable) != canonical(wanted):
                fail('PUBLIC_ANCESTOR_PUBLIC_RECONSTRUCTION_REJECTED')
            for name in actual['disclosure']['public_attachments']:
                content = expected['attachments'].get(name[len('attachments/'):])
                if content is None or name not in files or files[name]['sha256'] != digest(content.encode()):
                    fail('PUBLIC_ANCESTOR_ATTACHMENT_BYTES_REJECTED')
        verified.add(bundle_id)


def _is_sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _resolve_sources(store, plan, requests, records, metadata, at, cutoff, context):
    # No arbitrary validator name, events, certificate, or completeness flags.
    # Existing audited parsers prove only bytes/schema/declared partitions.
    payload, bindings, audits = legacy._decoded(context, store, requests, records, metadata, at, cutoff)
    return _Resolution(sha(plan), at, cutoff, payload, bindings, audits)


def _resolved(context, store, plan, requests, records, metadata, at, cutoff):
    _check_time(context)
    key = sha({'plan': sha(plan), 'requests': requests, 'at': at, 'cutoff': cutoff})
    cache = context.setdefault('formal_resolution', {})
    if key not in cache:
        value = _resolve_sources(store, plan, requests, records, metadata, at, cutoff, context)
        _reserve(context, value.__dict__ | {'capabilities': sorted(value.capabilities)})
        cache[key] = value
    _check_time(context)
    return cache[key]


def _disclosure(attachments):
    return {'visibility': 'PUBLIC', 'license': 'OWN_ANALYSIS',
        'public_attachments': ['attachments/' + name for name in sorted(attachments)
                               if name == 'METHOD.json' or name.startswith('SOURCE/') and name != 'SOURCE/researchlib/public.py'],
        'scope': 'Authored summaries and scanned source; private inputs and equity paths excluded. The public.py scanner exception prevents self-contained public method restore.'}


def _summary(plan, result, private_hash):
    before = utc(result['information_as_of']) < utc(plan['effective_from'])
    return {'schema_version': STATE_VERSION, 'plan_hash': result['plan_hash'],
        'state': 'SIMULATION_CLOSED' if result['data_complete'] else result['evaluation_stage'],
        'inventory': result['simulation_inventory'] if not before else '0',
        'inventory_scope': 'FROZEN_RULE_COUNTERFACTUAL_NOT_ACCOUNT', 'actual_inventory': None,
        'private_computation_sha256': private_hash,
        'accepted_observation_count': len(result['kernel_result']['simulation_state']['event_hashes'])}


def _coverage(plan, result, resolved):
    base = legacy._coverage(plan, result['market_event_cutoff'], resolved.audits, resolved.payload['events'])
    base.update(information_as_of=result['information_as_of'],
        qualification=deepcopy(result['qualification']),
        actually_evaluated_market_cutoff=result['actually_evaluated_market_cutoff'],
        result_is_evaluable=any(v is not None for v in result['metrics'].values()),
        source_coverage='VERIFIED_FOR_FROZEN_REQUIREMENTS' if result['data_complete'] else 'PARTIAL_OR_UNKNOWN',
        reason_codes=[name.upper() + '_UNPROVEN' for name, value in result['qualification'].items() if value != 'SATISFIED'],
        scope='PER_METRIC_FROZEN_RULE_COUNTERFACTUAL_NOT_ACCOUNT_EXECUTION',
        exchange_chronology='VERIFIED_FOR_REQUIRED_WINDOWS' if 'TRADE_ORDER' in resolved.capabilities else 'UNKNOWN',
        exact_settlement_mark=result['qualification']['funding_cashflow'],
        full_mark_path=result['qualification']['source_mark_path'],
        actual_costs=result['qualification']['actual_cost'],
        source_event_completeness='VERIFIED_FOR_CURRENT_POSITION_INTERVAL' if result['actually_evaluated_market_cutoff'] else 'UNKNOWN',
        cutoff_scope='VERIFIED_MARKET_DEPENDENCIES_COST_SEPARATE' if result['actually_evaluated_market_cutoff'] else 'CONDITIONAL_COMPUTATION_ONLY')
    return base


def _public_result(result, reused_from=None):
    # Construct explicit aggregate allowlist; never copy arbitrary private keys.
    metrics = {key: result['metrics'][key] for key in (
        'gross_price_pnl', 'realized_pnl', 'unrealized_pnl', 'funding_cashflow',
        'holding_period', 'trade_count', 'actual_total_cost', 'actual_net', 'net_pnl', 'observed_path_drawdown')}
    scenarios = [{key: s[key] for key in ('fee_bps_each_side', 'slippage_bps_each_side',
        'assumption_only', 'fees', 'slippage_cost', 'net_pnl', 'observed_path_drawdown')} for s in result['scenarios']]
    return metrics, {'metric_scope': result['metric_scope'], 'currency': 'USDT',
        'holding_period_unit': 'seconds', 'inventory_unit': 'BTC',
        'scenarios': scenarios, 'reused_from': reused_from,
        'economic_computation_information_as_of': result['information_as_of'], 'economic_recomputed': reused_from is None,
        'actual_path_summary': result['actual_path_summary'], 'terminal_requirements': result['terminal_requirements']}


def _fact_state(private=None, resolved=None):
    if resolved is not None:
        return {'capabilities': sorted(resolved.capabilities), 'cost_allocation': resolved.actual_costs}
    return {'capabilities': private['formal_result']['capabilities'], 'cost_allocation': private.get('cost_allocation')}


def _formal_correction(correction, parent, prior, parent_private, resolved):
    if not parent_private or parent_private.get('schema_version') != PRIVATE_VERSION:
        return _correction_summary(correction, parent, prior, resolved.payload)
    keys = {'previous_review_ref', 'old_input_fingerprint', 'new_input_fingerprint', 'event_diff', 'reason',
            'old_fact_fingerprint', 'new_fact_fingerprint', 'fact_diff'}
    if not isinstance(correction, dict) or set(correction) != keys:
        fail('FORMAL_CORRECTION_CONTRACT_REQUIRED')
    old, new = _fact_state(private=parent_private), _fact_state(resolved=resolved)
    facts = {key: {'old_sha256': sha(old[key]), 'new_sha256': sha(new[key])} for key in old if old[key] != new[key]}
    difference = _event_diff(prior['input_payload'], resolved.payload)
    if (correction['previous_review_ref'] != parent['review_id']
            or correction['old_input_fingerprint'] != sha(prior['input_payload'])
            or correction['new_input_fingerprint'] != sha(resolved.payload)
            or correction['event_diff'] != difference or correction['fact_diff'] != facts
            or correction['old_fact_fingerprint'] != sha(old) or correction['new_fact_fingerprint'] != sha(new)
            or not (any(difference.values()) or facts) or not isinstance(correction['reason'], str)
            or not 1 <= len(correction['reason']) <= 1000):
        fail('CORRECTION_NOT_BOUND_TO_EXACT_INPUT_DIFF')
    return {'diff_sha256': sha({'events': difference, 'facts': facts}),
        'old_input_fingerprint': sha(prior['input_payload']), 'new_input_fingerprint': sha(resolved.payload),
        'old_fact_fingerprint': sha(old), 'new_fact_fingerprint': sha(new),
        'counts': {k: len(v) for k, v in difference.items()}, 'changed_fact_groups': sorted(facts)}


def _verify_formal_transition(plan, review, private, parent, prior, parent_private, resolved, migration):
    correction = private['correction']
    if correction is None:
        if parent_private and parent_private.get('schema_version') == PRIVATE_VERSION and _fact_state(private=parent_private) != _fact_state(resolved=resolved):
            fail('EXPLICIT_FACT_CORRECTION_REQUIRED')
        _verify_transition(plan, review, private, parent, prior, migration)
        return
    summary = _formal_correction(correction, parent, prior, parent_private, resolved)
    if (review.get('opening_state_hash') != sha(parent['simulation_state'])
            or review.get('provenance', {}).get('state_migration') != migration
            or review.get('supersedes') != parent['review_id']
            or review.get('correction_reason') != 'EXPLICIT_INPUT_REVISION_SEE_PRIVATE_AUDIT'
            or review['provenance'].get('correction_summary') != summary):
        fail('PUBLIC_PRIVATE_CORRECTION_MISMATCH')
    legacy._verify_kernel(plan, private['kernel_result'], None)


def _previous(store, previous, plan, records, metadata, current_method, context=None):
    context = context if context is not None else _context()
    _check_time(context)
    if previous is None:
        fail('PREVIOUS_FORMAL_REVIEW_REQUIRED')
    ident = previous['review_id']
    if previous.get('plan_hash') != sha(plan):
        fail('PREVIOUS_PLAN_HASH_MISMATCH')
    if ident in context['visiting']:
        fail('PREVIOUS_REVIEW_CHAIN_CYCLE')
    if ident in context['verified']:
        return context['verified'][ident]
    if len(context['visiting']) >= MAX_HISTORY_REVIEWS:
        fail('PREVIOUS_REVIEW_CHAIN_LIMIT_EXCEEDED')
    context['nodes'].add(ident)
    if len(context['nodes']) > MAX_HISTORY_NODES:
        fail('PREVIOUS_REVIEW_NODE_LIMIT_EXCEEDED')
    context['visiting'].add(ident)
    try:
        result = _previous_node(store, previous, plan, records, metadata, current_method, context)
        _reserve(context, result)
        _check_time(context)
        context['verified'][ident] = result
        return result
    finally:
        context['visiting'].remove(ident)


def _previous_node(store, previous, plan, records, metadata, current_method, context):
    old_method = _old_method(current_method['available_at'])
    if previous.get('evaluator_version') != VERSION + '@sha256:' + current_method['method_code_sha256']:
        # This delegates only to installed, hash-pinned trusted code; never to
        # Python taken from a record attachment. Unknown methods fail there.
        prov = previous.get('provenance', {})
        if previous.get('evaluator_version', '').startswith(legacy.VERSION + '@') and (
                prov.get('method_code_sha256') != APPROVED_CONDITIONAL_HASH or prov.get('natural_trigger') is not False
                or prov.get('native_task_ref') is not None or prov.get('trigger_origin') != legacy.ORIGIN):
            fail('PREVIOUS_PROVENANCE_BINDING_INVALID')
        old_context = context.setdefault('old_context', _context())
        old_context['deadline'] = context['deadline']
        old_context['visiting'] = set(context['visiting']) - {previous['review_id']}
        old, private, migration = legacy._previous(store, previous, plan, records, metadata, old_method, old_context)
        if (len(context['nodes'] | old_context['nodes']) > MAX_HISTORY_NODES
                or context['encoded_bytes'] + old_context['encoded_bytes'] > legacy.MAX_CONTEXT_BYTES):
            fail('COMBINED_HISTORY_RESOURCE_LIMIT_EXCEEDED')
        return old, private, 'VERIFIED_7DB_OR_APPROVED_WAITING_TO_FORMAL:' + migration
    ref = previous['review_id']
    _visible(ref, records, metadata, current_method['available_at'])
    parent_ref = previous.get('previous_review_ref')
    if parent_ref != _latest_review_ref(records, metadata, previous['plan_ref'], previous['available_at'], ref):
        fail('HISTORICAL_LATEST_PREDECESSOR_SKIPPED')
    parent = _visible(parent_ref, records, metadata, previous['available_at'])
    if (parent.get('plan_ref') != previous['plan_ref'] or previous['revision'] != parent['revision'] + 1
            or utc(parent['available_at']) >= utc(previous['available_at'])
            or utc(parent['data_cutoff']) > utc(previous['data_cutoff'])):
        fail('FORMAL_PREDECESSOR_LINK_INVALID')
    prior, parent_private, migration = _previous(store, parent, plan, records, metadata, current_method, context)
    material, _, method_ref = _attachment(store, metadata, previous, 'METHOD.json', context, 1_000_000)
    expected = dict(current_method, available_at=previous['available_at'], created_at=previous['available_at'])
    if (material != expected or previous.get('review_method_ref') != method_ref
            or utc(previous['available_at']) > utc(metadata[ref]['committed_at'])
            or previous.get('provenance', {}).get('method_available_at') != previous['available_at']):
        fail('PREVIOUS_FORMAL_METHOD_BINDING_INVALID')
    for path, expected_sha in material['source_sha256'].items():
        raw, _ = _bound_attachment_bytes(store, metadata, previous, 'SOURCE/' + path, context)
        if digest(raw) != expected_sha:
            fail('PREVIOUS_METHOD_SOURCE_BYTES_MISMATCH')
    private, raw, _ = _attachment(store, metadata, previous, 'PRIVATE/' + ref + '.json', context)
    if (private.get('schema_version') != PRIVATE_VERSION or private.get('plan_hash') != sha(plan)
            or private.get('method_code_sha256') != material['method_code_sha256']
            or private.get('information_as_of') != previous['available_at']
            or private.get('market_event_cutoff') != previous['data_cutoff']):
        fail('PREVIOUS_PRIVATE_BINDING_INVALID')
    resolved = _resolved(context, store, plan, private['requests'], records, metadata,
                         previous['available_at'], previous['data_cutoff'])
    reused_from = private.get('reused_from')
    if reused_from is not None:
        if (reused_from != parent_ref or parent.get('evaluation_stage') != 'FINAL'
                or parent.get('evaluator_version') != previous.get('evaluator_version') or parent_private is None
                or private['correction'] is not None or previous.get('supersedes') or previous.get('correction_reason')
                or previous.get('opening_state_hash') != sha(parent['simulation_state'])
                or private.get('reuse_parent_kernel_state_sha256') != sha(prior['simulation_state'])
                or private.get('reuse_parent_private_sha256') != sha(parent_private)
                or private['requests'] != parent_private['requests']
                or resolved.bindings != parent_private['source_bindings']
                or resolved.payload != prior['input_payload']
                or sorted(resolved.capabilities) != parent_private['formal_result']['capabilities']
                or resolved.actual_costs != parent_private.get('cost_allocation')):
            fail('REUSED_FINAL_BINDING_INVALID')
        result = deepcopy(parent_private['formal_result'])
    else:
        if private.get('reuse_parent_kernel_state_sha256') is not None or private.get('reuse_parent_private_sha256') is not None:
            fail('ORDINARY_REVIEW_HAS_REUSE_CLAIMS')
        _verify_formal_transition(plan, previous, private, parent, prior, parent_private, resolved, migration)
        result = _compute(plan, resolved, None if private['correction'] else prior)
    expected_provenance = {'trigger_origin': ORIGIN, 'natural_trigger': False, 'native_task_ref': None,
        'method_available_at': previous['available_at'], 'method_code_sha256': material['method_code_sha256'],
        'evaluation_information_as_of': result['information_as_of'], 'state_migration': migration,
        'prior_state_preserved_in': parent_ref,
        'correction_summary': _formal_correction(private['correction'], parent, prior, parent_private, resolved) if private['correction'] else None}
    if previous.get('provenance') != expected_provenance:
        fail('PREVIOUS_PROVENANCE_BINDING_INVALID')
    if (private.get('formal_result') != result or private['kernel_result'] != result['kernel_result']
            or private.get('source_bindings') != resolved.bindings or private.get('decode_audits') != resolved.audits
            or private.get('cost_allocation') != resolved.actual_costs):
        fail('PREVIOUS_FORMAL_RESULT_NOT_REPRODUCIBLE')
    metrics, results = _public_result(result, reused_from)
    if (previous.get('simulation_state') != _summary(plan, result, digest(raw))
            or previous.get('metrics') != metrics or previous.get('results') != results
            or previous.get('coverage') != dict(_coverage(plan, result, resolved), information_as_of=previous['available_at'])
            or previous.get('evaluation_stage') != result['evaluation_stage']
            or previous.get('data_complete') != result['data_complete']
            or previous.get('input_fingerprint') != sha(resolved.payload)
            or previous.get('disposition') != ('REUSED_FINAL' if reused_from else result['evaluation_stage'])
            or previous.get('input_record_refs') != ([parent_ref] if reused_from else [])):
        fail('PREVIOUS_PUBLIC_PRIVATE_RESULT_MISMATCH')
    _, source_attachments = method_material(previous['available_at'])
    policy = _disclosure(source_attachments)
    bundle = metadata[ref]['bundle_id']
    if any(record.get('disclosure') != policy for key, record in records.items() if metadata[key]['bundle_id'] == bundle):
        fail('PREVIOUS_PUBLIC_ATTACHMENT_POLICY_CHANGED')
    return result['kernel_result'], private, 'FORMAL_PREFIX_CONTINUATION'


def _batch_coverage(batch, output, records):
    current = {r['plan_ref']: r for r in output if r['record_type'] == 'review'}
    handled, reused, refs = set(), 0, {}
    for item in batch['items']:
        ref = item['plan_ref']
        if ref in handled:
            fail('DUPLICATE_BATCH_DISPOSITION')
        rid = item['review_ref']
        if ref not in current or current[ref]['review_id'] != rid:
            fail('BATCH_REVIEW_MISSING')
        if item['disposition'] == 'REUSED_FINAL':
            carrier = current[ref]
            parent = records.get(carrier['previous_review_ref'])
            if (parent is None or parent['plan_ref'] != ref or parent['evaluation_stage'] != 'FINAL'
                    or carrier.get('disposition') != 'REUSED_FINAL'
                    or carrier.get('input_record_refs') != [parent['review_id']]
                    or carrier['results'].get('reused_from') != parent['review_id']):
                fail('INVALID_FINAL_REUSE_DISPOSITION')
            reused += 1
        handled.add(ref); refs[ref] = [rid]
    if handled != set(batch['plan_refs']):
        fail('BATCH_DISPOSITION_INCOMPLETE')
    return {'registered': len(handled), 'reviewed': len(current), 'reused': reused, 'new_economic_computations': sum(i['result_is_evaluable'] and i['disposition'] != 'REUSED_FINAL' for i in batch['items']),
        'missing': [], 'coverage_complete': True, 'review_refs': refs,
        'evaluable_results': sum(i['result_is_evaluable'] for i in batch['items']),
        'final_results': sum(i['disposition'] in {'FINAL', 'REUSED_FINAL'} for i in batch['items']),
        'technical_failures': sum(i['disposition'] == 'TECHNICAL_FAILURE' for i in batch['items'])}


def prepare_bundle(store, batch_id, input_manifest, market_event_cutoff=None):
    return _prepare_bundle(store, batch_id, input_manifest, market_event_cutoff, _context())


def _prepare_bundle(store, batch_id, input_manifest, market_event_cutoff, context):
    safe_id(batch_id)
    if len(batch_id) > 90:
        fail('BATCH_ID_TOO_LONG')
    if (not isinstance(input_manifest, dict) or set(input_manifest) != {'schema_version', 'plans'}
            or type(input_manifest['schema_version']) is not int or input_manifest['schema_version'] != 1
            or not isinstance(input_manifest['plans'], dict)):
        fail('INPUT_MANIFEST_FIELDS_REJECTED')
    at = store.clock(); now = utc(at)
    _old_method(at)  # Full deployed closure/runtime identity, before preparation.
    if market_event_cutoff and utc(market_event_cutoff) > now:
        fail('FUTURE_MARKET_CUTOFF_REJECTED')
    records, metadata, anomalies = store.load(strict=True)
    if anomalies or batch_id in records:
        fail('STORE_ANOMALY_OR_BATCH_ALREADY_COMMITTED')
    class FrozenStore:
        clock = staticmethod(lambda: at)
        def load(self, strict=True):
            return deepcopy(records), deepcopy(metadata), []
    batch = freeze_batch(FrozenStore(), batch_id, at, ORIGIN, None)
    if set(input_manifest['plans']) - set(batch['plan_refs']):
        fail('INPUT_PLAN_NOT_IN_FROZEN_BATCH')
    method, attachments = method_material(at)
    disclosure = _disclosure(attachments)
    common = {'schema_version': '1.0', 'created_at': at, 'available_at': at,
              'synthetic': False, 'disclosure': disclosure}
    bundle_id = 'bundle-' + batch_id
    method_ref = 'bundle:' + bundle_id + '/attachments/METHOD.json'
    evaluator = VERSION + '@sha256:' + method['method_code_sha256']
    output = []
    _ancestor_public_policy(store, records, metadata, batch['plan_refs'] + [i['previous_review_ref'] for i in batch['items'] if i['previous_review_ref']], context)
    for item in batch['items']:
        ref = item['plan_ref']; plan = records[ref]; previous = records.get(item['previous_review_ref'])
        suffix = digest(ref.encode())[:16]
        rid, fid = 'review-' + batch_id + '-' + suffix, 'feedback-' + batch_id + '-' + suffix
        cutoff = market_event_cutoff or (min(now, utc(plan['evaluation_end'])).isoformat() if PLAN_HASHES.get(ref) == item['plan_hash'] else at)
        stage, reasons, summary, migration = 'RULES_INCOMPLETE', ['UNSUPPORTED_OR_MODIFIED_PLAN'], None, None
        metrics = {key: None for key in waiting.METRICS}
        results = {'metric_scope': 'FROZEN_RULE_COUNTERFACTUAL_NOT_ACCOUNT_EXECUTION'}
        coverage = {'source_coverage': 'UNKNOWN', 'result_is_evaluable': False, 'actually_evaluated_market_cutoff': None}
        fingerprint, correction_public, complete = sha(input_manifest['plans'].get(ref, {})), None, False
        reused_from, evaluation_at = None, at
        if PLAN_HASHES.get(ref) == item['plan_hash']:
            try:
                _check_time(context)
                if utc(cutoff) > utc(plan['evaluation_end']):
                    fail('MARKET_CUTOFF_AFTER_ORIGINAL_ENDPOINT')
                _visible(ref, records, metadata, at)
                if item['previous_review_ref'] != _latest_review_ref(records, metadata, ref, at):
                    fail('LATEST_FORMAL_PREDECESSOR_SKIPPED')
                config = input_manifest['plans'].get(ref, {'sources': [], 'correction': None})
                if not isinstance(config, dict) or set(config) != {'sources', 'correction'}:
                    fail('PLAN_INPUT_FIELDS_REJECTED')
                prior, old_private, migration = _previous(store, previous, plan, records, metadata, method, context)
                resolved = _resolved(context, store, plan, config['sources'], records, metadata, at, cutoff)
                payload, correction = resolved.payload, config['correction']
                fingerprint = sha(payload)
                if prior and (utc(cutoff) < utc(prior['market_event_cutoff']) or utc(at) < utc(prior['information_as_of'])):
                    fail('CONTINUATION_CUTOFF_MOVED_BACKWARDS')
                if correction is not None:
                    correction_public = _formal_correction(correction, previous, prior, old_private, resolved)
                elif prior:
                    if old_private and old_private.get('schema_version') == PRIVATE_VERSION and _fact_state(private=old_private) != _fact_state(resolved=resolved):
                        fail('EXPLICIT_FACT_CORRECTION_REQUIRED')
                    diff = _event_diff(prior['input_payload'], payload)
                    late = any(e['event_id'] in diff['added'] and utc(e['event_at']) <= utc(prior['market_event_cutoff']) for e in payload['events'])
                    if diff['changed'] or diff['removed'] or late:
                        fail('EXPLICIT_CORRECTION_REQUIRED')
                # Revalidate exact latest FINAL and registered bytes first. No
                # caller fingerprint or newly stamped economic review can reuse it.
                if (previous['evaluation_stage'] == 'FINAL' and correction is None
                        and previous['evaluator_version'] == evaluator and old_private
                        and fingerprint == previous['input_fingerprint'] and cutoff == previous['data_cutoff']
                        and old_private['requests'] == config['sources']
                        and old_private['source_bindings'] == resolved.bindings
                        and old_private['formal_result']['capabilities'] == sorted(resolved.capabilities)
                        and old_private.get('cost_allocation') == resolved.actual_costs):
                    reused_from = previous['review_id']
                    result = deepcopy(old_private['formal_result'])
                else:
                    result = _compute(plan, resolved, None if correction else prior)
                evaluation_at = result['information_as_of']
                private = {'schema_version': PRIVATE_VERSION, 'plan_hash': item['plan_hash'],
                    'method_code_sha256': method['method_code_sha256'], 'information_as_of': at,
                    'market_event_cutoff': cutoff, 'requests': deepcopy(config['sources']),
                    'source_bindings': resolved.bindings, 'decode_audits': resolved.audits,
                    'cost_allocation': deepcopy(resolved.actual_costs),
                    'kernel_result': result['kernel_result'], 'formal_result': result,
                    'reused_from': reused_from,
                    'reuse_parent_kernel_state_sha256': sha(prior['simulation_state']) if reused_from else None,
                    'reuse_parent_private_sha256': sha(old_private) if reused_from else None,
                    'correction': deepcopy(correction)}
                raw = canonical(private)
                if len(raw) > MAX_PRIVATE_BYTES:
                    fail('PRIVATE_COMPUTATION_SIZE_LIMIT')
                attachments['PRIVATE/' + rid + '.json'] = raw.decode()
                summary = _summary(plan, result, digest(raw))
                stage, complete = result['evaluation_stage'], result['data_complete']
                metrics, results = _public_result(result, reused_from)
                coverage = _coverage(plan, result, resolved)
                reasons = coverage['reason_codes']
            except Exception as exc:
                stage = 'TECHNICAL_FAILURE'
                reasons = [str(exc) if isinstance(exc, Rejected) else 'FORMAL_INPUT_OR_STATE_REJECTED']
                summary, correction_public, complete = None, None, False
                reused_from, evaluation_at = None, at
                metrics = {key: None for key in waiting.METRICS}
                results = {'metric_scope': 'FROZEN_RULE_COUNTERFACTUAL_NOT_ACCOUNT_EXECUTION'}
                coverage = {'source_coverage': 'UNKNOWN', 'result_is_evaluable': False, 'actually_evaluated_market_cutoff': None}
                attachments.pop('PRIVATE/' + rid + '.json', None)
                cutoff = previous['data_cutoff'] if previous else plan['available_at']
        elif previous and utc(cutoff) < utc(previous['data_cutoff']):
            cutoff = previous['data_cutoff']
        coverage.update(information_as_of=at, reason_codes=reasons)
        provenance = {'trigger_origin': ORIGIN, 'natural_trigger': False, 'native_task_ref': None,
            'method_available_at': at, 'method_code_sha256': method['method_code_sha256'],
            'evaluation_information_as_of': evaluation_at, 'state_migration': migration,
            'prior_state_preserved_in': item['previous_review_ref'], 'correction_summary': correction_public}
        review = dict(common, record_type='review', review_id=rid, plan_ref=ref, plan_hash=item['plan_hash'],
            batch_ref=batch_id, revision=previous['revision'] + 1 if previous else 1,
            previous_review_ref=item['previous_review_ref'], opening_state_hash=item['opening_state_hash'],
            review_method_ref=method_ref, evaluator_version=evaluator, data_cutoff=cutoff,
            data_complete=complete, evaluation_stage=stage, simulation_state=summary,
            disposition='REUSED_FINAL' if reused_from else stage, input_record_refs=[reused_from] if reused_from else [],
            metrics=metrics, results=results, coverage=coverage, provenance=provenance,
            evidence_refs=[method_ref], feedback_refs=[fid], input_fingerprint=fingerprint,
            summary='按封存规则逐指标复算；模拟与实际成本分开，缺项不补零。',
            limitations=['Counterfactual simulation is not an account fill or trading authority.',
                         'No NOT_TRIGGERED branch is defined for these two already-triggered frozen plans.'])
        if correction_public:
            review.update(supersedes=previous['review_id'], correction_reason='EXPLICIT_INPUT_REVISION_SEE_PRIVATE_AUDIT')
        feedback = dict(common, record_type='feedback', feedback_id=fid, review_ref=rid,
            status='AVAILABLE_FOR_RESEARCH_NOT_YET_ADOPTED', supported_facts=[stage] + reasons,
            interpretation='仅支持有证据资格的分项模拟指标；假设成本不代表实际费用。',
            proposed_question='依据明确缺项补充合法证据，保留原规则与已有状态链。',
            what_changes='复核方法与信息时点；旧原件不变。', provenance=provenance)
        output.extend([review, feedback])
        item.update(disposition='REUSED_FINAL' if reused_from else stage, review_ref=rid, result_is_evaluable=coverage['result_is_evaluable'], reason_codes=reasons)
    batch.update(common, summary='全部登记方案逐项处置；新计算与已核验最终复用分别计数。')
    batch['coverage'] = _batch_coverage(batch, output, records)
    batch['complete'] = True
    batch['input_record_refs'] = [r['review_id'] for r in output if r['record_type'] == 'review']
    _check_time(context)
    output.insert(0, batch)
    for record in output:
        validate_record(record, 'review'); public_record(record)
    validate_relationships(dict(records, **{record_ref(r): r for r in output}))
    for name in disclosure['public_attachments']:
        scan_bytes(name, attachments[name[len('attachments/'):]].encode())
    request_hash = sha({'batch_id': batch_id, 'input_manifest': input_manifest, 'market_event_cutoff': market_event_cutoff})
    bundle = {'bundle_id': bundle_id, 'role': 'review', 'request_key': VERSION + ':' + batch_id,
        'records': output, 'attachments': attachments,
        'preparation': {'prepared_at': at, 'method_code_sha256': method['method_code_sha256'],
            'request_fingerprint': request_hash, 'state': 'OUTBOX_PREPARED_NOT_COMMITTED',
            'source_capability_validators': 'DECODE_ONLY_NO_BUSINESS_CAPABILITIES', 'natural_trigger': False}}
    bundle['preparation']['content_sha256'] = sha(bundle)
    return bundle


def correction_proposal(store, plan_ref, sources, market_event_cutoff, reason):
    at = store.clock()
    records, metadata, anomalies = store.load(strict=True)
    if anomalies or plan_ref not in PLAN_HASHES:
        fail('CORRECTION_PLAN_OR_STORE_INVALID')
    plan = _visible(plan_ref, records, metadata, at)
    previous = records[_latest_review_ref(records, metadata, plan_ref, at)]
    method, _ = method_material(at); context = _context()
    prior, old_private, _ = _previous(store, previous, plan, records, metadata, method, context)
    resolved = _resolved(context, store, plan, sources, records, metadata, at, market_event_cutoff)
    payload = resolved.payload
    correction = {'previous_review_ref': previous['review_id'],
        'old_input_fingerprint': sha(prior['input_payload']) if prior else None,
        'new_input_fingerprint': sha(payload), 'event_diff': _event_diff(prior['input_payload'], payload) if prior else {},
        'reason': reason}
    if old_private and old_private.get('schema_version') == PRIVATE_VERSION:
        old, new = _fact_state(private=old_private), _fact_state(resolved=resolved)
        correction.update(old_fact_fingerprint=sha(old), new_fact_fingerprint=sha(new),
            fact_diff={key: {'old_sha256': sha(old[key]), 'new_sha256': sha(new[key])} for key in old if old[key] != new[key]})
    _formal_correction(correction, previous, prior, old_private, resolved)
    return correction


def prepare_outbox(store, batch_id, input_manifest, relative, market_event_cutoff=None):
    """One immutable preparation per batch; retries return its retained original."""
    safe_id(batch_id)
    retained = under(store.code_root, '.local/review-outbox/.prepared-batches/' + digest(batch_id.encode()) + '.json')
    request_hash = sha({'batch_id': batch_id, 'input_manifest': input_manifest, 'market_event_cutoff': market_event_cutoff})
    if retained.exists():
        saved = read_json(retained)
        content_hash = saved['preparation'].pop('content_sha256')
        method, _ = method_material(saved['preparation']['prepared_at'])
        if (sha(saved) != content_hash or saved['preparation']['request_fingerprint'] != request_hash
                or saved['preparation']['method_code_sha256'] != method['method_code_sha256']):
            fail('PREPARED_BATCH_INPUT_METHOD_OR_CONTENT_CHANGED')
        prepared_at = saved['preparation']['prepared_at']
        if utc(prepared_at) > utc(store.clock()) or saved.get('bundle_id') != 'bundle-' + batch_id:
            fail('RECOVERY_TIME_OR_IDENTITY_INVALID')
        records, metadata, anomalies = store.load(strict=True)
        if anomalies:
            fail('STORE_ANOMALY_DURING_PREPARATION_RECOVERY')
        committed_refs = {ref for ref in records if metadata[ref]['bundle_id'] == saved['bundle_id']}
        if committed_refs:
            manifest = read_json(under(store.root / 'bundles' / saved['bundle_id'], 'manifest.json'))
            expected_files = {'records/' + record['record_type'] + '/' + record_ref(record) + '.json': canonical(record)
                              for record in saved['records']}
            expected_files.update({'attachments/' + name: content.encode() for name, content in saved['attachments'].items()})
            actual_files = {entry['path']: (entry['sha256'], entry['bytes']) for entry in manifest['files']}
            if (committed_refs != {record_ref(record) for record in saved['records']}
                    or manifest['producer_role'] != saved['role'] or manifest['request_key'] != saved['request_key']
                    or actual_files != {name: (digest(raw), len(raw)) for name, raw in expected_files.items()}):
                fail('PREPARED_BATCH_DIFFERS_FROM_COMMITTED_ORIGINAL')
        visible = {ref: record for ref, record in records.items()
                   if metadata[ref]['bundle_id'] != saved['bundle_id']
                   and utc(metadata[ref]['committed_at']) <= utc(prepared_at)
                   and utc(record['available_at']) <= utc(prepared_at)}
        class RecoverySnapshot:
            clock = staticmethod(lambda: prepared_at)
            def load(self, strict=True):
                return deepcopy(visible), {ref: deepcopy(metadata[ref]) for ref in visible}, []
            def __getattr__(self, name):
                return getattr(store, name)
        expected = prepare_bundle(RecoverySnapshot(), batch_id, input_manifest, market_event_cutoff)
        saved['preparation']['content_sha256'] = content_hash
        if canonical(saved) != canonical(expected):
            fail('RECOVERED_BUNDLE_SEMANTICS_DIFFER_FROM_FROZEN_REQUEST')
        return retained
    bundle = prepare_bundle(store, batch_id, input_manifest, market_event_cutoff)
    return waiting.write_outbox(store.code_root, relative, bundle)
