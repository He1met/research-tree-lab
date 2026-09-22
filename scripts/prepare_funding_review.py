#!/usr/bin/env python3
"""Prepare waiting-status review outbox; no market API, native identity or commit."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from researchlib.common import ContractError, canonical
from researchlib.funding_review import prepare_bundle, readonly_store, write_outbox


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--batch-id', required=True)
    parser.add_argument('--market-event-cutoff', help='Optional past market limit; information cutoff is always preparation now')
    parser.add_argument('--output', required=True, help='New JSON path relative to .local/review-outbox; never overwritten')
    args = parser.parse_args(argv)
    store = readonly_store(args.project_root)
    bundle = prepare_bundle(store, args.batch_id, args.market_event_cutoff)
    write_outbox(args.project_root, args.output, bundle)
    batch = bundle['records'][0]
    print(canonical({'state': 'OUTBOX_PREPARED_NOT_COMMITTED', 'batch_id': batch['batch_id'],
                     'coverage': batch['coverage'], 'natural_trigger': False,
                     'trigger_origin': 'MANUAL_PREPARATION_NOT_NATURAL',
                     'formal_economic_evaluation': False}).decode(), end='')


if __name__ == '__main__':
    try:
        main()
    except (ContractError, OSError, KeyError, TypeError, ValueError) as exc:
        # Do not print raw OSError filenames or private absolute input paths.
        reason = str(exc) if isinstance(exc, ContractError) else type(exc).__name__
        print(canonical({'state': 'REJECTED', 'reason': reason}).decode(), file=sys.stderr)
        sys.exit(2)
