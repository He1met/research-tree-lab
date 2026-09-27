"""Conservative structural deduplication, never an attestor of scientific novelty.

Labels/tickers/record identities are not mechanisms. Parameter values define a
variant inside a structural family. Unknown prose and unresolved method/data
references remain explicit; a unique hash never means an independent mechanism.
"""
from __future__ import annotations

import re
from collections import defaultdict

from .common import canonical, digest, utc

COSMETIC = {"title", "display_name", "label", "description", "summary", "question", "research_question",
            "created_at", "available_at", "sealed_at", "published_at", "observed_at", "version",
            "ticker", "symbol", "instrument", "instrument_ref", "product", "product_id", "product_refs"}
PARAMETER_KEYS = {"parameters", "params", "threshold", "window", "lookback", "period", "quantity",
                  "size", "leverage", "stop", "target", "multiplier", "side", "direction"}
RULE_FIELDS = ("signal", "entry", "quantity_or_inventory", "exit", "reentry", "termination")


def normalize(value, family=False, symbols=(), parameter=False):
    if isinstance(value, dict):
        return {key: normalize(item, family, symbols, parameter or key.lower() in PARAMETER_KEYS)
                for key, item in sorted(value.items()) if key.lower() not in COSMETIC
                and not key.lower().endswith(("_id", "_ref", "_refs", "_at")) and key.lower() != "id"}
    if isinstance(value, list):
        return [normalize(item, family, symbols, parameter) for item in value]
    if value is None:
        return None
    if family and (parameter or isinstance(value, (int, float, bool))):
        return "<parameter>"
    if isinstance(value, str):
        result = re.sub(r"\s+", " ", value.strip().lower())
        for symbol in sorted({str(s).lower() for s in symbols if s}, key=len, reverse=True):
            result = re.sub(r"(?<![\w])" + re.escape(symbol) + r"(?![\w])", "<instrument>", result)
        if family:
            # Prose remains semantically unverified even when this heuristic
            # groups numeric variants such as ATR(14) and ATR(20).
            result = re.sub(r"(?<![a-z_])-?\d+(?:\.\d+)?", "<number>", result)
        return result
    return value


def unique_sorted(items):
    return [value for _, value in sorted({canonical(item): item for item in items}.items())]


def plan_signature(plan, records):
    symbols = list(plan.get("product_refs", [])) + [plan.get("product_id"), plan.get("instrument_ref")]
    methods, unresolved = [], []
    for key in ("method_ref", "cost_model_ref", "fill_model_ref", "evaluation_contract_ref"):
        ref = plan.get(key)
        method = records.get(ref) if isinstance(ref, str) else None
        if method and method.get("record_type") == "method" and isinstance(method.get("algorithm"), (dict, list)):
            methods.append({"role": key, "algorithm": method["algorithm"]})
        elif ref:
            unresolved.append(key)
    inputs, input_roles = [], []
    for binding in plan.get("dataset_refs", []):
        declared_role = None
        ref = binding
        if isinstance(binding, dict):
            declared_role = binding.get("role") or binding.get("data_role")
            ref = binding.get("dataset_ref") or binding.get("ref") or binding.get("source_ref")
        dataset = records.get(ref) if isinstance(ref, str) else None
        if not dataset or dataset.get("record_type") != "dataset":
            unresolved.append("dataset_ref")
            if declared_role:
                input_roles.append({"data_role": declared_role})
            continue
        content = dataset.get("data_ref") or dataset.get("sha256")
        if not isinstance(content, str) or not re.fullmatch(r"(?:sha256:)?[a-fA-F0-9]{64}", content):
            content = None
            unresolved.append("dataset_content_identity")
        role = {"data_role": declared_role or dataset.get("data_role", "UNKNOWN"), "granularity": dataset.get("granularity"),
                "columns": dataset.get("columns", []), "units": dataset.get("units")}
        if role["data_role"] == "UNKNOWN":
            unresolved.append("dataset_role")
        input_roles.append(role)
        inputs.append({"content_hash": content.removeprefix("sha256:").lower() if content else None,
                       "role": role, "sample_role": plan.get("sample_role", "UNKNOWN"),
                       "event_start": dataset.get("event_start"), "event_end": dataset.get("event_end")})
    # Input roles can be declared before data acquisition, but never become
    # evidence that two inputs are actually identical.
    for role in plan.get("input_roles", []):
        if isinstance(role, (dict, str)):
            input_roles.append(role)
    rules = plan.get("rules") or {}
    rules_present = isinstance(rules, dict) and all(rules.get(key) for key in RULE_FIELDS)
    structured = rules_present and all(isinstance(rules[key], (dict, list)) for key in RULE_FIELDS)
    if not rules_present:
        return {"family": None, "variant": None, "inputs": None, "input_identity_known": False,
                "structure": "INCOMPLETE_RULES", "unresolved": sorted(set(unresolved))}
    normalized_rules = normalize(rules, False, symbols)
    if any(not normalized_rules.get(key) for key in RULE_FIELDS):
        return {"family": None, "variant": None, "inputs": None, "input_identity_known": False,
                "structure": "INSUFFICIENT_STRUCTURAL_FIELDS", "unresolved": sorted(set(unresolved))}
    material = {"rules": rules, "methods": methods, "input_roles": unique_sorted(input_roles)}
    family = normalize(material, True, symbols)
    variant = normalize(dict(material, parameters=plan.get("parameters", {})), False, symbols)
    return {"family": digest(canonical(family)), "variant": digest(canonical(variant)),
            "inputs": digest(canonical(unique_sorted(inputs))),
            "input_identity_known": bool(inputs) and not any(x.startswith("dataset") for x in unresolved),
            "structure": "STRUCTURED_COMPARISON_ONLY" if structured else "OPAQUE_TEXT_COMPARISON_ONLY",
            "unresolved": sorted(set(unresolved))}


def compare_rounds(rounds, plans_by_round, plans, records):
    signatures, families = {}, defaultdict(list)
    for ref, record in sorted(rounds.items()):
        plan_signatures = [plan_signature(plans[p], records) for p in sorted(plans_by_round.get(ref, []))]
        usable = [item for item in plan_signatures if item["family"]]
        family = digest(canonical(sorted({item["family"] for item in usable}))) if usable else None
        signature = {
            "family": family,
            "variant": digest(canonical(sorted({item["variant"] for item in usable}))) if usable else None,
            "inputs": digest(canonical(sorted({item["inputs"] for item in usable}))) if usable else None,
            "input_identity_known": bool(usable) and all(item["input_identity_known"] for item in usable),
            "product_scope": sorted(set(record.get("product_refs", [])) | {str(plans[p].get("instrument_ref")) for p in plans_by_round.get(ref, []) if plans[p].get("instrument_ref")}),
            "structure": sorted({item["structure"] for item in plan_signatures}) or ["NO_COMPARABLE_PLAN"],
            "unresolved": sorted({item for p in plan_signatures for item in p["unresolved"]}),
        }
        signatures[ref] = signature
        if family:
            families[family].append(ref)
    result = {}
    for ref, record in sorted(rounds.items()):
        signature = signatures[ref]
        peers = sorted(families.get(signature["family"], []))
        others = [p for p in peers if p != ref]
        evidence_refs = record.get("novelty_evidence_refs", [])
        traceable = [r for r in evidence_refs if isinstance(r, str) and r in records and records[r].get("synthetic") is False
                     and utc(records[r]["available_at"]) <= utc(record["available_at"])]
        unresolved_evidence = [r for r in evidence_refs if r not in traceable]
        declared = any(record.get(k) for k in ("mechanism_identity", "novelty_claim", "novelty_evidence_refs", "duplicate_of", "variant_of", "replication_of"))
        status = "DECLARED_UNVERIFIED" if declared else "UNKNOWN_NOVELTY"
        relation = None
        if others:
            same_variant = [p for p in others if signatures[p]["variant"] == signature["variant"]]
            same_scope = [p for p in same_variant if signatures[p]["product_scope"] == signature["product_scope"]]
            same_input = [p for p in same_scope if signatures[p]["inputs"] == signature["inputs"]]
            if same_input:
                status = ("DUPLICATE_RULES_AND_INPUTS" if signature["input_identity_known"] and all(signatures[p]["input_identity_known"] for p in same_input)
                          else "DUPLICATE_RULES_INPUTS_UNVERIFIED")
            elif same_scope:
                status = "NEW_SAMPLE_REPLICATION_CANDIDATE"
            elif same_variant:
                status = "CROSS_PRODUCT_REPLICATION_CANDIDATE"
            else:
                status = "PARAMETER_OR_RULE_VARIANT"
        for key, kind in (("duplicate_of", "DUPLICATE"), ("variant_of", "VARIANT"), ("replication_of", "REPLICATION")):
            target = record.get(key)
            if target:
                relation = {"kind": kind, "round_ref": target, "reference_state": "RESOLVED" if target in rounds else "UNRESOLVED",
                            "verification": "DECLARED_UNVERIFIED"}
                break
        result[ref] = {
            "mechanism_fingerprint": signature["family"], "mechanism_family_refs": peers,
            "originality": status,
            "novelty_comparison": {"basis": "STRUCTURAL_DEDUPLICATION_HINT_NOT_SEMANTIC_PROOF",
                                   "variant_signature": signature["variant"], "input_signature": signature["inputs"],
                                   "input_identity_known": signature["input_identity_known"],
                                   "structure": signature["structure"], "unresolved_dependencies": signature["unresolved"],
                                   "declared_mechanism_identity": record.get("mechanism_identity"),
                                   "declared_relation": relation, "traceable_evidence_refs": traceable,
                                   "unresolved_evidence_refs": unresolved_evidence, "scientific_independence": "NOT_ESTABLISHED"},
        }
    return result, len(families)
