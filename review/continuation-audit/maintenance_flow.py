"""Durable maintenance decisions, never a scheduler or business executor.

The caller verifies official tool/evidence results and supplies callbacks. A
reserved dispatch is UNKNOWN until reconciled; this module never retries it.
"""
import argparse
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def sha(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("INVALID_SHA256")
    return value


def transition(state, event, owner):
    s = copy.deepcopy(state)
    if s["owner_thread_id"] != owner:
        raise ValueError("FOREIGN_OWNER")
    # The same role may be dispatched again for a *new* frozen candidate.
    # Reentry for the existing candidate must still resolve to one intent.
    key = digest({"event": event, "candidate": s.get("candidate_manifest_sha256")}) if event.get("kind") == "RESERVE" else digest(event)
    if key in s.get("consumed_events", []):
        return s, False
    kind = event["kind"]
    stage = s["stage"]
    candidate = s.get("candidate_manifest_sha256")
    if kind in ("REVIEW_RESULT", "REPAIR_COMPLETE", "INSTALL_VERIFIED", "FLOW_GATE_VERIFIED"):
        evidence = event["evidence"]
        sha(evidence["sha256"])
        if not evidence.get("reference"):
            raise ValueError("MISSING_EVIDENCE_REFERENCE")
    if kind == "REVIEW_RESULT":
        receipt = sha(event["evidence"]["sha256"])
        if receipt in s.get("consumed_review_hashes", []):
            return s, False
        if event["candidate_manifest_sha256"] != candidate:
            raise ValueError("APPROVAL_CANDIDATE_MISMATCH")
        if stage not in ("REVIEW_READY", "REVIEW_RUNNING"):
            raise ValueError("REVIEW_NOT_EXPECTED")
        verdict = event["verdict"]
        if verdict not in ("CHANGES_REQUIRED", "APPROVED"):
            raise ValueError("UNSUPPORTED_VERDICT")
        s["stage"] = "REPAIR_READY" if verdict == "CHANGES_REQUIRED" else "INSTALL_READY"
        s["review_receipt"] = event["evidence"]
        s.setdefault("consumed_review_hashes", []).append(receipt)
        s["worker_handle"] = None
        s["next_action"] = "RESERVE_REPAIR" if verdict == "CHANGES_REQUIRED" else "VERIFY_AND_INSTALL_EXACT_APPROVED_CANDIDATE"
    elif kind == "RESERVE":
        role = event["role"]
        if role not in ("REPAIR", "REVIEW") or stage != role + "_READY":
            raise ValueError("DISPATCH_NOT_READY")
        s.update(stage="DISPATCH_UNKNOWN", dispatch_role=role,
                 dispatch_intent=key, worker_handle=None,
                 next_action="QUERY_DISPATCH_OUTCOME_DO_NOT_REDISPATCH")
    elif kind == "BIND":
        if stage != "DISPATCH_UNKNOWN" or event["dispatch_intent"] != s["dispatch_intent"]:
            raise ValueError("WRONG_DISPATCH_INTENT")
        handle = event["worker_handle"]
        if not handle.get("kind") or not handle.get("id") or not event.get("accepted"):
            raise ValueError("MISSING_REAL_ACCEPTED_HANDLE")
        s.update(stage=s["dispatch_role"] + "_RUNNING", worker_handle=handle,
                 next_action="POLL_BOUND_HANDLE")
    elif kind == "OBSERVATION":
        if stage not in ("DISPATCH_UNKNOWN", "REPAIR_RUNNING", "REVIEW_RUNNING"):
            raise ValueError("NO_LIVE_OPERATION")
        if event["status"] not in ("BUSY", "UNKNOWN", "TIMEOUT", "FAILED", "MISSING"):
            raise ValueError("USE_COMPLETION_CALLBACK")
        s["last_observation"] = event
        s["next_action"] = "QUERY_EXISTING_HANDLE_OR_RECONCILE_INTENT"
        s["error_class"] = event.get("error_class", event["status"])
    elif kind == "REPAIR_COMPLETE":
        if stage != "REPAIR_RUNNING" or event["worker_handle"] != s["worker_handle"]:
            raise ValueError("WRONG_REPAIR_HANDLE")
        new = sha(event["candidate_manifest_sha256"])
        if new == candidate:
            raise ValueError("NEW_FREEZE_REQUIRED")
        s.update(stage="REVIEW_READY", candidate_manifest_sha256=new,
                 candidate_evidence=event["evidence"], worker_handle=None,
                 next_action="RESERVE_INDEPENDENT_REVIEW")
    elif kind == "INSTALL_VERIFIED":
        if stage != "INSTALL_READY" or event["candidate_manifest_sha256"] != candidate:
            raise ValueError("INSTALL_NOT_APPROVED")
        if event["approval_receipt_sha256"] != s["review_receipt"]["sha256"]:
            raise ValueError("WRONG_APPROVAL_RECEIPT")
        s.update(stage="REAL_FLOW_WAIT", installed_source_sha256=sha(event["installed_source_sha256"]),
                 installation_evidence=event["evidence"], next_action="OBSERVE_REAL_EVALUATION_FEEDBACK_PUBLICATION")
    elif kind == "DATA_WAIT":
        if not event.get("direction") or not event.get("missing"):
            raise ValueError("EXPLICIT_DATA_GAP_REQUIRED")
        s.setdefault("direction_waits", {})[event["direction"]] = event
        s["independent_directions_blocked"] = False
    elif kind == "FLOW_GATE_VERIFIED":
        if stage != "REAL_FLOW_WAIT":
            raise ValueError("REAL_FLOW_NOT_EXPECTED")
        if set(event["gate_evidence"]) != {"real_inputs", "cost_evaluation", "feedback", "public_readback"}:
            raise ValueError("INCOMPLETE_REAL_FLOW")
        for item in event["gate_evidence"].values():
            sha(item["sha256"])
            if not item.get("reference"):
                raise ValueError("MISSING_GATE_REFERENCE")
        s.update(stage="TRIAL_GATE_READY", real_flow_evidence=event,
                 next_action="VERIFY_TWO_REAL_ROUTE_STARTS_BEFORE_TRIAL_CLOCK")
    else:
        raise ValueError("UNKNOWN_EVENT")
    s.setdefault("consumed_events", []).append(key)
    s["retry_class"] = "NO_BLIND_RETRY_RECONCILE_HANDLE"
    s["next_check"] = event.get("next_check", "NEXT_OFFICIAL_HEARTBEAT_OR_WORKER_COMPLETION")
    return s, True


def atomic(path, value):
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply(directory, owner, event=None, seed=None, crash_after_journal=False):
    """Journal is authoritative; current.json is a repairable materialized view.

    Existing schema-1 current state is accepted as baseline without rewriting
    history. No worker dispatch happens inside this function.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "flow.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        journal = directory / "flow-journal"
        journal.mkdir(exist_ok=True)
        entries = sorted(journal.glob("*.json"))
        current = directory / "current.json"
        if entries:
            previous = None
            for number, path in enumerate(entries, 1):
                entry = json.loads(path.read_text())
                if path.name != "%08d.json" % number or entry["sequence"] != number:
                    raise ValueError("JOURNAL_SEQUENCE_INVALID")
                if previous is not None and entry["previous_state_sha256"] != digest(previous):
                    raise ValueError("JOURNAL_CHAIN_INVALID")
                if digest(entry["state"]) != entry["state_sha256"]:
                    raise ValueError("JOURNAL_STATE_INVALID")
                previous = entry["state"]
            state = previous
        elif current.exists():
            state = json.loads(current.read_text())
        elif seed is not None:
            state = copy.deepcopy(seed)
        else:
            raise ValueError("EXPLICIT_INITIAL_STATE_REQUIRED")
        if state["owner_thread_id"] != owner:
            raise ValueError("FOREIGN_OWNER")
        updated, changed = transition(state, event, owner) if event else (state, False)
        if changed or not entries:
            entry = {"sequence": len(entries) + 1, "previous_state_sha256": digest(state),
                     "event": event, "state": updated, "state_sha256": digest(updated)}
            atomic(journal / ("%08d.json" % entry["sequence"]), entry)
            if crash_after_journal:
                raise RuntimeError("SIMULATED_CRASH_AFTER_DURABLE_JOURNAL")
        atomic(current, updated)
        return updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--event", help="Verified callback JSON; omitted = reconcile/read")
    parser.add_argument("--seed", help="Explicit initial state for a new state directory")
    args = parser.parse_args()
    event = json.loads(Path(args.event).read_text()) if args.event else None
    seed = json.loads(Path(args.seed).read_text()) if args.seed else None
    print(json.dumps(apply(args.state_dir, args.owner, event, seed), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
