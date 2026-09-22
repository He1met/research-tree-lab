"""Recheck one known real local sample; never download, publish or mutate store.

Run from the repository root with --sample PATH and --receipt NEW_PATH. This is
separate from the synthetic unit suite. The receipt excludes source rate rows.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from researchlib.common import ContractError, digest
from researchlib.okx_funding_file import MAX_SOURCE_BYTES, normalize_funding_file

KNOWN_ARCHIVE = '34a7e077c89ade3d60e5afe26e615bcf2df10fdfab04930b62d185810e8f698c'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path, help='New sanitized JSON file; never overwrite')
    args = parser.parse_args()
    with args.sample.open('rb') as stream:
        blob = stream.read(MAX_SOURCE_BYTES + 1)
    if digest(blob) != KNOWN_ARCHIVE:
        raise ContractError('Not the previously observed real bootstrap archive')
    source = json.loads((ROOT / 'research/bootstrap-v1/sources.json').read_text())['archive']
    manifest = {'schema_version': 1, 'format': 'zip', 'filename': source['original_filename'],
                'sha256': source['sha256'], 'size_bytes': source['bytes'],
                'source_url': source['source_url'], 'obtained_at': source['downloaded_at'],
                'declared_partition': {'date': '2026-09-21', 'timezone': 'UTC+08:00'}}
    info = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    result = normalize_funding_file(blob, manifest, information_as_of=info, synthetic=False)
    audit = result['audit']
    observed = {k: audit[k] for k in [
        'adapter_version', 'zip_crc', 'csv_member', 'csv_bytes', 'csv_sha256', 'partition_utc',
        'rows_read', 'target_rows_read', 'excluded_rows', 'unique_rows_all_instruments',
        'duplicate_rows_removed_all_instruments', 'target_events', 'source_coverage',
        'data_complete', 'expected_event_count', 'settlement_schedule_inferred']}
    if (audit['rows_read'], audit['target_events'], audit['excluded_rows']) != (2103, 3, 2100):
        raise ContractError('Known real sample counts did not reproduce')
    events = result['kernel_payload']['events']
    if not all(e['settlement_mark'] is None and e['available_at'] == source['downloaded_at'] for e in events):
        raise ContractError('Normalizer changed mark/acquisition boundary')
    receipt = {'schema_version': 1, 'status': 'PASS_SCOPED_REAL_FUNDING_FILE_DECODE',
               'evidence_stage': 'REAL_EXISTING_FILE_OFFLINE_RECHECK_NOT_NEW_ACQUISITION_OR_ECONOMIC_RESULT',
               'checked_at': info, 'source_manifest': manifest, 'observed': observed,
               'source_origin': audit['source_origin'],
               'source_acquisition_basis': 'Previously recorded official browser download; offline constraints do not independently prove origin or timestamp',
               'raw_disclosure': 'LOCAL_ONLY_NOT_INCLUDED_IN_RECEIPT',
               'adapter_sha256': digest((ROOT / 'researchlib/okx_funding_file.py').read_bytes()),
               'replay_script_sha256': digest(Path(__file__).read_bytes()),
               'network_calls': 0, 'production_or_native_writes': 0,
               'complete_coverage_verified': False, 'settlement_mark_verified': False,
               'kernel_economic_result_executed': False, 'synthetic_tests_included': False}
    # Explicit caller-selected receipt only. No raw output or automatic store write.
    with args.receipt.open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'status': receipt['status'], 'rows': audit['rows_read'],
                      'target_events': len(events), 'source_coverage': 'UNKNOWN'}))


if __name__ == '__main__':
    main()
