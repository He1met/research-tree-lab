"""Schema v1 identity, reference and temporal constraints for actual commits."""
from __future__ import annotations

from .common import ContractError, safe_id, utc, canonical, digest

SCHEMAS = {1, "1", "1.0"}
IDENTITIES = {
    "round": "round_id", "plan": "plan_id", "run": "run_id",
    "review": "review_id", "feedback": "feedback_id", "decision": "decision_id",
    "readiness": "assessment_id", "product": "product_id", "discovery": "discovery_id",
    "review_batch": "batch_id", "publication": "publication_id",
    "dataset": "dataset_id", "method": "method_id", "evidence": "evidence_id",
}
ROLE_TYPES = {
    "discovery": {"discovery", "product", "dataset", "evidence", "decision"},
    "research": {"round", "plan", "run", "decision", "readiness", "product", "dataset", "method", "evidence"},
    "review": {"review", "feedback", "review_batch", "dataset", "evidence"},
    "publish": {"publication"},
}
FINAL_STAGES = {"FINAL", "EXPIRED_UNTRIGGERED", "FINAL_NOT_TRIGGERED"}


def record_ref(record):
    kind = record.get("record_type")
    if kind not in IDENTITIES:
        raise ContractError("Unknown record_type")
    ident = safe_id(record.get(IDENTITIES[kind]))
    if kind == "plan":
        version = record.get("version")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise ContractError("Plan version must be a positive integer")
        ref = f"{ident}@{version}"
        if record.get("plan_ref", ref) != ref:
            raise ContractError("plan_ref must bind plan_id@version")
        return ref
    if kind in {"product", "dataset", "method"}:
        version = record.get("spec_version" if kind == "product" else "version")
        return safe_id(f"{ident}@{version}") if version is not None else ident
    if kind == "run" and record.get("attempt_id"):
        return safe_id(f"{ident}@{safe_id(record['attempt_id'])}")
    return ident


def validate_record(record, role):
    if not isinstance(record, dict) or record.get("schema_version") not in SCHEMAS:
        raise ContractError("UNSUPPORTED_SCHEMA: expected schema v1")
    kind = record.get("record_type")
    if kind not in ROLE_TYPES.get(role, set()):
        raise ContractError("ROLE_WRITE_DENIED: role cannot submit this object")
    ref = record_ref(record)
    if record.get("template_only") is True or record.get("record_state") == "DRAFT_NOT_COMMITTED":
        raise ContractError("Templates/drafts cannot become formal records")
    if not isinstance(record.get("synthetic"), bool):
        raise ContractError("synthetic must be explicitly true or false")
    created, available = utc(record.get("created_at")), utc(record.get("available_at"))
    if available < created:
        raise ContractError("Information availability cannot predate record creation")
    for key in ("data_cutoff", "as_of", "sealed_at"):
        if record.get(key) and utc(record[key]) > available:
            raise ContractError(f"Future {key} exceeds information availability")
    if kind == "round":
        if not (record.get("question") or record.get("title")) or not record.get("mechanism"):
            raise ContractError("Research round requires question and mechanism")
        if len(set(record.get("additional_source_refs", []))) != len(record.get("additional_source_refs", [])):
            raise ContractError("Repeated source refs")
    if kind == "plan":
        safe_id(record.get("round_id"))
        if record.get("account_input_required") is True:
            raise ContractError("Account integration is outside this project")
        if record.get("replay_eligibility") in {"ELIGIBLE", "REPLAYABLE"}:
            if not all(record.get("rules", {}).get(field) for field in ("signal", "entry", "quantity_or_inventory", "exit", "reentry", "termination")):
                raise ContractError("Replayable plan requires all frozen rules")
            for field in ("instrument_ref", "method_ref", "cost_model_ref", "fill_model_ref", "evaluation_contract_ref", "sealed_at", "effective_from", "entry_valid_until", "evaluation_end"):
                if not record.get(field):
                    raise ContractError("Replayable plan missing " + field)
            if not utc(record["sealed_at"]) <= utc(record["effective_from"]) <= utc(record["entry_valid_until"]) <= utc(record["evaluation_end"]):
                raise ContractError("Invalid seal/effective/entry/evaluation order")
    if kind == "review":
        if not isinstance(record.get("revision"), int) or record["revision"] < 1:
            raise ContractError("Review requires positive revision")
        if not record.get("plan_hash") or not record.get("review_method_ref"):
            raise ContractError("Review requires exact plan_hash and independent review_method_ref")
        utc(record.get("data_cutoff"))
        if record.get("supersedes") and not record.get("correction_reason"):
            raise ContractError("Correction requires explicit reason")
        if record.get("evaluation_stage") in {"STAGE", "IN_PROGRESS", "FINAL"} and not record.get("simulation_state"):
            raise ContractError("Simulation review must preserve carry state")
    if kind == "readiness":
        if record.get("account_eligibility", "NOT_ASSESSED") != "NOT_ASSESSED" or record.get("automatic_trade_authorized", False) is not False:
            raise ContractError("Readiness must never grant account/trading authorization")
    canonical(record)  # Reject NaN/Infinity and unserializable values.
    return ref


def semantic_refs(record):
    """References essential to lineage, evaluator independence and replay."""
    kind = record["record_type"]
    refs = []
    fields = {
        "round": ["parent_round_id", "selected_plan_ref"],
        "plan": ["round_id"],
        "run": ["round_id", "plan_ref", "method_ref"],
        "review": ["plan_ref", "supersedes", "previous_review_ref", "batch_ref"],
        "feedback": ["review_ref"],
        "decision": ["feedback_ref", "source_review_ref", "successor_round_id"],
        "readiness": ["plan_ref"],
    }.get(kind, [])
    for field in fields:
        if record.get(field):
            refs.append(record[field])
    for field in ("derived_from_feedback_refs", "source_review_refs", "plan_refs", "feedback_refs", "input_record_refs"):
        refs.extend(record.get(field, []))
    return sorted(set(refs))


def validate_relationships(records):
    for ref, item in records.items():
        kind = item["record_type"]
        for target in semantic_refs(item):
            if target not in records:
                raise ContractError(f"MISSING_REFERENCE: {ref} -> {target}")
            if utc(records[target]["available_at"]) > utc(item["available_at"]):
                raise ContractError("Reference information was unavailable when record was sealed")
        if kind == "round":
            seen, cur = {ref}, item.get("parent_round_id")
            while cur:
                if cur in seen or records[cur]["record_type"] != "round":
                    raise ContractError("Invalid/cyclic research lineage")
                seen.add(cur)
                cur = records[cur].get("parent_round_id")
            selected = item.get("selected_plan_ref")
            if selected and (records[selected]["record_type"] != "plan" or records[selected]["round_id"] != ref):
                raise ContractError("Selected plan belongs to a different round")
        if kind == "plan" and records[item["round_id"]]["record_type"] != "round":
            raise ContractError("Plan round reference has wrong type")
        if kind == "run" and item.get("method_ref") and records[item["method_ref"]]["record_type"] != "method":
            raise ContractError("Run method reference has wrong type")
        if kind == "review":
            plan = records[item["plan_ref"]]
            if plan["record_type"] != "plan" or item["plan_hash"] != digest(canonical(plan)):
                raise ContractError("Review plan hash mismatch")
            if item.get("evaluation_stage") in FINAL_STAGES:
                if not plan.get("evaluation_end") or utc(item["data_cutoff"]) < utc(plan["evaluation_end"]):
                    raise ContractError("Cannot finalize before frozen evaluation end")
                if item.get("data_complete") is not True:
                    raise ContractError("Cannot finalize without complete path")
            previous_ref = item.get("supersedes") or item.get("previous_review_ref")
            if previous_ref:
                previous = records[previous_ref]
                if previous["record_type"] != "review" or previous["plan_ref"] != item["plan_ref"]:
                    raise ContractError("Review chain crosses plan versions")
                if utc(previous["available_at"]) >= utc(item["available_at"]):
                    raise ContractError("Review chain is not chronological")
                if item.get("supersedes") and item["revision"] <= previous["revision"]:
                    raise ContractError("Correction revision must increase")
                if not item.get("supersedes") and item.get("opening_state_hash") != digest(canonical(previous.get("simulation_state"))):
                    raise ContractError("Cross-day state continuity failed")
                if not item.get("supersedes") and utc(item["data_cutoff"]) < utc(previous["data_cutoff"]):
                    raise ContractError("Cross-day cursor cannot move backwards")
        if kind == "feedback" and records[item["review_ref"]]["record_type"] != "review":
            raise ContractError("Feedback must bind a formal review")
