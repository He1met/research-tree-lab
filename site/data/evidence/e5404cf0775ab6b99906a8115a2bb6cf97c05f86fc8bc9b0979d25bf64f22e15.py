"""Deterministic public snapshots: objects, immutable manifest, then latest."""
from __future__ import annotations

import os
import tempfile
from collections import defaultdict
from pathlib import Path

from .common import ContractError, atomic_write, canonical, digest, read_json, under, utc
from .contracts import semantic_refs
from .public import attachment_allowed, public_record, scan_bytes
from .readiness import assess
from .novelty import compare_rounds

GENERATOR_VERSION = "file-projection-v1.1.0"


def _immutable(path, raw):
    path = Path(path)
    if path.is_symlink():
        raise ContractError("Projection symlink rejected")
    if path.exists():
        if path.read_bytes() != raw:
            raise ContractError("Immutable public object content conflict")
    else:
        atomic_write(path, raw)


def _corrections(records):
    superseded = {r["supersedes"] for r in records.values() if r["record_type"] == "review" and r.get("supersedes")}
    invalid_feedback = {ref for ref, r in records.items() if r["record_type"] == "feedback" and r.get("review_ref") in superseded}
    affected_rounds = {ref for ref, r in records.items() if r["record_type"] == "round" and set(r.get("derived_from_feedback_refs", [])) & invalid_feedback}
    for r in records.values():
        if r["record_type"] == "decision" and r.get("feedback_ref") in invalid_feedback and r.get("successor_round_id"):
            affected_rounds.add(r["successor_round_id"])
    changed = True
    while changed:
        changed = False
        for ref, r in records.items():
            if r["record_type"] == "round" and r.get("parent_round_id") in affected_rounds and ref not in affected_rounds:
                affected_rounds.add(ref)
                changed = True
    affected_plans = {ref for ref, r in records.items() if r["record_type"] == "plan" and (
        r["round_id"] in affected_rounds or set(r.get("source_review_refs", [])) & superseded)}
    return superseded, invalid_feedback, affected_rounds, affected_plans


def project(store, as_of):
    at = utc(as_of)
    all_records, metadata, load_anomalies = store.load()
    visible = {ref: r for ref, r in all_records.items() if r.get("synthetic") is False
               and utc(r["available_at"]) <= at and utc(metadata[ref]["committed_at"]) <= at}
    anomalies = [{"bundle_id": a["bundle_id"], "code": a["code"]} for a in load_anomalies]
    public, excluded = {}, []
    for ref, record in sorted(visible.items()):
        try:
            result = public_record(record)
            if result is None:
                excluded.append({"record_ref": ref, "reason": "NOT_PUBLICLY_LICENSED", "archive_status": "LOCAL_ONLY"})
                continue
            if "status_events" in result:
                result["status_events"] = [e for e in result["status_events"] if utc(e.get("available_at") or e.get("at")) <= at]
            public[ref] = result
        except (ValueError, KeyError, TypeError):
            anomalies.append({"record_ref": ref, "code": "PUBLIC_SCAN_OR_SCHEMA_REJECTED"})
    # Lineage essentials cannot silently disappear or become a fabricated root.
    changed = True
    while changed:
        changed = False
        for ref, record in list(public.items()):
            required = semantic_refs(record)
            if any(target not in public for target in required):
                anomalies.append({"record_ref": ref, "code": "PUBLIC_REFERENCE_UNAVAILABLE"})
                del public[ref]
                changed = True
    superseded, invalid_feedback, affected_rounds, affected_plans = _corrections(public)
    rounds = {ref: r for ref, r in public.items() if r["record_type"] == "round"}
    plans = {ref: r for ref, r in public.items() if r["record_type"] == "plan"}
    reviews = {ref: r for ref, r in public.items() if r["record_type"] == "review"}
    feedback = {ref: r for ref, r in public.items() if r["record_type"] == "feedback"}
    products = [dict(r, display_name=r.get("display_name") or r.get("name") or r["product_id"])
                for r in public.values() if r["record_type"] == "product"]
    plans_by_round, reviews_by_plan, feedback_by_review = defaultdict(list), defaultdict(list), defaultdict(list)
    for ref, plan in plans.items():
        plans_by_round[plan["round_id"]].append(ref)
    for ref, review in reviews.items():
        reviews_by_plan[review["plan_ref"]].append(ref)
    for ref, f in feedback.items():
        feedback_by_review[f["review_ref"]].append(ref)
    assessments = {}
    for ref, record in public.items():
        if record["record_type"] == "readiness":
            plan_ref = record.get("plan_ref")
            current = assessments.get(plan_ref)
            if current is None or (record["available_at"], ref) > (current["available_at"], current["assessment_id"]):
                result = assess(store, visible[ref], visible, as_of, affected_plans | superseded | invalid_feedback)
                result["evidence_stage"] = plans.get(plan_ref, {}).get("evidence_stage", "UNKNOWN")
                assessments[plan_ref] = result
    nodes, edges, search = [], [], []
    novelty, family_count = compare_rounds(rounds, plans_by_round, plans, public)
    for ref, record in sorted(rounds.items()):
        parent = record.get("parent_round_id")
        ancestors, cursor, seen = [], parent, {ref}
        while cursor:
            if cursor in seen or cursor not in rounds:
                raise ContractError("Invalid or broken research ancestry")
            seen.add(cursor)
            ancestors.insert(0, cursor)
            cursor = rounds[cursor].get("parent_round_id")
        plan_refs = sorted(plans_by_round[ref])
        review_refs = sorted(r for p in plan_refs for r in reviews_by_plan[p])
        feedback_refs = sorted(f for r in review_refs for f in feedback_by_review[r])
        selected = record.get("selected_plan_ref")
        selected = selected if selected in plan_refs else None
        selected_reviews = [reviews[r] for r in review_refs if reviews[r]["plan_ref"] == selected and r not in superseded] if selected else []
        latest = max(selected_reviews, key=lambda r: (utc(r["available_at"]), r["revision"], r["review_id"]), default=None)
        latest_any = max([reviews[r] for r in review_refs], key=lambda r: utc(r["available_at"]), default=None)
        status = record.get("status") or (record.get("status_events") or [{}])[-1].get("status") or "RESEARCH_RECORDED"
        if ref in affected_rounds:
            status = "NEEDS_RECHECK_AFTER_CORRECTION"
        p_summary = record.get("plan_summary") or (
            plans[selected].get("summary") or plans[selected].get("research_question") or selected if selected else
            (f"{len(plan_refs)} 个候选，未指定主选" if plan_refs else "资料与机制研究，尚未登记可回放方案"))
        review_summary = record.get("review_summary") or (latest.get("summary") or latest.get("evaluation_stage") if latest else
                         (f"{len(review_refs)} 份复核，按候选分别查看" if review_refs else "等待独立复核"))
        node = {"id": ref, "kind": "research_round", "title": record.get("title") or record["question"],
                "question": record.get("question"), "mechanism": record.get("mechanism"),
                "purpose_kind": record.get("purpose_kind", "RESEARCH"), "product_refs": record.get("product_refs", []),
                "generation": len(ancestors) + 1, "parent_round_id": parent, "ancestor_ids": ancestors,
                "plan_refs": plan_refs, "selected_plan_ref": selected, "review_refs": review_refs,
                "feedback_refs": feedback_refs, "latest_review_ref": latest["review_id"] if latest else None,
                "status": status, "next_action": record.get("next_action") or "等待新的可核验证据",
                "plan_summary": p_summary, "review_summary": review_summary,
                "feedback_summary": record.get("feedback_summary") or (f"{len(feedback_refs)} 项反馈" if feedback_refs else "尚无正式反馈"),
                "readiness": [assessments[p] for p in plan_refs if p in assessments],
                "available_at": record["available_at"],
                "evidence_stage": record.get("evidence_stage", "UNKNOWN"), "is_synthetic": False}
        node.update(novelty[ref])
        if latest and "net_return_fraction" in latest:
            node["net_return_fraction"] = latest["net_return_fraction"]
        nodes.append(node)
        if parent:
            edges.append({"source": parent, "target": ref, "relation": "DERIVED_FROM",
                          "feedback_refs": record.get("derived_from_feedback_refs", [])})
        related = [public[k] for k in plan_refs + review_refs + feedback_refs]
        summary_words = [str(r.get(k, ""))[:1000] for r in related for k in
                         ("title", "summary", "research_question", "review_id", "plan_id", "feedback_id", "evaluation_stage", "proposed_question")]
        search.append({"id": ref, "title": node["title"], "text": " ".join([node["title"], record.get("mechanism", "")] + summary_words),
                       "ancestor_ids": ancestors, "product_refs": node["product_refs"], "purpose_kind": node["purpose_kind"],
                       "available_at": record["available_at"]})
    decisions = [r for r in public.values() if r["record_type"] == "decision"]
    details = {}
    nodes_by_id = {n["id"]: n for n in nodes}
    for ref, record in public.items():
        detail = dict(record, record_ref=ref, original_record_hash=metadata[ref]["record_hash"],
                      committed_at=metadata[ref]["committed_at"], archive_status="PUBLIC_PROJECTION_GENERATED_NOT_REMOTE_CONFIRMED")
        allowed_attachments = record.get("disclosure", {}).get("public_attachments", [])
        detail["public_attachment_refs"] = ["bundle:" + metadata[ref]["bundle_id"] + "/" + relative
                                            for relative in allowed_attachments if attachment_allowed(record, relative)]
        report = record.get("report_ref")
        if isinstance(report, str):
            relative_report = report if report.startswith("attachments/") else "attachments/" + report
            if relative_report in allowed_attachments:
                detail["report_ref"] = "bundle:" + metadata[ref]["bundle_id"] + "/" + relative_report
        if record["record_type"] == "round":
            node = nodes_by_id[ref]
            detail.update(plan_refs=node["plan_refs"], review_refs=node["review_refs"], feedback_refs=node["feedback_refs"],
                          decision_refs=[d["decision_id"] for d in decisions if d.get("successor_round_id") == ref])
            detail.update(novelty[ref])
        if ref in superseded:
            detail["correction_status"] = "SUPERSEDED_RETAINED"
        if ref in invalid_feedback:
            detail["status"] = "INVALIDATED_BY_REVIEW_CORRECTION"
        if ref in affected_rounds or ref in affected_plans:
            detail["correction_status"] = "NEEDS_RECHECK_AFTER_CORRECTION"
        if record["record_type"] == "feedback":
            detail["adoption_decision_refs"] = sorted(d["decision_id"] for d in decisions if d.get("feedback_ref") == ref)
        if record["record_type"] == "readiness":
            detail.update(assess(store, visible[ref], visible, as_of, affected_plans | superseded | invalid_feedback))
        details[ref] = detail
    batches = []
    for record in public.values():
        if record["record_type"] != "review_batch":
            continue
        batch_reviews = [r for r in reviews.values() if r.get("batch_ref") == record["batch_id"]]
        completed = {r["plan_ref"] for r in batch_reviews}
        batches.append(dict(record, review_refs=sorted(r["review_id"] for r in batch_reviews),
                            product_refs=sorted({p for plan in record.get("plan_refs", []) for p in plans.get(plan, {}).get("product_refs", [])}),
                            coverage={"registered": len(record.get("plan_refs", [])), "reviewed": len(completed),
                                      "missing": sorted(set(record.get("plan_refs", [])) - completed)}))
    catalog = {"schema_version": "1.0", "generator_version": GENERATOR_VERSION,
               "mode": "PRODUCTION_NO_DEMO_FALLBACK", "as_of": as_of,
               "round_count": len(nodes), "record_count": len(public), "mechanism_family_count": family_count,
               "scientifically_independent_mechanism_count": None,
               "novelty_counting_policy": "STRUCTURAL_FAMILIES_ARE_NOT_SCIENTIFICALLY_INDEPENDENT_MECHANISMS",
               "nodes": nodes, "edges": edges, "products": products, "review_batches": sorted(batches, key=lambda r: (r["frozen_at"], r["batch_id"])),
               "directions": sorted({r.get("purpose_kind", "RESEARCH") for r in rounds.values()}),
               "search_index": search, "anomalies": anomalies, "excluded_records": excluded,
               "profit_aggregation": "FORBIDDEN_INDEPENDENT_HYPOTHETICAL_CAPITAL", "snapshots": []}
    return catalog, details, public, metadata


def publish_snapshot(store, output_root, as_of=None, role="publish", fail_at=None):
    if role != "publish":
        raise ContractError("ROLE_WRITE_DENIED: only publish may switch public snapshot")
    as_of = as_of or store.clock()
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    # Dedicated publication lock; research keeps committing independently.
    import fcntl
    with (output_root / ".publish.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        catalog, detail_records, originals, metadata = project(store, as_of)
        objects, detail_urls = {}, {}
        for ref, record in sorted(detail_records.items()):
            raw = canonical(record)
            scan_bytes("detail.json", raw)
            sha = digest(raw)
            relative = "objects/" + sha + ".json"
            objects[relative] = raw
            detail_urls[ref] = relative
        catalog["details"] = detail_urls
        shards = []
        # Search covers all summaries; graph consumers may read bounded chunks.
        for offset in range(0, len(catalog["nodes"]), 200):
            chunk = catalog["nodes"][offset:offset + 200]
            raw = canonical({"schema_version": "1.0", "nodes": chunk, "offset": offset})
            sha = digest(raw)
            relative = "objects/" + sha + ".json"
            objects[relative] = raw
            shards.append({"url": relative, "offset": offset, "count": len(chunk),
                           "product_refs": sorted({p for n in chunk for p in n["product_refs"]})})
        catalog["shards"] = shards
        evidence_index = {}
        bundle_manifests = {}
        for ref, record in originals.items():
            bundle_id = metadata[ref]["bundle_id"]
            directory = store.root / "bundles" / bundle_id
            if bundle_id not in bundle_manifests:
                bundle_manifests[bundle_id] = store._read_bundle(directory)[0]
            manifest = bundle_manifests[bundle_id]
            for entry in manifest["files"]:
                relative = entry["path"]
                if entry.get("kind") != "attachment" or not attachment_allowed(record, relative):
                    continue
                raw = under(directory, relative).read_bytes()
                scan_bytes(relative, raw)
                suffix = Path(relative).suffix.lower()
                public_path = "evidence/" + digest(raw) + suffix
                objects[public_path] = raw
                evidence_index["bundle:" + bundle_id + "/" + relative] = {"url": public_path, "sha256": digest(raw), "bytes": len(raw)}
        catalog["evidence"] = evidence_index
        snapshot_id = digest(canonical(catalog))
        catalog["snapshot_id"] = snapshot_id
        catalog_bytes = canonical(catalog)
        scan_bytes("catalog.json", catalog_bytes)
        manifest = {"schema_version": "1.0", "snapshot_id": snapshot_id, "as_of": as_of,
                    "generator_version": GENERATOR_VERSION, "commit_state": "COMMITTED",
                    "files": [{"path": "catalog.json", "sha256": digest(catalog_bytes), "bytes": len(catalog_bytes)}],
                    "object_refs": [{"path": p, "sha256": digest(raw), "bytes": len(raw)} for p, raw in sorted(objects.items())],
                    "source_record_refs": sorted(originals)}
        for relative, raw in sorted(objects.items()):
            _immutable(under(output_root, relative), raw)
        if fail_at == "objects":
            raise InterruptedError("Injected publication interruption after objects")
        snapshot_dir = under(output_root, "snapshots/" + snapshot_id)
        _immutable(snapshot_dir / "catalog.json", catalog_bytes)
        _immutable(snapshot_dir / "manifest.json", canonical(manifest))
        verify_snapshot(output_root, snapshot_id)
        if fail_at == "manifest":
            raise InterruptedError("Injected publication interruption before latest pointer")
        pointer = {"schema_version": "1.0", "snapshot_id": snapshot_id,
                   "manifest_url": "snapshots/" + snapshot_id + "/manifest.json",
                   "catalog_url": "snapshots/" + snapshot_id + "/catalog.json",
                   "history_url": "history.json", "as_of": as_of, "generated_at": as_of,
                   "mode": "PRODUCTION_NO_DEMO_FALLBACK"}
        history_path = output_root / "history.json"
        history = read_json(history_path) if history_path.exists() else []
        history = [item for item in history if item["snapshot_id"] != snapshot_id]
        history.append(pointer)
        history.sort(key=lambda item: (utc(item["as_of"]), item["snapshot_id"]))
        atomic_write(history_path, canonical(history))
        atomic_write(output_root / "latest.json", canonical(pointer))
        return dict(pointer, publication_state="GENERATED_NOT_REMOTE_CONFIRMED", record_count=len(originals),
                    round_count=catalog["round_count"], anomalies=catalog["anomalies"])


def verify_snapshot(root, snapshot_id):
    directory = under(root, "snapshots/" + snapshot_id)
    manifest = read_json(directory / "manifest.json")
    if manifest.get("snapshot_id") != snapshot_id or manifest.get("commit_state") != "COMMITTED":
        raise ContractError("Incomplete snapshot manifest")
    for base, entries in ((directory, manifest["files"]), (root, manifest["object_refs"])):
        for entry in entries:
            raw = under(base, entry["path"]).read_bytes()
            if len(raw) != entry["bytes"] or digest(raw) != entry["sha256"]:
                raise ContractError("Snapshot object hash mismatch")
    catalog = read_json(directory / "catalog.json")
    source = dict(catalog)
    source.pop("snapshot_id", None)
    if digest(canonical(source)) != snapshot_id:
        raise ContractError("Snapshot identity does not match projection")
    return manifest
