#!/usr/bin/env python3
"""Official-app local file helper. Never starts another Codex/model process."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from researchlib import Store, publish_snapshot
from researchlib.archive import export_backup, restore_backup
from researchlib.common import ContractError, canonical, read_json
from researchlib.review import freeze_batch
from researchlib.snapshot import verify_snapshot


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog="Examples: python3 scripts/store_cli.py commit --input research/bundle.json; python3 scripts/store_cli.py snapshot --output web/public/data; python3 scripts/store_cli.py review-batch --id review-20260924")
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="Read committed counts, anomalies and live ownership")
    commands.add_parser("validate", help="Rehash every complete manifest and check references")
    c = commands.add_parser("claim", help="Claim a request; unknown owners are never stolen")
    c.add_argument("--request-key", required=True)
    c.add_argument("--owner", required=True)
    c.add_argument("--role", choices=["discovery", "research", "review", "publish"], required=True)
    c = commands.add_parser("commit", help="Append bundle JSON: {bundle_id,role,request_key,records,attachments}")
    c.add_argument("--input", required=True)
    c.add_argument("--claim-token")
    c = commands.add_parser("snapshot", help="Generate an immutable production snapshot, no synthetic fallback")
    c.add_argument("--output", required=True)
    c.add_argument("--as-of")
    c = commands.add_parser("verify-snapshot")
    c.add_argument("--output", required=True)
    c.add_argument("--snapshot-id", required=True)
    c = commands.add_parser("review-batch", help="Freeze every registered plan version including waiting/negative/old plans")
    c.add_argument("--id", required=True)
    c.add_argument("--cutoff")
    c.add_argument("--trigger-origin", default="MANUAL_SAFE_TEST")
    c.add_argument("--native-task-ref")
    c.add_argument("--commit", action="store_true")
    c = commands.add_parser("backup", help="Export exact publicly licensed closure; no restricted originals")
    c.add_argument("--output", required=True)
    c.add_argument("--record-ref", action="append")
    c = commands.add_parser("restore", help="Recover verified bytes into a new directory")
    c.add_argument("--archive", required=True)
    c.add_argument("--directory", required=True)
    args = parser.parse_args(argv)
    store = Store(args.project_root)
    if args.command == "status":
        result = store.status()
    elif args.command == "validate":
        from researchlib.contracts import validate_relationships
        records, metadata, anomalies = store.load(strict=True)
        validate_relationships(records)
        result = {"state": "VALIDATED", "records": len(records), "anomalies": anomalies}
    elif args.command == "claim":
        result = store.claim(args.request_key, args.owner, args.role)
    elif args.command == "commit":
        bundle = read_json(args.input)
        result = store.commit_bundle(bundle["bundle_id"], bundle["role"], bundle["records"], bundle.get("attachments"),
                                     request_key=bundle.get("request_key"), claim_token=args.claim_token)
    elif args.command == "snapshot":
        result = publish_snapshot(store, args.output, args.as_of)
    elif args.command == "verify-snapshot":
        result = verify_snapshot(args.output, args.snapshot_id)
    elif args.command == "review-batch":
        result = freeze_batch(store, args.id, args.cutoff, args.trigger_origin, args.native_task_ref)
        if args.commit:
            result = store.commit_bundle(args.id, "review", [result], request_key=args.id)
    elif args.command == "backup":
        result = export_backup(store, args.output, args.record_ref)
    elif args.command == "restore":
        result = restore_backup(args.archive, args.directory)
    print(canonical(result).decode(), end="")


if __name__ == "__main__":
    try:
        main()
    except (ContractError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"state": "REJECTED", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
