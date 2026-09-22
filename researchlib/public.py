"""Explicit public projection and recursive content checks (no raw handoff export)."""
from __future__ import annotations

import io
import re
import tarfile
import zipfile
from pathlib import PurePosixPath

from .common import ContractError, canonical, safe_relative

PUBLIC_LICENSES = {"CC0-1.0", "CC-BY-4.0", "MIT", "Apache-2.0", "FACTS_ONLY", "PUBLIC_DOMAIN", "OWN_ANALYSIS"}
TEXT_SUFFIXES = {".json", ".md", ".txt", ".csv", ".tsv", ".py", ".js", ".ts", ".toml", ".yaml", ".yml", ".lock"}
SECRET_PATTERNS = (
    ("PRIVATE_LOCAL_PATH", re.compile(r"(?:/Users/|/home/|/private/var/|[A-Za-z]:\\Users\\)")),
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
    ("TOKEN", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{20,})\b")),
    ("BEARER", re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/-]{16,}")),
    ("CREDENTIAL", re.compile(r'''(?i)["']?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)["']?\s*[:=]\s*["'](?!REDACTED|UNKNOWN|null|NOT_)[^"']{8,}["']''')),
    ("URL_CREDENTIAL", re.compile(r"https?://[^\s/:]+:[^\s/@]+@")),
    ("SIGNED_URL", re.compile(r"(?i)[?&](?:access_token|token|signature|x-amz-signature|credential|key)=[^&\s]{6,}")),
)

COMMON_FIELDS = {
    "schema_version", "record_type", "record_state", "synthetic", "created_at", "available_at",
    "source_refs", "source_urls", "artifact_refs", "evidence_refs", "input_record_refs", "disclosure",
    "title", "summary", "description", "limitations", "status", "status_events", "next_action",
    "evidence_stage", "data_cutoff", "research_question", "hypothesis", "counterevidence",
    "facts", "findings", "results", "methodology", "data_role", "license", "source_citations",
    "completion_criteria", "restart_conditions", "scope", "units", "provenance", "unknowns",
    "state", "report_ref", "sources", "account_eligibility", "automatic_trade_authorized",
}
TYPE_FIELDS = {
    "round": {"round_id", "parent_round_id", "derived_from_feedback_refs", "additional_source_refs", "product_refs", "question", "mechanism", "purpose_kind", "input_snapshot_ref", "plan_refs", "selected_plan_ref", "plan_summary", "review_summary", "feedback_summary", "mechanism_fingerprint", "variant_of", "replication_of", "not_natural_feedback_loop"},
    "plan": {"plan_id", "plan_ref", "version", "round_id", "instrument_ref", "product_refs", "method_ref", "dataset_refs", "source_review_refs", "candidate_set_ref", "baseline_refs", "selection_rationale", "rules", "cost_model_ref", "fill_model_ref", "evaluation_contract_ref", "sealed_at", "public_visibility_ref", "effective_from", "entry_valid_until", "evaluation_end", "replay_eligibility", "account_input_required", "sample_role", "comparison_group", "parameters"},
    "run": {"run_id", "attempt_id", "request_key", "round_id", "plan_ref", "started_at", "completed_at", "stage", "code_ref", "dataset_refs", "metrics", "result_refs", "error", "trigger_origin", "native_task_ref", "invocation_evidence_ref"},
    "review": {"review_id", "plan_ref", "batch_ref", "revision", "supersedes", "correction_reason", "plan_hash", "review_method_ref", "dataset_refs", "evaluation_stage", "simulation_state", "metrics", "baseline_comparison", "feedback_refs", "previous_review_ref", "opening_state_hash", "data_complete", "net_return_fraction", "sample_role", "coverage", "disposition", "evaluator_version", "input_fingerprint"},
    "feedback": {"feedback_id", "review_ref", "supported_facts", "interpretation", "alternative_explanations", "proposed_question", "what_changes", "comparison", "required_data", "adoption_decision_refs"},
    "decision": {"decision_id", "feedback_ref", "source_review_ref", "successor_round_id", "decision", "reason", "adopted_changes", "read_input_refs", "discovery_ref", "priority", "deferred_reason", "recheck_at"},
    "readiness": {"assessment_id", "plan_ref", "policy_ref", "as_of", "valid_until", "effective_from", "replay_eligible", "invalidated", "checks", "trigger_status", "trigger_evidence_refs", "state", "reason", "account_eligibility", "automatic_trade_authorized"},
    "product": {"product_id", "spec_version", "display_name", "name", "instrument_ref", "target_contract", "reference_instrument", "venue", "active", "capabilities", "specification", "settlement_currency", "native_code", "price_types", "data_sources", "fees", "funding", "calendar", "gaps", "verification_status", "evidence_status", "observed_at", "valid_until"},
    "discovery": {"discovery_id", "product_refs", "question", "mechanism", "purpose_kind", "novelty", "existing_work_refs", "baseline", "required_data", "proposed_round_id", "seed_category", "queue_state"},
    "review_batch": {"batch_id", "frozen_at", "plan_refs", "items", "cutoff", "complete", "coverage", "trigger_origin", "native_task_ref"},
    "publication": {"publication_id", "snapshot_id", "pages_url", "repository", "published_at", "verified_at", "remote_commit", "readback_hash", "archive_status", "recovery_status", "source_record_refs"},
    "dataset": {"dataset_id", "version", "instrument_ref", "product_refs", "source_url", "acquired_at", "event_start", "event_end", "published_at", "data_available_at", "format", "granularity", "data_ref", "sha256", "bytes", "normalization", "columns", "quality", "redistribution"},
    "method": {"method_id", "version", "method_ref", "code_ref", "code_hash", "environment_ref", "parameters", "algorithm", "validation_refs", "evaluator_role"},
    "evidence": {"evidence_id", "plan_ref", "instrument_ref", "evidence_status", "observed_at", "valid_until", "invalidated", "check_names", "source_url", "source_excerpt", "verification_method"},
}
TYPE_FIELDS["plan"].update({"product_id", "cost_model", "evaluation_contract", "replay_missing", "current_execution_conditions", "natural_run_status"})
TYPE_FIELDS["plan"].add("input_roles")
TYPE_FIELDS["round"].update({"mechanism_identity", "novelty_claim", "novelty_evidence_refs", "duplicate_of", "source_review_refs"})
TYPE_FIELDS["run"].update({"actual_trigger", "natural_trigger", "receipt"})
TYPE_FIELDS["run"].update({"economic_evidence", "actual_trade_result"})
TYPE_FIELDS["discovery"].update({"seed_code", "restart_condition", "defer_reason", "counts_as_completed_economic_research", "mechanism_signature", "round_id"})
TYPE_FIELDS["decision"].update({"source_round_ref", "derived_round_ref", "source_feedback_ref"})
TYPE_FIELDS["product"].update({"contract_face_value", "contract_kind", "contract_multiplier", "data_source", "displayed_max_leverage", "enabled", "face_value_unit", "funding_sample", "funding_schedule", "minimum_quantity_contracts", "native_code_evidence", "normalized_format", "price_roles", "price_tick_usdt", "quantity_step_contracts", "raw_format", "readiness", "reference_underlying", "rule_observation_recorded_at", "rule_valid_until"})


def scan_bytes(name, data, depth=0, budget=None):
    """Reject secrets and unsafe nested archive members without extracting them."""
    safe_relative(name)
    if depth > 4:
        raise ContractError("Archive nesting exceeds public scanner policy")
    budget = budget if budget is not None else [64 * 1024 * 1024]
    budget[0] -= len(data)
    if budget[0] < 0:
        raise ContractError("Archive exceeds public scanner byte budget")
    suffix = PurePosixPath(name).suffix.lower()
    if zipfile.is_zipfile(io.BytesIO(data)):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            if len(members) > 10000:
                raise ContractError("Archive member count exceeds policy")
            for member in members:
                safe_relative(member.filename.rstrip("/"))
                if (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ContractError("Archive symlink rejected")
                if member.is_dir():
                    continue
                if member.file_size > budget[0]:
                    raise ContractError("Archive decompression budget exceeded")
                scan_bytes(member.filename, archive.read(member), depth + 1, budget)
        return
    if suffix in {".tar", ".gz", ".tgz", ".bz2", ".xz"}:
        try:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
                for member in archive:
                    safe_relative(member.name.rstrip("/"))
                    if member.issym() or member.islnk() or member.isdev():
                        raise ContractError("Unsafe archive member rejected")
                    if member.isfile():
                        if member.size > budget[0]:
                            raise ContractError("Archive decompression budget exceeded")
                        scan_bytes(member.name, archive.extractfile(member).read(), depth + 1, budget)
            return
        except tarfile.TarError as exc:
            raise ContractError("Unsupported compressed public attachment") from exc
    if suffix not in TEXT_SUFFIXES:
        raise ContractError("Public attachment type requires an explicit reviewed exporter")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractError("Binary content hidden in text attachment") from exc
    for code, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise ContractError("PUBLIC_SCAN_REJECTED: " + code)


def public_record(record):
    policy = record.get("disclosure") or {}
    if policy.get("visibility") != "PUBLIC" or policy.get("license") not in PUBLIC_LICENSES:
        return None
    if record.get("synthetic") is not False:
        return None
    allowed = COMMON_FIELDS | TYPE_FIELDS.get(record["record_type"], set())
    # Caller-requested fields may restrict the schema, never widen the whitelist.
    fields = policy.get("export_fields")
    if fields:
        required = {"schema_version", "record_type", "synthetic", "created_at", "available_at", "disclosure"}
        identity_fields = {f for f in TYPE_FIELDS.get(record["record_type"], set()) if f.endswith("_id") or f in {"version", "spec_version", "plan_ref"}}
        allowed &= set(fields) | required | identity_fields
    result = {key: value for key, value in record.items() if key in allowed}
    scan_bytes("record.json", canonical(result))
    return result


def attachment_allowed(record, relative):
    disclosure = record.get("disclosure") or {}
    return (disclosure.get("visibility") == "PUBLIC" and disclosure.get("license") in PUBLIC_LICENSES
            and relative in disclosure.get("public_attachments", []))
