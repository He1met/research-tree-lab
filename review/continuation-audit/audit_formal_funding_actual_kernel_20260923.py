#!/usr/bin/env python3
"""Frozen candidate + actual kernel, independent SYNTHETIC mathematical audit.

Supply --candidate-root explicitly and a JSON object containing the two complete
public plan records under "plans" on stdin. This script never opens a Store or
market dataset. It copies the frozen method sources to a disposable directory,
imports the actual copied candidate and kernel without substitutes, and prints
JSON evidence. Internal capabilities are deliberately synthesized for engineering
branch tests, not granted by production validators or caller certificates.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal as D, localcontext
import hashlib
import importlib
import json
from pathlib import Path
import platform
import sys
import tempfile

CANDIDATE_SHA = 'c1462692042912dfac4b8ced5a26e3492b9ab94c606a7f97f4dfcff631713a73'
SOURCE_SHA = 'd2599ce3e09d937745511bbe8dc434079f93f2600aed3c65b20eaa4657d5b8fa'
MATH_SHA = '920f3348471eda846d2e28fa17398acd6174703749ce6a5455557d0e52aeae66'
WRAPPER_SHA = '8ed274cef8718fb8fcdc09d80cccb044c4232bee91c5d0e85ab8cf3e1b5cf406'
METHOD_SHA = 'fdc04ae33547764e49cae7fe60836a8922f6a568dd674188f7cac55ac00b2084'
PLAN_HASHES = {
    'p-btc-funding-short-20260923@1': '65ff62c3603d257b82b3274785fd1bfe2c5a784d215786be4775fe7fa076bce4',
    'p-btc-funding-long-control-20260923@1': 'a8dd9a25bd4a5353bc8ed479ec41056bcf07704fccb285f2d014a9615358d02c',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def event(ident, kind, at, **values):
    return dict(event_id=ident, kind=kind, event_at=at, available_at=at,
                instrument='BTC-USDT-SWAP', currency='USDT',
                source_sha256=sha(b'SYNTHETIC_INDEPENDENT_ORACLE_NOT_A_REAL_SOURCE'), **values)


def observations():
    return [
        event('outside_entry', 'trade', '2026-09-23T00:04:59.999Z', price='99', sequence=1),
        event('funding_before_entry', 'funding', '2026-09-23T00:05:09.999Z', rate='.99', settlement_mark='100'),
        event('entry', 'trade', '2026-09-23T00:05:10Z', price='100', sequence=2),
        event('funding_a', 'funding', '2026-09-23T00:05:10Z', rate='.01', settlement_mark='100'),
        event('funding_b', 'funding', '2026-09-23T08:00:00Z', rate='-.005', settlement_mark='120'),
        event('mark_90', 'mark', '2026-09-23T16:00:00Z', price='90'),
        event('exit', 'trade', '2026-09-24T00:05:20Z', price='110', sequence=3),
        event('funding_at_exit', 'funding', '2026-09-24T00:05:20Z', rate='.5', settlement_mark='110'),
    ]


def utc(text):
    return datetime.fromisoformat(text.replace('Z', '+00:00'))


def check_frozen(root):
    pointer = root / 'docs/formal-review-candidate.json'
    raw = pointer.read_bytes()
    if sha(raw) != CANDIDATE_SHA:
        raise RuntimeError('Frozen candidate manifest changed')
    candidate = json.loads(raw)
    checked = {}
    for group in ['delivery_files', 'method_source_sha256']:
        for rel, expected in candidate[group].items():
            raw = (root / rel).read_bytes()
            if sha(raw) != expected:
                raise RuntimeError('Frozen declared file identity mismatch: ' + rel)
            checked[rel] = expected
    paths = []
    for part in ['researchlib', 'scripts', 'web/src', 'web/public', '.agents/skills']:
        paths.extend(p for p in (root / part).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    paths.extend(root / p for p in ['web/index.html', 'web/package.json', 'web/package-lock.json',
        'web/vite.config.ts', 'web/tsconfig.json', 'config/readiness_policy.json', 'AGENTS.md', 'docs/THIRD_PARTY_NOTICES.md'])
    source_files = {p.relative_to(root).as_posix(): sha(p.read_bytes()) for p in sorted(set(paths)) if p.exists()}
    if sha(canonical(source_files)) != SOURCE_SHA or candidate['source_sha256'] != SOURCE_SHA:
        raise RuntimeError('Frozen complete source fingerprint mismatch')
    runtime = {'implementation': platform.python_implementation(), 'python_version': platform.python_version(), 'third_party_runtime_dependencies': []}
    identity = sha(canonical({'sources': candidate['method_source_sha256'], 'runtime': runtime}))
    if identity != METHOD_SHA or candidate['method_code_sha256'] != METHOD_SHA:
        raise RuntimeError('Frozen method/runtime identity mismatch')
    if checked['researchlib/formal_funding.py'] != MATH_SHA or checked['researchlib/formal_review.py'] != WRAPPER_SHA:
        raise RuntimeError('Frozen component identity mismatch')
    return candidate, checked, source_files


def run_math(module, plans):
    checks, cases, failures = [], [], []
    full_cost = {'entry_fee': '.0003', 'entry_slippage': '.0002', 'exit_fee': '.00077', 'exit_slippage': '.00033'}

    def check(condition, label):
        checks.append(label)
        if not condition:
            failures.append(label)

    def evaluate(plan, rows=None, cutoff='2026-09-24T00:06:00Z', info='2026-09-24T01:00:00Z', omit=(), costs=full_cost, previous=None):
        rows = observations() if rows is None else rows
        payload = {'instrument': 'BTC-USDT-SWAP', 'currency': 'USDT', 'synthetic': True, 'events': rows}
        resolution = module._Resolution(sha(canonical(plan)), info, cutoff, payload, [], [], module.CAPABILITIES - set(omit), costs)
        return module._compute(plan, resolution, previous_kernel=previous)

    def rejection(plan, rows, label, **kwargs):
        try:
            evaluate(plan, rows, **kwargs)
        except ValueError:
            check(True, label)
        else:
            check(False, label)

    with localcontext() as context:
        context.prec = 50
        for plan in plans:
            direction = plan['rules']['quantity_or_inventory']['direction']
            suffix = ':direction_' + str(direction)
            result = evaluate(plan)
            expected_net = D('.0944') if direction == 1 else D('-.0976')
            check(result['evaluation_stage'] == 'FINAL' and result['data_complete'], 'closed_final_internal_facts' + suffix)
            check(D(result['metrics']['gross_price_pnl']) == D('.1') * direction, 'closed_gross' + suffix)
            check(D(result['metrics']['funding_cashflow']) == -D('.004') * direction, 'funding_signed_cashflow' + suffix)
            check([e['event_id'] for e in result['kernel_result']['simulation_state']['funding_observations']] == ['funding_a', 'funding_b'], 'funding_left_inclusive_right_exclusive' + suffix)
            check(result['kernel_result']['simulation_state']['entry_observation']['event_id'] == 'entry', 'legal_first_entry' + suffix)
            check(result['kernel_result']['simulation_state']['exit_observation']['event_id'] == 'exit', 'legal_first_exit' + suffix)
            check(D(result['metrics']['actual_total_cost']) == D('.0016'), 'asymmetric_cost_total' + suffix)
            check(D(result['metrics']['actual_net']) == expected_net, 'asymmetric_actual_net' + suffix)
            check(result['simulation_inventory'] == '0' and result['actual_inventory'] is None, 'closed_counterfactual_inventory' + suffix)
            check(result['metrics']['trade_count'] == 2 and D(result['metrics']['holding_period']) == D(86410), 'closed_count_and_holding' + suffix)
            eq = ['.9995', '.9895', '1.1955', '.8955', '1.0944'] if direction == 1 else ['.9995', '1.0095', '.8035', '1.1035', '.9024']
            check([D(p['equity']) for p in result['private_actual_equity_path']] == list(map(D, eq)), 'actual_path_entry_cashflow_and_exit_cost' + suffix)
            check(result['actual_path_summary']['point_count'] == 5 and result['actual_path_summary']['sha256'] == sha(canonical(result['private_actual_equity_path'])), 'actual_path_summary_binding' + suffix)
            dd = result['metrics']['observed_path_drawdown']
            check(D(dd['absolute_usdt']) == (D('.3') if direction == 1 else D('.206')), 'actual_absolute_dd' + suffix)
            check(D(dd['fraction_of_observed_peak']) == (D('.3') / D('1.1955') if direction == 1 else D('.206') / D('1.0095')), 'actual_fraction_dd' + suffix)
            check(len(result['scenarios']) == 12, 'all_12_frozen_scenarios' + suffix)
            for scenario in result['scenarios']:
                f, s = D(scenario['fee_bps_each_side']), D(scenario['slippage_bps_each_side'])
                key = ':fee_' + str(f) + ':slip_' + str(s)
                check(D(scenario['fees']) == D('2.1') * f / 10000, 'scenario_fees' + key + suffix)
                check(D(scenario['slippage_cost']) == D('2.1') * s / 10000, 'scenario_slip_once' + key + suffix)
                check(D(scenario['net_pnl']) == D('.096') * direction - D('2.1') * (f + s) / 10000, 'scenario_net' + key + suffix)
            primary = next(s for s in result['scenarios'] if s['fee_bps_each_side'] == '5' and s['slippage_bps_each_side'] == '1')
            check(D(primary['observed_path_drawdown']['absolute_usdt']) == (D('.3') if direction == 1 else D('.206')), 'primary_scenario_dd' + suffix)
            cases.append('full_oracle_closed' + suffix)

            early = evaluate(plan, cutoff='2026-09-24T00:05:30Z')
            check(early['evaluation_stage'] == 'STAGE' and early['simulation_inventory'] == '0' and not early['data_complete'], 'closed_before_endpoint_stage' + suffix)
            check(D(early['metrics']['actual_net']) == expected_net, 'closed_before_endpoint_known_net' + suffix)
            cases.append('closed_before_endpoint' + suffix)

            sparse_rows = [e for e in observations() if e['event_id'] != 'mark_90']
            sparse = evaluate(plan, sparse_rows, omit={'MARK_PATH'})
            check(D(sparse['metrics']['gross_price_pnl']) == D('.1') * direction and D(sparse['metrics']['actual_net']) == expected_net, 'missing_mark_retains_closed_components' + suffix)
            check(sparse['metrics']['observed_path_drawdown'] is None and sparse['private_actual_equity_path'] is None and not sparse['data_complete'], 'missing_mark_blocks_complete_path' + suffix)
            cases.append('missing_ordinary_mark' + suffix)

            bad_mark = observations()
            next(e for e in bad_mark if e['event_id'] == 'funding_b')['settlement_mark'] = None
            incomplete = evaluate(plan, bad_mark)
            check(D(incomplete['metrics']['gross_price_pnl']) == D('.1') * direction and D(incomplete['metrics']['actual_total_cost']) == D('.0016'), 'missing_settlement_mark_keeps_price_cost' + suffix)
            check(incomplete['metrics']['funding_cashflow'] is None and incomplete['metrics']['actual_net'] is None and incomplete['metrics']['observed_path_drawdown'] is None and not incomplete['data_complete'], 'missing_settlement_mark_null_dependents' + suffix)
            check(D(incomplete['kernel_result']['simulation_state']['known_funding_cashflow']) == -D('.01') * direction, 'known_partial_funding_not_total' + suffix)
            cases.append('missing_settlement_mark' + suffix)

            for label, costs, omit in [('missing_exit_slip', dict(full_cost, exit_slippage=None), ()), ('schedule_only', None, {'ACTUAL_COST'})]:
                unknown = evaluate(plan, costs=costs, omit=omit)
                check(unknown['metrics']['actual_net'] is None and unknown['private_actual_equity_path'] is None and not unknown['data_complete'], label + ':no_actual_final' + suffix)
                check(all(s['net_pnl'] is not None for s in unknown['scenarios']), label + ':scenarios_retained' + suffix)
                cases.append(label + suffix)
            no_schedule = evaluate(plan, omit={'COST_SCHEDULE'})
            check(D(no_schedule['metrics']['actual_net']) == expected_net and not no_schedule['data_complete'], 'actual_without_schedule_no_final' + suffix)
            cases.append('missing_cost_schedule' + suffix)

            open_rows = [e for e in observations() if utc(e['event_at']) <= utc('2026-09-23T16:00:00Z')]
            open_cost = {'entry_fee': '.0005', 'entry_slippage': '.0001'}
            opened = evaluate(plan, open_rows, cutoff='2026-09-23T16:00:00Z', info='2026-09-23T17:00:00Z', omit={'EXIT_WINDOW'}, costs=open_cost)
            check(opened['evaluation_stage'] == 'STAGE' and D(opened['simulation_inventory']) == D('.01') * direction, 'open_quantity' + suffix)
            check(D(opened['metrics']['actual_total_cost']) == D('.0006') and D(opened['metrics']['actual_net']) == (D('-.1046') if direction == 1 else D('.1034')), 'open_only_entry_cost' + suffix)
            check(D(opened['metrics']['realized_pnl']) == 0 and D(opened['metrics']['unrealized_pnl']) == -D('.1') * direction, 'open_realized_price_vs_unrealized' + suffix)
            check(opened['metrics']['trade_count'] == 1 and D(opened['metrics']['holding_period']) == 57290, 'open_count_holding' + suffix)
            check(D(opened['private_actual_equity_path'][-1]['equity']) == (D('.8954') if direction == 1 else D('1.1034')), 'open_equity' + suffix)
            cases.append('open_state' + suffix)
            continued = evaluate(plan, previous=opened['kernel_result'])
            check(continued['metrics'] == result['metrics'] and continued['private_actual_equity_path'] == result['private_actual_equity_path'], 'cross_day_equals_one_shot_no_double_fee_funding' + suffix)
            cases.append('cross_day_continuation' + suffix)

            unresolved = evaluate(plan, open_rows, omit={'EXIT_WINDOW'}, costs=open_cost)
            check(unresolved['simulation_inventory'] is None and unresolved['evaluation_stage'] == 'MISSING_DATA' and not unresolved['data_complete'], 'unknown_exit_not_proven_open_or_closed' + suffix)
            check(unresolved['terminal_requirements']['not_triggered_supported'] is False, 'no_not_triggered_branch' + suffix)
            cases.append('unknown_exit' + suffix)

            no_entry = [e for e in observations() if e['event_id'] != 'entry']
            unentered = evaluate(plan, no_entry)
            check(unentered['simulation_inventory'] is None and unentered['metrics']['trade_count'] is None and unentered['evaluation_stage'] == 'MISSING_DATA', 'no_entry_not_zero_trade_or_not_triggered' + suffix)
            cases.append('missing_entry' + suffix)
            invalid_entry = observations()
            e = next(e for e in invalid_entry if e['event_id'] == 'entry');e['event_at'] = e['available_at'] = '2026-09-23T00:06:00Z'
            excluded_entry = evaluate(plan, invalid_entry)
            check(excluded_entry['kernel_result']['simulation_state']['entry_observation'] is None, 'entry_right_boundary_excluded' + suffix)
            cases.append('entry_window_right_boundary' + suffix)
            invalid_exit = observations()
            e = next(e for e in invalid_exit if e['event_id'] == 'exit');e['event_at'] = e['available_at'] = '2026-09-24T00:06:00Z'
            excluded_exit = evaluate(plan, invalid_exit)
            check(excluded_exit['kernel_result']['simulation_state']['exit_observation'] is None and excluded_exit['simulation_inventory'] is None, 'exit_right_boundary_excluded' + suffix)
            cases.append('exit_window_right_boundary' + suffix)

            pre = evaluate(plan, [], cutoff='2026-09-22T23:00:00Z', info='2026-09-22T23:00:00Z', omit=module.CAPABILITIES, costs=None)
            check(pre['evaluation_stage'] == 'NOT_YET_EFFECTIVE' and pre['metrics']['trade_count'] is None, 'pre_effective_no_zero_result' + suffix)
            retrospective = evaluate(plan, [], cutoff='2026-09-22T23:00:00Z', info='2026-09-23T01:00:00Z', omit=module.CAPABILITIES, costs=None)
            check(retrospective['evaluation_stage'] == 'WAITING_DATA' and retrospective['kernel_result']['evaluation_stage'] == 'NOT_YET_EFFECTIVE', 'current_public_wait_vs_historical_kernel_stage' + suffix)
            cases.append('separate_information_and_market_cutoff' + suffix)

            delayed = observations();delayed[0]['available_at'] = '2026-09-24T02:00:00Z'
            rejection(plan, delayed, 'future_available_rejected' + suffix)
            rejection(plan, observations(), 'future_market_event_rejected' + suffix, cutoff='2026-09-23T16:00:00Z')
            rejection(plan, [], 'market_after_information_rejected' + suffix, cutoff='2026-09-24T00:06:00Z', info='2026-09-24T00:05:00Z')
            modified = deepcopy(plan);modified['rules']['quantity_or_inventory']['base_quantity_btc'] = '.02'
            rejection(modified, observations(), 'modified_exact_plan_rejected' + suffix)
            cases.append('time_and_exact_plan_rejection' + suffix)

            duplicated = observations();duplicated.append(deepcopy(next(e for e in duplicated if e['event_id'] == 'funding_a')))
            duplicate_result = evaluate(plan, duplicated)
            check(duplicate_result['metrics'] == result['metrics'], 'duplicate_same_event_not_double_funding' + suffix)
            cases.append('deduplicate_same_event' + suffix)
    return checks, cases, failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-root', type=Path, required=True)
    args = parser.parse_args()
    candidate, checked, source_files = check_frozen(args.candidate_root)
    plans = json.load(sys.stdin)['plans']
    incoming = {p['plan_id'] + '@' + str(p['version']): sha(canonical(p)) for p in plans}
    if incoming != PLAN_HASHES or len(plans) != 2:
        raise RuntimeError('The two exact original plan identities are required')
    with tempfile.TemporaryDirectory(prefix='formal-funding-frozen-math-') as temporary:
        copy_root = Path(temporary)
        copied_hashes = {}
        for rel, expected in candidate['method_source_sha256'].items():
            raw = (args.candidate_root / rel).read_bytes()
            if sha(raw) != expected:
                raise RuntimeError('Source changed before copy')
            target = copy_root / rel;target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as output:output.write(raw)
            copied_hashes[rel] = sha(target.read_bytes())
        sys.path.insert(0, str(copy_root))
        module = importlib.import_module('researchlib.formal_funding')
        if Path(module.__file__).resolve() != (copy_root / 'researchlib/formal_funding.py').resolve():
            raise RuntimeError('Wrong actual candidate module imported')
        checks, cases, failures = run_math(module, plans)
        for rel, expected in copied_hashes.items():
            if sha((copy_root / rel).read_bytes()) != expected:raise RuntimeError('Copied source changed during audit')
    after_candidate, after_checked, after_sources = check_frozen(args.candidate_root)
    if after_checked != checked or after_sources != source_files:raise RuntimeError('Candidate source changed during audit')
    report = {
        'schema_version': '1.0',
        'state': 'PASS_FROZEN_ACTUAL_KERNEL_MATHEMATICS_ONLY' if not failures else 'CHANGES_REQUIRED_MATHEMATICAL_FINDING',
        'synthetic_inputs': True, 'executed_at': datetime.now(timezone.utc).isoformat(),
        'script': 'review/continuation-audit/' + Path(__file__).name,
        'script_sha256': sha(Path(__file__).read_bytes()),
        'candidate_manifest_sha256': CANDIDATE_SHA, 'source_sha256': SOURCE_SHA,
        'formal_funding_sha256': MATH_SHA, 'formal_review_sha256': WRAPPER_SHA,
        'method_code_sha256': METHOD_SHA, 'method_source_files_checked_and_copied': len(copied_hashes),
        'delivery_files_checked': len(candidate['delivery_files']),
        'complete_source_fingerprint_file_count': len(source_files),
        'copied_source_sha256': copied_hashes, 'original_plan_hashes': incoming,
        'runtime': {'implementation': platform.python_implementation(), 'python_version': platform.python_version(), 'decimal_precision': 50, 'third_party_dependencies': []},
        'case_count': len(cases), 'assertion_count': len(checks),
        'assertions_passed': len(checks) - len(failures), 'failures': failures,
        'cases': cases, 'checks': checks,
        'actual_candidate_and_kernel_imported': True, 'dependency_substitution': False,
        'source_unchanged': True, 'temporary_source_copy_removed': True,
        'internal_capability_facts': 'SYNTHETIC_TEST_ONLY_NOT_PRODUCTION_SOURCE_AUTHORITY',
        'production_store_opened_by_script': False, 'source_or_production_mutations': False,
        'real_source_decode_repeated': False, 'source_coverage_or_economic_acceptance': False,
        'boundary': 'Mathematical and eligibility branches only. Exact plans are supplied read-only over stdin. Production resolvers, acquisition proof, Store chain/archives and natural execution are separately reviewed; passing synthetic FINAL does not establish a real economic FINAL.',
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
