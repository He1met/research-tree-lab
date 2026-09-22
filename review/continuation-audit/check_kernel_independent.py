"""Independent synthetic kernel probes; no production plan/store writes or data."""
from copy import deepcopy
from decimal import Decimal as D, localcontext, ROUND_UP
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile


def main():
    root = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(root))
    from researchlib.common import ContractError, canonical
    from researchlib.funding_forward import evaluate
    plans = json.loads((root / 'research/bootstrap-v1/forward_plans.json').read_text())['plans']
    cases = []

    def case(name, fn):
        try:
            fn()
            cases.append({'case': name, 'result': 'PASS'})
        except Exception as error:
            cases.append({'case': name, 'result': 'FAIL', 'error': type(error).__name__ + ': ' + str(error)})

    def eq(actual, expected):
        assert actual == expected, repr(actual) + ' != ' + repr(expected)

    def reject(fn):
        try:
            fn()
        except ContractError:
            return
        raise AssertionError('Expected ContractError')

    def row(ident, kind, at, **values):
        return dict(event_id=ident, kind=kind, event_at=at, available_at=at,
                    source_sha256='b' * 64, instrument='BTC-USDT-SWAP', currency='USDT', **values)

    def payload():
        return dict(instrument='BTC-USDT-SWAP', currency='USDT', synthetic=True, events=[
            row('entry', 'trade', '2026-09-23T00:05:00Z', price='100123.456789', sequence=10),
            row('mark1', 'mark', '2026-09-23T04:00:00Z', price='99999.1'),
            row('fund1', 'funding', '2026-09-23T08:00:00Z', rate='.00001234567', settlement_mark='100001.123456'),
            row('mark2', 'mark', '2026-09-23T20:00:00Z', price='100300.25'),
            row('fund2', 'funding', '2026-09-24T00:00:00Z', rate='-.0000234', settlement_mark='100099.44'),
            row('exit', 'trade', '2026-09-24T00:05:00Z', price='100234.567891', sequence=20)])

    def run(data=None, plan=None, previous=None, cutoff='2026-09-24T00:06:00Z', info='2026-09-24T02:00:00Z'):
        return evaluate(plan or plans[0], data if data is not None else payload(), info, cutoff, previous)

    def formulas():
        for plan in plans:
            r = run(plan=plan)
            direction = D(plan['rules']['quantity_or_inventory']['direction'])
            q, entry, exit_price = D('.01'), D('100123.456789'), D('100234.567891')
            funding = -direction * q * (D('100001.123456') * D('.00001234567') + D('100099.44') * D('-.0000234'))
            gross = direction * q * (exit_price - entry)
            eq(D(r['conditional_observed_input_metrics']['gross_price_pnl']), gross)
            eq(D(r['conditional_observed_input_metrics']['observed_funding_cashflow']), funding)
            eq(len(r['scenarios']), 12)
            for s in r['scenarios']:
                expected = gross + funding - q * (entry + exit_price) * (D(s['fee_bps_each_side']) + D(s['slippage_bps_each_side'])) / 10000
                eq(D(s['conditional_net_pnl']), expected)
                eq(D(s['conditional_equity_path'][-1]['equity']), q * entry + expected)
    case('two_directions_all_12_scenarios_formula_and_path_terminal', formulas)

    def no_authority():
        p = payload()
        p.update(complete=True, verified=True, provenance_verified=True, coverage={'complete': True})
        r = run(p)
        eq(r['evaluation_stage'], 'WAITING_DATA')
        eq(r['data_complete'], False)
        assert all(v is None for v in r['metrics'].values())
        assert r['source_coverage'].startswith('UNVERIFIED')
    case('caller_complete_verified_never_promote', no_authority)

    def same_time_conflict():
        p = payload()
        p['events'].append(row('conflict', 'mark', '2026-09-23T08:00:00Z', price='110000'))
        reject(lambda: run(p))
    case('conflicting_mark_at_funding_time_rejected', same_time_conflict)

    def same_time_equal():
        p = payload()
        p['events'] = p['events'][:3]
        p['events'].append(row('equalmark', 'mark', '2026-09-23T08:00:00Z', price='100001.123456'))
        r = run(p, cutoff='2026-09-23T08:00:00Z')
        for s in r['scenarios']:
            eq(D(s['conditional_equity_path'][-1]['equity']), D(r['conditional_observed_input_metrics']['initial_notional_usdt']) + D(s['conditional_net_pnl']))
    case('equal_mark_at_funding_time_open_path_consistent', same_time_equal)

    def null_sequence():
        p = payload()
        p['events'].append(row('tie', 'trade', '2026-09-23T00:05:00Z', price='110000', sequence=None))
        eq(run(p)['evaluation_stage'], 'PATH_AMBIGUOUS')
    case('null_trade_sequence_with_numeric_tie_ambiguous', null_sequence)

    def sequence_selects():
        p = payload()
        p['events'].append(row('tie', 'trade', '2026-09-23T00:05:00Z', price='110000', sequence=11))
        eq(run(p)['simulation_state']['entry_observation']['event_id'], 'entry')
    case('unique_exchange_sequence_selects_first', sequence_selects)

    def crossday():
        p = payload(); p['events'] = p['events'][:4]
        prior = run(p, cutoff='2026-09-23T23:59:59Z', info='2026-09-24T00:00:00Z')
        r, full = run(previous=prior), run()
        eq(r['simulation_state'], full['simulation_state'])
        eq(r['scenarios'], full['scenarios'])
        eq(prior['simulation_state']['inventory'], '-0.01')
    case('cross_day_and_single_prefix_identical', crossday)

    def delayed_source():
        p = payload()
        for e in p['events']:
            e['available_at'] = '2026-09-24T01:00:00Z'
        eq(run(p)['evaluation_stage'], 'WAITING_DATA')
        reject(lambda: run(p, info='2026-09-24T00:30:00Z'))
    case('late_real_acquisition_information_cutoff_distinct', delayed_source)

    def mutation(kind):
        p, prior = payload(), run()
        if kind == 'remove':
            p['events'].pop(1)
        elif kind == 'revise':
            p['events'][1]['price'] = '100000'
        else:
            p['events'].append(row('late', 'mark', '2026-09-23T05:00:00Z', price='100001'))
        reject(lambda: run(p, previous=prior))
    for kind in ('remove', 'revise', 'late'):
        case('prior_history_' + kind + '_requires_correction', lambda kind=kind: mutation(kind))

    def missing_funding_mark():
        p = payload(); p['events'][2]['settlement_mark'] = None
        r = run(p)
        eq(r['conditional_observed_input_metrics']['observed_funding_cashflow'], None)
        assert all(s['conditional_net_pnl'] is None and s['conditional_equity_path'] is None for s in r['scenarios'])
    case('missing_exact_settlement_mark_nulls_dependent_metrics', missing_funding_mark)

    def missing_exit():
        p = payload(); p['events'].pop()
        r = run(p)
        eq(r['simulation_state']['inventory'], '-0.01')
        eq(r['simulation_state']['exit_observation'], None)
        eq(r['conditional_observed_input_metrics']['realized_price_pnl'], '0')
    case('missing_exit_does_not_force_close', missing_exit)

    def missing_entry():
        p = payload(); p['events'].pop(0)
        r = run(p)
        eq(r['simulation_state']['state'], 'ENTRY_DATA_UNRESOLVED')
        eq(r['scenarios'], [])
    case('missing_entry_not_zero_trade_or_untriggered', missing_entry)

    def boundary(which):
        p = payload()
        index = 0 if which == 'entry' else -1
        at = '2026-09-23T00:06:00Z' if which == 'entry' else '2026-09-24T00:06:00Z'
        p['events'][index]['event_at'] = p['events'][index]['available_at'] = at
        eq(run(p)['simulation_state'][which + '_observation'], None)
    for which in ('entry', 'exit'):
        case(which + '_minute_end_is_exclusive', lambda which=which: boundary(which))

    def duplicate():
        p = payload(); p['events'].append(deepcopy(p['events'][2]))
        eq(run(p)['scenarios'], run()['scenarios'])
        p['events'][-1]['event_id'] = 'fund1-copy'
        reject(lambda: run(p))
    case('duplicate_exact_event_idempotent_alias_timestamp_rejected', duplicate)

    def pre_effective():
        p = payload(); p['events'] = []
        r = run(p, cutoff='2026-09-22T20:00:00Z', info='2026-09-22T20:00:00Z')
        eq(r['evaluation_stage'], 'NOT_YET_EFFECTIVE')
        eq(r['scenarios'], [])
    case('pre_effective_no_conditional_returns', pre_effective)

    def decimal_context():
        expected = canonical(run())
        with localcontext() as context:
            context.prec = 6
            context.rounding = ROUND_UP
            eq(canonical(run()), expected)
    case('ambient_decimal_context_does_not_change_results', decimal_context)

    def plan_mutation():
        p = deepcopy(plans[0]); p['rules']['quantity_or_inventory']['base_quantity_btc'] = '.02'
        reject(lambda: run(plan=p))
    case('canonical_plan_modification_rejected', plan_mutation)

    def output_safety():
        spec = importlib.util.spec_from_file_location('independent_evaluate_cli', root / 'scripts/evaluate_funding.py')
        cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            project = Path(temporary)
            written = cli.write_report(project, 'first.json', {'synthetic_probe': True})
            before = written.read_bytes()
            try:
                cli.write_report(project, 'first.json', {'overwrite': True})
            except FileExistsError:
                pass
            else:
                raise AssertionError('Existing report overwritten')
            eq(written.read_bytes(), before)
            for escaped in ('../store/original.json', '../../outside.json', '/tmp/absolute.json', 'a/../../bad.json'):
                reject(lambda escaped=escaped: cli.write_report(project, escaped, {}))
            outside = project / 'outside'; outside.mkdir()
            (written.parent / 'linked').symlink_to(outside)
            reject(lambda: cli.write_report(project, 'linked/output.json', {}))
            eq(list(outside.iterdir()), [])
            linked_file = written.parent / 'linked-file.json'; linked_file.symlink_to(written)
            reject(lambda: cli.write_report(project, 'linked-file.json', {}))
            eq(written.read_bytes(), before)
    case('helper_no_overwrite_traversal_absolute_or_symlink_escape', output_safety)

    files = ['researchlib/funding_forward.py', 'scripts/evaluate_funding.py', 'docs/FUNDING_FORWARD_KERNEL.md', 'tests/test_funding_forward.py']
    result = {'scope': 'independent synthetic arithmetic only; not official source, economic result, formal review or natural trigger evidence',
              'decision': 'PASS_CONDITIONAL_KERNEL' if all(c['result'] == 'PASS' for c in cases) else 'CHANGES_REQUIRED',
              'cases': cases,
              'source_sha256': {file: hashlib.sha256((root / file).read_bytes()).hexdigest() for file in files},
              'production_store_mutations': False, 'new_real_market_data': False}
    Path(__file__).with_name('kernel-independent-receipt.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'decision': result['decision'], 'cases': len(cases), 'failures': [c for c in cases if c['result'] == 'FAIL']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
