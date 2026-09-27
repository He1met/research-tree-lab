"""Transparent event ledger for evidence/tests, not an exchange execution engine.

Strategies must supply their frozen-rule events; this module does not invent
fills from coarse OHLC, load external strategy code or reconstruct missing LLM
decisions. All amounts use one explicitly declared quote currency.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation

from .common import ContractError, canonical, digest, utc


def decimal(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ContractError("Invalid decimal amount") from exc
    if not number.is_finite():
        raise ContractError("Non-finite amount")
    return number


def initial_state(initial_cash, currency):
    if not currency:
        raise ContractError("Quote currency must be explicit")
    return {"currency": currency, "cash_excluding_costs": str(decimal(initial_cash)), "inventory": "0",
            "known_fees": "0", "known_funding": "0", "known_exit_cost": "0",
            "costs_complete": True, "unknown_cost_event_ids": [], "last_event_at": None,
            "event_hashes": {}, "mark_price": None, "closed": False}


def replay_events(state, events, cutoff, effective_from=None, required_decision_refs=None):
    state = deepcopy(state)
    cutoff_dt = utc(cutoff)
    effective_dt = utc(effective_from) if effective_from else None
    previous_time = utc(state["last_event_at"]) if state.get("last_event_at") else None
    for event in events:
        ident = event.get("event_id")
        if not isinstance(ident, str) or not ident:
            raise ContractError("Every event needs stable identity")
        event_hash = digest(canonical(event))
        if ident in state["event_hashes"]:
            if state["event_hashes"][ident] != event_hash:
                raise ContractError("Same event identity has conflicting bytes")
            continue
        event_time, available = utc(event["event_time"]), utc(event["available_at"])
        if event_time > cutoff_dt or available > cutoff_dt:
            raise ContractError("Future/unavailable events cannot enter historical evaluation")
        if effective_dt and event_time < effective_dt:
            raise ContractError("Cannot evaluate before original lawful effective time")
        if previous_time and event_time < previous_time:
            raise ContractError("Out-of-order path; a revision is required")
        if event.get("currency") != state["currency"]:
            raise ContractError("Mixed quote units")
        decision_ref = event.get("decision_ref")
        if event.get("requires_llm_decision") and decision_ref not in (required_decision_refs or {}):
            raise ContractError("MISSING_PRIOR_MODEL_DECISION: never reconstruct after the event")
        if event.get("requires_llm_decision"):
            decision = required_decision_refs[decision_ref]
            if utc(decision["available_at"]) > event_time or not decision.get("output_hash"):
                raise ContractError("Model decision was not recorded before action")
        kind = event["kind"]
        if kind == "fill":
            quantity, price = decimal(event["quantity"]), decimal(event["price"])
            if price <= 0:
                raise ContractError("Fill price must be positive")
            state["inventory"] = str(decimal(state["inventory"]) + quantity)
            state["cash_excluding_costs"] = str(decimal(state["cash_excluding_costs"]) - quantity * price)
            cost, key = event.get("fee"), "known_fees"
        elif kind == "funding":
            # Positive amount is paid, negative amount is received; never assume zero.
            cost, key = event.get("amount"), "known_funding"
        elif kind == "exit_cost":
            cost, key = event.get("amount"), "known_exit_cost"
        elif kind == "mark":
            if decimal(event["price"]) <= 0:
                raise ContractError("Mark price must be positive")
            state["mark_price"] = str(decimal(event["price"]))
            cost, key = "0", None
        else:
            raise ContractError("Unknown ledger event kind")
        if cost is None:
            state["costs_complete"] = False
            state["unknown_cost_event_ids"].append(ident)
        elif key:
            state[key] = str(decimal(state[key]) + decimal(cost))
        state["last_event_at"] = event["event_time"]
        state["event_hashes"][ident] = event_hash
        previous_time = event_time
    inventory = decimal(state["inventory"])
    gross_equity = None if inventory and state["mark_price"] is None else decimal(state["cash_excluding_costs"]) + inventory * decimal(state["mark_price"] or "0")
    total_cost = sum((decimal(state[k]) for k in ("known_fees", "known_funding", "known_exit_cost")), Decimal("0"))
    state["gross_equity"] = str(gross_equity) if gross_equity is not None else None
    state["net_equity"] = str(gross_equity - total_cost) if gross_equity is not None and state["costs_complete"] else None
    # A cutoff never adds a closing trade or resets the inventory.
    return state


def ambiguous_bar_exit(low, high, stop, target, policy):
    low, high, stop, target = map(decimal, (low, high, stop, target))
    hit_stop, hit_target = low <= stop, high >= target
    if hit_stop and hit_target:
        if policy == "STOP_FIRST_CONSERVATIVE":
            return {"state": "ASSUMED_CONSERVATIVE", "exit_price": str(stop), "policy": policy}
        if policy == "REPORT_BOUNDS":
            return {"state": "PATH_AMBIGUOUS", "exit_price": None, "bounds": [str(stop), str(target)]}
        return {"state": "PATH_AMBIGUOUS", "exit_price": None, "requires_finer_data": True}
    return {"state": "UNAMBIGUOUS" if hit_stop or hit_target else "NOT_TRIGGERED",
            "exit_price": str(stop) if hit_stop else str(target) if hit_target else None}
