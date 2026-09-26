#!/usr/bin/env python3
"""Offline formal review preparation; no commit, network, publish or native action."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from researchlib.common import canonical, read_json
from researchlib.formal_review import prepare_outbox
from researchlib.funding_review import readonly_store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--batch-id', required=True)
    parser.add_argument('--input-manifest', required=True, help='Registered dataset requests only; no market event JSON')
    parser.add_argument('--market-event-cutoff')
    parser.add_argument('--output', required=True, help='New relative JSON name in private review outbox')
    args = parser.parse_args()
    try:
        store = readonly_store(args.project_root)
        path = prepare_outbox(store, args.batch_id, read_json(args.input_manifest), args.output, args.market_event_cutoff)
        print(canonical({'state': 'OUTBOX_PREPARED_NOT_COMMITTED', 'filename': path.name,
                         'formal_economic_evaluation': False, 'source_coverage': 'UNKNOWN'}).decode(), end='')
        return 0
    except Exception:
        print(canonical({'state': 'REJECTED', 'reason_code': 'FORMAL_PREPARATION_FAILED'}).decode(), file=sys.stderr, end='')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
