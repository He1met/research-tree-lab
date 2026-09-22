"""SYNTHETIC fixtures: public field compatibility, never production evidence."""
import copy
import tempfile
import unittest
import zipfile
from pathlib import Path

from researchlib.archive import export_backup, inspect_backup, restore_backup
from researchlib.common import ContractError, canonical, digest
from researchlib.contracts import semantic_refs, validate_relationships
from researchlib.public import attachment_allowed, public_record
from researchlib.snapshot import project
from researchlib.store import Store


T0 = "2026-01-01T00:00:00Z"
T1 = "2026-01-02T00:00:00Z"


def record(kind, **fields):
    # synthetic=False exercises the production filter only in temporary stores.
    return dict(schema_version="1.0", record_type=kind, synthetic=False,
                created_at=T0, available_at=T0,
                disclosure={"visibility": "PUBLIC", "license": "OWN_ANALYSIS"},
                **fields)


class PublicFieldsV2Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="synthetic-public-fields-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = Store(self.root, clock=lambda: T1)
        self.round = record("round", round_id="round", question="Synthetic question",
                            mechanism="synthetic", parent_round_id=None, plan_refs=[])
        self.method = record("method", method_id="method", version=1,
                             protocol_refs=["bundle:fixture/attachments/protocol.json"])
        self.method2 = record("method", method_id="method-two", version=1)
        self.run = record("run", run_id="run", attempt_id="attempt-1",
                          round_id="round", method_ref="method@1")
        self.run2 = record("run", run_id="run-two", attempt_id="attempt-1",
                           round_id="round", method_ref="method-two@1")
        self.decision = record("decision", decision_id="decision",
                               comparison_set=["immediate", "confirmed", "wait"],
                               feedback_disposition={"status": "SYNTHETIC_BOUNDARY_ONLY",
                                                     "adopted": ["Unknown costs remain null."]},
                               selected_plan_ref=None, input_record_refs=["round"])

    def commit(self, changes=None):
        records = [self.round, self.method, self.method2, self.run, self.run2, self.decision]
        if changes:
            records = changes(records)
        self.store.commit_bundle("fixture", "research", records, attachments={
            "protocol.json": canonical({"purpose": "SYNTHETIC protocol, not allowlisted"}),
            "PRIVATE/state.json": b'{"private_canary":"DO_NOT_EXPORT_PRIVATE_INPUT"}',
            "raw_source.csv": b"time,price\nSYNTHETIC,987654.123\n",
        })
        return records

    def test_all_new_type_fields_preserve_exact_original_without_mutation(self):
        for original in (self.method, self.run, self.run2, self.decision):
            before = copy.deepcopy(original)
            self.assertEqual(public_record(original), before)
            self.assertEqual(original, before)
        unrelated = dict(self.round, comparison_set=[], protocol_refs=[], method_ref="method@1")
        projected = public_record(unrelated)
        self.assertNotIn("comparison_set", projected)
        self.assertNotIn("protocol_refs", projected)
        self.assertNotIn("method_ref", projected)

    def test_two_run_single_root_archives_include_their_method(self):
        self.commit()
        for ref, method in (("run@attempt-1", "method@1"),
                            ("run-two@attempt-1", "method-two@1")):
            path = self.root / (ref + ".zip")
            manifest = export_backup(self.store, path, [ref])
            self.assertEqual(set(manifest["record_refs"]), {ref, method, "round"})
            self.assertEqual(inspect_backup(path)["archive_id"], manifest["archive_id"])

    def test_four_roots_are_exact_deterministic_and_restore_to_a_new_directory(self):
        self.commit()
        before, metadata, _ = self.store.load(strict=True)
        refs = ["decision", "method@1", "run@attempt-1", "run-two@attempt-1"]
        a, b = self.root / "a.zip", self.root / "b.zip"
        first = export_backup(self.store, a, refs)
        second = export_backup(self.store, b, list(reversed(refs)))
        self.assertEqual(first["archive_id"], second["archive_id"])
        self.assertEqual(a.read_bytes(), b.read_bytes())
        recovered = self.root / "new-recovery"
        result = restore_backup(a, recovered)
        self.assertEqual(set(result["record_refs"]), set(before))
        for ref, original in before.items():
            raw = (recovered / "records" / (ref + ".json")).read_bytes()
            self.assertEqual(raw, canonical(original))
            self.assertEqual(digest(raw), metadata[ref]["record_hash"])
        with self.assertRaisesRegex(ContractError, "new directory"):
            restore_backup(a, recovered)
        self.assertEqual(self.store.load(strict=True)[0], before)

    def test_protocol_is_a_locator_not_an_attachment_or_record_authorization(self):
        self.commit()
        archive = self.root / "no-private.zip"
        manifest = export_backup(self.store, archive, ["run@attempt-1", "decision"])
        self.assertEqual(semantic_refs(self.method), [])
        self.assertFalse(attachment_allowed(self.method, "attachments/protocol.json"))
        self.assertTrue(all(not f["path"].startswith("evidence/") for f in manifest["files"]))
        with zipfile.ZipFile(archive) as contents:
            payload = b"\n".join(contents.read(name) for name in contents.namelist())
        self.assertIn(b"bundle:fixture/attachments/protocol.json", payload)
        self.assertNotIn(b"SYNTHETIC protocol, not allowlisted", payload)
        self.assertNotIn(b"DO_NOT_EXPORT_PRIVATE_INPUT", payload)
        self.assertNotIn(b"987654.123", payload)

    def test_existing_explicit_attachment_allowlist_still_exports_only_that_file(self):
        self.method["disclosure"]["public_attachments"] = ["attachments/protocol.json"]
        self.commit()
        manifest = export_backup(self.store, self.root / "explicit.zip", ["run@attempt-1"])
        evidence = [e["path"] for e in manifest["files"] if e["path"].startswith("evidence/")]
        self.assertEqual(evidence, ["evidence/fixture/attachments/protocol.json"])

    def test_missing_method_and_future_method_are_rejected(self):
        records = {"round": self.round, "method@1": self.method, "run@attempt-1": self.run}
        with self.assertRaisesRegex(ContractError, "MISSING_REFERENCE"):
            validate_relationships({k: v for k, v in records.items() if k != "method@1"})
        records["method@1"] = dict(self.method, created_at=T1, available_at=T1)
        with self.assertRaisesRegex(ContractError, "unavailable"):
            validate_relationships(records)

    def test_method_reference_cannot_point_to_another_record_type(self):
        run = dict(self.run, method_ref="round")
        with self.assertRaisesRegex(ContractError, "Run method reference has wrong type"):
            validate_relationships({"round": self.round, "run@attempt-1": run})

    def test_private_method_prevents_public_run_closure_export(self):
        self.method["disclosure"]["visibility"] = "LOCAL_ONLY"
        self.commit()
        with self.assertRaisesRegex(ContractError, "non-public"):
            export_backup(self.store, self.root / "private-method.zip", ["run@attempt-1"])
        self.assertFalse((self.root / "private-method.zip").exists())

    def test_private_method_also_removes_dependent_run_from_public_snapshot(self):
        self.method["disclosure"]["visibility"] = "LOCAL_ONLY"
        self.commit()
        catalog, _, public, _ = project(self.store, T1)
        self.assertNotIn("method@1", public)
        self.assertNotIn("run@attempt-1", public)
        self.assertIn("run-two@attempt-1", public)
        self.assertIn({"record_ref": "run@attempt-1", "code": "PUBLIC_REFERENCE_UNAVAILABLE"},
                      catalog["anomalies"])

    def test_disallowed_method_license_prevents_export(self):
        self.method["disclosure"]["license"] = "RESTRICTED"
        self.commit()
        with self.assertRaisesRegex(ContractError, "non-public"):
            export_backup(self.store, self.root / "restricted-method.zip", ["run@attempt-1"])

    def test_unknown_field_cannot_be_added_by_export_fields(self):
        self.decision["unreviewed_raw_rows"] = [["SYNTHETIC", "123"]]
        self.decision["disclosure"]["export_fields"] = list(self.decision)
        self.assertNotIn("unreviewed_raw_rows", public_record(self.decision))
        self.commit()
        with self.assertRaisesRegex(ContractError, "non-whitelisted"):
            export_backup(self.store, self.root / "unknown.zip", ["decision"])

    def test_export_fields_can_still_narrow_each_new_field(self):
        cases = ((self.method, "protocol_refs"), (self.run, "method_ref"),
                 (self.decision, "comparison_set"), (self.decision, "feedback_disposition"),
                 (self.decision, "selected_plan_ref"))
        for original, field in cases:
            candidate = copy.deepcopy(original)
            candidate["disclosure"]["export_fields"] = [k for k in candidate if k != field]
            self.assertNotIn(field, public_record(candidate))

    def test_new_fields_remain_subject_to_recursive_secret_and_path_scan(self):
        cases = ((self.method, "protocol_refs"), (self.run, "method_ref"),
                 (self.decision, "comparison_set"), (self.decision, "feedback_disposition"),
                 (self.decision, "selected_plan_ref"))
        for original, field in cases:
            for value, error in (("/" + "Users/fixture/private", "PRIVATE_LOCAL_PATH"),
                                 ("ghp_" + "x" * 30, "TOKEN")):
                candidate = copy.deepcopy(original)
                candidate[field] = {"nested": [value]} if field == "feedback_disposition" else value
                with self.assertRaisesRegex(ContractError, error):
                    public_record(candidate)

    def test_absent_or_null_method_ref_keeps_legacy_run_compatibility(self):
        for method_ref in (None, ""):
            run = dict(self.run, method_ref=method_ref)
            self.assertEqual(semantic_refs(run), ["round"])
            validate_relationships({"round": self.round, "run@attempt-1": run})
        legacy = dict(self.run)
        legacy.pop("method_ref")
        self.assertEqual(public_record(legacy), legacy)
        validate_relationships({"round": self.round, "run@attempt-1": legacy})


if __name__ == "__main__":
    unittest.main()
