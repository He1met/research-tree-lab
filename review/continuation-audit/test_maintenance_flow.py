"""Isolated engineering tests; no production research or natural-run evidence."""
import fcntl
import json
from pathlib import Path
import tempfile
import unittest

from maintenance_flow import apply, digest, transition


OWNER = "test-maintenance-owner"
HANDLE = {"kind": "isolated_test_handle", "id": "worker-1"}


def evidence(char):
    return {"reference": "isolated-evidence-" + char, "sha256": char * 64}


def initial():
    return {"schema_version": 1, "owner_thread_id": OWNER, "stage": "REVIEW_READY",
            "candidate_manifest_sha256": "a" * 64, "consumed_review_hashes": []}


def review(verdict, candidate="a", receipt="b"):
    return {"kind": "REVIEW_RESULT", "candidate_manifest_sha256": candidate * 64,
            "verdict": verdict, "evidence": evidence(receipt)}


def advance(state, event):
    return transition(state, event, OWNER)[0]


class MaintenanceFlowTests(unittest.TestCase):
    def repaired(self):
        state = advance(initial(), review("CHANGES_REQUIRED"))
        state = advance(state, {"kind": "RESERVE", "role": "REPAIR"})
        state = advance(state, {"kind": "BIND", "accepted": True,
                              "dispatch_intent": state["dispatch_intent"], "worker_handle": HANDLE})
        return advance(state, {"kind": "REPAIR_COMPLETE", "worker_handle": HANDLE,
                              "candidate_manifest_sha256": "c" * 64, "evidence": evidence("d")})

    def test_failure_enters_repair_once(self):
        result = advance(initial(), review("CHANGES_REQUIRED"))
        self.assertEqual(result["stage"], "REPAIR_READY")
        result = advance(result, {"kind": "RESERVE", "role": "REPAIR"})
        duplicate = review("CHANGES_REQUIRED")
        duplicate["next_check"] = "DIFFERENT_TRANSPORT_METADATA"
        self.assertEqual(advance(result, duplicate), result)
        self.assertEqual(result["stage"], "DISPATCH_UNKNOWN")

    def test_repair_delivery_enters_review(self):
        self.assertEqual(self.repaired()["stage"], "REVIEW_READY")
        state = advance(self.repaired(), {"kind": "RESERVE", "role": "REVIEW"})
        state = advance(state, {"kind": "BIND", "accepted": True,
                              "dispatch_intent": state["dispatch_intent"], "worker_handle": HANDLE})
        self.assertEqual(state["stage"], "REVIEW_RUNNING")

    def test_approval_install_real_flow(self):
        state = advance(self.repaired(), review("APPROVED", "c", "e"))
        self.assertEqual(state["stage"], "INSTALL_READY")
        state = advance(state, {"kind": "INSTALL_VERIFIED", "candidate_manifest_sha256": "c" * 64,
                              "approval_receipt_sha256": "e" * 64,
                              "installed_source_sha256": "f" * 64, "evidence": evidence("f")})
        self.assertEqual(state["stage"], "REAL_FLOW_WAIT")

    def test_data_wait_does_not_block_independent_direction(self):
        state = advance(self.repaired(), {"kind": "DATA_WAIT", "direction": "A",
                                         "missing": ["qualified_input"], "next_check": "NEW_SOURCE_EVIDENCE"})
        self.assertFalse(state["independent_directions_blocked"])
        self.assertEqual(state["stage"], "REVIEW_READY")
        self.assertNotIn("B", state["direction_waits"])

    def test_wrong_approval_candidate_rejected(self):
        with self.assertRaisesRegex(ValueError, "CANDIDATE_MISMATCH"):
            advance(self.repaired(), review("APPROVED", "a", "e"))

    def test_second_candidate_can_reserve_new_repair(self):
        state = self.repaired()
        old_intent = state["dispatch_intent"]
        state = advance(state, review("CHANGES_REQUIRED", "c", "e"))
        state = advance(state, {"kind": "RESERVE", "role": "REPAIR"})
        self.assertEqual(state["stage"], "DISPATCH_UNKNOWN")
        self.assertNotEqual(state["dispatch_intent"], old_intent)

    def test_foreign_owner_rejected(self):
        with self.assertRaisesRegex(ValueError, "FOREIGN_OWNER"):
            transition(initial(), review("CHANGES_REQUIRED"), "someone-else")

    def test_unknown_timeout_never_redispatch(self):
        state = advance(advance(initial(), review("CHANGES_REQUIRED")), {"kind": "RESERVE", "role": "REPAIR"})
        for status in ("UNKNOWN", "TIMEOUT", "BUSY", "FAILED", "MISSING"):
            state = advance(state, {"kind": "OBSERVATION", "status": status})
            self.assertEqual(state["stage"], "DISPATCH_UNKNOWN")
            with self.assertRaisesRegex(ValueError, "NOT_READY"):
                advance(state, {"kind": "RESERVE", "role": "REPAIR", "nonce": status})

    def test_crash_after_journal_reentry_deduplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "SIMULATED_CRASH"):
                apply(directory, OWNER, review("CHANGES_REQUIRED"), initial(), True)
            self.assertFalse((Path(directory) / "current.json").exists())
            restored = apply(directory, OWNER, review("CHANGES_REQUIRED"))
            self.assertEqual(restored["stage"], "REPAIR_READY")
            self.assertEqual(len(list((Path(directory) / "flow-journal").glob("*.json"))), 1)

    def test_import_schema1_keeps_existing_binding_and_consumed_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            seed = initial()
            seed.update(stage="REPAIR_RUNNING", worker_handle=HANDLE, dispatch_intent="existing-intent",
                        consumed_review_hashes=["b" * 64], installed_source_sha256="f" * 64)
            (Path(directory) / "current.json").write_text(json.dumps(seed))
            self.assertEqual(apply(directory, OWNER), seed)
            self.assertEqual(apply(directory, OWNER, review("CHANGES_REQUIRED")), seed)
            self.assertEqual(len(list((Path(directory) / "flow-journal").glob("*.json"))), 1)

    def test_busy_lock_is_not_stolen(self):
        with tempfile.TemporaryDirectory() as directory:
            with (Path(directory) / "flow.lock").open("a+b") as locked:
                fcntl.flock(locked, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    apply(directory, OWNER, seed=initial())
            self.assertFalse((Path(directory) / "current.json").exists())

    def test_tampered_journal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            apply(directory, OWNER, seed=initial())
            path = Path(directory) / "flow-journal" / "00000001.json"
            value = json.loads(path.read_text())
            value["state"]["stage"] = "INSTALL_READY"
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "JOURNAL_STATE_INVALID"):
                apply(directory, OWNER)


if __name__ == "__main__":
    unittest.main()
