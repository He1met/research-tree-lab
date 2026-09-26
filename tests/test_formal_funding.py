"""Synthetic internal arithmetic only; no official-source claims or Store writes."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal, getcontext
import json
from pathlib import Path
import unittest
from researchlib.common import canonical, digest, ContractError, utc
from researchlib.formal_funding import _Resolution, _compute, CAPABILITIES

ROOT = Path(__file__).resolve().parents[1]
PLANS = [r for r in json.loads((ROOT/'research/bootstrap-v1/research_bundle.json').read_text())['records'] if r['record_type']=='plan']
INFO = '2026-09-25T00:00:00Z'
END = '2026-09-24T00:06:00Z'
ENTRY = '2026-09-23T00:05:01Z'
EXIT = '2026-09-24T00:05:01Z'


def event(ident, kind, at, **kw):
    return dict(event_id=ident, kind=kind, event_at=at, available_at=at,
        instrument='BTC-USDT-SWAP', currency='USDT', source_sha256='0'*64,
        sequence=None, **kw)


def resolution(plan, cutoff=END, caps=CAPABILITIES, actual='.00160', info=INFO):
    events = [event('entry','trade',ENTRY,price='100'), event('exit','trade',EXIT,price='110'),
        event('f0','funding',ENTRY,rate='.01',settlement_mark='100'),
        event('f1','funding','2026-09-23T08:00:00Z',rate='-.005',settlement_mark='120'),
        event('ignored-exit-funding','funding',EXIT,rate='999',settlement_mark='110'),
        event('m0','mark',ENTRY,price='100'), event('m1','mark','2026-09-23T08:00:00Z',price='120'),
        event('m2','mark','2026-09-23T16:00:00Z',price='90')]
    payload={'instrument':'BTC-USDT-SWAP','currency':'USDT','events':[e for e in events if utc(e['event_at'])<=utc(cutoff)]}
    if 'ACTUAL_COST' not in caps: actual=None
    costs = None if actual is None else {'entry_fee': actual, 'entry_slippage': '0', 'exit_fee': '0', 'exit_slippage': '0'}
    return _Resolution(digest(canonical(plan)),info,cutoff,payload,[],[],frozenset(caps),costs)


class FormalArithmeticTests(unittest.TestCase):
    def test_exact_twelve_scenarios_both_directions_and_boundary_funding(self):
        for plan in PLANS:
            r=_compute(plan,resolution(plan)); d=Decimal(plan['rules']['quantity_or_inventory']['direction'])
            self.assertEqual(r['evaluation_stage'],'FINAL')
            self.assertTrue(r['data_complete']); self.assertEqual(r['simulation_inventory'],'0')
            self.assertIsNone(r['actual_inventory']); self.assertEqual(r['metrics']['trade_count'],2)
            self.assertEqual(Decimal(r['metrics']['gross_price_pnl']),d*Decimal('.1'))
            self.assertEqual(Decimal(r['metrics']['funding_cashflow']),-d*Decimal('.004'))
            self.assertEqual(Decimal(r['metrics']['actual_net']),d*Decimal('.096')-Decimal('.00160'))
            self.assertEqual(len(r['scenarios']),12)
            for s in r['scenarios']:
                expected=d*Decimal('.096')-Decimal('2.1')*(Decimal(s['fee_bps_each_side'])+Decimal(s['slippage_bps_each_side']))/10000
                self.assertEqual(Decimal(s['net_pnl']),expected)
                self.assertTrue(s['assumption_only'])

    def test_open_inventory_only_entry_cost_and_no_forced_exit(self):
        for plan in PLANS:
            r=_compute(plan,resolution(plan,'2026-09-23T16:00:00Z',actual='.0006'))
            d=Decimal(plan['rules']['quantity_or_inventory']['direction'])
            self.assertEqual(r['evaluation_stage'],'STAGE');self.assertFalse(r['data_complete'])
            self.assertEqual(Decimal(r['simulation_inventory']),d*Decimal('.01'))
            self.assertEqual(r['metrics']['trade_count'],1)
            primary=next(s for s in r['scenarios'] if s['fee_bps_each_side']=='5' and s['slippage_bps_each_side']=='1')
            self.assertEqual(Decimal(primary['fees']),Decimal('.0005'))
            self.assertEqual(Decimal(primary['slippage_cost']),Decimal('.0001'))
            self.assertEqual(Decimal(primary['net_pnl']),-d*Decimal('.104')-Decimal('.0006'))

    def test_cross_day_exact_prefix_equals_one_shot(self):
        for plan in PLANS:
            first=_compute(plan,resolution(plan,'2026-09-23T16:00:00Z',actual='.0006',info='2026-09-23T18:00:00Z'))
            split=_compute(plan,resolution(plan),first['kernel_result'])
            once=_compute(plan,resolution(plan))
            for k in ('metrics','scenarios','private_equity_paths','simulation_inventory','qualification'):
                self.assertEqual(split[k],once[k])

    def test_schedule_only_does_not_resolve_terminal_cost_interpretation(self):
        p=PLANS[0];r=_compute(p,resolution(p,caps=CAPABILITIES-{'ACTUAL_COST'}))
        self.assertEqual(r['evaluation_stage'],'MISSING_DATA');self.assertFalse(r['data_complete'])
        self.assertIsNone(r['metrics']['actual_net']);self.assertIsNotNone(r['scenarios'][0]['net_pnl'])
        self.assertEqual(r['qualification']['cost_terminal_interpretation'],'UNPROVEN')

    def test_missing_settlement_mark_preserves_price_but_not_partial_funding_sum(self):
        p=PLANS[0];v=resolution(p)
        next(e for e in v.payload['events'] if e['event_id']=='f1')['settlement_mark']=None
        r=_compute(p,v)
        self.assertIsNotNone(r['metrics']['gross_price_pnl']);self.assertIsNone(r['metrics']['funding_cashflow'])
        self.assertTrue(all(s['net_pnl'] is None and s['observed_path_drawdown'] is None for s in r['scenarios']))
        self.assertFalse(r['data_complete'])

    def test_missing_mark_path_does_not_erase_proven_fill_or_funding(self):
        p=PLANS[0];r=_compute(p,resolution(p,caps=CAPABILITIES-{'MARK_PATH'}))
        self.assertIsNotNone(r['metrics']['gross_price_pnl']);self.assertIsNotNone(r['metrics']['funding_cashflow'])
        self.assertTrue(all(s['net_pnl'] is not None and s['observed_path_drawdown'] is None for s in r['scenarios']))
        self.assertIsNone(r['actually_evaluated_market_cutoff']);self.assertFalse(r['data_complete'])

    def test_midpath_drawdown_not_endpoint_only(self):
        p=PLANS[0];v=resolution(p);r=_compute(p,v)
        reduced=deepcopy(v.payload);reduced['events']=[e for e in reduced['events'] if e['event_id']!='m2']
        other=_compute(p,replace(v,payload=reduced,capabilities=CAPABILITIES-{'MARK_PATH'}))
        self.assertEqual(r['metrics']['gross_price_pnl'],other['metrics']['gross_price_pnl'])
        self.assertIsNotNone(r['scenarios'][0]['observed_path_drawdown'])
        self.assertIsNone(other['scenarios'][0]['observed_path_drawdown'])

    def test_same_millisecond_without_order_cannot_pick_first_even_same_price(self):
        p=PLANS[0];v=resolution(p)
        v.payload['events'].append(event('entry2','trade',ENTRY,price='100'))
        r=_compute(p,v)
        self.assertEqual(r['evaluation_stage'],'PATH_AMBIGUOUS');self.assertIsNone(r['metrics']['trade_count'])

    def test_empty_complete_window_never_becomes_not_triggered(self):
        p=PLANS[0];v=resolution(p);v.payload['events']=[]
        r=_compute(p,v)
        self.assertEqual(r['evaluation_stage'],'MISSING_DATA');self.assertIsNone(r['simulation_inventory'])
        self.assertFalse(r['terminal_requirements']['not_triggered_supported'])

    def test_no_capabilities_keeps_formal_unknown_but_all_scenarios_visible(self):
        p=PLANS[0];r=_compute(p,resolution(p,caps=frozenset()))
        self.assertTrue(all(x is None for x in r['metrics'].values()))
        self.assertEqual(len(r['scenarios']),12);self.assertIsNone(r['simulation_inventory'])

    def test_time_plan_source_identity_and_prefix_tampering_rejected(self):
        p=PLANS[0];v=resolution(p);first=_compute(p,v)
        wrong=deepcopy(p);wrong['title']='changed'
        with self.assertRaises(ContractError):_compute(wrong,v)
        with self.assertRaises(ContractError):_compute(p,replace(v,information_as_of=ENTRY))
        v.payload['events']=[]
        with self.assertRaises(ContractError):_compute(p,v,first['kernel_result'])

    def test_historical_market_cutoff_does_not_restore_public_pre_effective_state(self):
        p=PLANS[0];r=_compute(p,resolution(p,'2026-09-22T20:00:00Z'))
        self.assertEqual(r['evaluation_stage'],'WAITING_DATA');self.assertIsNone(r['simulation_inventory'])

    def test_decimal_context_and_actual_cost_finite(self):
        p=PLANS[0];expected=_compute(p,resolution(p))
        old=getcontext().prec
        try:
            getcontext().prec=6;self.assertEqual(_compute(p,resolution(p)),expected)
        finally:getcontext().prec=old
        with self.assertRaises(ContractError):_compute(p,resolution(p,actual='NaN'))

    def test_actual_cost_allocation_path_and_missing_component(self):
        for p in PLANS:
            v=replace(resolution(p),actual_costs={'entry_fee':'.0003','entry_slippage':'.0002','exit_fee':'.00077','exit_slippage':'.00033'})
            r=_compute(p,v)
            self.assertEqual(Decimal(r['metrics']['actual_total_cost']),Decimal('.00160'))
            expected=Decimal('.3') if p['rules']['quantity_or_inventory']['direction']==1 else Decimal('.206')
            self.assertEqual(Decimal(r['metrics']['observed_path_drawdown']['absolute_usdt']),expected)
            self.assertIsNotNone(r['private_actual_equity_path']);self.assertIsNotNone(r['actual_path_summary'])
            bad=dict(v.actual_costs,exit_slippage=None);r=_compute(p,replace(v,actual_costs=bad))
            self.assertIsNone(r['metrics']['actual_net']);self.assertIsNone(r['private_actual_equity_path'])
            self.assertFalse(r['data_complete'])

    def test_proven_exit_before_endpoint_keeps_closed_metrics_but_not_final(self):
        p=PLANS[0];r=_compute(p,resolution(p,'2026-09-24T00:05:30Z'))
        self.assertEqual(r['evaluation_stage'],'STAGE');self.assertEqual(r['simulation_inventory'],'0')
        self.assertEqual(r['metrics']['trade_count'],2);self.assertIsNotNone(r['metrics']['gross_price_pnl'])
        self.assertFalse(r['data_complete'])
