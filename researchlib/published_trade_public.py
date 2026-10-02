"""Fixed public admission for the new v2 method; no old policy is widened.

This validates authored originals before controlled submission. It grants no
source, execution, economic or natural-run authority. All source/ledger/group
objects stay in PRIVATE attachments. Public-only validation is forced by the reviewed fixed export, inspect,
restore and publisher entrypoints. It grants no private source authority.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal

from .common import ContractError, canonical, digest, safe_id, safe_relative, utc
from .contracts import record_ref, semantic_refs, validate_record, validate_relationships
from .public import attachment_allowed, public_record, scan_bytes

PROFILE = 'PUBLISHED_TRADE_COUNTERFACTUAL_PUBLIC_V2'
METHOD_REF = 'm-btc-published-trade-sliced-counterfactual@2'
VERSION = 'btc-published-trade-sliced-counterfactual-v2'
START, ENTRY_END, END = '2026-10-03T00:05:00Z', '2026-10-03T00:06:00Z', '2026-10-03T00:11:00Z'
COMPLETE = ('FLOW_SCENARIO_COMPLETE', 'DEVELOPMENT_EXPOSED_SCENARIO_COMPLETE')
STATUSES = COMPLETE + ('WAITING_SOURCE_REVIEW', 'WAITING_NATURAL_OUTCOME', 'WAITING_PARENT_RESULT', 'DATA_REQUIRED')
HASH = {'kind': 'hash'}
REF = {'kind': 'ref'}
TEXT = {'kind': 'text', 'maximum': 4096}
TIME = {'kind': 'time'}
DECIMAL = {'kind': 'decimal'}


def const(value):
    return {'const': value}


def enum(*values):
    return {'enum': list(values)}


def nullable(spec):
    return {'nullable': spec}


def array(spec, maximum=10000):
    return {'array': spec, 'maximum': maximum}


def obj(fields, optional=()):
    return {'object': fields, 'optional': list(optional)}


REFS = array(REF)
PROVENANCE = obj({
    'public_profile': const(PROFILE), 'method_ref': const(METHOD_REF),
    'method_source_identity': HASH, 'design_sha256': HASH, 'source_policy_sha256': HASH,
    'source_authority_sha256': nullable(HASH),
    'trigger_origin': enum('UNKNOWN', 'OFFICIAL_APP_HELPER_NOT_NATIVE_ATTESTATION'),
    'natural_origin': const('UNKNOWN'), 'native_task_ref': nullable(REF),
})
DISCLOSURE = obj({'visibility': const('PUBLIC'), 'license': const('OWN_ANALYSIS'),
    'public_attachments': array({'kind': 'summary_path'}, 1)})
WINDOW = obj({'start_inclusive': const(START), 'end_exclusive': const(END)})
DECLARATION = obj({
    'trade_filename': const('BTC-USDT-SWAP-trades-2026-10-03.zip'),
    'funding_filename': const('allswap-fundingrates-2026-10-03.zip'),
    'trade_role': const('TARGET_TRADE_HISTORY'), 'funding_role': const('SETTLEMENT_CASHFLOW'),
    'partition': obj({'date': const('2026-10-03'), 'timezone': const('UTC+08:00')}),
    'source_policy_sha256': HASH, 'future_raw_hashes': const(None),
})
SCENARIO_KEYS = (
    'gross_price_pnl', 'entry_fees', 'exit_fees', 'entry_slippage', 'exit_slippage',
    'funding_cashflow', 'scenario_net', 'terminal_cash', 'terminal_inventory',
    'baseline_difference', 'observed_trade_valuation_drawdown_lower',
    'observed_trade_valuation_drawdown_upper',
)
SCENARIOS = obj({name: obj({key: DECIMAL for key in SCENARIO_KEYS})
    for name in ('base', 'pressure-5', 'pressure-10')})
SUMMARY = obj({
    'schema_version': const(1), 'status': enum(*STATUSES), 'plan_ref': REF, 'plan_hash': HASH,
    'source_identity': HASH, 'actual_net': const(None), 'actual_inventory': const(None),
    'scenarios': nullable(SCENARIOS), 'economic_final': const(False),
    'sample_count': nullable(const(1)), 'planned_window_count': const(1), 'natural_origin': const('UNKNOWN'),
    'reason_code': nullable({'kind': 'reason_code'}),
    'valuation_scope': const('PUBLISHED_OBSERVATION_SET_ABSOLUTE_USDT_DD_BOUNDS'),
    'full_paths_and_sources': const('PRIVATE_EXCLUDED'),
})
PARAMETERS = obj({
    'initial_virtual_capital_usdt': const('10000'), 'direction': enum(-1, 1),
    'quantity_btc': const('0.01'), 'source_policy_sha256': HASH, 'design_sha256': HASH,
    'method_source_identity': HASH, 'window': WINDOW,
    'parent_plan_ref': REF, 'adoption_decision_ref': REF,
}, ('parent_plan_ref', 'adoption_decision_ref'))
COSTS = const([
    {'id': 'base', 'fee_bp_per_leg': '5', 'slippage_bp_per_leg': '2'},
    {'id': 'pressure-5', 'fee_bp_per_leg': '5', 'slippage_bp_per_leg': '5'},
    {'id': 'pressure-10', 'fee_bp_per_leg': '5', 'slippage_bp_per_leg': '10'},
])
RULES = obj({key: TEXT for key in ('signal', 'entry', 'quantity_or_inventory', 'exit', 'reentry', 'termination')})
VALUATION = obj({key: TEXT for key in ('drawdown_bounds', 'end', 'post_fill_points', 'valuation')})
BATCH_ITEM = obj({
    'plan_ref': REF, 'plan_hash': HASH,
    'disposition': enum(*STATUSES, 'REVIEW_REQUIRED', 'RULES_INCOMPLETE', 'WAITING_DATA',
        'REUSE_FINAL_UNLESS_INPUT_OR_EVALUATOR_CHANGED', 'UNSUPPORTED_METHOD_DISPOSITION_ONLY',
        'FIXED_PLAN_VALIDATION_FAILED_DISPOSITION_ONLY',
        'DEVELOPMENT_RESEARCH_RESULT_DISPOSITION_ONLY', 'DEVELOPMENT_RESEARCH_REQUIRED_DISPOSITION_ONLY',
        'KNOWN_CAPACITY_BLOCKER_NOT_REPLAYED', 'OLD_CHAIN_CHANGED_NO_REPLAY_BY_THIS_METHOD'),
    'previous_review_ref': nullable(REF), 'opening_state_hash': nullable(HASH),
    'previous_input_fingerprint': nullable(HASH), 'previous_evaluator_version': nullable({'kind': 'version'}),
    'product_refs': array(REF, 20), 'failure_ref': REF, 'failure_sha256': HASH,
    'preserved_revision4_ref': REF, 'preserved_revision4_sha256': HASH,
    'old_evaluator_executed': const(False),
}, ('failure_ref', 'failure_sha256', 'preserved_revision4_ref', 'preserved_revision4_sha256', 'old_evaluator_executed'))
COVERAGE = obj({'registered': {'kind': 'integer', 'minimum': 0}, 'reviewed': {'kind': 'integer', 'minimum': 0},
    'missing': REFS, 'coverage_complete': {'kind': 'bool'},
    'review_refs': {'mapping': array(REF), 'key': REF},
    'scenario_completed_plans': {'kind': 'integer', 'minimum': 0}})
COMMON = {
    'schema_version': const('1.0'), 'record_type': None,
    'created_at': TIME, 'available_at': TIME, 'synthetic': const(False),
    'provenance': PROVENANCE, 'disclosure': DISCLOSURE,
}


def schema(kind, fields, optional=()):
    return obj(dict(COMMON, record_type=const(kind), **fields), optional)


SCHEMAS = {
    'run': schema('run', {
        'run_id': REF, 'attempt_id': const('v1'), 'request_key': REF, 'round_id': REF, 'plan_ref': REF,
        'started_at': TIME, 'completed_at': TIME,
        'stage': enum('DEVELOPMENT_EXPOSED_SCENARIO_COMPLETE', 'WAITING_PARENT_RESULT', 'DATA_REQUIRED', 'WAITING_SOURCE_REVIEW'),
        'code_ref': {'kind': 'text', 'maximum': 256}, 'dataset_refs': const([]),
        'metrics': obj({'actual_net': const(None), 'actual_inventory': const(None)}), 'results': SUMMARY,
        'receipt': obj({'private_result_sha256': HASH, 'sample_role': const('DEVELOPMENT_EXPOSED'),
            'independent_market_sample': const(False), 'formal_review': const(False)}),
        'input_record_refs': REFS,
    }),
    'round': schema('round', {
        'round_id': REF, 'question': TEXT, 'mechanism': TEXT,
        'purpose_kind': enum('NEW_LIMITED_PUBLISHED_OBSERVATION_SCENARIO', 'DEVELOPMENT_EXPOSED_COUNTEREXAMPLE'),
        'selected_plan_ref': REF, 'plan_refs': REFS, 'product_refs': const(['btc']),
        'input_record_refs': REFS, 'parent_round_id': nullable(REF),
        'derived_from_feedback_refs': REFS, 'source_review_refs': REFS,
    }, ('parent_round_id', 'derived_from_feedback_refs', 'source_review_refs')),
    'plan': schema('plan', {
        'plan_id': REF, 'plan_ref': REF, 'version': const(1), 'round_id': REF,
        'instrument_ref': const('BTC-USDT-SWAP'), 'method_ref': const(METHOD_REF),
        'dataset_refs': const([]), 'input_roles': DECLARATION, 'product_refs': const(['btc']),
        'source_review_refs': REFS, 'input_record_refs': REFS,
        'rules': RULES, 'cost_model': COSTS, 'cost_model_ref': const(METHOD_REF),
        'fill_model_ref': const(METHOD_REF), 'evaluation_contract_ref': const(METHOD_REF),
        'evaluation_contract': obj({'valuation': VALUATION, 'actual_net': const(None),
            'terminal_stage': enum('FLOW_SCENARIO_COMPLETE_NOT_ECONOMIC_FINAL', 'DEVELOPMENT_EXPOSED_SCENARIO_COMPLETE'),
            'exchange_event_completeness': const('UNKNOWN')}),
        'sealed_at': TIME, 'effective_from': const(START), 'entry_valid_until': const(ENTRY_END),
        'evaluation_end': const(END), 'replay_eligibility': const('METHOD_OBSERVATION_ONLY'),
        'account_input_required': const(False),
        'sample_role': enum('FORWARD_FROZEN_SINGLE_WINDOW', 'DEVELOPMENT_EXPOSED'),
        'comparison_group': REF, 'parameters': PARAMETERS,
    }),
    'review': schema('review', {
        'review_id': REF, 'plan_ref': REF, 'plan_hash': HASH, 'batch_ref': REF,
        'revision': {'kind': 'integer', 'minimum': 1}, 'review_method_ref': const(METHOD_REF),
        'evaluator_version': {'kind': 'evaluator_version'}, 'dataset_refs': const([]),
        'evaluation_stage': enum(*STATUSES), 'disposition': enum(*STATUSES),
        'simulation_state': obj({'schema_version': const('published-trade-counterfactual-state-v2'),
            'state': enum(*STATUSES), 'plan_hash': HASH, 'actual_net': const(None),
            'actual_inventory': const(None), 'private_result_sha256': HASH}),
        'metrics': obj({'actual_net': const(None), 'actual_inventory': const(None)}),
        'feedback_refs': REFS, 'data_cutoff': TIME,
        'previous_review_ref': nullable(REF), 'opening_state_hash': nullable(HASH),
        'data_complete': {'kind': 'bool'}, 'results': SUMMARY, 'input_fingerprint': HASH,
    }),
    'feedback': schema('feedback', {
        'feedback_id': REF, 'review_ref': REF,
        'supported_facts': obj({'actual_net': const(None), 'economic_final': const(False),
            'scenario_status': enum(*STATUSES),
            'sample_role': enum('ONE_FIXED_MARKET_WINDOW', 'DEVELOPMENT_EXPOSED'),
            'independent_market_sample': const(False)}),
        'interpretation': enum('COMPLETE_FIXED_SCENARIOS_NO_ACCOUNT_CLAIM', 'WAIT_FOR_EXACT_QUALIFIED_INPUTS'),
        'proposed_question': TEXT, 'what_changes': const('FIXED_MATCHED_QUANTITY_REVERSE_EXPOSURE_V1'),
        'comparison': obj({'market_sample_count': nullable(const(1)), 'aggregate_account_profit': const(False)}),
        'required_data': array(enum('EXACT_INDEPENDENT_SOURCE_REVIEW', 'PARENT_QUALIFIED_SCENARIOS',
            'REAL_FEEDBACK_ADOPTION_DECISION'), 3), 'adoption_decision_refs': REFS,
        'summary': TEXT,
    }),
    'decision': schema('decision', {
        'decision_id': REF, 'feedback_ref': REF, 'source_review_ref': REF,
        'successor_round_id': nullable(REF),
        'decision': enum('ADOPT_FIXED_REVERSE_EXPOSURE_TEST', 'WAIT_QUALIFIED_PARENT_SCENARIOS'),
        'reason': TEXT, 'adopted_changes': obj({'test': const('FIXED_MATCHED_QUANTITY_REVERSE_EXPOSURE_V1'),
            'parent_plan_ref': REF, 'sample_role': const('DEVELOPMENT_EXPOSED'),
            'independent_market_sample': const(False), 'actual_net': const(None)}),
        'read_input_refs': REFS, 'input_record_refs': REFS,
    }),
    'review_batch': schema('review_batch', {
        'batch_id': REF, 'frozen_at': TIME, 'cutoff': TIME, 'plan_refs': REFS,
        'items': array(BATCH_ITEM), 'complete': {'kind': 'bool'}, 'coverage': COVERAGE,
        'trigger_origin': enum('UNKNOWN', 'OFFICIAL_APP_HELPER_NOT_NATIVE_ATTESTATION'),
        'native_task_ref': nullable(REF), 'input_record_refs': REFS,
    }),
}


def _fail(path, reason):
    raise ContractError('NEW_PUBLIC_PROFILE:' + path + ':' + reason)


def _check(value, spec, path):
    if 'nullable' in spec:
        if value is not None:
            _check(value, spec['nullable'], path)
        return
    if 'const' in spec:
        # Canonical equality distinguishes 0/False and 1/True at every depth.
        if canonical(value) != canonical(spec['const']):
            _fail(path, 'FIXED_VALUE_OR_TYPE')
        return
    if 'enum' in spec:
        if not any(canonical(value) == canonical(item) for item in spec['enum']):
            _fail(path, 'ENUM_OR_TYPE')
        return
    if 'object' in spec:
        fields, optional = spec['object'], set(spec['optional'])
        if not isinstance(value, dict) or set(value) - set(fields) or (set(fields) - optional) - set(value):
            _fail(path, 'EXACT_OBJECT_KEYS')
        for key, child in value.items():
            _check(child, fields[key], path + '.' + key)
        return
    if 'array' in spec:
        if not isinstance(value, list) or len(value) > spec['maximum']:
            _fail(path, 'BOUNDED_LIST')
        for i, child in enumerate(value):
            _check(child, spec['array'], path + '[' + str(i) + ']')
        return
    if 'mapping' in spec:
        if not isinstance(value, dict) or len(value) > 10000:
            _fail(path, 'BOUNDED_MAPPING')
        for key, child in value.items():
            _check(key, spec['key'], path + '.key')
            _check(child, spec['mapping'], path + '.' + key)
        return
    kind = spec['kind']
    if kind == 'integer':
        if type(value) is not int or not spec['minimum'] <= value <= 10000000:
            _fail(path, 'BOUNDED_INTEGER')
    elif kind == 'bool':
        if type(value) is not bool:
            _fail(path, 'BOOLEAN')
    else:
        if not isinstance(value, str) or not value:
            _fail(path, 'NONEMPTY_STRING')
        if kind == 'hash' and not re.fullmatch('[0-9a-f]{64}', value):
            _fail(path, 'SHA256')
        if kind == 'ref':
            safe_id(value)
            if len(value) > 200 or 'PRIVATE' in value or 'bundle:' in value:
                _fail(path, 'PUBLIC_RECORD_REFERENCE')
        elif kind == 'time':
            utc(value)
        elif kind == 'text' and len(value) > spec['maximum']:
            _fail(path, 'BOUNDED_TEXT')
        elif kind == 'reason_code' and not re.fullmatch('[A-Z0-9_:.-]{1,256}', value):
            _fail(path, 'REASON_CODE_NO_RAW_DETAILS')
        elif kind == 'summary_path' and not re.fullmatch('attachments/SUMMARY/[0-9a-f]{16}\\.json', value):
            _fail(path, 'FIXED_SUMMARY_ATTACHMENT')
        elif kind == 'evaluator_version' and not re.fullmatch(re.escape(VERSION) + '@sha256:[0-9a-f]{64}', value):
            _fail(path, 'FIXED_EVALUATOR_VERSION')
        elif kind == 'version' and (len(value) > 200 or not re.fullmatch('[A-Za-z0-9_.:@+/-]+', value)):
            _fail(path, 'VERSION_NO_RAW_DETAILS')
        elif kind == 'decimal':
            if len(value) > 128 or not re.fullmatch('-?(?:0|[1-9][0-9]*)(?:\\.[0-9]+)?', value) or not Decimal(value).is_finite():
                _fail(path, 'FINITE_DECIMAL_STRING')


def provenance(source_identity, design_sha256, source_policy_sha256, source_authority_sha256=None,
               trigger_origin='UNKNOWN', native_task_ref=None):
    result = dict(public_profile=PROFILE, method_ref=METHOD_REF, method_source_identity=source_identity,
        design_sha256=design_sha256, source_policy_sha256=source_policy_sha256,
        source_authority_sha256=source_authority_sha256, trigger_origin=trigger_origin,
        natural_origin='UNKNOWN', native_task_ref=native_task_ref)
    _check(result, PROVENANCE, 'provenance')
    return result


def public_summary(result, plan_ref, plan_hash, source_identity):
    """Fixed aggregate projection; reason text/raw source authority never copied."""
    if (not isinstance(result, dict) or result.get('actual_net', 'MISSING') is not None
            or result.get('actual_inventory') is not None
            or result.get('economic_final', False) is not False):
        _fail('result', 'UNKNOWN_ACTUAL_AND_NONFINAL_REQUIRED')
    status = result.get('status')
    complete = status in COMPLETE
    scenarios = None
    if complete:
        source = result.get('scenarios')
        if not isinstance(source, dict) or set(source) != {'base', 'pressure-5', 'pressure-10'}:
            _fail('result', 'THREE_FIXED_SCENARIOS_REQUIRED')
        scenarios = {name: {key: source[name][key] for key in SCENARIO_KEYS} for name in source}
    reason = result.get('reason')
    # Unknown or raw exception details are excluded, not converted to permission.
    reason_code = reason if isinstance(reason, str) and re.fullmatch('[A-Z0-9_:.-]{1,256}', reason) else None
    summary = dict(schema_version=1, status=status, plan_ref=plan_ref, plan_hash=plan_hash,
        source_identity=source_identity, actual_net=None, actual_inventory=None, scenarios=scenarios,
        economic_final=False, sample_count=1 if complete else None, planned_window_count=1, natural_origin='UNKNOWN', reason_code=reason_code,
        valuation_scope='PUBLISHED_OBSERVATION_SET_ABSOLUTE_USDT_DD_BOUNDS', full_paths_and_sources='PRIVATE_EXCLUDED')
    validate_summary(summary)
    return summary


def validate_summary(summary):
    _check(summary, SUMMARY, 'summary')
    complete = summary['status'] in COMPLETE
    if (summary['scenarios'] is not None) != complete or summary['sample_count'] != (1 if complete else None):
        _fail('summary', 'STATUS_AND_SCENARIOS_OR_SAMPLE_COUNT')
    if complete:
        for name, metrics in summary['scenarios'].items():
            if Decimal(metrics['terminal_inventory']) != 0:
                _fail(name, 'TERMINAL_INVENTORY_NOT_ZERO')
            for key in ('entry_fees', 'exit_fees', 'entry_slippage', 'exit_slippage',
                        'observed_trade_valuation_drawdown_lower', 'observed_trade_valuation_drawdown_upper'):
                if Decimal(metrics[key]) < 0:
                    _fail(name, 'NEGATIVE_COST_OR_DRAWDOWN')
            if Decimal(metrics['observed_trade_valuation_drawdown_lower']) > Decimal(metrics['observed_trade_valuation_drawdown_upper']):
                _fail(name, 'DRAWDOWN_BOUNDS_REVERSED')
    scan_bytes('summary.json', canonical(summary))
    return summary


def validate_public_record(record, role):
    kind = record.get('record_type') if isinstance(record, dict) else None
    if kind not in SCHEMAS:
        _fail('record', 'FIXED_RECORD_TYPE_REQUIRED')
    _check(record, SCHEMAS[kind], kind)
    ref = validate_record(record, role)
    if canonical(public_record(record)) != canonical(record):
        _fail(ref, 'OLD_PUBLIC_POLICY_MUST_PRESERVE_ALL_ORIGINAL_FIELDS')
    prov = record['provenance']
    if kind == 'plan':
        params = record['parameters']
        for field in ('method_source_identity', 'design_sha256', 'source_policy_sha256'):
            if params[field] != prov[field]:
                _fail(ref, 'PLAN_PROVENANCE_BINDING')
        if record['input_roles']['source_policy_sha256'] != prov['source_policy_sha256']:
            _fail(ref, 'DECLARATION_POLICY_BINDING')
        successor = record['sample_role'] == 'DEVELOPMENT_EXPOSED'
        if params['direction'] != (-1 if successor else 1):
            _fail(ref, 'DIRECTION_AND_SAMPLE_ROLE')
        expected_terminal = 'DEVELOPMENT_EXPOSED_SCENARIO_COMPLETE' if successor else 'FLOW_SCENARIO_COMPLETE_NOT_ECONOMIC_FINAL'
        if record['evaluation_contract']['terminal_stage'] != expected_terminal:
            _fail(ref, 'TERMINAL_STAGE_AND_SAMPLE_ROLE')
        if successor != ('parent_plan_ref' in params and 'adoption_decision_ref' in params):
            _fail(ref, 'SUCCESSOR_REQUIRES_EXACT_PUBLIC_ADOPTION')
        for field in ('parent_plan_ref', 'adoption_decision_ref'):
            if field in params and params[field] not in record['input_record_refs']:
                _fail(ref, 'NESTED_REFERENCE_NOT_IN_ARCHIVE_CLOSURE')
    if kind == 'run':
        summary = record['results']
        validate_summary(summary)
        if (summary['plan_ref'], summary['source_identity'], summary['status']) != (record['plan_ref'], prov['method_source_identity'], record['stage']):
            _fail(ref, 'RUN_SUMMARY_BINDING')
        if record['completed_at'] != record['available_at'] or utc(record['started_at']) > utc(record['completed_at']):
            _fail(ref, 'RUN_ACTUAL_CLOCK_ORDER')
        if record['code_ref'] != 'method-source-sha256:' + prov['method_source_identity'] or len(record['disclosure']['public_attachments']) != 1:
            _fail(ref, 'RUN_EXACT_METHOD_AND_SUMMARY')
        if record['stage'] == 'DEVELOPMENT_EXPOSED_SCENARIO_COMPLETE' and prov['source_authority_sha256'] is None:
            _fail(ref, 'RUN_PRIVATE_SOURCE_AUTHORITY_REQUIRED')
    elif kind == 'review':
        summary, state = record['results'], record['simulation_state']
        validate_summary(summary)
        if (summary['plan_ref'], summary['plan_hash'], summary['source_identity'], summary['status']) != (
            record['plan_ref'], record['plan_hash'], prov['method_source_identity'], record['evaluation_stage']):
            _fail(ref, 'SUMMARY_REVIEW_BINDING')
        if (state['state'], state['plan_hash'], record['disposition']) != (
            record['evaluation_stage'], record['plan_hash'], record['evaluation_stage']):
            _fail(ref, 'STATE_REVIEW_BINDING')
        if record['data_complete'] != (record['evaluation_stage'] in COMPLETE):
            _fail(ref, 'COMPLETENESS_NOT_STATUS_EQUIVALENT')
        if record['evaluator_version'] != VERSION + '@sha256:' + prov['method_source_identity']:
            _fail(ref, 'EVALUATOR_IDENTITY_BINDING')
        if record['evaluation_stage'] in COMPLETE and prov['source_authority_sha256'] is None:
            _fail(ref, 'COMPLETION_REQUIRES_PRIVATE_AUTHORITY_HASH')
        if len(record['disclosure']['public_attachments']) != 1:
            _fail(ref, 'EXACT_SUMMARY_ATTACHMENT_REQUIRED')
    elif record['disclosure']['public_attachments']:
        _fail(ref, 'ONLY_REVIEW_HAS_PUBLIC_ATTACHMENT')
    if kind == 'feedback':
        complete = record['supported_facts']['scenario_status'] in COMPLETE
        if record['comparison']['market_sample_count'] != (1 if complete else None):
            _fail(ref, 'FEEDBACK_SAMPLE_COUNT')
        expected = 'COMPLETE_FIXED_SCENARIOS_NO_ACCOUNT_CLAIM' if complete else 'WAIT_FOR_EXACT_QUALIFIED_INPUTS'
        if record['interpretation'] != expected:
            _fail(ref, 'FEEDBACK_COMPLETION_INTERPRETATION')
    scan_bytes('record.json', canonical(record))
    return ref




def _validate_batch(batch, records):
    refs = batch['plan_refs']
    if refs != sorted(set(refs)) or len(batch['items']) != len(refs) or [x['plan_ref'] for x in batch['items']] != refs:
        _fail(batch['batch_id'], 'ALL_PLAN_FREEZE_MEMBERSHIP')
    for item in batch['items']:
        plan = records[item['plan_ref']]
        if plan.get('record_type') != 'plan' or item['plan_hash'] != digest(canonical(plan)):
            _fail(batch['batch_id'], 'FROZEN_PLAN_HASH')
        for field in ('previous_review_ref', 'failure_ref', 'preserved_revision4_ref'):
            target = item.get(field)
            if target and target not in batch['input_record_refs']:
                _fail(batch['batch_id'], 'BATCH_ITEM_REF_NOT_IN_ARCHIVE_CLOSURE')
        old_dispositions = ('KNOWN_CAPACITY_BLOCKER_NOT_REPLAYED', 'OLD_CHAIN_CHANGED_NO_REPLAY_BY_THIS_METHOD')
        old_fields = ('failure_ref', 'failure_sha256', 'preserved_revision4_ref', 'preserved_revision4_sha256', 'old_evaluator_executed')
        if item['disposition'] not in old_dispositions and any(field in item for field in old_fields):
            _fail(batch['batch_id'], 'OLD_PRESERVATION_ANNOTATIONS_REQUIRE_DECLARED_DISPOSITION')
        previous_ref = item.get('previous_review_ref')
        if previous_ref:
            previous = records.get(previous_ref)
            if (not isinstance(previous, dict) or previous.get('record_type') != 'review'
                    or previous.get('plan_ref') != item['plan_ref']
                    or previous.get('plan_hash') != digest(canonical(plan))):
                _fail(batch['batch_id'], 'PREVIOUS_REVIEW_EXACT_PLAN_IDENTITY')
            if item['opening_state_hash'] is not None and item['opening_state_hash'] != digest(canonical(previous.get('simulation_state'))):
                _fail(batch['batch_id'], 'PREVIOUS_REVIEW_EXACT_OPENING_STATE')
        if item['disposition'] in old_dispositions:
            if item.get('old_evaluator_executed') is not False or not item.get('failure_ref') or not item.get('preserved_revision4_ref'):
                _fail(batch['batch_id'], 'OLD_FAILURE_CHAIN_NOT_PRESERVED')
            failure, old_review = records.get(item['failure_ref']), records.get(item['preserved_revision4_ref'])
            if (not isinstance(failure, dict) or failure.get('record_type') != 'evidence'
                    or failure.get('results', {}).get('reason_code') != 'COMBINED_HISTORY_RESOURCE_LIMIT_EXCEEDED'
                    or not isinstance(old_review, dict) or old_review.get('record_type') != 'review'
                    or old_review.get('revision') != 4 or old_review.get('plan_ref') != item['plan_ref']
                    or old_review.get('plan_hash') != digest(canonical(plan))):
                _fail(batch['batch_id'], 'OLD_FAILURE_TARGET_KIND_PLAN_AND_REVISION')
            pairs = (('failure_sha256', failure), ('preserved_revision4_sha256', old_review))
            for field, original in pairs:
                if field in item and item[field] != digest(canonical(original)):
                    _fail(batch['batch_id'], 'OLD_PRESERVATION_HASH_MISMATCH')
                if item['disposition'] == 'KNOWN_CAPACITY_BLOCKER_NOT_REPLAYED' and field not in item:
                    _fail(batch['batch_id'], 'KNOWN_PRESERVATION_HASH_REQUIRED')
            if item['disposition'] == 'KNOWN_CAPACITY_BLOCKER_NOT_REPLAYED' and item['previous_review_ref'] != item['preserved_revision4_ref']:
                _fail(batch['batch_id'], 'KNOWN_PRESERVED_PREVIOUS_REVIEW_REQUIRED')
    actual = {}
    completed = 0
    for ref, record in records.items():
        if record['record_type'] == 'review' and record.get('batch_ref') == batch['batch_id']:
            if record['plan_ref'] not in refs:
                _fail(batch['batch_id'], 'OUT_OF_BATCH_REVIEW')
            actual.setdefault(record['plan_ref'], []).append(ref)
            completed += record.get('evaluation_stage') in COMPLETE
    coverage = batch['coverage']
    expected = dict(registered=len(refs), reviewed=len(actual), missing=sorted(set(refs) - set(actual)),
        coverage_complete=set(refs) == set(actual), review_refs=actual, scenario_completed_plans=completed)
    if canonical(coverage) != canonical(expected) or batch['complete'] != expected['coverage_complete']:
        _fail(batch['batch_id'], 'ACTUAL_REVIEW_COVERAGE_NOT_SCENARIO_COVERAGE')


def _validate_decision(decision, records):
    review = _profile_target(records, decision['source_review_ref'], 'review', decision['decision_id'])
    feedback = _profile_target(records, decision['feedback_ref'], 'feedback', decision['decision_id'])
    _validate_public_review_relation(review, records)
    if (feedback.get('review_ref') != decision['source_review_ref']
            or decision['adopted_changes']['parent_plan_ref'] != review.get('plan_ref')
            or not _same_method_provenance(review, decision)
            or not _same_method_provenance(review, feedback)):
        _fail(decision['decision_id'], 'EXACT_ADOPTION_PARENT_REFERENCES')
    complete = review.get('evaluation_stage') == 'FLOW_SCENARIO_COMPLETE'
    if decision['decision'] == 'ADOPT_FIXED_REVERSE_EXPOSURE_TEST' and not complete:
        _fail(decision['decision_id'], 'MISSING_QUALIFIED_PARENT_SCENARIOS')
    if not complete and decision['successor_round_id'] is not None:
        _fail(decision['decision_id'], 'WAIT_CANNOT_CREATE_EXECUTED_SUCCESSOR')
    if decision['adopted_changes']['parent_plan_ref'] not in decision['input_record_refs']:
        _fail(decision['decision_id'], 'DECISION_PARENT_PLAN_NOT_IN_ARCHIVE_CLOSURE')


def _validate_feedback(feedback, records):
    review = _profile_target(records, feedback['review_ref'], 'review', feedback['feedback_id'])
    if (review.get('provenance', {}).get('public_profile') != PROFILE
            or review['evaluation_stage'] != feedback['supported_facts']['scenario_status']
            or feedback['feedback_id'] not in review['feedback_refs']
            or not _same_method_provenance(review, feedback)):
        _fail(feedback['feedback_id'], 'EXACT_PARENT_REVIEW_FEEDBACK_BINDING')


def _same_method_provenance(left, right):
    fields = ('public_profile', 'method_ref', 'method_source_identity', 'design_sha256',
              'source_policy_sha256', 'source_authority_sha256')
    return all(left.get('provenance', {}).get(key) == right.get('provenance', {}).get(key) for key in fields)








def schema_document():
    """Exact machine-readable profile for independent review, not runtime policy input."""
    return dict(profile=PROFILE, method_ref=METHOD_REF, schemas=SCHEMAS, summary_schema=SUMMARY,
        private_exclusions=['source_registry', 'source_authority originals', 'ledger', 'timestamp_groups',
            'raw ZIP/CSV', 'tool/download receipts', 'sensitive full method closure'],
        old_public_policy='UNCHANGED', old_archive_policy='UNCHANGED_FOR_LEGACY_RECORDS',
        new_profile_routes=['FIXED_PUBLISH_SAME_VALIDATED_READ_SET', 'ARCHIVE_EXPORT', 'ARCHIVE_INSPECT', 'NEW_DIRECTORY_RESTORE_VIA_INSPECT'],
        author_tests='ENGINEERING_ONLY_NOT_INDEPENDENT_REVIEW')
def selected_profile_refs(records):
    """Fixed method seeds and semantic lineage edges cannot drop to old policy.

    PRIVATE approval/acquisition objects stay outside this public profile. A
    PUBLIC review of a selected plan must use the profile even if its own
    marker/evaluator/method fields were removed or changed by a forged archive.
    """
    public = {ref: r for ref, r in records.items()
        if (r.get('disclosure') or {}).get('visibility') == 'PUBLIC'}
    fixed_refs = {'p-btc-published-trade-sliced-long-20261003-v2@1',
        'p-btc-published-trade-sliced-reverse-20261003-v2@1',
        'r-btc-published-trade-sliced-20261003-v2'}
    selected = {ref for ref, r in public.items()
        if ref in fixed_refs or r.get('provenance', {}).get('public_profile') == PROFILE
        or r.get('method_ref') == METHOD_REF or r.get('review_method_ref') == METHOD_REF
        or (isinstance(r.get('evaluator_version'), str) and r['evaluator_version'].startswith(VERSION + '@'))}
    changed = True
    while changed:
        changed = False
        for ref, r in public.items():
            if ref in selected:
                continue
            kind = r.get('record_type')
            if kind == 'round':
                targets = r.get('plan_refs', []) + [r.get('selected_plan_ref'), r.get('parent_round_id')]
            elif kind == 'plan':
                params = r.get('parameters') or {}
                targets = [r.get('round_id'), params.get('parent_plan_ref'), params.get('adoption_decision_ref')]
            elif kind == 'review_batch':
                targets = r.get('plan_refs', [])
            elif kind == 'review':
                targets = [r.get('plan_ref')]
            elif kind == 'feedback':
                targets = [r.get('review_ref')]
            elif kind == 'decision':
                targets = [r.get('feedback_ref'), r.get('source_review_ref')]
            elif kind == 'run':
                targets = [r.get('plan_ref'), r.get('round_id')]
            else:
                targets = [r.get('plan_ref'), r.get('review_ref'), r.get('source_review_ref')]
            if any(target in selected for target in targets):
                selected.add(ref)
                changed = True
    return selected


def _base_method_provenance(left, right):
    fields = ('public_profile', 'method_ref', 'method_source_identity', 'design_sha256', 'source_policy_sha256')
    return all(left.get('provenance', {}).get(key) == right.get('provenance', {}).get(key) for key in fields)


def _profile_target(records, ref, kind, owner):
    target = records.get(ref)
    if (not isinstance(target, dict) or target.get('record_type') != kind
            or target.get('provenance', {}).get('public_profile') != PROFILE):
        _fail(owner, 'EXACT_PROFILE_TARGET_' + kind.upper())
    role = 'review' if kind in ('review', 'review_batch', 'feedback') else 'research'
    validate_public_record(target, role)
    return target


def _validate_public_round_relation(round_, records):
    rid = round_['round_id']
    if round_['plan_refs'] != sorted(set(round_['plan_refs'])) or round_['selected_plan_ref'] not in round_['plan_refs']:
        _fail(rid, 'ROUND_EXACT_PLAN_MEMBERSHIP')
    for ref in round_['plan_refs']:
        plan = _profile_target(records, ref, 'plan', rid)
        if plan.get('round_id') != rid or not _base_method_provenance(round_, plan):
            _fail(rid, 'ROUND_PLAN_IDENTITY_AND_PROVENANCE')
    if round_['purpose_kind'] == 'DEVELOPMENT_EXPOSED_COUNTEREXAMPLE':
        parent = _profile_target(records, round_.get('parent_round_id'), 'round', rid)
        if parent.get('purpose_kind') != 'NEW_LIMITED_PUBLISHED_OBSERVATION_SCENARIO':
            _fail(rid, 'ROUND_EXPOSED_PARENT_KIND')
        for ref in round_['plan_refs']:
            plan = records[ref]
            if plan.get('sample_role') != 'DEVELOPMENT_EXPOSED':
                _fail(rid, 'ROUND_EXPOSED_PLAN_ROLE')
            decision = _profile_target(records, plan['parameters'].get('adoption_decision_ref'), 'decision', rid)
            parent_plan = _profile_target(records, plan['parameters'].get('parent_plan_ref'), 'plan', rid)
            if (parent_plan['round_id'] != parent['round_id']
                    or round_.get('source_review_refs') != [decision['source_review_ref']]
                    or round_.get('derived_from_feedback_refs') != [decision['feedback_ref']]
                    or decision['decision_id'] not in round_['input_record_refs']):
                _fail(rid, 'ROUND_EXACT_ADOPTED_LINEAGE')
    elif round_.get('parent_round_id') or round_.get('source_review_refs') or round_.get('derived_from_feedback_refs'):
        _fail(rid, 'FORWARD_ROOT_HAS_NO_ADOPTED_PARENT')


def _validate_public_plan_relation(plan, records):
    ref = record_ref(plan)
    round_ = _profile_target(records, plan['round_id'], 'round', ref)
    if ref not in round_['plan_refs'] or not _base_method_provenance(plan, round_):
        _fail(ref, 'PLAN_EXACT_ROUND_AND_PROVENANCE')
    if plan['sample_role'] == 'DEVELOPMENT_EXPOSED':
        params = plan['parameters']
        parent = _profile_target(records, params['parent_plan_ref'], 'plan', ref)
        decision = _profile_target(records, params['adoption_decision_ref'], 'decision', ref)
        if (parent.get('sample_role') != 'FORWARD_FROZEN_SINGLE_WINDOW'
                or parent.get('parameters', {}).get('direction') != 1
                or decision.get('decision') != 'ADOPT_FIXED_REVERSE_EXPOSURE_TEST'
                or decision.get('adopted_changes', {}).get('parent_plan_ref') != params['parent_plan_ref']
                or round_.get('parent_round_id') != parent['round_id']
                or not _base_method_provenance(plan, parent)
                or not _base_method_provenance(plan, decision)
                or plan['source_review_refs'] != [decision['source_review_ref']]):
            _fail(ref, 'PLAN_EXACT_EXPOSED_ADOPTION')
        _validate_decision(decision, records)


def _validate_public_review_relation(review, records):
    ref = review['review_id']
    plan = _profile_target(records, review['plan_ref'], 'plan', ref)
    batch = _profile_target(records, review['batch_ref'], 'review_batch', ref)
    if (review['plan_hash'] != digest(canonical(plan))
            or review['plan_ref'] not in batch['plan_refs']
            or not _base_method_provenance(review, plan)
            or not _base_method_provenance(review, batch)):
        _fail(ref, 'REVIEW_EXACT_PLAN_BATCH_AND_PROVENANCE')
    cutoff = utc(review['data_cutoff'])
    if review['data_cutoff'] != batch['cutoff']:
        _fail(ref, 'REVIEW_EXACT_FROZEN_BATCH_CUTOFF')
    if not (cutoff <= utc(batch['frozen_at']) <= utc(batch['created_at']) <= utc(batch['available_at'])
            <= utc(review['created_at']) <= utc(review['available_at'])):
        _fail(ref, 'REVIEW_BATCH_ACTUAL_DECLARED_CLOCK_ORDER')
    if review['evaluation_stage'] in COMPLETE and cutoff < utc(plan['evaluation_end']):
        _fail(ref, 'COMPLETE_REVIEW_REQUIRES_MATURE_FIXED_WINDOW')
    if review['evaluation_stage'] == 'FLOW_SCENARIO_COMPLETE' and plan['sample_role'] != 'FORWARD_FROZEN_SINGLE_WINDOW':
        _fail(ref, 'REVIEW_FORWARD_COMPLETION_ROLE')
    if review['evaluation_stage'] == 'DEVELOPMENT_EXPOSED_SCENARIO_COMPLETE' and plan['sample_role'] != 'DEVELOPMENT_EXPOSED':
        _fail(ref, 'REVIEW_EXPOSED_COMPLETION_ROLE')
    for fref in review['feedback_refs']:
        feedback = _profile_target(records, fref, 'feedback', ref)
        if feedback.get('review_ref') != ref:
            _fail(ref, 'REVIEW_EXACT_FEEDBACK_RELATION')


def _validate_public_run_relation(run, records):
    ref = run['run_id']
    plan = _profile_target(records, run['plan_ref'], 'plan', ref)
    if (plan['sample_role'] != 'DEVELOPMENT_EXPOSED' or plan['parameters']['direction'] != -1
            or run['round_id'] != plan['round_id']
            or run['results']['plan_hash'] != digest(canonical(plan))
            or not _base_method_provenance(run, plan)):
        _fail(ref, 'RUN_EXACT_DEVELOPMENT_PLAN')
    _validate_public_plan_relation(plan, records)
    decision = records[plan['parameters']['adoption_decision_ref']]
    if not {decision['decision_id'], decision['source_review_ref'], decision['feedback_ref']}.issubset(run['input_record_refs']):
        _fail(ref, 'RUN_EXACT_ADOPTION_INPUTS')
    parent_review = _profile_target(records, decision['source_review_ref'], 'review', ref)
    _validate_public_review_relation(parent_review, records)
    if (parent_review['evaluation_stage'] != 'FLOW_SCENARIO_COMPLETE'
            or not utc(parent_review['data_cutoff']) <= utc(parent_review['created_at']) <= utc(parent_review['available_at'])
                <= utc(decision['created_at']) <= utc(decision['available_at'])
                <= utc(plan['created_at']) <= utc(plan['available_at']) <= utc(run['started_at'])
                <= utc(run['completed_at']) <= utc(run['created_at']) <= utc(run['available_at'])):
        _fail(ref, 'RUN_MATURE_PARENT_ADOPTION_AND_DECLARED_CLOCKS')
    if not _same_method_provenance(run, parent_review):
        _fail(ref, 'RUN_PARENT_SOURCE_AUTHORITY_BINDING')


def validate_public_archive_records(records, producer_roles, public_attachments):
    """Public-only contract; no helper, PRIVATE inputs or installed authority.

    Record/role/attachment originals have already passed archive byte checks or
    the controlled Store read. Missing markers cannot downgrade linked records.
    """
    selected = selected_profile_refs(records)
    if not selected:
        return {'checked_new_profile_refs': [], 'state': 'LEGACY_PUBLIC_PROFILE_UNCHANGED',
            'source_qualification': 'NOT_REVERIFIED_PRIVATE_INPUTS_EXCLUDED', 'scientific_reproduction': 'NOT_RUN'}
    validate_relationships(records)
    for ref in sorted(selected):
        if ref not in producer_roles:
            _fail(ref, 'ARCHIVE_PRODUCER_ROLE_MISSING')
        validate_public_record(records[ref], producer_roles[ref])
    for ref in sorted(selected):
        record = records[ref]
        kind = record['record_type']
        if kind == 'round':
            _validate_public_round_relation(record, records)
        elif kind == 'plan':
            _validate_public_plan_relation(record, records)
        elif kind == 'review_batch':
            _validate_batch(record, records)
        elif kind == 'review':
            _validate_public_review_relation(record, records)
        elif kind == 'run':
            _validate_public_run_relation(record, records)
        elif kind == 'feedback':
            _validate_feedback(record, records)
        elif kind == 'decision':
            _validate_decision(record, records)
        expected = {path: canonical(record['results']) for path in record['disclosure']['public_attachments']}
        actual = public_attachments.get(ref, {})
        if set(actual) != set(expected):
            _fail(ref, 'ARCHIVE_SUMMARY_LICENSE_OR_MISSING')
        for path, content in actual.items():
            raw = content.encode('utf-8') if isinstance(content, str) else content
            if raw != expected[path]:
                _fail(ref, 'ARCHIVE_SUMMARY_ORIGINAL_BYTES_MISMATCH')
            scan_bytes(path, raw)
    todo, seen = list(selected), set()
    while todo:
        ref = todo.pop()
        if ref in seen:
            continue
        seen.add(ref)
        if ref not in records or public_record(records[ref]) is None:
            _fail(ref, 'ARCHIVE_PUBLIC_CLOSURE_CONTAINS_PRIVATE_OR_MISSING')
        todo.extend(semantic_refs(records[ref]))
    return {'checked_new_profile_refs': sorted(selected), 'state': 'FIXED_V2_PUBLIC_PROFILE_VALIDATED',
        'source_qualification': 'NOT_REVERIFIED_PRIVATE_INPUTS_EXCLUDED', 'scientific_reproduction': 'NOT_RUN'}


def validate_public_archive_payload(records, producer_roles, files, record_entries):
    """Bind each new licensed summary to its original controlled bundle identity."""
    selected = selected_profile_refs(records)
    entries = {entry['record_ref']: entry for entry in record_entries}
    if len(entries) != len(record_entries):
        _fail('archive', 'DUPLICATE_RECORD_ENTRY')
    attachments = {}
    for ref in selected:
        record = records[ref]
        validate_public_record(record, producer_roles.get(ref))
        entry = entries.get(ref, {})
        bundle_id = entry.get('original_bundle_id')
        if not isinstance(bundle_id, str):
            _fail(ref, 'ARCHIVE_ORIGINAL_BUNDLE_ID_REQUIRED')
        safe_id(bundle_id)
        if entry.get('original_record_hash') != digest(canonical(record)):
            _fail(ref, 'ARCHIVE_EXACT_ORIGINAL_RECORD_HASH')
        attachments[ref] = {}
        for path in record['disclosure']['public_attachments']:
            if not attachment_allowed(record, path):
                _fail(ref, 'ARCHIVE_SUMMARY_NOT_LICENSED')
            name = 'evidence/' + bundle_id + '/' + path
            safe_relative(name)
            if name not in files:
                _fail(ref, 'ARCHIVE_ORIGINAL_BUNDLE_SUMMARY_MISSING')
            attachments[ref][path] = files[name]
    return validate_public_archive_records(records, producer_roles, attachments)


def validate_public_store(store, records=None, metadata=None):
    """Mandatory fixed publisher preflight before exporting any new projection."""
    from .common import under
    if records is None or metadata is None:
        records, metadata, _ = store.load(strict=True)
    selected = selected_profile_refs(records)
    attachments = {}
    roles = {ref: item['producer_role'] for ref, item in metadata.items()}
    for ref in selected:
        record = records[ref]
        validate_public_record(record, roles.get(ref))
        item = metadata.get(ref, {})
        if item.get('record_hash') != digest(canonical(record)):
            _fail(ref, 'STORE_EXACT_ORIGINAL_HASH')
        bundle_id = item.get('bundle_id')
        safe_id(bundle_id)
        directory = store.root / 'bundles' / bundle_id
        manifest, _ = store._read_bundle(directory)
        manifest_files = {entry['path']: entry for entry in manifest['files']}
        attachments[ref] = {}
        for path in record['disclosure']['public_attachments']:
            entry = manifest_files.get(path, {})
            if entry.get('kind') != 'attachment' or not attachment_allowed(record, path):
                _fail(ref, 'STORE_ORIGINAL_LICENSED_SUMMARY_REQUIRED')
            raw = under(directory, path).read_bytes()
            if digest(raw) != entry.get('sha256') or len(raw) != entry.get('bytes'):
                _fail(ref, 'STORE_ORIGINAL_SUMMARY_HASH')
            attachments[ref][path] = raw
    return validate_public_archive_records(records, roles, attachments)


class ValidatedPublicationStore:
    """Same read set for profile admission, fingerprint and fixed projection.

    Research can append concurrently. New records appear on the next run rather
    than bypassing validation via project() performing a second Store load.
    """
    def __init__(self, store, records, metadata, anomalies):
        from copy import deepcopy
        self.root, self.data_root, self.clock = store.root, store.data_root, store.clock
        self._store = store
        self._records, self._metadata, self._anomalies = deepcopy((records, metadata, anomalies))

    def load(self, strict=False):
        from copy import deepcopy
        if strict and self._anomalies:
            _fail('publication', 'STRICT_FROZEN_STORE_CONTAINS_ANOMALIES')
        return deepcopy((self._records, self._metadata, self._anomalies))

    def _read_bundle(self, directory):
        return self._store._read_bundle(directory)

    def resolve_evidence(self, ref, records):
        return self._store.resolve_evidence(ref, records)


def validated_publication_store(store, records, metadata, anomalies):
    validate_public_store(store, records, metadata)
    return ValidatedPublicationStore(store, records, metadata, anomalies)
