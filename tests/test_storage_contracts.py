"""SYNTHETIC engineering fixtures only; never install these in production store."""
import copy
import io
import json
import multiprocessing
import tempfile
import unittest
import zipfile
from pathlib import Path

from researchlib import Store, publish_snapshot
from researchlib.archive import export_backup, restore_backup
from researchlib.common import BusyError, ConflictError, ContractError, canonical, digest, read_json
from researchlib.contracts import validate_relationships
from researchlib.public import public_record, scan_bytes
from researchlib.readiness import REQUIRED_CHECKS, assess
from researchlib.review import freeze_batch, should_reuse_final
from researchlib.snapshot import project, verify_snapshot

T0 = "2026-01-01T00:00:00Z"
T1 = "2026-01-02T00:00:00Z"
T2 = "2026-01-03T00:00:00Z"
T3 = "2026-01-04T00:00:00Z"
T4 = "2026-01-05T00:00:00Z"


def base(kind, at=T0, **extra):
    return dict(schema_version="1.0", record_type=kind, created_at=at, available_at=at,
                synthetic=False, disclosure={"visibility": "PUBLIC", "license": "OWN_ANALYSIS"}, **extra)


def round_record(ident="R1", at=T0, **extra):
    return base("round", at, round_id=ident, question="Synthetic contract question", mechanism="frozen mechanism",
                parent_round_id=None, product_refs=["BTC"], plan_refs=[], **extra)


def plan_record(ident="P1", version=1, at=T0, **extra):
    result = base("plan", at, plan_id=ident, version=version, round_id="R1", product_refs=["BTC"],
                  instrument_ref="BTC-TARGET", method_ref="frozen-method-v1", cost_model_ref="cost-v1",
                  fill_model_ref="fill-v1", evaluation_contract_ref="evaluation-v1", sealed_at=at,
                  effective_from=at, entry_valid_until=T3, evaluation_end=T3, replay_eligibility="ELIGIBLE",
                  rules={k: "explicit frozen rule" for k in ("signal", "entry", "quantity_or_inventory", "exit", "reentry", "termination")},
                  evidence_stage="SYNTHETIC_TEST_ONLY")
    result.update(extra)
    return result


def review_record(plan, ident="V1", at=T1, **extra):
    result = base("review", at, review_id=ident, plan_ref=plan["plan_id"] + "@" + str(plan["version"]),
                  revision=1, plan_hash=digest(canonical(plan)), review_method_ref="independent-review-v1",
                  data_cutoff=at, evaluation_stage="STAGE", simulation_state={"inventory": "2", "fees": "1", "cursor": at},
                  metrics=[], limitations=[], data_complete=True)
    result.update(extra)
    return result


def racing_claim(project, queue):
    try:
        c = Store(project).claim("same-question", "worker-" + str(multiprocessing.current_process().pid), "research")
        queue.put(c["state"])
    except BusyError:
        queue.put("BUSY")


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.time = T0
        self.store = Store(self.root, clock=lambda: self.time)

    def tearDown(self):
        self.tmp.cleanup()

    def commit_plan(self):
        plan = plan_record()
        self.store.commit_bundle("base", "research", [round_record(), plan])
        return plan

    def test_manifest_barrier_and_idempotency_preserve_bytes(self):
        record = round_record()
        m = self.store.commit_bundle("B1", "research", [record], {"report.md": "analysis"})
        directory = self.store.root / "bundles/B1"
        original = {p.relative_to(directory): p.read_bytes() for p in directory.rglob("*") if p.is_file()}
        self.time = T1
        again = self.store.commit_bundle("B1", "research", [record], {"report.md": "analysis"})
        self.assertTrue(again["replayed"])
        self.assertEqual(m["payload_hash"], again["payload_hash"])
        self.assertEqual(original, {p.relative_to(directory): p.read_bytes() for p in directory.rglob("*") if p.is_file()})
        with self.assertRaises(ConflictError):
            self.store.commit_bundle("B1", "research", [dict(record, question="changed")])

    def test_request_key_deduplicates_different_bundle_name(self):
        m = self.store.commit_bundle("B1", "research", [round_record()], request_key="same")
        again = self.store.commit_bundle("B2", "research", [round_record()], request_key="same")
        self.assertEqual(again["bundle_id"], "B1")
        with self.assertRaises(ConflictError):
            self.store.commit_bundle("B3", "research", [round_record("R2")], request_key="same")

    def test_interrupted_write_excluded_and_resumable(self):
        claim = self.store.claim("work", "worker", "research")
        with self.assertRaises(InterruptedError):
            self.store.commit_bundle("B1", "research", [round_record()], request_key="work", claim_token=claim["token"], fail_before_commit=True)
        self.assertEqual(self.store.load()[0], {})
        self.assertEqual(self.store.status()["uncommitted_staging_count"], 1)
        self.store.commit_bundle("B1", "research", [round_record()], request_key="work", claim_token=claim["token"])
        self.assertIn("R1", self.store.load()[0])

    def test_claim_transfer_requires_investigation_and_fences_old_owner(self):
        old = self.store.claim("work", "old", "research")
        with self.assertRaises(BusyError):
            self.store.claim("work", "new", "research")
        with self.assertRaises(ContractError):
            self.store.transfer_claim("work", "old", "new", None, "reason")
        new = self.store.transfer_claim("work", "old", "new", "owner-investigation-1", "Original owner confirmed stopped")
        self.assertEqual(new["generation"], 2)
        with self.assertRaises(ConflictError):
            self.store.commit_bundle("B1", "research", [round_record()], request_key="work", claim_token=old["token"])
        self.store.commit_bundle("B1", "research", [round_record()], request_key="work", claim_token=new["token"])

    def test_process_concurrency_has_only_one_owner(self):
        context = multiprocessing.get_context("spawn")
        queue = context.Queue()
        workers = [context.Process(target=racing_claim, args=(str(self.root), queue)) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=10)
            self.assertEqual(worker.exitcode, 0)
        self.assertEqual(sorted([queue.get(timeout=2), queue.get(timeout=2)]), ["BUSY", "CLAIMED"])

    def test_role_violations_and_record_overwrite_are_rejected(self):
        with self.assertRaises(ContractError):
            self.store.commit_bundle("bad", "review", [round_record()])
        self.store.commit_bundle("good", "research", [round_record()])
        with self.assertRaises(ConflictError):
            self.store.commit_bundle("different-bundle", "research", [round_record()])
        with self.assertRaises(ContractError):
            publish_snapshot(self.store, self.root / "public", role="research")

    def test_path_escape_and_symlink_rejected(self):
        with self.assertRaises(ContractError):
            self.store.commit_bundle("bad", "research", [round_record()], {"../escape.md": "x"})
        (self.store.root / "staging/link").symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ContractError):
            self.store.commit_bundle("bad2", "research", [round_record()], {"link/leak.md": "x"})

    def test_corrupt_and_unknown_schema_are_explicit_anomalies(self):
        self.store.commit_bundle("B1", "research", [round_record()])
        p = self.store.root / "bundles/B1/records/round/R1.json"
        p.write_text("{}")
        records, _, anomalies = self.store.load()
        self.assertEqual(records, {})
        self.assertEqual(anomalies[0]["code"], "INVALID_BUNDLE")
        with self.assertRaises(ContractError):
            self.store.load(strict=True)
        with self.assertRaises(ContractError):
            self.store.commit_bundle("future", "research", [dict(round_record("R2"), schema_version="99")])

    def test_corrupt_unrelated_record_does_not_block_independent_research(self):
        self.store.commit_bundle("B1", "research", [round_record()])
        (self.store.root / "bundles/B1/records/round/R1.json").write_text("{}")
        self.store.commit_bundle("B2", "research", [round_record("R2")])
        self.assertIn("R2", self.store.load()[0])
        (self.store.root / "bundles/B1/manifest.json").write_text("[]")
        self.store.commit_bundle("B3", "research", [round_record("R3")])
        with self.assertRaises(ConflictError):
            self.store.commit_bundle("reuse-corrupted-id", "research", [round_record()])

    def test_stable_shared_data_deduplicates_without_copying_per_round(self):
        metadata = {"source_url": "https://example.org/source", "acquired_at": T0, "license": "LOCAL_ONLY", "data_role": "TARGET"}
        first = self.store.put_data(b"timestamp,value\n", metadata, "research")
        second = self.store.put_data(b"timestamp,value\n", metadata, "review")
        self.assertEqual(first["data_ref"], second["data_ref"])
        self.assertEqual(len(list((self.store.data_root / "objects").iterdir())), 1)
        self.assertEqual(self.store.resolve_evidence(first["data_ref"])["sha256"], first["sha256"])

    def test_all_plan_versions_registered_including_waiting_and_negative(self):
        p1 = self.commit_plan()
        self.time = T1
        p2 = plan_record(version=2, at=T1, replay_eligibility="INCOMPLETE_DATA")
        p3 = plan_record("P-other", at=T1, replay_eligibility="UNKNOWN")
        self.store.commit_bundle("more", "research", [p2, p3])
        batch = freeze_batch(self.store, "day-1", T1)
        self.assertEqual(set(batch["plan_refs"]), {"P1@1", "P1@2", "P-other@1"})
        dispositions = {i["plan_ref"]: i["disposition"] for i in batch["items"]}
        self.assertEqual(dispositions["P1@2"], "WAITING_DATA")
        self.assertEqual(dispositions["P-other@1"], "RULES_INCOMPLETE")

    def test_cross_day_review_must_bind_original_and_carry_state(self):
        plan = self.commit_plan()
        self.time = T1
        v1 = review_record(plan)
        self.store.commit_bundle("v1", "review", [v1])
        self.time = T2
        v2 = review_record(plan, "V2", T2, previous_review_ref="V1", opening_state_hash="wrong")
        with self.assertRaises(ContractError):
            self.store.commit_bundle("v2-bad", "review", [v2])
        v2["opening_state_hash"] = digest(canonical(v1["simulation_state"]))
        self.store.commit_bundle("v2", "review", [v2])
        broken = review_record(plan, "V3", T2, plan_hash="wrong")
        with self.assertRaises(ContractError):
            self.store.commit_bundle("wrong-plan", "review", [broken])

    def test_final_requires_original_endpoint_and_complete_path(self):
        plan = self.commit_plan()
        self.time = T1
        with self.assertRaises(ContractError):
            self.store.commit_bundle("early-final", "review", [review_record(plan, evaluation_stage="FINAL")])
        self.time = T3
        final = review_record(plan, "Vfinal", T3, evaluation_stage="FINAL", input_fingerprint="input-a", evaluator_version="v1")
        self.store.commit_bundle("final", "review", [final])
        self.assertTrue(should_reuse_final(final, "input-a", "v1"))
        self.assertFalse(should_reuse_final(final, "input-b", "v1"))

    def test_late_commit_review_cannot_leak_into_earlier_frozen_batch(self):
        plan = self.commit_plan()
        self.time = T3
        self.store.commit_bundle("late", "review", [review_record(plan, at=T1)])
        batch = freeze_batch(self.store, "historical", T2)
        self.assertIsNone(batch["items"][0]["previous_review_ref"])
        self.assertEqual(batch["items"][0]["disposition"], "REVIEW_REQUIRED")

    def test_feedback_correction_propagates_without_changing_old_snapshot(self):
        plan = self.commit_plan()
        self.time = T1
        v1 = review_record(plan)
        feedback = base("feedback", T1, feedback_id="F1", review_ref="V1", supported_facts=["cost finding"], status="PROPOSED")
        self.store.commit_bundle("review", "review", [v1, feedback])
        child = round_record("R2", T1)
        child.update(parent_round_id="R1", derived_from_feedback_refs=["F1"])
        self.store.commit_bundle("child", "research", [child])
        before = publish_snapshot(self.store, self.root / "public", T1)
        original_bytes = (self.root / "public" / before["catalog_url"]).read_bytes()
        self.time = T2
        v2 = review_record(plan, "V2", T2, supersedes="V1", revision=2, correction_reason="Correct fee unit")
        self.store.commit_bundle("correction", "review", [v2])
        after = publish_snapshot(self.store, self.root / "public", T2)
        catalog = read_json(self.root / "public" / after["catalog_url"])
        self.assertEqual([n for n in catalog["nodes"] if n["id"] == "R2"][0]["status"], "NEEDS_RECHECK_AFTER_CORRECTION")
        historical, _, _, _ = project(self.store, T1)
        self.assertNotEqual([n for n in historical["nodes"] if n["id"] == "R2"][0]["status"], "NEEDS_RECHECK_AFTER_CORRECTION")
        self.assertEqual(original_bytes, (self.root / "public" / before["catalog_url"]).read_bytes())

    def test_daily_reviews_do_not_add_generation_or_implicit_selected_plan(self):
        plan = self.commit_plan()
        self.time = T1
        self.store.commit_bundle("review", "review", [review_record(plan)])
        catalog, _, _, _ = project(self.store, T1)
        self.assertEqual(catalog["round_count"], 1)
        self.assertEqual(catalog["nodes"][0]["generation"], 1)
        self.assertIsNone(catalog["nodes"][0]["selected_plan_ref"])
        self.assertIsNone(catalog["nodes"][0]["latest_review_ref"])
        self.assertEqual(catalog["nodes"][0]["review_refs"], ["V1"])

    def test_new_product_does_not_leak_into_old_asof(self):
        self.store.commit_bundle("B1", "research", [round_record()])
        self.time = T2
        self.store.commit_bundle("intc", "research", [base("product", T2, product_id="INTC", spec_version=1, active=False)])
        self.assertEqual(project(self.store, T1)[0]["products"], [])
        self.assertEqual(project(self.store, T2)[0]["products"][0]["product_id"], "INTC")
        self.assertFalse(project(self.store, T2)[0]["products"][0]["active"])

    def test_production_empty_never_falls_back_and_synthetic_is_excluded(self):
        self.store.commit_bundle("synthetic", "research", [dict(round_record(), synthetic=True)])
        result = publish_snapshot(self.store, self.root / "public", T0)
        self.assertEqual(result["round_count"], 0)
        self.assertEqual(result["mode"], "PRODUCTION_NO_DEMO_FALLBACK")

    def test_projection_is_deterministic_and_search_has_unloaded_ancestors(self):
        self.store.commit_bundle("B1", "research", [round_record()])
        child = round_record("R2")
        child.update(parent_round_id="R1", question="Hidden search target")
        self.store.commit_bundle("B2", "research", [child])
        a = publish_snapshot(self.store, self.root / "public", T0)
        b = publish_snapshot(self.store, self.root / "public2", T0)
        self.assertEqual(a["snapshot_id"], b["snapshot_id"])
        catalog = read_json(self.root / "public" / a["catalog_url"])
        result = next(r for r in catalog["search_index"] if r["id"] == "R2")
        self.assertEqual(result["ancestor_ids"], ["R1"])
        self.assertEqual(len(catalog["nodes"]), 2)
        self.assertEqual(catalog["mechanism_family_count"], 0)
        self.assertTrue(all(node["originality"] == "UNKNOWN_NOVELTY" for node in catalog["nodes"]))

    def test_publication_interrupt_does_not_switch_latest(self):
        self.store.commit_bundle("B1", "research", [round_record()])
        first = publish_snapshot(self.store, self.root / "public", T0)
        self.time = T1
        self.store.commit_bundle("B2", "research", [round_record("R2", T1)])
        with self.assertRaises(InterruptedError):
            publish_snapshot(self.store, self.root / "public", T1, fail_at="manifest")
        self.assertEqual(read_json(self.root / "public/latest.json")["snapshot_id"], first["snapshot_id"])
        second = publish_snapshot(self.store, self.root / "public", T1)
        verify_snapshot(self.root / "public", second["snapshot_id"])
        self.assertEqual(second["round_count"], 2)
        self.assertEqual(len(self.store.load()[0]), 2)

    def test_public_scanner_blocks_secret_nested_archive_and_private_paths(self):
        fake_private_path = b"/" + b"Users/" + b"synthetic-user/" + b"source"
        for content in (fake_private_path, b'"password":"not-allowed-private-value"', b'https://u:password@example.org'):
            with self.assertRaises(ContractError):
                scan_bytes("data.json", content)
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, "w") as z:
            z.writestr("secret.txt", fake_private_path)
        outer = io.BytesIO()
        with zipfile.ZipFile(outer, "w") as z:
            z.writestr("inner.zip", inner.getvalue())
        with self.assertRaises(ContractError):
            scan_bytes("outer.zip", outer.getvalue())

    def test_public_explicit_whitelist_and_license(self):
        record = round_record()
        record["private_note"] = "private content"
        projected = public_record(record)
        self.assertNotIn("private_note", projected)
        record["disclosure"] = {"visibility": "PUBLIC", "license": "UNKNOWN"}
        self.assertIsNone(public_record(record))

    def test_recovery_new_directory_verifies_original_bytes_and_manifest(self):
        record = round_record()
        record["disclosure"]["public_attachments"] = ["attachments/code.py", "attachments/result.json"]
        self.store.commit_bundle("B1", "research", [record], {"code.py": "print(1 + 1)\n", "result.json": '{"result":2}\n'})
        archive = self.root / "research.zip"
        exported = export_backup(self.store, archive, ["R1"])
        recovered = restore_backup(archive, self.root / "restored")
        self.assertEqual(recovered["state"], "EXACT_PUBLIC_BYTES_RECOVERED")
        self.assertEqual((self.root / "restored/records/R1.json").read_bytes(), canonical(record))
        self.assertEqual(recovered["scientific_reproduction"], "NOT_RUN")
        with self.assertRaises(ContractError):
            restore_backup(archive, self.root / "restored")
        self.assertEqual(export_backup(self.store, archive, ["R1"])["archive_id"], exported["archive_id"])

    def test_public_attachment_details_have_exact_bundle_identity(self):
        record = round_record()
        record["report_ref"] = "report.md"
        record["disclosure"]["public_attachments"] = ["attachments/report.md"]
        self.store.commit_bundle("B1", "research", [record], {"report.md": "safe public report"})
        catalog, details, _, _ = project(self.store, T0)
        self.assertEqual(details["R1"]["report_ref"], "bundle:B1/attachments/report.md")
        self.assertEqual(details["R1"]["public_attachment_refs"], ["bundle:B1/attachments/report.md"])


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name, clock=lambda: T2)
        self.plan = plan_record()
        self.evidence = base("evidence", T1, evidence_id="E1", plan_ref="P1@1", evidence_status="VERIFIED",
                             observed_at=T1, valid_until=T3, source_refs=["S1"], artifact_refs=[],
                             check_names=list(REQUIRED_CHECKS) + ["trigger"], verification_method="Synthetic source scope inspection")
        data = self.store.put_data(b"Synthetic official contract fixture", {"source_url": "https://official.example/spec", "acquired_at": T1,
                                                                           "license": "OWN_ANALYSIS", "data_role": "CONTRACT"}, "research")
        self.source = base("evidence", T1, evidence_id="S1", evidence_status="VERIFIED", observed_at=T1, valid_until=T3,
                           source_url="https://official.example/spec", artifact_refs=[data["data_ref"]])
        self.records = {"R1": round_record(), "P1@1": self.plan, "E1": self.evidence, "S1": self.source}
        for ref in ("frozen-method-v1", "cost-v1", "fill-v1", "evaluation-v1"):
            self.records[ref] = base("method", T0, method_id=ref, code_ref=data["data_ref"])
        self.records["TARGET"] = base("product", T0, product_id="TARGET", instrument_ref="BTC-TARGET")
        self.records["DATA"] = base("dataset", T0, dataset_id="DATA", instrument_ref="BTC-TARGET", data_role="TARGET", data_ref=data["data_ref"])
        self.plan["dataset_refs"] = ["DATA"]
        self.assessment = base("readiness", T1, assessment_id="A1", plan_ref="P1@1", as_of=T1,
                               policy_ref="execution-conditions-v1",
                               effective_from=T0, valid_until=T3, replay_eligible=True,
                               checks={name: {"status": "PASS", "evidence_refs": ["E1"], "observed_at": T1, "valid_until": T3} for name in REQUIRED_CHECKS},
                               trigger_status="MET", trigger_evidence_refs=["E1"])

    def tearDown(self):
        self.tmp.cleanup()

    def test_bound_verified_evidence_ready_only_within_validity(self):
        result = assess(self.store, self.assessment, self.records, T2)
        self.assertEqual(result["state"], "EXECUTION_READY_AS_OF")
        self.assertFalse(result["automatic_trade_authorized"])
        self.assertEqual(assess(self.store, self.assessment, self.records, T3)["state"], "EXPIRED")

    def test_wrong_plan_synthetic_unknown_schema_and_invalidated_never_ready(self):
        for mutation in ({"plan_ref": "P1@2"}, {"synthetic": True}, {"schema_version": "99"}, {"invalidated": True}):
            a = dict(self.assessment, **mutation)
            self.assertNotEqual(assess(self.store, a, self.records, T2)["state"], "EXECUTION_READY_AS_OF")
        self.assertEqual(assess(self.store, self.assessment, self.records, T2, {"P1@1"})["state"], "INVALIDATED")

    def test_bare_hash_or_wrong_scope_cannot_attest_market_fact(self):
        self.evidence["plan_ref"] = "another-version"
        self.assertEqual(assess(self.store, self.assessment, self.records, T2)["state"], "UNKNOWN")
        self.evidence["plan_ref"] = "P1@1"
        self.evidence["source_refs"] = []
        self.assertEqual(assess(self.store, self.assessment, self.records, T2)["state"], "UNKNOWN")

    def test_profit_is_not_a_gate_and_observation_never_execution_ready(self):
        self.plan["net_return_fraction"] = -0.5
        self.assertEqual(assess(self.store, self.assessment, self.records, T2)["state"], "EXECUTION_READY_AS_OF")
        self.plan["replay_eligibility"] = "METHOD_OBSERVATION_ONLY"
        self.assertEqual(assess(self.store, self.assessment, self.records, T2)["state"], "RESEARCH_ONLY")

    def test_missing_or_overextended_boundaries_and_reference_data_fail_closed(self):
        a = dict(self.assessment, valid_until=T4)
        self.assertEqual(assess(self.store, a, self.records, T2)["state"], "UNKNOWN")
        a = copy.deepcopy(self.assessment)
        a["checks"]["target_data_current"]["status"] = "REFERENCE_ONLY"
        self.assertEqual(assess(self.store, a, self.records, T2)["state"], "REPLAYABLE_ONLY")
        self.assertEqual(assess(self.store, dict(self.assessment, trigger_status="NOT_MET"), self.records, T2)["state"], "RULES_READY_WAITING_TRIGGER")

    def test_independent_review_missing_rules_policy_source_scope_regression(self):
        original_plan = copy.deepcopy(self.plan)
        for mutations in ({"replay_eligibility": "INCOMPLETE_DATA"}, {"rules": {}}):
            self.plan.update(mutations)
            self.assertNotEqual(assess(self.store, self.assessment, self.records, T2)["state"], "EXECUTION_READY_AS_OF")
            self.plan.clear()
            self.plan.update(original_plan)
        self.assertEqual(assess(self.store, dict(self.assessment, policy_ref=None), self.records, T2)["state"], "UNKNOWN")
        self.evidence["source_refs"] = ["does-not-exist"]
        self.assertEqual(assess(self.store, self.assessment, self.records, T2)["state"], "UNKNOWN")
        self.evidence["source_refs"] = ["S1"]
        self.evidence["check_names"] = []
        self.assertEqual(assess(self.store, self.assessment, self.records, T2)["state"], "UNKNOWN")

    def test_source_chain_cycle_or_missing_capture_fails_closed(self):
        self.source.pop("source_url")
        self.source["source_refs"] = ["E1"]
        self.assertEqual(assess(self.store, self.assessment, self.records, T2)["state"], "UNKNOWN")

    def test_check_cannot_override_broken_plan_dependency_or_reference_only_data(self):
        self.plan["method_ref"] = "does-not-exist"
        self.assertEqual(assess(self.store, self.assessment, self.records, T2)["state"], "UNKNOWN")
        self.plan["method_ref"] = "frozen-method-v1"
        self.records["DATA"]["data_role"] = "REFERENCE"
        self.assertEqual(assess(self.store, self.assessment, self.records, T2)["state"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
