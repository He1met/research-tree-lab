"""Internal arithmetic/eligibility, not an uploaded official evidence format.

Only formal_review's fixed Store resolver may construct production resolutions.
Tests replace that resolver in memory; no production backend/claims switch exists.
An in-process Python object is not an OS security boundary.
"""
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, Context, ROUND_HALF_EVEN, localcontext

from .common import ContractError, canonical, digest, utc
from .funding_forward import evaluate, PLAN_HASHES, _drawdown
from .replay import decimal

VERSION = 'funding-formal-arithmetic-v1'
CAPABILITIES = frozenset({'ENTRY_WINDOW', 'EXIT_WINDOW', 'TRADE_ORDER',
    'FUNDING_SET', 'SETTLEMENT_MARKS', 'MARK_PATH', 'VALUATION_MARK',
    'COST_SCHEDULE', 'ACTUAL_COST'})


@dataclass(frozen=True)
class _Resolution:
    """Private fixed-validator output scoped to one plan, information/cutoff.

    Capabilities denote verified requirements of that exact plan and cutoff,
    not exchange-wide authority. They are recomputed, never read as authority
    from a saved JSON attachment. This class is NOT a source certificate schema.
    """
    plan_hash: str
    information_as_of: str
    market_cutoff: str
    payload: dict
    bindings: list
    audits: list
    capabilities: frozenset = frozenset()
    actual_costs: object = None


def _compute(plan, resolved, previous_kernel=None):
    if not isinstance(resolved, _Resolution):
        raise ContractError('INTERNAL_RESOLUTION_REQUIRED')
    if resolved.plan_hash != digest(canonical(plan)) or not resolved.capabilities <= CAPABILITIES:
        raise ContractError('RESOLUTION_SCOPE_INVALID')
    with localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN)):
        return _calculate(plan, resolved, previous_kernel)


def _calculate(plan, resolved, previous_kernel):
    kernel = evaluate(plan, resolved.payload, resolved.information_as_of,
                      resolved.market_cutoff, previous=previous_kernel)
    caps = resolved.capabilities
    cutoff, info = utc(resolved.market_cutoff), utc(resolved.information_as_of)
    state = kernel['simulation_state']
    entry, exit_fill = state['entry_observation'], state['exit_observation']
    entry_ok = bool(entry and {'ENTRY_WINDOW', 'TRADE_ORDER'} <= caps)
    exit_ok = bool(entry_ok and exit_fill and {'EXIT_WINDOW', 'TRADE_ORDER'} <= caps)
    # Before the scheduled exit an established position stays open. A missing
    # legal exit after that point is unresolved, never a fabricated liquidation.
    open_ok = entry_ok and cutoff < utc(plan['rules']['exit']['scheduled_at'])
    position_ok = open_ok or exit_ok
    funding_ok = bool(position_ok and {'FUNDING_SET', 'SETTLEMENT_MARKS'} <= caps
                      and all(e.get('settlement_mark') is not None for e in state['funding_observations']))
    valuation_ok = exit_ok or (open_ok and 'VALUATION_MARK' in caps)
    price_ok = bool(position_ok and valuation_ok
                    and kernel['conditional_observed_input_metrics'] is not None
                    and kernel['conditional_observed_input_metrics']['gross_price_pnl'] is not None)
    path_ok = bool(price_ok and funding_ok and 'MARK_PATH' in caps)
    terminal = cutoff >= utc(plan['evaluation_end'])
    schedule_ok = 'COST_SCHEDULE' in caps
    complete = False  # assigned after the separate actual-cost check below
    actual_claim = 'ACTUAL_COST' in caps
    costs = resolved.actual_costs
    required_costs = {'entry_fee', 'entry_slippage'} | ({'exit_fee', 'exit_slippage'} if exit_ok else set())
    if costs is not None and (not isinstance(costs, dict) or set(costs) - {'entry_fee', 'exit_fee', 'entry_slippage', 'exit_slippage'}):
        raise ContractError('ACTUAL_COST_ALLOCATION_INVALID')
    actual_ok = bool(actual_claim and costs is not None and all(costs.get(k) is not None for k in required_costs))
    if costs is not None and not actual_claim:
        raise ContractError('ACTUAL_COST_VALUE_WITHOUT_VERIFICATION')
    checked_costs = {k: decimal(v) for k, v in (costs or {}).items() if v is not None}
    actual = str(sum((checked_costs[k] for k in required_costs), Decimal(0))) if actual_ok else None
    # Schedule-only FINAL has not been approved as an interpretation of the
    # sealed protocol. Fully allocated known costs satisfy this conservative
    # branch; unknown actual costs remain a distinct terminal interpretation gap.
    cost_terminal_ok = schedule_ok and actual_ok
    complete = bool(terminal and exit_ok and funding_ok and path_ok and cost_terminal_ok)
    observed = kernel['conditional_observed_input_metrics'] or {}
    inventory = str(Decimal(plan['rules']['quantity_or_inventory']['direction']) *
                    Decimal(plan['rules']['quantity_or_inventory']['base_quantity_btc'])) if open_ok else ('0' if exit_ok else None)
    metrics = {
        'gross_price_pnl': observed.get('gross_price_pnl') if price_ok else None,
        'realized_pnl': observed.get('realized_price_pnl') if position_ok else None,
        'unrealized_pnl': observed.get('unrealized_price_pnl') if price_ok else None,
        'funding_cashflow': state['known_funding_cashflow'] if funding_ok else None,
        'holding_period': observed.get('holding_seconds') if position_ok else None,
        'trade_count': (2 if exit_ok else 1) if position_ok else None,
        'actual_total_cost': actual if position_ok else None,
        'actual_net': None, 'net_pnl': None,
        'equity_path': None, 'observed_path_drawdown': None,
    }
    if price_ok and funding_ok and actual_ok:
        metrics['actual_net'] = metrics['net_pnl'] = str(
            Decimal(metrics['gross_price_pnl']) + Decimal(metrics['funding_cashflow']) - Decimal(actual))
    # Always return every frozen scenario, even if all its dependent values are
    # unknown. An applicable cost schedule does not supply actual paid costs.
    scenarios, private_paths = [], []
    observed_scenarios = {(s['fee_bps_each_side'], s['slippage_bps_each_side']): s for s in kernel['scenarios']}
    for fee in plan['cost_model']['scenario_per_side_fee_bps']:
        for slip in plan['cost_model']['scenario_per_side_slippage_bps']:
            source = observed_scenarios.get((fee, slip), {})
            scenarios.append({'fee_bps_each_side': fee, 'slippage_bps_each_side': slip,
                'assumption_only': True,
                'fees': source.get('observed_fees') if position_ok else None,
                'slippage_cost': source.get('observed_slippage_cost') if position_ok else None,
                'net_pnl': source.get('conditional_net_pnl') if price_ok and funding_ok else None,
                'observed_path_drawdown': source.get('observed_path_drawdown') if path_ok else None})
            private_paths.append(source.get('conditional_equity_path') if path_ok else None)
    actual_path = None
    if path_ok and actual_ok:
        zero = observed_scenarios[('0', '0')]['conditional_equity_path']
        entry_cost = checked_costs['entry_fee'] + checked_costs['entry_slippage']
        exit_cost = (checked_costs['exit_fee'] + checked_costs['exit_slippage']) if exit_ok else Decimal(0)
        actual_path = [dict(point, equity=str(Decimal(point['equity']) - entry_cost -
                        (exit_cost if exit_ok and point['event_id'] == exit_fill['event_id'] else Decimal(0)))) for point in zero]
        initial = Decimal(plan['rules']['quantity_or_inventory']['base_quantity_btc']) * Decimal(entry['price'])
        metrics['observed_path_drawdown'] = _drawdown(actual_path, initial)
    # Full arrays stay in private attachments; public metrics carry a hash-bound
    # aggregate path summary, never original prices or individual mark rows.
    requirements = {'entry_first_trade': entry_ok, 'exit_first_trade': exit_ok,
                    'position_at_cutoff': position_ok, 'price_pnl': price_ok,
                    'funding_cashflow': funding_ok, 'source_mark_path': path_ok,
                    'verified_cost_schedule': schedule_ok, 'actual_cost': actual_ok,
                    'cost_terminal_interpretation': cost_terminal_ok}
    if info < utc(plan['effective_from']):
        stage = 'NOT_YET_EFFECTIVE'
    elif complete:
        stage = 'FINAL'
    elif kernel['evaluation_stage'] == 'PATH_AMBIGUOUS':
        stage = 'PATH_AMBIGUOUS'
    elif terminal:
        stage = 'MISSING_DATA'
    elif position_ok:
        stage = 'STAGE'
    else:
        stage = 'WAITING_DATA'
    # These exact frozen predicates are already met. No source absence, later
    # signal or timer can create a NOT_TRIGGERED branch for either sealed plan.
    result = {'version': VERSION, 'plan_hash': resolved.plan_hash,
        'information_as_of': resolved.information_as_of, 'market_event_cutoff': resolved.market_cutoff,
        'input_fingerprint': digest(canonical(resolved.payload)), 'kernel_result': kernel,
        'evaluation_stage': stage, 'data_complete': complete,
        'metric_scope': 'FROZEN_RULE_COUNTERFACTUAL_NOT_ACCOUNT_EXECUTION',
        'simulation_inventory': inventory, 'actual_inventory': None,
        'metrics': metrics, 'scenarios': scenarios, 'private_equity_paths': private_paths, 'private_actual_equity_path': actual_path,
        'actual_path_summary': {'point_count': len(actual_path), 'sha256': digest(canonical(actual_path)),
            'scope': 'VERIFIED_COST_APPLIED_COUNTERFACTUAL_OBSERVED_MARK_PATH'} if actual_path is not None else None,
        'qualification': {key: 'SATISFIED' if value else 'UNPROVEN' for key, value in requirements.items()},
        'actually_evaluated_market_cutoff': resolved.market_cutoff if position_ok and price_ok and funding_ok and path_ok else None,
        'terminal_requirements': {'endpoint_reached': terminal, 'cost_schedule_required': True,
            'actual_net_separate_from_schedule': True, 'not_triggered_supported': False},
        'capabilities': sorted(caps)}
    return result
