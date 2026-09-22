"""SYNTHETIC engineering fixtures in temporary stores; never production input."""
import copy
import tempfile
import unittest
import zipfile
from pathlib import Path

from researchlib.archive import export_backup, inspect_backup
from researchlib.common import ContractError, canonical, digest
from researchlib.contracts import semantic_refs, validate_relationships
from researchlib.public import public_record
from researchlib.store import Store


T0 = "2026-01-01T00:00:00Z"
T1 = "2026-01-02T00:00:00Z"
T2 = "2026-01-03T00:00:00Z"


def record(kind, at, **fields):
    # False exercises the real public exporter, confined to this temporary fixture.
    return dict(schema_version="1.0", record_type=kind, synthetic=False,
                created_at=at, available_at=at,
                disclosure={"visibility": "PUBLIC", "license": "OWN_ANALYSIS"},
                **fields)


class PublicRoundArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.time = T0
        self.store = Store(self.root, clock=lambda: self.time)
        self.parent = record("round", T0, round_id="parent", question="Synthetic parent",
                             mechanism="fixture", parent_round_id=None, plan_refs=[])
        self.plan = record("plan", T0, plan_id="plan", version=1, round_id="parent")
        self.store.commit_bundle("initial", "research", [self.parent, self.plan])
        self.review = record("review", T1, review_id="review", plan_ref="plan@1",
                             plan_hash=digest(canonical(self.plan)), revision=1,
                             review_method_ref="synthetic-status-method", data_cutoff=T1,
                             evaluation_stage="WAITING_DATA", metrics={"net_pnl": None})
        self.feedback = record("feedback", T1, feedback_id="feedback", review_ref="review")
        self.time = T1
        self.store.commit_bundle("reviewed", "review", [self.review, self.feedback])
        self.successor = record("round", T2, round_id="successor", question="Synthetic successor",
                                mechanism="fixture-child", parent_round_id="parent", plan_refs=[],
                                derived_from_feedback_refs=["feedback"], source_review_refs=["review"])
        self.time = T2

    def test_source_review_field_is_preserved_without_mutating_original(self):
        before = copy.deepcopy(self.successor)
        projected = public_record(self.successor)
        self.assertEqual(projected, before)
        self.assertEqual(self.successor, before)
        self.assertIn("review", semantic_refs(projected))
        # The change is scoped to round; it must not widen arbitrary record types.
        run = record("run", T2, run_id="run", round_id="parent", source_review_refs=["review"])
        self.assertNotIn("source_review_refs", public_record(run))

    def test_round_and_dependent_recovery_closure_preserves_exact_record_bytes(self):
        decision = record("decision", T2, decision_id="decision", feedback_ref="feedback",
                          source_review_ref="review", successor_round_id="successor")
        run = record("run", T2, run_id="run", round_id="successor")
        self.store.commit_bundle("successor", "research", [self.successor, decision, run])
        before, metadata, _ = self.store.load(strict=True)
        archive = self.root / "round-closure.zip"
        exported = export_backup(self.store, archive, ["successor", "decision", "run"])
        inspected = inspect_backup(archive)
        self.assertEqual(inspected["archive_id"], exported["archive_id"])
        self.assertEqual(set(inspected["record_refs"]), set(before))
        self.assertEqual(len(inspected["record_refs"]), 7)
        validate_relationships(before)
        with zipfile.ZipFile(archive) as contents:
            for ref, original in before.items():
                raw = contents.read("records/" + ref + ".json")
                self.assertEqual(raw, canonical(original))
                self.assertEqual(digest(raw), metadata[ref]["record_hash"])
        self.assertEqual(self.store.load(strict=True)[0], before)

    def test_missing_or_future_source_review_relationship_is_still_rejected(self):
        originals = self.store.load(strict=True)[0]
        missing = dict(self.successor, source_review_refs=["missing-review"])
        with self.assertRaisesRegex(ContractError, "MISSING_REFERENCE"):
            validate_relationships(dict(originals, successor=missing))
        early = dict(self.successor, created_at=T0, available_at=T0,
                     parent_round_id=None, derived_from_feedback_refs=[])
        with self.assertRaisesRegex(ContractError, "unavailable"):
            validate_relationships(dict(originals, successor=early))

    def test_unknown_round_field_cannot_be_widened_into_exact_archive(self):
        candidate = copy.deepcopy(self.successor)
        candidate["unreviewed_extra"] = "must remain excluded"
        candidate["disclosure"]["export_fields"] = list(candidate)
        self.assertNotIn("unreviewed_extra", public_record(candidate))
        self.assertEqual(public_record(candidate)["source_review_refs"], ["review"])
        self.store.commit_bundle("unknown-field", "research", [candidate])
        archive = self.root / "rejected.zip"
        with self.assertRaisesRegex(ContractError, "non-whitelisted fields"):
            export_backup(self.store, archive, ["successor"])
        self.assertFalse(archive.exists())

    def test_disclosure_can_still_exclude_the_new_field(self):
        candidate = copy.deepcopy(self.successor)
        candidate["disclosure"]["export_fields"] = [k for k in candidate if k != "source_review_refs"]
        self.assertNotIn("source_review_refs", public_record(candidate))
        self.store.commit_bundle("restricted-field", "research", [candidate])
        with self.assertRaisesRegex(ContractError, "non-whitelisted fields"):
            export_backup(self.store, self.root / "restricted.zip", ["successor"])

    def test_newly_allowed_field_remains_subject_to_recursive_privacy_scan(self):
        candidate = dict(self.successor, source_review_refs=["/" + "Users/fixture/private"])
        with self.assertRaisesRegex(ContractError, "PRIVATE_LOCAL_PATH"):
            public_record(candidate)
        candidate = dict(self.successor, source_review_refs=["ghp_" + "x" * 30])
        with self.assertRaisesRegex(ContractError, "TOKEN"):
            public_record(candidate)


if __name__ == "__main__":
    unittest.main()
