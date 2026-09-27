"""Versioned arithmetic for the two sealed funding-counterevidence plans.

This is a computation kernel, NOT an official-source coverage adapter. It accepts
normalized observations, preserves their exact prefix, and ALWAYS labels source
coverage UNVERIFIED. No flag or caller assertion can produce FINAL/NOT_TRIGGERED.
Raw download/schema/coverage verification must be implemented and independently
reviewed separately before this output can establish a complete economic result.
"""
from copy import deepcopy
from decimal import Decimal, Context, DecimalException, ROUND_HALF_EVEN, localcontext
from .common import ContractError, canonical, digest, utc
from .replay import decimal

VERSION = 'funding-forward-kernel-v1'
PLAN_HASHES = {
    'p-btc-funding-short-20260923@1': '65ff62c3603d257b82b3274785fd1bfe2c5a784d215786be4775fe7fa076bce4',
    'p-btc-funding-long-control-20260923@1': 'a8dd9a25bd4a5353bc8ed479ec41056bcf07704fccb285f2d014a9615358d02c',
}
D = Decimal


def _hash(value):
    return digest(canonical(value))


def _positive(value):
    n = decimal(value)
    if n <= 0:
        raise ContractError('Nonpositive price')
    return n


def _observations(payload, information_as_of, market_cutoff):
    """Reject ambiguous identities, time travel and undeclared currencies/units."""
    if payload.get('instrument') != 'BTC-USDT-SWAP' or payload.get('currency') != 'USDT':
        raise ContractError('Only BTC-USDT-SWAP quoted in USDT is supported')
    rows, hashes = [], {}
    for original in payload.get('events', []):
        e = deepcopy(original)
        ident, kind = e.get('event_id'), e.get('kind')
        if not isinstance(ident, str) or not ident or kind not in {'trade', 'mark', 'funding'}:
            raise ContractError('Every observation needs stable identity and supported kind')
        if e.get('instrument') != payload['instrument'] or e.get('currency') != payload['currency']:
            raise ContractError('Mixed instrument or quote currency')
        event_at, available = utc(e['event_at']), utc(e['available_at'])
        if event_at > market_cutoff or available > information_as_of or available < event_at:
            raise ContractError('Observation is outside market/information cutoff or backdated')
        if not isinstance(e.get('source_sha256'), str) or len(e['source_sha256']) != 64 or any(c not in '0123456789abcdef' for c in e['source_sha256']):
            raise ContractError('Source byte identity required; hash alone does not prove provenance')
        if kind in {'trade', 'mark'}:
            _positive(e['price'])
        else:
            decimal(e['rate'])
            if e.get('settlement_mark') is not None:
                _positive(e['settlement_mark'])
        if e.get('sequence') is not None and (not isinstance(e['sequence'], int) or isinstance(e['sequence'], bool) or e['sequence'] < 0):
            raise ContractError('Exchange sequence must be a nonnegative integer')
        sha = _hash(e)
        if ident in hashes:
            if hashes[ident] != sha:
                raise ContractError('Same event identity has conflicting bytes')
            continue
        hashes[ident] = sha
        rows.append(e)
    # Funding is one settlement per instrument/timestamp. Duplicate identities
    # must never count the same cashflow twice. Conflicting marks are not averaged.
    seen = {}
    for e in rows:
        key = e['kind'], utc(e['event_at'])
        if e['kind'] in {'funding', 'mark'} and key in seen:
            raise ContractError('Duplicate funding/mark timestamp requires source correction')
        seen[key] = e
    for e in rows:
        if e['kind'] == 'funding' and e.get('settlement_mark') is not None:
            mark = seen.get(('mark', utc(e['event_at'])))
            if mark and decimal(mark['price']) != decimal(e['settlement_mark']):
                raise ContractError('Conflicting mark prices at exact settlement timestamp')
    return sorted(rows, key=lambda e: (utc(e['event_at']), e['kind'], e['sequence'] if e.get('sequence') is not None else -1, e['event_id'])), hashes


def _first_trade(events, start, end):
    selected = [e for e in events if e['kind'] == 'trade' and start <= utc(e['event_at']) < end]
    if not selected:
        return None, False
    first_time = min(utc(e['event_at']) for e in selected)
    tied = [e for e in selected if utc(e['event_at']) == first_time]
    if len(tied) > 1:
        seq = [e.get('sequence') for e in tied]
        if None in seq or len(set(seq)) != len(seq):
            # Equal prices still fail: there is no proven unique first identity.
            return None, True
        tied.sort(key=lambda e: e['sequence'])
    return tied[0], False


def _drawdown(path, initial):
    peak, maximum, fraction = initial, D(0), D(0)
    for point in path:
        equity = D(point['equity'])
        peak = max(peak, equity)
        drop = peak - equity
        maximum = max(maximum, drop)
        if peak > 0:
            fraction = max(fraction, drop / peak)
    return {'absolute_usdt': str(maximum), 'fraction_of_observed_peak': str(fraction),
            'scope': 'OBSERVED_POINTS_ONLY_NOT_CONTINUOUS_RISK_BOUND'}


def evaluate(plan, payload, information_as_of, market_event_cutoff, previous=None):
    # Do not inherit precision, exponent bounds or rounding from another analysis.
    try:
        with localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN)):
            return _evaluate(plan, payload, information_as_of, market_event_cutoff, previous)
    except DecimalException as exc:
        raise ContractError('Decimal arithmetic outside fixed 50-digit context') from exc


def _evaluate(plan, payload, information_as_of, market_event_cutoff, previous=None):
    """Recompute the accumulated prefix; immutable prior input must remain present.

    Times are separate: information_as_of includes delayed acquisition, whereas
    market_event_cutoff stops market events (never later than the original end).
    A previous kernel result must be passed whole. Recalculation checks its exact
    input/state, so callers cannot silently drop positions or alter past events.
    Caller-supplied completeness/coverage fields have no authority here.
    """
    ref = f"{plan.get('plan_id')}@{plan.get('version')}"
    sha = _hash(plan)
    if PLAN_HASHES.get(ref) != sha:
        raise ContractError('Unsupported or modified sealed plan; create/review a new evaluator version')
    info, cutoff = utc(information_as_of), utc(market_event_cutoff)
    effective, endpoint = utc(plan['effective_from']), utc(plan['evaluation_end'])
    if cutoff > info or cutoff > endpoint or info < utc(plan['available_at']):
        raise ContractError('Invalid information/market cutoff')
    events, event_hashes = _observations(payload, info, cutoff)
    opening_hash = None
    if previous:
        if previous.get('evaluator_version') != VERSION or previous.get('plan_hash') != sha:
            raise ContractError('Evaluator/plan migration requires an explicit reviewed correction')
        if utc(previous['market_event_cutoff']) > cutoff or utc(previous['information_as_of']) > info:
            raise ContractError('Continuation cutoff cannot move backwards')
        recomputed = evaluate(plan, previous['input_payload'], previous['information_as_of'], previous['market_event_cutoff'])
        if recomputed['simulation_state'] != previous['simulation_state']:
            raise ContractError('Previous state does not reproduce from frozen inputs')
        for ident, old_sha in previous['simulation_state']['event_hashes'].items():
            if event_hashes.get(ident) != old_sha:
                raise ContractError('Prior event removed or revised; correction required')
        if any(ident not in previous['simulation_state']['event_hashes'] and utc(event['event_at']) <= utc(previous['market_event_cutoff']) for event in events for ident in [event['event_id']]):
            raise ContractError('Late evidence enters prior evaluated interval; explicit correction required')
        opening_hash = _hash(previous['simulation_state'])
    quantity = D(plan['rules']['quantity_or_inventory']['base_quantity_btc'])
    direction = D(plan['rules']['quantity_or_inventory']['direction'])
    entry_at = utc(plan['rules']['entry']['scheduled_at'])
    entry_end = utc(plan['entry_valid_until'])
    exit_at = utc(plan['rules']['exit']['scheduled_at'])
    entry, ambiguous_entry = _first_trade(events, entry_at, entry_end)
    exit_fill, ambiguous_exit = _first_trade(events, exit_at, endpoint)
    if entry and previous:
        old_entry = previous['simulation_state'].get('entry_observation')
        old_exit = previous['simulation_state'].get('exit_observation')
        if (old_entry and old_entry != entry) or (old_exit and old_exit != exit_fill):
            raise ContractError('Late input changes selected fill; explicit correction required')
    state = {'version': VERSION, 'plan_hash': sha, 'currency': 'USDT', 'event_hashes': event_hashes,
             'inventory': None, 'entry_observation': entry, 'exit_observation': exit_fill if entry else None,
             'funding_observations': [], 'known_funding_cashflow': None, 'funding_cashflow': None,
             'last_market_event_at': events[-1]['event_at'] if events else None,
             'source_coverage': 'UNVERIFIED', 'actual_costs': None}
    signal = plan['rules']['signal']
    signal_age = (entry_at - utc(signal['event_at'])).total_seconds()
    if signal['observed_sign'] != 'POSITIVE' or not 0 <= signal_age <= 72 * 3600:
        raise ContractError('Whitelisted frozen signal no longer matches implementation contract')
    result = {'evaluator_version': VERSION, 'plan_ref': ref, 'plan_hash': sha,
              'information_as_of': information_as_of, 'market_event_cutoff': market_event_cutoff,
              'input_fingerprint': _hash(payload), 'input_payload': deepcopy(payload),
              'opening_state_hash': opening_hash, 'simulation_state': state,
              'evaluation_stage': 'WAITING_DATA', 'data_complete': False,
              'source_coverage': 'UNVERIFIED_NO_AUDITED_OFFICIAL_ADAPTER',
              'missing_capabilities': ['OFFICIAL_SOURCE_ADAPTER_NOT_IMPLEMENTED', 'SOURCE_COVERAGE_VERIFIER_NOT_IMPLEMENTED', 'FORMAL_REVIEW_STATE_MIGRATION_NOT_IMPLEMENTED'],
              'frozen_signal': {'dataset_hash': signal['dataset_hash'], 'event_at': signal['event_at'],
                                'age_at_scheduled_entry_seconds': str(signal_age), 'predicate_met': True,
                                'reevaluated_with_future_funding': False},
              'metrics': {'gross_price_pnl': None, 'realized_pnl': None, 'unrealized_pnl': None,
                          'funding_cashflow': None, 'net_pnl': None, 'actual_total_cost': None,
                          'holding_seconds': None, 'trade_count': None},
              'conditional_observed_input_metrics': None, 'scenarios': [],
              'baseline_comparison': {'refs': plan['baseline_refs'], 'state': 'NOT_JOINED',
                                      'scope': 'MATCHED_ABSOLUTE_QUANTITY_AND_TIME_NOT_BETA; NEVER_SUM_AS_ACCOUNT'},
              'limitations': ['Normalized observations are not proof of official provenance or complete coverage.',
                              'All calculated fills, funding and paths below are conditional on supplied observations.',
                              'Actual fees/slippage remain unknown; no scenario is an actual return.',
                              'No completion flag can establish FINAL, NOT_TRIGGERED, readiness or natural execution.']}
    if cutoff < effective:
        state.update(inventory='0', state='NOT_STARTED_BEFORE_EFFECTIVE')
        result['evaluation_stage'] = 'NOT_YET_EFFECTIVE'
        return result
    if ambiguous_entry or ambiguous_exit:
        result['evaluation_stage'] = 'PATH_AMBIGUOUS'
        state['state'] = 'UNRESOLVED_TRADE_ORDER'
        return result
    if entry is None:
        state['state'] = 'ENTRY_DATA_UNRESOLVED'
        return result
    entry_price = _positive(entry['price'])
    actual_entry = utc(entry['event_at'])
    actual_exit = utc(exit_fill['event_at']) if exit_fill else None
    terminal = actual_exit or cutoff
    state.update(inventory='0' if exit_fill else str(direction * quantity),
                 state='CONDITIONAL_CLOSED' if exit_fill else 'CONDITIONAL_OPEN')
    funding = [e for e in events if e['kind'] == 'funding' and actual_entry <= utc(e['event_at'])
               and (utc(e['event_at']) < actual_exit if actual_exit else utc(e['event_at']) <= terminal)]
    state['funding_observations'] = funding
    known_funding = sum((-direction * quantity * _positive(e['settlement_mark']) * decimal(e['rate'])
                         for e in funding if e.get('settlement_mark') is not None), D(0))
    missing_mark = any(e.get('settlement_mark') is None for e in funding)
    state['known_funding_cashflow'] = str(known_funding)
    marks = [e for e in events if e['kind'] == 'mark' and actual_entry <= utc(e['event_at']) <= terminal]
    valuation_points = [(utc(e['event_at']), _positive(e['price'])) for e in marks]
    valuation_points.extend((utc(e['event_at']), _positive(e['settlement_mark'])) for e in funding if e.get('settlement_mark') is not None)
    valuation_points.sort(key=lambda point: point[0])
    last_price = _positive(exit_fill['price']) if exit_fill else (valuation_points[-1][1] if valuation_points else None)
    gross = direction * quantity * (last_price - entry_price) if last_price is not None else None
    conditional = {'initial_notional_usdt': str(quantity * entry_price),
                   'gross_price_pnl': str(gross) if gross is not None else None,
                   'realized_price_pnl': str(gross) if exit_fill else '0',
                   'unrealized_price_pnl': '0' if exit_fill else (str(gross) if gross is not None else None),
                   'observed_funding_cashflow': None if missing_mark else str(known_funding),
                   'holding_seconds': str(D(str((terminal - actual_entry).total_seconds()))),
                   'trade_count': 2 if exit_fill else 1,
                   'entry_first_trade_proven': False, 'exit_first_trade_proven': False,
                   'funding_settlement_coverage_proven': False}
    result['conditional_observed_input_metrics'] = conditional
    # Mark points retain funding changes at their own timestamps; absent exact
    # settlement marks disable dependent scenario paths, never silently add zero.
    trajectory = [(actual_entry, 0, entry['event_id'], entry_price, D(0), False)]
    for e in marks:
        if actual_exit is None or utc(e['event_at']) < actual_exit:
            trajectory.append((utc(e['event_at']), 2, e['event_id'], _positive(e['price']), D(0), False))
    for e in funding:
        if e.get('settlement_mark') is not None:
            mark = _positive(e['settlement_mark'])
            trajectory.append((utc(e['event_at']), 1, e['event_id'], mark,
                               -direction * quantity * mark * decimal(e['rate']), False))
    if exit_fill:
        trajectory.append((actual_exit, 3, exit_fill['event_id'], _positive(exit_fill['price']), D(0), True))
    for fee in plan['cost_model']['scenario_per_side_fee_bps']:
        for slip in plan['cost_model']['scenario_per_side_slippage_bps']:
            cumulative_funding, path = D(0), []
            for at, _, ident, price, cashflow, closed in sorted(trajectory):
                cumulative_funding += cashflow
                traded_notional = quantity * (entry_price + (price if closed else D(0)))
                equity = quantity * entry_price + direction * quantity * (price - entry_price) + cumulative_funding - traded_notional * (D(fee) + D(slip)) / 10000
                path.append({'event_at': at.isoformat(), 'event_id': ident, 'equity': str(equity)})
            notional = quantity * (entry_price + (_positive(exit_fill['price']) if exit_fill else D(0)))
            fees, slippage = notional * D(fee) / 10000, notional * D(slip) / 10000
            net = gross + known_funding - fees - slippage if gross is not None and not missing_mark else None
            result['scenarios'].append({'fee_bps_each_side': fee, 'slippage_bps_each_side': slip,
                'assumption_only': True, 'source_coverage_proven': False,
                'observed_fees': str(fees), 'observed_slippage_cost': str(slippage),
                'conditional_net_pnl': str(net) if net is not None else None,
                'conditional_equity_path': path if not missing_mark else None,
                'observed_path_drawdown': _drawdown(path, quantity * entry_price) if not missing_mark else None})
    return result
