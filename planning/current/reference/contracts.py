"""Pure reference logic, not a production executor, evidence attestor or publisher.

Only Python's standard library is used. Nothing calls a model, downloads data,
executes strategy code, reads account information, or publishes externally.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any

REQUIRED_CHECKS = (
    "target_contract_verified", "rules_complete", "execution_model_supported",
    "quantity_cost_model_explicit", "target_data_current",
    "technical_validation_complete", "references_intact",
)


def utc(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("A timezone-aware ISO timestamp is required")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Naive timestamps are not accepted")
    return result


def readiness(assessment: dict[str, Any], now: str) -> dict[str, Any]:
    """Classify supplied evidence fields; DOES NOT verify evidence authenticity.

    Production must resolve each evidence reference, validate its scope/version,
    check new invalidations, and enforce the selected policy before using this.
    """
    def result(state: str, reason: str) -> dict[str, Any]:
        return {"state": state, "reason": reason,
                "account_eligibility": "NOT_ASSESSED",
                "automatic_trade_authorized": False}

    if assessment.get("synthetic") is not False:
        return result("DEMO_ONLY", "Synthetic/unspecified provenance cannot be live-ready")
    if assessment.get("invalidated") is True:
        return result("INVALIDATED", "Bound evidence or original plan was invalidated")
    try:
        current = utc(now)
        as_of = utc(assessment.get("as_of"))
        valid_until = utc(assessment.get("valid_until"))
        effective_from = utc(assessment.get("effective_from"))
        if as_of > current or valid_until <= as_of:
            return result("UNKNOWN", "Invalid or future evidence timestamp")
        if current >= valid_until:
            return result("EXPIRED", "Evidence or entry window has expired")
        if current < effective_from:
            return result("NOT_YET_EFFECTIVE", "The original plan is not yet effective")
    except (ValueError, TypeError):
        return result("UNKNOWN", "Missing/invalid timezone-aware validity boundary")
    if not assessment.get("plan_ref"):
        return result("UNKNOWN", "No exact plan version bound")
    fallback = "REPLAYABLE_ONLY" if assessment.get("replay_eligible") is True else "RESEARCH_ONLY"
    checks = assessment.get("checks") or {}
    for name in REQUIRED_CHECKS:
        check = checks.get(name) or {}
        if check.get("status") != "PASS" or not check.get("evidence_refs"):
            return result(fallback, "Missing verified check: " + name)
        try:
            if utc(check.get("observed_at")) > as_of or utc(check.get("valid_until")) < valid_until:
                return result("UNKNOWN", "Check cannot support overall observation/validity: " + name)
        except (TypeError, ValueError):
            return result("UNKNOWN", "Missing check timing: " + name)
    trigger = assessment.get("trigger_status")
    if trigger == "NOT_MET":
        return result("RULES_READY_WAITING_TRIGGER", "Rules ready; trigger not met")
    if trigger != "MET" or not assessment.get("trigger_evidence_refs"):
        return result("UNKNOWN", "Trigger evidence is not established")
    return result("EXECUTION_READY_AS_OF", "Market/rule conditions satisfied as of evidence time")


def _unique(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        ident = item.get(key)
        if not isinstance(ident, str) or not ident or ident in out:
            raise ValueError(f"Missing/duplicate {key}: {ident}")
        out[ident] = item
    return out


def validate_fixture(data: dict[str, Any]) -> None:
    if data.get("schema_version") != "1.0":
        raise ValueError("Unsupported schema version")
    rounds = _unique(data.get("rounds", []), "round_id")
    plans = _unique(data.get("plans", []), "plan_ref")
    reviews = _unique(data.get("reviews", []), "review_id")
    feedback = _unique(data.get("feedback", []), "feedback_id")
    for ident, item in rounds.items():
        utc(item["available_at"])
        parent = item.get("parent_round_id")
        if parent is not None and parent not in rounds:
            raise ValueError("Missing parent: " + str(parent))
        if item.get("selected_plan_ref") is not None:
            selected = plans.get(item["selected_plan_ref"])
            if not selected or selected["round_id"] != ident:
                raise ValueError("Selected plan belongs to another/missing round")
        visited = {ident}
        cur = parent
        while cur is not None:
            if cur in visited:
                raise ValueError("Round derivation cycle")
            visited.add(cur)
            cur = rounds[cur].get("parent_round_id")
        for ref in item.get("derived_from_feedback", []):
            if ref not in feedback:
                raise ValueError("Missing derivation feedback")
    for item in plans.values():
        if item["round_id"] not in rounds:
            raise ValueError("Plan round does not exist")
        utc(item["available_at"])
    for item in reviews.values():
        if item["plan_ref"] not in plans:
            raise ValueError("Review plan does not exist")
        utc(item["available_at"])
        if utc(item["data_cutoff"]) > utc(item["available_at"]):
            raise ValueError("Review uses future data")
        previous = item.get("supersedes")
        if previous:
            if previous not in reviews or reviews[previous]["plan_ref"] != item["plan_ref"]:
                raise ValueError("Invalid correction link")
            if utc(reviews[previous]["available_at"]) >= utc(item["available_at"]):
                raise ValueError("Correction does not follow original")
    for item in feedback.values():
        if item["review_id"] not in reviews:
            raise ValueError("Feedback has no source review")
        utc(item["available_at"])


def make_snapshot(data: dict[str, Any], as_of: str, *, demo: bool = False) -> dict[str, Any]:
    """Illustrate file -> view model. Production must add state histories,
    evidence resolution, pagination, manifest commit barriers and permission checks.
    """
    validate_fixture(data)
    at = utc(as_of)
    def visible(item: dict[str, Any]) -> bool:
        return (demo or item.get("synthetic") is False) and utc(item["available_at"]) <= at
    rounds = {r["round_id"]: r for r in data["rounds"] if visible(r)}
    plans = {p["plan_ref"]: p for p in data["plans"] if visible(p) and p["round_id"] in rounds}
    reviews = {r["review_id"]: r for r in data["reviews"] if visible(r) and r["plan_ref"] in plans}
    feedback = {f["feedback_id"]: f for f in data["feedback"] if visible(f) and f["review_id"] in reviews}
    nodes, edges = [], []
    for ident, item in sorted(rounds.items()):
        parent = item.get("parent_round_id")
        generation, cur = 1, parent
        while cur:
            if cur not in rounds:
                raise ValueError("Historical snapshot lacks known ancestor")
            generation += 1
            cur = rounds[cur].get("parent_round_id")
        plan_refs = sorted(p["plan_ref"] for p in plans.values() if p["round_id"] == ident)
        review_refs = sorted(r["review_id"] for r in reviews.values() if r["plan_ref"] in plan_refs)
        selected = item.get("selected_plan_ref")
        eligible = [r for r in reviews.values() if r["plan_ref"] == selected]
        latest = max(eligible, key=lambda r: (utc(r["available_at"]), r["revision"]), default=None)
        nodes.append({"id": ident, "kind": "research_round", "title": item["title"],
                      "generation": generation, "parent_round_id": parent,
                      "plan_refs": plan_refs, "review_refs": review_refs,
                      "feedback_refs": sorted(f["feedback_id"] for f in feedback.values() if f["review_id"] in review_refs),
                      "selected_plan_ref": selected if selected in plans else None,
                      "latest_review_ref": latest["review_id"] if latest else None,
                      "net_return_fraction": latest.get("net_return_fraction") if latest else None,
                      "is_synthetic": item.get("synthetic") is not False})
        if parent:
            edges.append({"source": parent, "target": ident, "relation": "DERIVED_FROM",
                          "feedback_refs": [f for f in item.get("derived_from_feedback", []) if f in feedback]})
    return {"schema_version": "1.0", "mode": "SYNTHETIC_UI_ONLY" if demo else "PRODUCTION_NO_DEMO_FALLBACK",
            "as_of": as_of, "round_count": len(nodes), "nodes": nodes, "edges": edges}
