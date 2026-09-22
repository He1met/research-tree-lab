"""Freeze complete plan registry and preserve incremental evaluator state."""
from .common import ContractError, canonical, digest, utc
from .contracts import FINAL_STAGES


def freeze_batch(store, batch_id, cutoff=None, trigger_origin="MANUAL_SAFE_TEST", native_task_ref=None):
    cutoff = cutoff or store.clock()
    records, meta, anomalies = store.load(strict=True)
    now = store.clock()
    plans = {ref: r for ref, r in records.items() if r["record_type"] == "plan" and r.get("synthetic") is False
             and utc(r["available_at"]) <= utc(cutoff) and utc(meta[ref]["committed_at"]) <= utc(cutoff)}
    reviews = [r for ref, r in records.items() if r["record_type"] == "review" and utc(r["available_at"]) <= utc(cutoff)
               and utc(meta[ref]["committed_at"]) <= utc(cutoff)]
    items = []
    for ref, plan in sorted(plans.items()):
        previous = max([r for r in reviews if r["plan_ref"] == ref], key=lambda r: (utc(r["available_at"]), r["revision"]), default=None)
        eligible = plan.get("replay_eligibility") in {"ELIGIBLE", "REPLAYABLE", "METHOD_OBSERVATION_ONLY"}
        disposition = "REVIEW_REQUIRED" if eligible else "RULES_INCOMPLETE"
        if plan.get("replay_eligibility") in {"INCOMPLETE_DATA", "WAITING_DATA"}:
            disposition = "WAITING_DATA"
        if previous and previous.get("evaluation_stage") in FINAL_STAGES:
            disposition = "REUSE_FINAL_UNLESS_INPUT_OR_EVALUATOR_CHANGED"
        items.append({"plan_ref": ref, "plan_hash": digest(canonical(plan)), "disposition": disposition,
                      "previous_review_ref": previous["review_id"] if previous else None,
                      "opening_state_hash": digest(canonical(previous.get("simulation_state"))) if previous else None,
                      "previous_input_fingerprint": previous.get("input_fingerprint") if previous else None,
                      "previous_evaluator_version": previous.get("evaluator_version") if previous else None,
                      "product_refs": plan.get("product_refs", [])})
    return {"schema_version": "1.0", "record_type": "review_batch", "batch_id": batch_id,
            "created_at": now, "available_at": now, "synthetic": False,
            "frozen_at": cutoff, "cutoff": cutoff, "plan_refs": sorted(plans), "items": items,
            "complete": not items, "trigger_origin": trigger_origin, "native_task_ref": native_task_ref,
            "disclosure": {"visibility": "PUBLIC", "license": "OWN_ANALYSIS"}}


def should_reuse_final(previous, input_fingerprint, evaluator_version):
    return bool(previous and previous.get("evaluation_stage") in FINAL_STAGES
                and previous.get("input_fingerprint") == input_fingerprint
                and previous.get("evaluator_version") == evaluator_version)


def verify_batch_coverage(batch, records):
    expected = set(batch["plan_refs"])
    actual = {}
    for ref, record in records.items():
        if record["record_type"] == "review" and record.get("batch_ref") == batch["batch_id"]:
            if record["plan_ref"] not in expected:
                raise ContractError("Review belongs to a plan outside the frozen batch")
            actual.setdefault(record["plan_ref"], []).append(ref)
    return {"registered": len(expected), "reviewed": len(actual), "missing": sorted(expected - set(actual)),
            "coverage_complete": expected == set(actual), "review_refs": actual}
