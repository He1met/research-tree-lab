"""Independent registered historical decode only; no plan evaluation or writes."""
import argparse
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--code-root', required=True, type=Path)
    parser.add_argument('--project-root', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.code_root))
    from researchlib import conditional_review as cr
    from researchlib.funding_review import readonly_store
    from researchlib.common import canonical, digest
    store = readonly_store(args.project_root)
    records, metadata, anomalies = store.load(strict=True)
    assert not anomalies
    ref = 'd-btc-trades-20260921@1'
    dataset = records[ref]
    old_dataset = canonical(dataset)
    raw = store.data_root / 'objects' / dataset['sha256']
    old_stat = raw.stat()
    request = {'dataset_ref': ref, 'adapter': cr.TRADE_ADAPTER,
        'filename': 'BTC-USDT-SWAP-trades-2026-09-21.zip',
        'declared_partition': {'date': '2026-09-21', 'timezone': 'UTC+08:00'},
        'window': {'start_inclusive': '2026-09-20T16:00:00Z',
                   'end_exclusive': '2026-09-20T16:00:01Z'}}
    at = store.clock()
    method, attachments = cr.method_material(at)
    with args.receipt.open('x', encoding='utf-8') as output:
        started = time.monotonic()
        with patch.object(cr, 'evaluate', side_effect=AssertionError('Real plan evaluation forbidden')) as blocked:
            payload, bindings, audits = cr.decode_sources(store, [request], records, metadata, at,
                request['window']['end_exclusive'])
            assert not blocked.called
        elapsed = time.monotonic() - started
        audit = audits[0]
        after_records, after_meta, after_anomalies = store.load(strict=True)
        assert not after_anomalies
        new_stat = raw.stat()
        checks = {
            'dataset_canonical_bytes_unchanged': canonical(after_records[ref]) == old_dataset,
            'dataset_metadata_unchanged': after_meta[ref] == metadata[ref],
            'source_inode_size_mtime_unchanged': (old_stat.st_ino, old_stat.st_size, old_stat.st_mtime_ns) == (new_stat.st_ino, new_stat.st_size, new_stat.st_mtime_ns),
            'full_row_count_matches': audit['rows_read'] == 4_969_733,
            'full_expanded_byte_count_matches': audit['csv_bytes'] == 295_527_908,
            'full_csv_hash_matches': audit['csv_sha256'] == '478179bb74b5caceedf6fe55acb907a257bc661944b4867b559e1abaad2fde8b',
            'zip_crc_verified': audit['zip_crc'] == 'PASS',
            'selected_count_matches': len(payload['events']) == 112,
            'sequence_all_null': all(e['sequence'] is None for e in payload['events']),
            'coverage_unknown': payload['source_coverage'] == audit['source_coverage'] == 'UNKNOWN',
            'data_complete_false': payload['data_complete'] is False and audit['data_complete'] is False,
            'sixteen_sources_bound_and_retained': len(method['source_sha256']) == 16 and all(digest(attachments['SOURCE/'+p].encode()) == h for p,h in method['source_sha256'].items()),
        }
        assert all(checks.values()), checks
        receipt = {'state': 'PASS_INDEPENDENT_REGISTERED_HISTORICAL_DECODE_ONLY',
            'information_as_of': at, 'module_sha256': digest((args.code_root/'researchlib/conditional_review.py').read_bytes()),
            'method_code_sha256': method['method_code_sha256'], 'runtime': method['runtime'],
            'checks': checks, 'binding': bindings[0],
            'rows_read': audit['rows_read'], 'csv_bytes': audit['csv_bytes'], 'csv_sha256': audit['csv_sha256'],
            'zip_crc': audit['zip_crc'], 'same_open_fd_pre_post_sha256': audit['same_open_fd_pre_post_sha256'],
            'selected_event_count': len(payload['events']), 'source_coverage': 'UNKNOWN', 'data_complete': False,
            'elapsed_seconds_observed': round(elapsed, 3), 'kernel_evaluate_called': False,
            'formal_plan_evaluation_run': False, 'source_store_native_writes': False,
            'raw_events_or_prices_saved': False,
            'source_origin_and_acquisition': 'REGISTERED_DECLARATIONS_NOT_INDEPENDENT_OFFICIAL_AUTHENTICATION'}
        output.write(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'state': receipt['state'], 'checks': len(checks), 'rows_read': audit['rows_read'],
                      'elapsed_seconds': receipt['elapsed_seconds_observed']}))


if __name__ == '__main__':
    main()
