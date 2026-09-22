"""Synthetic arithmetic only; never a production or natural outcome fixture."""
import copy
import json
from pathlib import Path
import unittest
from researchlib.common import ContractError
from researchlib.funding_forward import evaluate

ROOT = Path(__file__).resolve().parents[1]
PLANS = json.loads((ROOT / 'research/bootstrap-v1/forward_plans.json').read_text())['plans']


def row(ident, kind, at, **fields):
    return dict(event_id=ident, kind=kind, event_at=at, available_at=at,
                source_sha256='a'*64, instrument='BTC-USDT-SWAP', currency='USDT', **fields)


def sample():
    return dict(instrument='BTC-USDT-SWAP', currency='USDT', synthetic=True, events=[
        row('entry', 'trade', '2026-09-23T00:05:01Z', price='100', sequence=1),
        row('m1', 'mark', '2026-09-23T01:00:00Z', price='110'),
        row('f1', 'funding', '2026-09-23T08:00:00Z', rate='.01', settlement_mark='105'),
        row('m2', 'mark', '2026-09-23T12:00:00Z', price='90'),
        row('f2', 'funding', '2026-09-24T00:00:00Z', rate='-.005', settlement_mark='95'),
        row('exit', 'trade', '2026-09-24T00:05:02Z', price='98', sequence=2),
    ])


def run(payload=None, previous=None, plan=None, cutoff='2026-09-24T00:06:00Z', info='2026-09-24T01:00:00Z'):
    return evaluate(plan or PLANS[0], sample() if payload is None else payload, info, cutoff, previous)


class FundingForward(unittest.TestCase):
    def test_external_decimal_context_cannot_change_result(self):
        from decimal import localcontext, ROUND_DOWN
        from researchlib.common import canonical
        expected = canonical(run())
        with localcontext() as context:
            context.prec = 6; context.rounding = ROUND_DOWN; context.Emax = 10
            self.assertEqual(canonical(run()), expected)

    def test_report_output_cannot_overwrite_or_escape_scratch(self):
        import tempfile
        from scripts.evaluate_funding import write_report
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = write_report(root, 'first.json', {'value': 1})
            original = report.read_bytes()
            with self.assertRaises(FileExistsError):
                write_report(root, 'first.json', {'value': 2})
            self.assertEqual(report.read_bytes(), original)
            for path in ['../../outside.json', '/absolute.json', 'nested/../../../../escape.json']:
                with self.assertRaises(ContractError):
                    write_report(root, path, {})
            (report.parent / 'link').symlink_to(root, target_is_directory=True)
            with self.assertRaises(ContractError):
                write_report(root, 'link/escape.json', {})

    def test_closed_short_all_scenarios_by_independent_formula(self):
        result = run()
        self.assertEqual(result['evaluation_stage'], 'WAITING_DATA')
        self.assertFalse(result['data_complete'])
        self.assertEqual(result['conditional_observed_input_metrics']['gross_price_pnl'], '0.02')
        self.assertEqual(result['conditional_observed_input_metrics']['observed_funding_cashflow'], '0.00575')
        self.assertEqual(result['simulation_state']['inventory'], '0')
        from decimal import Decimal as D
        self.assertEqual(len(result['scenarios']), 12)
        for scenario in result['scenarios']:
            expected = D('.02575') - D('1.98') * (D(scenario['fee_bps_each_side']) + D(scenario['slippage_bps_each_side'])) / 10000
            self.assertEqual(D(scenario['conditional_net_pnl']), expected)
        self.assertIsNone(result['metrics']['net_pnl'])
        self.assertIsNone(result['metrics']['funding_cashflow'])

    def test_opposite_direction_price_funding_reverse_costs_do_not(self):
        a, b = run(), run(plan=PLANS[1])
        from decimal import Decimal as D
        self.assertEqual(D(a['conditional_observed_input_metrics']['gross_price_pnl']), -D(b['conditional_observed_input_metrics']['gross_price_pnl']))
        self.assertEqual(a['scenarios'][5]['observed_fees'], b['scenarios'][5]['observed_fees'])
        self.assertEqual(b['baseline_comparison']['state'], 'NOT_JOINED')

    def test_cross_day_replay_preserves_position_and_prefix(self):
        first = sample()
        first['events'] = first['events'][:4]
        prior = run(first, cutoff='2026-09-23T23:59:59Z', info='2026-09-24T00:00:00Z')
        self.assertEqual(prior['simulation_state']['inventory'], '-0.01')
        self.assertEqual(prior['conditional_observed_input_metrics']['trade_count'], 1)
        self.assertEqual(prior['simulation_state']['known_funding_cashflow'], '0.0105')
        continued = run(previous=prior)
        self.assertEqual(continued['simulation_state'], run()['simulation_state'])
        self.assertIsNotNone(continued['opening_state_hash'])
        self.assertEqual(continued['scenarios'], run()['scenarios'])

    def test_tampered_prior_state_rejected(self):
        prior = run()
        prior['simulation_state']['inventory'] = '100'
        with self.assertRaises(ContractError):
            run(previous=prior)

    def test_removed_or_changed_prior_event_rejected(self):
        prior = run()
        for remove in [False, True]:
            altered = sample()
            if remove:
                altered['events'].pop(1)
            else:
                altered['events'][1]['price'] = '109'
            with self.assertRaises(ContractError):
                run(altered, previous=prior)

    def test_late_earlier_fill_needs_correction(self):
        prior = run()
        data = sample()
        data['events'].append(row('earlier', 'trade', '2026-09-23T00:05:00Z', price='99', sequence=0))
        with self.assertRaises(ContractError):
            run(data, previous=prior)

    def test_late_mark_in_prior_interval_needs_correction(self):
        prior = run()
        data = sample()
        data['events'].append(row('backfill', 'mark', '2026-09-23T02:00:00Z', price='200'))
        with self.assertRaises(ContractError):
            run(data, previous=prior)

    def test_last_settlement_mark_values_open_position(self):
        data = sample(); data['events'].pop()
        result = run(data)
        self.assertEqual(result['conditional_observed_input_metrics']['unrealized_price_pnl'], '0.05')

    def test_missing_entry_not_zero_trade_or_untriggered(self):
        data = sample()
        data['events'] = [e for e in data['events'] if e['event_id'] != 'entry']
        output = run(data)
        self.assertIsNone(output['metrics']['trade_count'])
        self.assertEqual(output['simulation_state']['state'], 'ENTRY_DATA_UNRESOLVED')
        self.assertEqual(output['scenarios'], [])

    def test_missing_exit_never_forces_close(self):
        data = sample()
        data['events'].pop()
        result = run(data)
        self.assertEqual(result['simulation_state']['inventory'], '-0.01')
        self.assertIsNone(result['simulation_state']['exit_observation'])
        self.assertEqual(result['conditional_observed_input_metrics']['realized_price_pnl'], '0')

    def test_missing_settlement_mark_disables_dependent_results(self):
        data = sample()
        data['events'][2]['settlement_mark'] = None
        result = run(data)
        self.assertIsNone(result['conditional_observed_input_metrics']['observed_funding_cashflow'])
        self.assertTrue(all(s['conditional_net_pnl'] is None and s['conditional_equity_path'] is None for s in result['scenarios']))
        self.assertEqual(result['conditional_observed_input_metrics']['gross_price_pnl'], '0.02')

    def test_conflicting_mark_at_settlement_rejected(self):
        data = sample()
        data['events'].append(row('conflict', 'mark', '2026-09-23T08:00:00Z', price='104'))
        with self.assertRaises(ContractError):
            run(data)

    def test_open_scenario_final_equity_equals_initial_plus_net(self):
        data = sample(); data['events'].pop()
        data['events'].append(row('matching', 'mark', '2026-09-24T00:00:00Z', price='95'))
        from decimal import Decimal as D
        for scenario in run(data)['scenarios']:
            self.assertEqual(D(scenario['conditional_equity_path'][-1]['equity']), D('1') + D(scenario['conditional_net_pnl']))

    def test_duplicate_funding_timestamp_rejected(self):
        data = sample()
        extra = copy.deepcopy(data['events'][2]); extra['event_id'] = 'f1-copy'
        data['events'].append(extra)
        with self.assertRaises(ContractError):
            run(data)

    def test_repeat_exact_identity_idempotent(self):
        data = sample()
        data['events'].append(copy.deepcopy(data['events'][2]))
        self.assertEqual(run(data)['scenarios'], run()['scenarios'])

    def test_entry_tie_without_exchange_sequence_ambiguous(self):
        data = sample()
        data['events'].append(row('tie', 'trade', '2026-09-23T00:05:01Z', price='101'))
        self.assertEqual(run(data)['evaluation_stage'], 'PATH_AMBIGUOUS')
        self.assertEqual(run(data)['scenarios'], [])

    def test_null_sequence_is_ambiguity_not_sort_error(self):
        data = sample()
        data['events'].append(row('tie', 'trade', '2026-09-23T00:05:01Z', price='101', sequence=None))
        self.assertEqual(run(data)['evaluation_stage'], 'PATH_AMBIGUOUS')

    def test_entry_end_is_exclusive(self):
        data = sample()
        data['events'][0]['event_at'] = data['events'][0]['available_at'] = '2026-09-23T00:06:00Z'
        self.assertIsNone(run(data)['simulation_state']['entry_observation'])

    def test_funding_exit_is_exclusive_entry_inclusive(self):
        data = sample()
        data['events'].extend([
            row('atentry', 'funding', '2026-09-23T00:05:01Z', rate='.01', settlement_mark='100'),
            row('atexit', 'funding', '2026-09-24T00:05:02Z', rate='1', settlement_mark='98')])
        self.assertEqual(run(data)['conditional_observed_input_metrics']['observed_funding_cashflow'], '0.01575')

    def test_future_or_backdated_and_wrong_unit_rejected(self):
        for field, value in [('available_at', '2026-09-25T00:00:00Z'), ('available_at', '2026-09-22T00:00:00Z'), ('currency', 'USD'), ('price', 'NaN')]:
            data = sample(); data['events'][0][field] = value
            with self.assertRaises(ContractError):
                run(data)

    def test_frozen_plan_change_rejected(self):
        plan = copy.deepcopy(PLANS[0]); plan['rules']['quantity_or_inventory']['base_quantity_btc'] = '0.02'
        with self.assertRaises(ContractError):
            run(plan=plan)

    def test_pre_effective_has_no_economic_numbers(self):
        data = sample(); data['events'] = []
        result = run(data, cutoff='2026-09-22T20:00:00Z', info='2026-09-22T20:00:00Z')
        self.assertEqual(result['evaluation_stage'], 'NOT_YET_EFFECTIVE')
        self.assertTrue(all(v is None for v in result['metrics'].values()))

    def test_caller_complete_cannot_promote(self):
        data = sample(); data.update(complete=True, verified=True, coverage='COMPLETE')
        result = run(data)
        self.assertFalse(result['data_complete'])
        self.assertEqual(result['evaluation_stage'], 'WAITING_DATA')
        self.assertIsNone(result['metrics']['net_pnl'])

    def test_observed_drawdown_retains_peak_not_just_last_mark(self):
        zero = run()['scenarios'][0]
        self.assertEqual(len(zero['conditional_equity_path']), 6)
        # initial1 -> adverse.9 ->1.0355 ->1.1105 ->1.0605 ->1.02575
        self.assertEqual(zero['observed_path_drawdown']['absolute_usdt'], '0.10')


if __name__ == '__main__':
    unittest.main()
