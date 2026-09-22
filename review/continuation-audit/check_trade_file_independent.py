"""Independent synthetic probes; no production input or economic acceptance."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import zipfile
from decimal import localcontext, ROUND_UP
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--code-root', required=True, type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.code_root))
    from researchlib import okx_trade_file as m
    start = 1704124800000
    name = 'BTC-USDT-SWAP-trades-2024-01-02'
    header = 'instrument_name,trade_id,side,price,size,created_time,source\n'
    window = {'start_inclusive': '2024-01-01T16:00:00Z', 'end_exclusive': '2024-01-01T16:00:00.001Z'}
    results = []
    with tempfile.TemporaryDirectory(prefix='independent-trade-') as temp:
        source = Path(temp) / 'input'
        def row(identifier, at=start, price='101.2500'):
            return f'BTC-USDT-SWAP,{identifier},buy,{price},0.1,{at},0\n'
        def pack(raw):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(name + '.csv', raw)
            return buffer.getvalue()
        def scan(raw, fmt='zip', manifest_change=None, **options):
            source.write_bytes(raw)
            manifest = {'schema_version': 1, 'format': fmt, 'filename': name + '.' + fmt,
                        'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw),
                        'source_url': 'https://www.okx.com/historical-data',
                        'obtained_at': '2024-01-03T00:00:00Z',
                        'declared_partition': {'date': '2024-01-02', 'timezone': 'UTC+08:00'}}
            if manifest_change:
                manifest_change(manifest)
            return m.scan_trade_file(source, manifest, information_as_of='2024-01-03T00:00:01Z',
                                     synthetic=True, **options)
        def reject(raw, **options):
            try:
                scan(raw, **options)
            except m.TradeFileError as error:
                assert error.validation_complete is False
                assert error.status == 'FILE_DECODE_NOT_COMPLETE'
                assert not hasattr(error, 'events') and str(source) not in str(error)
                return
            raise AssertionError('Unsafe fixture returned a complete result')
        basic = (header + row(1) + row(2, price='101.250') + row(3, price='102')).encode()
        with localcontext() as context:
            context.prec = 2
            context.rounding = ROUND_UP
            context.Emax = 9
            context.Emin = -9
            sample = scan(pack(basic), window=window)
        events = sample['kernel_payload']['events']
        assert len(events) == 3 and {e['sequence'] for e in events} == {None}
        assert [e['price'] for e in events] == ['101.25', '101.25', '102']
        assert len({e['event_id'] for e in events}) == 3
        assert sample['audit']['same_ms']['multiple_price_groups'] == 1
        results.append('same_ms_all_ids_preserved_no_order_or_first_fill_and_decimal_context_independent')
        raw_result = scan(basic, fmt='csv', window=window)
        assert [e['event_id'] for e in events] == [e['event_id'] for e in raw_result['kernel_payload']['events']]
        assert all(e['evidence_status'] == 'PROVISIONAL_SOURCE_COVERAGE_UNKNOWN' for e in events)
        assert raw_result['audit']['source_coverage'] == 'UNKNOWN' and not raw_result['audit']['data_complete']
        results.append('business_identity_stable_across_packaging_provenance_separate')
        prefix = header + row(1)
        tail = ''.join(row(i, start+1000) for i in range(2,5001))
        reject(pack((prefix+tail+row(1,start+1001)).encode()), window=window)
        reject(pack((prefix+tail+'malformed-final-row').encode()), window=window)
        reject(pack((prefix+tail+row(5001,start+86400000)).encode()), window=window)
        results.append('distant_duplicate_bad_tail_and_partition_violation_outside_selection_reject_whole_file')
        reject(pack(basic), window=window, max_selected_events=2)
        results.append('selected_limit_returns_no_truncated_payload')
        blob = bytearray(pack(basic)); central = blob.index(b'PK\x01\x02')
        # Declarations and CRC falsely promise a valid one-row prefix.
        import binascii
        prefix_bytes = prefix.encode()
        for position in (22, central+24): struct.pack_into('<I', blob, position, len(prefix_bytes))
        for position in (14, central+16): struct.pack_into('<I', blob, position, binascii.crc32(prefix_bytes))
        reject(bytes(blob), window=window)
        results.append('matching_local_central_prefix_size_crc_cannot_hide_deflate_tail')
        blob = bytearray(pack(basic)); central = blob.index(b'PK\x01\x02')
        for position in (14, central+16): struct.pack_into('<I', blob, position, 0)
        reject(bytes(blob), window=window)
        results.append('late_crc_error_invalidates_selected_prefix')
        with patch.object(m, 'CHUNK_BYTES', 31):
            assert scan(pack(basic),window=window)['audit']['rows_read'] == 3
            reject(pack((prefix+'x'*1025).encode()),window=window)
        results.append('small_chunk_boundaries_and_unterminated_overlong_line')
        reject(pack(basic), manifest_change=lambda value:value.update(data_complete=True))
        reject(pack(basic), manifest_change=lambda value:value.update(obtained_at='2024-01-01T15:59:59.999999Z'))
        assert scan(pack(basic), manifest_change=lambda value:value.update(obtained_at='2024-01-01T16:00:00.000001Z'))['audit']['rows_read'] == 3
        results.append('caller_completeness_rejected_and_fractional_acquisition_boundary_checked')
        completed_hashes = [0]
        original_hash = m._hash
        def observed_hash(*args):
            result = original_hash(*args)
            completed_hashes[0] += 1
            return result
        with patch.object(m, '_hash', observed_hash):
            reject(pack(basic),window=window,cancel=lambda: completed_hashes[0] == 2)
        assert completed_hashes == [2]
        results.append('cancellation_after_successful_final_hash_still_no_complete_result')
        result=scan(pack(basic))
        assert result['kernel_payload']['events'] == []
        assert result['audit']['selection']['presence'] == 'NOT_REQUESTED'
        empty={'start_inclusive':'2024-01-01T16:00:01Z','end_exclusive':'2024-01-01T16:00:02Z'}
        result=scan(pack(basic),window=empty)
        assert result['audit']['selection']['presence'] == 'NOT_OBSERVED_NOT_PROVEN_ABSENT'
        assert result['audit']['selection']['coverage'] == 'UNKNOWN'
        results.append('audit_only_and_empty_window_never_prove_absence')
    print(json.dumps({'state':'PASS_SYNTHETIC_INDEPENDENT_PROBES','groups':len(results),'checks':results,
                      'module_sha256':hashlib.sha256((args.code_root/'researchlib/okx_trade_file.py').read_bytes()).hexdigest(),
                      'production_mutated':False,'natural_or_economic_review':False},sort_keys=True))


if __name__ == '__main__':
    main()
