"""Version-bound execution conditions, independently degraded by publisher."""
from .common import ContractError, utc
from .contracts import SCHEMAS, validate_record
from urllib.parse import urlsplit

REQUIRED_CHECKS = (
    "target_contract_verified", "rules_complete", "execution_model_supported",
    "quantity_cost_model_explicit", "target_data_current",
    "technical_validation_complete", "references_intact",
)


def assess(store, assessment, records, now, invalidated_refs=None):
    invalidated_refs = set(invalidated_refs or [])
    def result(state, reason):
        return dict(assessment, state=state, reason=reason,
                    account_eligibility="NOT_ASSESSED", automatic_trade_authorized=False)
    if assessment.get("schema_version") not in SCHEMAS:
        return result("UNKNOWN", "Unsupported assessment schema")
    if assessment.get("synthetic") is not False:
        return result("DEMO_ONLY", "Synthetic provenance cannot support production execution")
    plan_ref = assessment.get("plan_ref")
    plan = records.get(plan_ref)
    if not plan or plan.get("record_type") != "plan" or plan.get("synthetic") is not False:
        return result("UNKNOWN", "Exact original plan version is unavailable")
    if assessment.get("policy_ref") != "execution-conditions-v1":
        return result("UNKNOWN", "Missing or unsupported fixed readiness policy")
    if assessment.get("invalidated") or plan_ref in invalidated_refs or assessment.get("assessment_id") in invalidated_refs:
        return result("INVALIDATED", "Bound plan/evidence requires recheck")
    fallback = "REPLAYABLE_ONLY" if plan.get("replay_eligibility") in {"ELIGIBLE", "REPLAYABLE"} else "RESEARCH_ONLY"
    if plan.get("replay_eligibility") not in {"ELIGIBLE", "REPLAYABLE"}:
        return result("RESEARCH_ONLY", "Plan is not eligible for exact-rule trading replay")
    try:
        validate_record(plan, "research")
    except (ContractError, TypeError, KeyError):
        return result("RESEARCH_ONLY", "Frozen plan rules or execution contract are incomplete")
    # Evidence claiming 'references_intact' cannot substitute for actual identity
    # resolution. Exact execution methods and data must remain readable.
    try:
        for name in ("method_ref", "cost_model_ref", "fill_model_ref", "evaluation_contract_ref"):
            store.resolve_evidence(plan[name], records)
        if not plan.get("dataset_refs"):
            raise ContractError("Frozen plan has no target dataset version")
        for ref in plan["dataset_refs"]:
            resolved = store.resolve_evidence(ref, records)
            if resolved["kind"] == "record":
                data_record = resolved["record"]
                if data_record.get("record_type") != "dataset" or data_record.get("data_role") != "TARGET" or data_record.get("instrument_ref") != plan.get("instrument_ref"):
                    raise ContractError("Referenced data is not the exact target contract")
                store.resolve_evidence(data_record["data_ref"], records)
            else:
                raise ContractError("A target dataset needs versioned provenance and units")
        if not any(r.get("record_type") == "product" and r.get("synthetic") is False
                   and r.get("instrument_ref") == plan.get("instrument_ref") for r in records.values()):
            raise ContractError("Exact target contract is absent from product registry")
    except (ContractError, TypeError, KeyError, OSError):
        return result("UNKNOWN", "Frozen plan dependencies do not resolve to exact methods and target data")
    try:
        current, as_of = utc(now), utc(assessment.get("as_of"))
        valid_until = utc(assessment.get("valid_until"))
        effective = utc(plan.get("effective_from"))
        if utc(assessment.get("effective_from")) != effective:
            return result("UNKNOWN", "Assessment effective boundary differs from original plan")
        if as_of > current or valid_until <= as_of or valid_until > utc(plan.get("entry_valid_until")):
            return result("UNKNOWN", "Evidence time or original entry window cannot support validity")
        if current >= valid_until:
            return result("EXPIRED", "New-entry evidence expired; no claim of position liquidation")
        if current < effective:
            return result("NOT_YET_EFFECTIVE", "Original plan is not effective yet")
    except (TypeError, ValueError):
        return result("UNKNOWN", "Missing timezone-aware validity boundaries")

    def verify_source(ref, visiting):
        if ref in visiting or ref in invalidated_refs:
            raise ContractError("Cyclic or invalidated source chain")
        resolved = store.resolve_evidence(ref, records)
        if resolved["kind"] != "record":
            raise ContractError("A source must have a committed provenance record")
        source = resolved["record"]
        if source.get("synthetic") is not False or source.get("invalidated") or source.get("evidence_status") != "VERIFIED":
            raise ContractError("Source is synthetic, invalidated or unverified")
        if utc(source["available_at"]) > as_of or utc(source.get("observed_at")) > as_of or utc(source.get("valid_until")) < valid_until:
            raise ContractError("Source timing does not support current evidence")
        source_url, artifacts = source.get("source_url"), source.get("artifact_refs", [])
        if source_url and artifacts:
            url = urlsplit(source_url)
            if url.scheme != "https" or not url.hostname or url.username or url.password or url.hostname in {"localhost", "127.0.0.1", "::1"}:
                raise ContractError("Source provenance requires a public HTTPS origin")
            for artifact_ref in artifacts:
                artifact = store.resolve_evidence(artifact_ref, records)
                if artifact["kind"] not in {"data", "attachment"}:
                    raise ContractError("Source capture must resolve to actual immutable bytes")
        else:
            if not source.get("source_refs"):
                raise ContractError("Source chain ends without captured public source bytes")
            for source_ref in source["source_refs"]:
                verify_source(source_ref, visiting | {ref})

    def verify_refs(refs, check_name):
        if not isinstance(refs, list) or not refs:
            raise ContractError("Missing evidence refs")
        for ref in refs:
            if ref in invalidated_refs:
                raise ContractError("Evidence has been invalidated")
            resolved = store.resolve_evidence(ref, records)
            # A bare file hash proves integrity, not observation scope or freshness.
            if resolved["kind"] != "record":
                raise ContractError("Raw evidence requires an associated scoped provenance record")
            evidence = resolved["record"]
            if evidence.get("synthetic") is not False or evidence.get("invalidated"):
                raise ContractError("Synthetic/invalid evidence")
            if evidence.get("evidence_status") != "VERIFIED" or not evidence.get("source_refs"):
                raise ContractError("Evidence has not been source-verified")
            if check_name not in evidence.get("check_names", []) or not evidence.get("verification_method"):
                raise ContractError("Evidence does not attest this particular check")
            if evidence.get("plan_ref") != plan_ref and not (
                evidence.get("instrument_ref") == plan.get("instrument_ref") and check_name == "target_contract_verified"
            ):
                raise ContractError("Evidence scope does not match exact plan version")
            if utc(evidence["available_at"]) > as_of or utc(evidence.get("observed_at")) > as_of or utc(evidence.get("valid_until")) < valid_until:
                raise ContractError("Evidence cannot support observation/validity bounds")
            for source_ref in evidence.get("artifact_refs", []):
                store.resolve_evidence(source_ref, records)
            for source_ref in evidence["source_refs"]:
                verify_source(source_ref, {ref})

    for name in REQUIRED_CHECKS:
        check = (assessment.get("checks") or {}).get(name) or {}
        if check.get("status") != "PASS":
            return result(fallback, "Missing verified condition: " + name)
        try:
            if utc(check.get("observed_at")) > as_of or utc(check.get("valid_until")) < valid_until:
                return result("UNKNOWN", "Check timing does not support validity: " + name)
            verify_refs(check.get("evidence_refs"), name)
        except (ContractError, TypeError, KeyError, OSError):
            return result("UNKNOWN", "Evidence unresolved, stale or outside plan scope: " + name)
    if assessment.get("trigger_status") == "NOT_MET":
        return result("RULES_READY_WAITING_TRIGGER", "All conditions checked; original trigger is not met")
    if assessment.get("trigger_status") != "MET":
        return result("UNKNOWN", "Trigger not observed")
    try:
        verify_refs(assessment.get("trigger_evidence_refs"), "trigger")
    except (ContractError, TypeError, KeyError, OSError):
        return result("UNKNOWN", "Trigger evidence unresolved or outside exact plan scope")
    return result("EXECUTION_READY_AS_OF", "Market/rule conditions verified at the recorded observation time")
