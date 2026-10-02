#!/usr/bin/env python3
"""Repeat the independent 12-case / 56-assertion DEVELOPMENT arithmetic audit.

SYNTHETIC ONLY. Read a single explicitly selected candidate source file, copy
its bytes into an automatically removed temporary directory, replace only its
relative imports with paper-oracle dependencies, and print a JSON receipt.
No production data or other candidate module is loaded. No candidate files,
shared indexes, Store records, Git state or installed identities are changed.

Usage from any directory:
  python3 audit_formal_funding_in_memory_20260923.py --candidate-root CANDIDATE_ROOT

The script's sibling frozen Markdown oracle must be present. There is no output
path argument: stdout lets the caller choose whether to preserve the receipt.
A pass is neither final source approval nor source/resolver/Store integration
validation. The temporary source copy is removed after execution; its hash is
retained. This is not an OS sandbox for arbitrary untrusted Python programs.
"""
import argparse
import ast
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import hashlib
import json
from pathlib import Path
import platform
import sys
import tempfile
import types

D = Decimal
ORACLE_NAME = 'FORMAL_FUNDING_ORACLE_20260923.md'
ORACLE_SHA256 = 'ff3f06795fdf3158f25018f5e179b5ae617d95b699faf1eee84b0e69d8bcce00'
CANDIDATE_FILE = 'researchlib/formal_funding.py'
RELATIVE_IMPORTS = {
    'common': {'ContractError', 'canonical', 'digest', 'utc'},
    'funding_forward': {'evaluate', 'PLAN_HASHES', '_drawdown'},
    'replay': {'decimal'},
}
STANDARD_IMPORTS = {
    'copy': {'deepcopy'}, 'dataclasses': {'dataclass'},
    'decimal': {'Decimal', 'Context', 'ROUND_HALF_EVEN', 'localcontext'},
}

# These historical hashes were actually printed by the early read-only probes.
# No old source bytes were retained, and no date is reconstructed here.
EARLY_REVIEW = {
    'initial_observed_source_sha256': '80b2c19ec49961c504752dadf60256612b883935ab461d9302b9894a26d5bf0c',
    'first_recheck_observed_source_sha256': '920f3348471eda846d2e28fa17398acd6174703749ce6a5455557d0e52aeae66',
    'historical_source_copies_preserved': False,
    'scope': 'Earlier in-memory probe outputs, not frozen or installed approvals.',
    'findings_and_fixes': [
        {'finding': 'A scalar actual-cost total permitted FINAL while actual-cost-applied equity/drawdown remained absent.',
         'fix_observed': 'Require applicable entry/exit fee/slippage allocations; form the private actual-cost path and drawdown; missing allocation prevents complete FINAL.'},
        {'finding': 'Proven legal fills before the corresponding window endpoint lost otherwise known closed metrics and inventory.',
         'fix_observed': 'Keep proven closed components and inventory zero as STAGE before the original endpoint; only FINAL waits for that endpoint.'},
    ],
}

BASE_PLAN = {
    'effective_from': '2026-09-23T00:05:00Z',
    'entry_valid_until': '2026-09-23T00:06:00Z',
    'evaluation_end': '2026-09-24T00:06:00Z',
    'rules': {
        'exit': {'scheduled_at': '2026-09-24T00:05:00Z'},
        'quantity_or_inventory': {'direction': 1, 'base_quantity_btc': '0.01'},
    },
    'cost_model': {'scenario_per_side_fee_bps': ['0', '2', '5', '10'],
                   'scenario_per_side_slippage_bps': ['0', '1', '3']},
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fixture_canonical(value):
    # A local fixture identity, deliberately not the production serializer.
    return json.dumps(value, sort_keys=True).encode()


def oracle_drawdown(path, initial):
    peak, absolute, fraction = initial, D(0), D(0)
    for point in path:
        value = D(point['equity'])
        peak = max(peak, value)
        absolute = max(absolute, peak - value)
        fraction = max(fraction, (peak - value) / peak)
    return {'absolute_usdt': str(absolute),
            'fraction_of_observed_peak': str(fraction), 'scope': 'SYNTHETIC_ORACLE'}


def load_candidate_only(raw):
    tree = ast.parse(raw, filename='candidate/formal_funding.py')
    # Fail on unreviewed import expansion instead of loading another candidate
    # module. This guard is structural, not a claim of process-level isolation.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            raise RuntimeError('Candidate import surface changed; review the harness before replay')
        if isinstance(node, ast.ImportFrom):
            allowed = RELATIVE_IMPORTS if node.level == 1 else STANDARD_IMPORTS if node.level == 0 else {}
            if node.module not in allowed or any(n.asname or n.name not in allowed[node.module] for n in node.names):
                raise RuntimeError('Candidate import surface changed; review the harness before replay')
    tree.body = [node for node in tree.body if not
                 (isinstance(node, ast.ImportFrom) and node.level)]
    module = types.ModuleType('_independent_formal_funding_oracle')
    sys.modules[module.__name__] = module
    module.__dict__.update(
        ContractError=ValueError, canonical=fixture_canonical, digest=sha,
        utc=lambda text: datetime.fromisoformat(text.replace('Z', '+00:00')),
        decimal=D, PLAN_HASHES={}, _drawdown=oracle_drawdown)
    exec(compile(tree, 'candidate/formal_funding.py', 'exec'), module.__dict__)
    return module


def paper_kernel(direction, closed):
    # These five frictionless point equities are fixed from the independent
    # handwritten scenario, not generated by a candidate evaluator.
    values = ['1', '.99', '1.196', '.896', '1.096'] if direction == 1 else ['1', '1.01', '.804', '1.104', '.904']
    identities = ['entry', 'funding_a', 'funding_b', 'mark_90', 'exit']
    if not closed:
        values, identities = values[:-1], identities[:-1]
    scenarios = []
    for fee in BASE_PLAN['cost_model']['scenario_per_side_fee_bps']:
        for slip in BASE_PLAN['cost_model']['scenario_per_side_slippage_bps']:
            cost_rate = (D(fee) + D(slip)) / 10000
            notional = D('2.1') if closed else D(1)
            path = [{'event_id': ident,
                     'equity': str(D(value) - cost_rate - (D('1.1') * cost_rate if ident == 'exit' else 0))}
                    for ident, value in zip(identities, values)]
            net = (D('.096') * direction if closed else -D('.104') * direction) - notional * cost_rate
            scenarios.append({
                'fee_bps_each_side': fee, 'slippage_bps_each_side': slip,
                'observed_fees': str(notional * D(fee) / 10000),
                'observed_slippage_cost': str(notional * D(slip) / 10000),
                'conditional_net_pnl': str(net), 'conditional_equity_path': path,
                'observed_path_drawdown': oracle_drawdown(path, D(1)),
            })
    gross = D('.1') * direction if closed else -D('.1') * direction
    return {
        'simulation_state': {
            'entry_observation': {'event_id': 'entry', 'price': '100'},
            'exit_observation': {'event_id': 'exit', 'price': '110'} if closed else None,
            'funding_observations': [{'settlement_mark': '100'}, {'settlement_mark': '120'}],
            'known_funding_cashflow': str(-D('.004') * direction),
        },
        'evaluation_stage': 'WAITING_DATA',
        'conditional_observed_input_metrics': {
            'gross_price_pnl': str(gross),
            'realized_price_pnl': str(gross) if closed else '0',
            'unrealized_price_pnl': '0' if closed else str(gross),
            'holding_seconds': '86410' if closed else '57290',
        },
        'scenarios': scenarios,
    }


def run_checks(module):
    passed, cases = [], []

    def check(condition, label):
        if not condition:
            raise AssertionError('Independent SYNTHETIC mismatch: ' + label)
        passed.append(label)

    def result(direction, closed=True, cutoff='2026-09-24T00:06:00Z', omit=(), costs=None):
        plan = deepcopy(BASE_PLAN)
        plan['rules']['quantity_or_inventory']['direction'] = direction
        fixture = paper_kernel(direction, closed)
        module.evaluate = lambda *args, **kwargs: deepcopy(fixture)
        resolved = module._Resolution(
            sha(fixture_canonical(plan)), '2026-09-24T01:00:00Z', cutoff,
            {}, [], [], module.CAPABILITIES - set(omit), costs)
        return module._compute(plan, resolved)

    with localcontext() as context:
        context.prec, context.rounding = 50, ROUND_HALF_EVEN
        full_cost = {'entry_fee': '.0003', 'entry_slippage': '.0002',
                     'exit_fee': '.00077', 'exit_slippage': '.00033'}
        for direction in [1, -1]:
            suffix = ':direction_' + str(direction)
            closed = result(direction, costs=full_cost)
            expected_net = D('.0944') if direction == 1 else D('-.0976')
            check(closed['evaluation_stage'] == 'FINAL' and closed['data_complete'], 'closed_complete' + suffix)
            check(D(closed['metrics']['actual_net']) == expected_net, 'closed_actual_net' + suffix)
            expected_equity = ['.9995', '.9895', '1.1955', '.8955', '1.0944'] if direction == 1 else ['.9995', '1.0095', '.8035', '1.1035', '.9024']
            check([D(x['equity']) for x in closed['private_actual_equity_path']] == list(map(D, expected_equity)), 'actual_equity_path' + suffix)
            check(closed['actual_path_summary']['point_count'] == 5, 'actual_path_count' + suffix)
            check(D(closed['metrics']['observed_path_drawdown']['absolute_usdt']) == (D('.3') if direction == 1 else D('.206')), 'actual_absolute_drawdown' + suffix)
            check(D(closed['metrics']['observed_path_drawdown']['fraction_of_observed_peak']) == (D('.3') / D('1.1955') if direction == 1 else D('.206') / D('1.0095')), 'actual_fraction_drawdown' + suffix)
            check(len(closed['scenarios']) == 12, 'all_scenarios_retained' + suffix)
            for scenario in closed['scenarios']:
                fee, slip = D(scenario['fee_bps_each_side']), D(scenario['slippage_bps_each_side'])
                check(D(scenario['net_pnl']) == direction * D('.096') - D('2.1') * (fee + slip) / 10000,
                      'scenario_net_fee_' + str(fee) + '_slip_' + str(slip) + suffix)
            cases.append('closed_asymmetric_cost' + suffix)

            before = result(direction, cutoff='2026-09-24T00:05:30Z', costs=full_cost)
            check(before['evaluation_stage'] == 'STAGE' and before['simulation_inventory'] == '0' and not before['data_complete'], 'proven_closed_before_endpoint_state' + suffix)
            check(D(before['metrics']['actual_net']) == expected_net, 'proven_closed_before_endpoint_net' + suffix)
            cases.append('proven_closed_before_endpoint' + suffix)

            missing = result(direction, omit={'MARK_PATH'}, costs=full_cost)
            check(D(missing['metrics']['actual_net']) == expected_net, 'missing_mark_path_preserves_net' + suffix)
            check(missing['private_actual_equity_path'] is None and missing['metrics']['observed_path_drawdown'] is None and not missing['data_complete'], 'missing_mark_path_blocks_complete' + suffix)
            cases.append('missing_mark_path_preserves_net' + suffix)

            partial = result(direction, costs=dict(full_cost, exit_slippage=None))
            check(partial['metrics']['actual_net'] is None and partial['private_actual_equity_path'] is None and not partial['data_complete'], 'missing_cost_allocation_blocks_complete' + suffix)
            cases.append('missing_cost_allocation' + suffix)

            opened = result(direction, closed=False, cutoff='2026-09-23T16:00:00Z', omit={'EXIT_WINDOW'}, costs={'entry_fee': '.0005', 'entry_slippage': '.0001'})
            check(opened['evaluation_stage'] == 'STAGE' and D(opened['simulation_inventory']) == D('.01') * direction, 'open_inventory' + suffix)
            check(D(opened['metrics']['actual_net']) == (D('-.1046') if direction == 1 else D('.1034')), 'open_entry_cost_only_net' + suffix)
            cases.append('open_entry_cost_only' + suffix)

            unresolved = result(direction, closed=False, omit={'EXIT_WINDOW'}, costs={'entry_fee': '.0005', 'entry_slippage': '.0001'})
            check(unresolved['simulation_inventory'] is None and unresolved['evaluation_stage'] == 'MISSING_DATA' and not unresolved['data_complete'], 'unknown_exit_inventory' + suffix)
            check(unresolved['terminal_requirements']['not_triggered_supported'] is False, 'not_triggered_unsupported' + suffix)
            cases.append('unknown_exit' + suffix)
    if len(passed) != 56 or len(cases) != 12:
        raise RuntimeError('The preserved audit scope is exactly 12 cases / 56 assertions')
    return passed, cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-root', type=Path, required=True, metavar='CANDIDATE_ROOT')
    args = parser.parse_args()
    candidate = args.candidate_root / CANDIDATE_FILE
    if not candidate.is_file():
        raise RuntimeError('Explicit candidate root lacks the required source file')
    oracle = Path(__file__).with_name(ORACLE_NAME)
    oracle_hash = sha(oracle.read_bytes())
    if oracle_hash != ORACLE_SHA256:
        raise RuntimeError('Frozen oracle identity changed; no success receipt')
    raw = candidate.read_bytes()
    if len(raw) > 1024 * 1024:
        raise RuntimeError('Candidate source exceeds this bounded audit scope')
    source_hash = sha(raw)
    with tempfile.TemporaryDirectory(prefix='formal-funding-independent-') as temporary:
        copied = Path(temporary) / 'formal_funding.py'
        with copied.open('xb') as output:
            output.write(raw)
        copied_bytes = copied.read_bytes()
        copy_hash = sha(copied_bytes)
        if copy_hash != source_hash:
            raise RuntimeError('Temporary source copy identity mismatch')
        module = load_candidate_only(copied_bytes)
        try:
            passed, cases = run_checks(module)
        finally:
            sys.modules.pop(module.__name__, None)
        if copied.read_bytes() != raw:
            raise RuntimeError('Temporary copy changed during audit')
    if candidate.read_bytes() != raw:
        raise RuntimeError('Candidate changed during audit; no stable-version success receipt')
    receipt = {
        'schema_version': '1.0',
        'state': 'PASS_DEVELOPMENT_IN_MEMORY_ORACLE_ONLY_NOT_FINAL_APPROVAL',
        'synthetic': True,
        'executed_at': datetime.now(timezone.utc).isoformat(),
        'script': 'review/continuation-audit/' + Path(__file__).name,
        'script_sha256': sha(Path(__file__).read_bytes()),
        'oracle': 'review/continuation-audit/' + ORACLE_NAME,
        'oracle_sha256': oracle_hash,
        'candidate_relative_file': CANDIDATE_FILE,
        'candidate_source_sha256': source_hash,
        'temporary_source_copy_sha256': copy_hash,
        'temporary_source_copy_equals_read_bytes': True,
        'temporary_source_copy_removed': True,
        'candidate_source_unchanged_during_audit': True,
        'private_absolute_paths_recorded': False,
        'case_count': len(cases), 'assertion_count': len(passed),
        'assertions_passed': len(passed), 'cases': cases, 'passed_checks': passed,
        'runtime': {'implementation': platform.python_implementation(),
                    'python_version': platform.python_version(), 'python_build': sys.version,
                    'decimal_precision': 50, 'decimal_rounding': ROUND_HALF_EVEN,
                    'third_party_dependencies': []},
        'scope': 'Only the captured formal_funding module executes. All relative dependencies, including kernel, serializer, time helper, decimal parser and drawdown helper, are independently substituted in memory. No other candidate module or production record is loaded.',
        'fixture_identity': 'Minimal SYNTHETIC plan-shaped object and paper-kernel output; not either complete production plan and not proof of plan whitelisting or source provenance.',
        'early_review_history': EARLY_REVIEW,
        'not_tested': ['Production source resolver or evidence admission',
                       'Store, method identity, canonical serialization or private attachment/public archive enforcement',
                       'Original kernel event selection, chronology, complete source coverage or natural trigger',
                       'End-to-end real economic evaluation or deployment readiness'],
        'writes': 'Only a disposable local source copy; receipt goes to stdout. No candidate/production/shared-index writes.',
        'installed_source_closure_member': False,
        'final_source_approval': False,
        'real_economic_acceptance': False,
    }
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
