"""Real old-file recheck plus separately labeled synthetic parser probes."""
from copy import deepcopy
from decimal import Decimal, localcontext
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile


def main():
    code, production = map(lambda x: Path(x).resolve(), sys.argv[1:3])
    sys.path.insert(0, str(code))
    from researchlib.common import ContractError, canonical
    from researchlib.okx_funding_file import normalize_funding_file
    sha = lambda b: hashlib.sha256(b).hexdigest()
    checks = []

    def check(name, function):
        function()
        checks.append({'case': name, 'result': 'PASS'})

    def reject(function):
        try:
            function()
        except ContractError:
            return
        raise AssertionError('expected ContractError')

    def manifest(blob, fmt='csv'):
        return {'schema_version': 1, 'format': fmt,
                'filename': 'allswap-fundingrates-2024-01-02.' + fmt,
                'sha256': sha(blob), 'size_bytes': len(blob),
                'source_url': 'https://www.okx.com/historical-data',
                'obtained_at': '2024-01-03T01:02:03Z',
                'declared_partition': {'date': '2024-01-02', 'timezone': 'UTC+08:00'}}

    def content(rows):
        out = io.StringIO(newline='')
        writer = csv.writer(out); writer.writerow(['instrument_name', 'funding_rate', 'funding_time'])
        writer.writerows(rows)
        return out.getvalue().encode()

    def run(rows, declaration=None):
        blob = content(rows)
        return normalize_funding_file(blob, declaration or manifest(blob),
            information_as_of='2024-01-04T00:00:00Z', synthetic=True)

    start = 1704124800000
    def edges():
        r = run([('BTC-USDT-SWAP', '.01', str(start)), ('BTC-USDT-SWAP', '-.01', str(start + 86399999))])
        assert len(r['kernel_payload']['events']) == 2
        for invalid in (start - 1, start + 86400000):
            reject(lambda: run([('BTC-USDT-SWAP', '.01', str(invalid))]))
    check('declared_utc8_partition_exact_millisecond_edges', edges)

    def duplicates():
        r = run([('BTC-USDT-SWAP', '1e-5', str(start)), ('BTC-USDT-SWAP', '.0000100', str(start))])
        e = r['kernel_payload']['events'][0]
        assert len(e['source_location']['source_rows']) == 2 and e['rate'] == '0.00001'
        assert r['audit']['duplicate_rows_removed_all_instruments'] == 1
        reject(lambda: run([('ETH-USDT-SWAP', '1e-5', str(start)), ('ETH-USDT-SWAP', '.1', str(start))]))
    check('numeric_dedup_keeps_source_rows_non_target_conflict_blocks', duplicates)

    def malformed_excluded():
        for rate, stamp in [('NaN', str(start)), ('.01', str(start - 1)), ('.01', str(start) + '.0')]:
            reject(lambda: run([('BTC-USDT-SWAP', '.01', str(start)), ('ETH-USDT-SWAP', rate, stamp)]))
    check('excluded_rows_still_validate_rate_timestamp_partition', malformed_excluded)

    def unknown_coverage():
        r = run([('ETH-USDT-SWAP', '.01', str(start))])
        assert r['kernel_payload']['events'] == []
        assert r['audit']['target_presence'] == 'NOT_OBSERVED_NOT_PROVEN_ABSENT'
        assert r['audit']['source_coverage'] == 'UNKNOWN' and r['audit']['data_complete'] is False
    check('missing_target_does_not_infer_zero_or_coverage', unknown_coverage)

    def declarations():
        blob = content([('BTC-USDT-SWAP', '.01', str(start))])
        for key, value in [('sha256', '0' * 64), ('size_bytes', True), ('source_url', 'https://www.okx.com.evil.example/a.csv'), ('obtained_at', '2024-01-01T15:59:59Z')]:
            m = manifest(blob); m[key] = value
            reject(lambda: normalize_funding_file(blob, m, information_as_of='2024-01-04T00:00:00Z', synthetic=True))
        m = manifest(blob); m['complete'] = True
        reject(lambda: normalize_funding_file(blob, m, information_as_of='2024-01-04T00:00:00Z', synthetic=True))
    check('false_identity_backdate_and_complete_assertion_rejected', declarations)

    def precision():
        rows = [('BTC-USDT-SWAP', '.1234567890123456789012345678900', str(start))]
        expected = canonical(run(rows))
        with localcontext() as ctx:
            ctx.prec = 2; ctx.Emax = 2; ctx.Emin = -2
            assert canonical(run(rows)) == expected
    check('ambient_precision_cannot_change_normalized_rate', precision)

    def zip_scope():
        data = content([('BTC-USDT-SWAP', '.01', str(start))])
        for name in ['../allswap-fundingrates-2024-01-02.csv', 'nested/allswap-fundingrates-2024-01-02.csv']:
            out = io.BytesIO()
            with zipfile.ZipFile(out, 'w') as archive:
                archive.writestr(name, data)
            blob = out.getvalue()
            reject(lambda: normalize_funding_file(blob, manifest(blob, 'zip'), information_as_of='2024-01-04T00:00:00Z', synthetic=True))
    check('zip_paths_do_not_extract_or_parse_as_valid_source', zip_scope)

    source = json.loads((production / 'research/bootstrap-v1/sources.json').read_text())['archive']
    blob = (production / '.local/data/okx/research-bootstrap-20260923-v1/allswap-fundingrates-2026-09-21.zip').read_bytes()
    m = {'schema_version': 1, 'format': 'zip', 'filename': source['original_filename'],
         'sha256': source['sha256'], 'size_bytes': source['bytes'], 'source_url': source['source_url'],
         'obtained_at': source['downloaded_at'], 'declared_partition': {'date': '2026-09-21', 'timezone': 'UTC+08:00'}}
    immutable_m = deepcopy(m)
    real = normalize_funding_file(blob, m, information_as_of=datetime.now(timezone.utc).isoformat(), synthetic=False)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        rows = list(csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode())))
    originals = {int(r['funding_time']): Decimal(r['funding_rate']) for r in rows if r['instrument_name'] == 'BTC-USDT-SWAP'}
    for event in real['kernel_payload']['events']:
        assert Decimal(event['rate']) == originals[int(event['event_id'].rsplit(':', 1)[1])]
        assert event['settlement_mark'] is None and event['available_at'] == source['downloaded_at']
    assert (real['audit']['rows_read'], real['audit']['target_events'], real['audit']['excluded_rows']) == (2103, 3, 2100)
    assert real['audit']['source_coverage'] == 'UNKNOWN' and real['audit']['data_complete'] is False
    assert m == immutable_m and sha(blob) == source['sha256']
    files = ['researchlib/okx_funding_file.py', 'tests/test_okx_funding_file.py', 'tests/replay_okx_funding_sample.py', 'docs/OKX_FUNDING_FILE.md', 'tests/receipts/okx-funding-real-sample.json']
    receipt = {'decision': 'PASS_SCOPED_SINGLE_FUNDING_FILE_DECODE',
               'synthetic_probe_groups': checks,
               'real_old_sample_recheck': {'source_sha256': sha(blob), 'rows': 2103, 'target_events': 3, 'excluded_rows': 2100, 'all_target_rates_equal_independent_csv_decode': True, 'zip_crc': real['audit']['zip_crc'], 'source_coverage': 'UNKNOWN', 'settlement_marks': 'MISSING'},
               'source_sha256': {file: sha((code / file).read_bytes()) for file in files},
               'economic_or_natural_result': False, 'production_store_writes': False,
               'new_source_acquisition': False, 'raw_rows_written_to_receipt': False}
    Path(__file__).with_name('funding-file-independent-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'decision': receipt['decision'], 'synthetic_probe_groups': len(checks), 'real_target_events': 3}))


if __name__ == '__main__':
    main()
