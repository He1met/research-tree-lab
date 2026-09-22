"""Read-only real-sample decode, separate from synthetic unit tests.

Writes only a redacted diagnostic receipt to --receipt. Reads the existing
content-addressed source and dataset directly; never copies raw data or computes
an economic result. Run from the repository root with Python 3.9+.
"""
import argparse
import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
import platform
import resource
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from researchlib.okx_trade_file import scan_trade_file


@contextmanager
def new_receipt(path, source, dataset):
    """Reserve a new output inode before scanning; never replace any file.

    Existing parent directories are walked using directory FDs with NOFOLLOW.
    O_EXCL handles a competing creator, including a symlink/hardlink alias. The
    output FD remains open throughout the scan: a later pathname replacement
    cannot redirect writes. Failure can leave an empty new reservation; it is
    not a receipt, and the helper deliberately performs no path-based cleanup.
    """
    destination = Path(os.path.abspath(os.fspath(path)))
    protected = {os.path.abspath(os.fspath(source)), os.path.abspath(os.fspath(dataset))}
    if str(destination) in protected:
        raise ValueError('Receipt must be a new path distinct from source and dataset')
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent_fd = os.open(destination.anchor, directory_flags)
    output_fd = None
    try:
        for component in destination.parent.parts[1:]:
            child_fd = os.open(component, directory_flags, dir_fd=parent_fd)
            os.close(parent_fd)
            parent_fd = child_fd
        output_fd = os.open(destination.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                            0o600, dir_fd=parent_fd)
    finally:
        os.close(parent_fd)
    try:
        with os.fdopen(output_fd, 'w', encoding='utf-8') as output:
            output_fd = None
            yield output
    finally:
        if output_fd is not None:
            os.close(output_fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--dataset', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    args = parser.parse_args(argv)
    with new_receipt(args.receipt, args.source, args.dataset) as receipt_stream:
        return run(args, receipt_stream)


def run(args, receipt_stream):
    dataset_bytes = args.dataset.read_bytes()
    dataset = json.loads(dataset_bytes)
    if (dataset.get('dataset_id') != 'd-btc-trades-20260921' or dataset.get('version') != 1
            or dataset.get('synthetic') is not False or dataset.get('instrument_ref') != 'BTC-USDT-SWAP'
            or dataset.get('data_role') != 'TARGET_TRADE_HISTORY'):
        raise ValueError('Expected the recorded real historical trade dataset v1')
    manifest = {'schema_version': 1, 'format': 'zip', 'filename': 'BTC-USDT-SWAP-trades-2026-09-21.zip',
                'sha256': dataset['sha256'], 'size_bytes': dataset['bytes'],
                'source_url': dataset['source_url'], 'obtained_at': dataset['acquired_at'],
                'declared_partition': {'date': '2026-09-21', 'timezone': 'UTC+08:00'}}
    information_as_of = datetime.now(timezone.utc).isoformat()
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    started = time.monotonic()
    result = scan_trade_file(args.source, manifest, information_as_of=information_as_of, synthetic=False,
        window={'start_inclusive': '2026-09-20T16:00:00Z', 'end_exclusive': '2026-09-20T16:00:01Z'})
    elapsed = time.monotonic() - started
    audit, payload = result['audit'], result['kernel_payload']
    if args.dataset.read_bytes() != dataset_bytes:
        raise ValueError('Dataset changed during read-only sample replay')
    # Prior report is a comparison target, not the decoder implementation.
    checks = {'rows_match_previous_diagnostic': audit['rows_read'] == 4_969_733,
              'expanded_bytes_match_previous_diagnostic': audit['csv_bytes'] == 295_527_908,
              'member_sha_matches_previous_diagnostic': audit['csv_sha256'] == '478179bb74b5caceedf6fe55acb907a257bc661944b4867b559e1abaad2fde8b',
              'same_ms_groups_match_previous_diagnostic': audit['same_ms']['multiple_row_groups'] == 352_819,
              'same_ms_multi_price_groups_match_previous_diagnostic': audit['same_ms']['multiple_price_groups'] == 157_283,
              'max_same_ms_rows_match_previous_diagnostic': audit['same_ms']['max_rows_per_ms'] == 2743,
              'selected_events_sequence_null': all(e['sequence'] is None for e in payload['events']),
              'coverage_remains_unknown': audit['source_coverage'] == 'UNKNOWN' and not audit['data_complete'],
              'dataset_bytes_unchanged': True}
    module = Path(__file__).resolve().parents[1] / 'researchlib' / 'okx_trade_file.py'
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    receipt = {'status': 'PASS_SCOPED_REAL_FILE_DECODE' if all(checks.values()) else 'COMPARISON_FAILED',
               'evidence_class': 'REAL_EXISTING_SOURCE_READ_ONLY_NOT_ECONOMIC_REVIEW',
               'adapter_sha256': hashlib.sha256(module.read_bytes()).hexdigest(),
               'adapter_version': audit['adapter_version'], 'information_as_of': information_as_of,
               'source_archive_sha256': manifest['sha256'], 'source_archive_bytes': manifest['size_bytes'],
               'dataset_ref': dataset['dataset_id'] + '@1', 'dataset_sha256': hashlib.sha256(dataset_bytes).hexdigest(),
               'declared_obtained_at_from_dataset': manifest['obtained_at'],
               'source_url_declaration': manifest['source_url'], 'source_origin': audit['source_origin'],
               'acquisition_time': audit['acquisition_time'], 'decode_status': audit['status'],
               'csv_bytes': audit['csv_bytes'], 'csv_sha256': audit['csv_sha256'],
               'zip_crc': audit['zip_crc'], 'rows_read': audit['rows_read'],
               'same_ms': audit['same_ms'], 'selection': audit['selection'],
               'source_coverage': audit['source_coverage'], 'data_complete': audit['data_complete'],
               'same_open_fd_pre_post_sha256': audit['same_open_fd_pre_post_sha256'],
               'limits': audit['limits'], 'checks': checks,
               'elapsed_seconds_observed': round(elapsed, 3),
               'peak_rss_before': rss_before, 'peak_rss_after': rss_after,
               'peak_rss_units': 'bytes' if sys.platform == 'darwin' else 'KiB on Linux; OS-specific otherwise',
               'python': platform.python_version(), 'platform': sys.platform,
               'boundary': ['No network or new acquisition', 'No source/native/store writes',
                            'No raw redistribution; receipt excludes selected rows and prices',
                            'No event ordering, first trade, omission guarantee, mark, funding, costs, or economic review',
                            'Same-ms metrics are whole-file observed groups; sequence remains null']}
    receipt_stream.write(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n')
    receipt_stream.flush()
    os.fsync(receipt_stream.fileno())
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
