#!/usr/bin/env python3
"""Read-only conditional arithmetic report; no commit, publish or source promotion."""
import argparse
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from researchlib import Store
from researchlib.common import ContractError, canonical, now_iso, read_json, utc, under
from researchlib.funding_forward import evaluate


def write_report(project_root, relative, result):
    output = under(Path(project_root), '.local/review-computation/' + relative)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves existing reports/inputs, including concurrent writers.
    with output.open('xb') as stream:
        stream.write(canonical(result))
        stream.flush()
        os.fsync(stream.fileno())
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--plan-ref', required=True)
    parser.add_argument('--input', required=True, help='Normalized observations, never an implicit fixture fallback')
    parser.add_argument('--information-as-of', default=None)
    parser.add_argument('--market-event-cutoff', required=True)
    parser.add_argument('--previous', help='Previous complete kernel report; original reviews require explicit migration')
    parser.add_argument('--output', required=True, help='New relative filename under project .local/review-computation; no overwrite')
    args = parser.parse_args()
    info = args.information_as_of or now_iso()
    if utc(info) > utc(now_iso()):
        raise ContractError('Real evaluation cannot use a future information cutoff')
    store = Store(args.project_root)
    records, metadata, _ = store.load(strict=True)
    plan = records[args.plan_ref]
    if utc(metadata[args.plan_ref]['committed_at']) > utc(info):
        raise ContractError('Plan had not been committed by information cutoff')
    payload = read_json(args.input)
    if payload.get('synthetic') is not False:
        raise ContractError('Production helper requires explicitly nonsynthetic observations')
    previous = read_json(args.previous) if args.previous else None
    result = evaluate(plan, payload, info, args.market_event_cutoff, previous)
    result['report_scope'] = 'CONDITIONAL_COMPUTATION_ONLY_NOT_A_FORMAL_REVIEW'
    result['natural_trigger'] = False
    write_report(args.project_root, args.output, result)
    print(canonical({'state': result['evaluation_stage'], 'source_coverage': result['source_coverage'],
                     'data_complete': False, 'formal_review_committed': False}).decode(), end='')


if __name__ == '__main__':
    try:
        main()
    except (ContractError, OSError, KeyError, TypeError) as exc:
        print(canonical({'state': 'REJECTED', 'reason': str(exc)}).decode(), file=sys.stderr)
        sys.exit(2)
