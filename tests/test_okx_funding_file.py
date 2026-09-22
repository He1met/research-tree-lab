"""SYNTHETIC hostile inputs; not real source/coverage or economic acceptance."""
import copy
import io
import json
import struct
import unittest
import warnings
import zipfile
from decimal import localcontext
from pathlib import Path
from unittest.mock import patch

from researchlib.common import ContractError, canonical, digest
from researchlib import okx_funding_file as adapter

NAME = 'allswap-fundingrates-2024-01-02'
START = 1704124800000  # 2024-01-01T16:00:00Z, UTC+8 date 2024-01-02.
INFO = '2024-01-04T00:00:00Z'


def csv_bytes(rows=None, header=adapter.HEADER):
    if rows is None:
        rows = [('BTC-USDT-SWAP', '0.001', str(START)),
                ('ETH-USDT-SWAP', '-0.002', str(START + 3600000)),
                ('BTC-USDT-SWAP', '1e-5', str(START + 2345678))]
    return (','.join(header) + '\r\n' + ''.join(','.join(row) + '\r\n' for row in rows)).encode()


def zip_bytes(payload=None, names=None, compression=zipfile.ZIP_DEFLATED):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=compression) as archive:
        for name in names or [NAME + '.csv']:
            archive.writestr(name, csv_bytes() if payload is None else payload)
    return stream.getvalue()


def manifest(blob, fmt='zip'):
    return {'schema_version': 1, 'format': fmt, 'filename': NAME + '.' + fmt,
            'sha256': digest(blob), 'size_bytes': len(blob),
            'source_url': 'https://www.okx.com/zh-hans/historical-data',
            'obtained_at': '2024-01-03T23:00:00Z',
            'declared_partition': {'date': '2024-01-02', 'timezone': 'UTC+08:00'}}


def parse(blob=None, source=None, **kwargs):
    blob = zip_bytes() if blob is None else blob
    return adapter.normalize_funding_file(blob, manifest(blob) if source is None else source,
                                          information_as_of=kwargs.pop('information_as_of', INFO),
                                          synthetic=kwargs.pop('synthetic', True), **kwargs)


class FundingFileSynthetic(unittest.TestCase):
    def test_zip_real_structure_normalizes_only_target_without_calendar(self):
        result = parse()
        events, audit = result['kernel_payload']['events'], result['audit']
        self.assertEqual([e['event_at'] for e in events], ['2024-01-01T16:00:00.000Z', '2024-01-01T16:39:05.678Z'])
        self.assertEqual([e['rate'] for e in events], ['0.001', '0.00001'])
        self.assertEqual(audit['excluded_rows'], 1)
        self.assertEqual(audit['zip_crc'], 'PASS')
        self.assertEqual(audit['source_coverage'], 'UNKNOWN')
        self.assertFalse(audit['data_complete'])
        self.assertIsNone(audit['expected_event_count'])
        self.assertFalse(audit['settlement_schedule_inferred'])
        self.assertTrue(all(e['settlement_mark'] is None for e in events))
        self.assertEqual(events[1]['source_location']['source_rows'][0]['line'], 4)
        self.assertEqual(events[1]['available_at'], '2024-01-03T23:00:00Z')
        self.assertIn('NOT_NETWORK_PROOF', audit['source_origin'])

    def test_direct_csv_and_optional_bom_preserve_byte_identity(self):
        for prefix in [b'', b'\xef\xbb\xbf']:
            blob = prefix + csv_bytes()
            result = parse(blob, manifest(blob, 'csv'))
            self.assertEqual(result['audit']['zip_crc'], 'NOT_APPLICABLE')
            self.assertEqual(result['audit']['csv_sha256'], digest(blob))
            self.assertEqual(result['kernel_payload']['events'][0]['source_sha256'], digest(blob))

    def test_numeric_duplicate_keeps_each_original_line_and_lexeme(self):
        data = csv_bytes([('BTC-USDT-SWAP', '1e-5', str(START)),
                          ('BTC-USDT-SWAP', '0.0000100', str(START))])
        result = parse(zip_bytes(data))
        self.assertEqual(result['audit']['duplicate_rows_removed_all_instruments'], 1)
        event = result['kernel_payload']['events'][0]
        self.assertEqual(event['rate'], '0.00001')
        self.assertEqual([v['line'] for v in event['source_location']['source_rows']], [2, 3])
        self.assertEqual([v['raw_fields']['funding_rate'] for v in event['source_location']['source_rows']], ['1e-5', '0.0000100'])

    def test_conflicting_duplicate_rejected_including_excluded_contract(self):
        for instrument in ['BTC-USDT-SWAP', 'ETH-USDT-SWAP']:
            with self.subTest(instrument=instrument), self.assertRaises(ContractError):
                parse(zip_bytes(csv_bytes([(instrument, '.001', str(START)), (instrument, '.002', str(START))])))

    def test_event_identity_is_not_archive_hash_or_line_number(self):
        a, b = zip_bytes(), zip_bytes(compression=zipfile.ZIP_STORED)
        self.assertNotEqual(digest(a), digest(b))
        ea, eb = parse(a)['kernel_payload']['events'][0], parse(b)['kernel_payload']['events'][0]
        self.assertEqual(ea['event_id'], eb['event_id'])
        self.assertNotEqual(ea['source_sha256'], eb['source_sha256'])
        self.assertNotEqual(canonical(ea), canonical(eb))  # Needs explicit merge/correction.

    def test_actual_manifest_size_sha_and_exact_fields_required(self):
        blob = zip_bytes()
        for field, value in [('sha256', '0' * 64), ('size_bytes', len(blob) + 1),
                             ('size_bytes', True), ('schema_version', True), ('schema_version', '1')]:
            source = manifest(blob); source[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ContractError):
                parse(blob, source)
        for key in ['sha256', 'obtained_at', 'source_url']:
            source = manifest(blob); del source[key]
            with self.assertRaises(ContractError): parse(blob, source)
        source = manifest(blob); source['complete'] = True
        with self.assertRaises(ContractError): parse(blob, source)

    def test_host_allowlist_and_no_credentials_parameters_or_api_source(self):
        blob = zip_bytes()
        bad = ['http://www.okx.com/historical-data', 'https://www.okx.com.evil.test/a.zip',
               'https://user:secret@www.okx.com/a.zip', 'https://www.okx.com/a.zip?obtained_at=2024',
               'https://www.okx.com/a.zip#secret', 'https://www.okx.com:443/a.zip',
               'https://www.okx.com/api/v5/public/funding-rate', 'https://www.okx.com\\@evil.test/a.zip']
        for url in bad:
            source = manifest(blob); source['source_url'] = url
            with self.subTest(url=url), self.assertRaises(ContractError): parse(blob, source)

    def test_declared_partition_filename_timezone_and_calendar_must_agree(self):
        blob = zip_bytes()
        for change in [{'date': '2024-01-03', 'timezone': 'UTC+08:00'},
                       {'date': '2024-01-02', 'timezone': 'UTC'},
                       {'date': '2024-01-02', 'timezone': 'UTC+08:00', 'complete': True}]:
            source = manifest(blob); source['declared_partition'] = change
            with self.assertRaises(ContractError): parse(blob, source)
        source = manifest(blob); source['filename'] = '../' + source['filename']
        with self.assertRaises(ContractError): parse(blob, source)

    def test_half_open_partition_exact_millisecond_edges(self):
        for ms in [START, START + 86400000 - 1]:
            self.assertEqual(parse(zip_bytes(csv_bytes([('BTC-USDT-SWAP', '0', str(ms))])))['audit']['target_events'], 1)
        for ms in [START - 1, START + 86400000]:
            with self.assertRaises(ContractError): parse(zip_bytes(csv_bytes([('BTC-USDT-SWAP', '0', str(ms))])))

    def test_event_after_acquisition_or_acquisition_after_information_rejected(self):
        blob = zip_bytes()
        for at in ['2024-01-01T15:59:59.999Z', '2024-01-05T00:00:00Z', '2024-01-03T00:00:00']:
            source = manifest(blob); source['obtained_at'] = at
            with self.assertRaises(ContractError): parse(blob, source)
        with self.assertRaises(ContractError): parse(information_as_of='2999-01-01T00:00:00Z')
        with self.assertRaises(ContractError): parse(information_as_of='2024-01-04')
        with self.assertRaises(ContractError): parse(information_as_of='2024-01-04T00:00:00+00:60')

    def test_unfinished_declared_day_can_never_claim_full_partition_coverage(self):
        blob = zip_bytes(csv_bytes([('BTC-USDT-SWAP', '.01', str(START))]))
        source = manifest(blob); source['obtained_at'] = '2024-01-01T16:00:01Z'
        result = parse(blob, source, information_as_of='2024-01-01T16:00:02Z')
        self.assertEqual(result['audit']['target_events'], 1)
        self.assertEqual(result['audit']['source_coverage'], 'UNKNOWN')
        self.assertFalse(result['audit']['data_complete'])
        self.assertIsNone(result['audit']['expected_event_count'])

    def test_integer_milliseconds_only_no_float_rounding_or_unicode_digits(self):
        for raw in [str(START) + '.0', str(START) + '.9', '1.7041248e12', '+' + str(START),
                    '0' + str(START), ' ' + str(START), '-1', '１７０４１２４８０００００']:
            with self.subTest(raw=raw), self.assertRaises(ContractError):
                parse(zip_bytes(csv_bytes([('BTC-USDT-SWAP', '0', raw)])))

    def test_finite_decimal_and_bounded_encoding_in_every_row(self):
        for raw in ['NaN', 'sNaN', 'Infinity', '-Inf', '1_000', '', ' 0.01', '1e1001', '０.１']:
            with self.subTest(raw=raw), self.assertRaises(ContractError):
                parse(zip_bytes(csv_bytes([('ETH-USDT-SWAP', raw, str(START))])))

    def test_decimal_precision_is_not_inherited(self):
        blob = zip_bytes(csv_bytes([('BTC-USDT-SWAP', '0.12345678901234567890123456789000', str(START))]))
        expected = canonical(parse(blob))
        with localcontext() as context:
            context.prec = 3; context.Emax = 3
            self.assertEqual(canonical(parse(blob)), expected)

    def test_zero_sign_variants_deduplicated_without_fee_assumption(self):
        result = parse(zip_bytes(csv_bytes([('BTC-USDT-SWAP', '-0.00', str(START)),
                                           ('BTC-USDT-SWAP', '0e-5', str(START))])))
        self.assertEqual(result['kernel_payload']['events'][0]['rate'], '0')
        self.assertIsNone(result['kernel_payload']['events'][0]['settlement_mark'])
        self.assertEqual(result['audit']['source_coverage'], 'UNKNOWN')

    def test_no_target_is_unknown_not_zero_funding(self):
        result = parse(zip_bytes(csv_bytes([('ETH-USDT-SWAP', '.01', str(START))])))
        self.assertEqual(result['kernel_payload']['events'], [])
        self.assertEqual(result['audit']['target_presence'], 'NOT_OBSERVED_NOT_PROVEN_ABSENT')
        self.assertFalse(result['audit']['data_complete'])

    def test_unsupported_target_or_malformed_instrument_rejected(self):
        for target in ['ETH-USDT-SWAP', 'BTC-USD-SWAP', 'BTC-USDT']:
            with self.assertRaises(ContractError): parse(target_instrument=target)
        for instrument in ['BTC-USDT', 'BTC-usdt-SWAP', 'BTC-EUR-SWAP']:
            with self.assertRaises(ContractError): parse(zip_bytes(csv_bytes([(instrument, '.01', str(START))])))

    def test_strict_header_columns_bad_encoding_empty_and_blank_rows(self):
        bad = [b'', csv_bytes([]), csv_bytes(header=tuple(reversed(adapter.HEADER))),
               csv_bytes(header=adapter.HEADER + ('complete',)), b'\xff' + csv_bytes(),
               csv_bytes() + b'\r\n', csv_bytes() + b'BTC-USDT-SWAP,.1\r\n',
               csv_bytes() + b'"BTC-USDT-SWAP,.1,1704124800000\r\n']
        for blob in bad:
            with self.subTest(blob=blob[:50]), self.assertRaises(ContractError): parse(zip_bytes(blob))

    def test_unsafe_duplicate_nested_or_extra_zip_members_rejected(self):
        for names in [['../' + NAME + '.csv'], ['nested/' + NAME + '.csv'],
                      [NAME + '.csv', 'README'], [NAME + '.csv', NAME + '.csv']]:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                blob = zip_bytes(names=names)
            with self.subTest(names=names), self.assertRaises(ContractError): parse(blob)

    def test_zip_symlink_and_unsupported_codec_rejected(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            member = zipfile.ZipInfo(NAME + '.csv'); member.create_system = 3
            member.external_attr = (0o120777 << 16)
            archive.writestr(member, csv_bytes())
        with self.assertRaises(ContractError): parse(stream.getvalue())
        with self.assertRaises(ContractError): parse(zip_bytes(compression=zipfile.ZIP_BZIP2))

    def test_crc_corruption_cannot_be_approved_by_matching_outer_hash(self):
        blob = bytearray(zip_bytes(compression=zipfile.ZIP_STORED))
        start = 30 + len(NAME + '.csv')
        blob[start + 1] ^= 1
        with self.assertRaisesRegex(ContractError, 'CRC'): parse(bytes(blob))

    def test_forged_central_uncompressed_length_rejected(self):
        blob = bytearray(zip_bytes()); at = blob.index(b'PK\x01\x02')
        struct.pack_into('<I', blob, at + 24, 10)
        with self.assertRaisesRegex(ContractError, 'declarations disagree'): parse(bytes(blob))

    def test_safety_limits_are_checked_before_oversized_materialization(self):
        blob = zip_bytes()
        with patch.object(adapter, 'MAX_SOURCE_BYTES', len(blob) - 1), self.assertRaises(ContractError): parse(blob)
        with patch.object(adapter, 'MAX_CSV_BYTES', 10), self.assertRaises(ContractError): parse(blob)
        with patch.object(adapter, 'MAX_ROWS', 2), self.assertRaises(ContractError): parse(blob)

    def test_malformed_non_target_row_still_blocks_entire_file(self):
        for rate, at in [('NaN', str(START)), ('.01', str(START - 1))]:
            data = csv_bytes([('BTC-USDT-SWAP', '.01', str(START)), ('ETH-USDT-SWAP', rate, at)])
            with self.assertRaises(ContractError): parse(zip_bytes(data))

    def test_kernel_accepts_payload_but_cannot_promote_it(self):
        from researchlib.funding_forward import evaluate
        root = Path(__file__).resolve().parents[1]
        plan = json.loads((root / 'research/bootstrap-v1/forward_plans.json').read_text())['plans'][0]
        payload = parse()['kernel_payload']
        result = evaluate(plan, payload, '2026-09-22T18:30:00Z', '2026-09-22T18:30:00Z')
        self.assertEqual(result['evaluation_stage'], 'NOT_YET_EFFECTIVE')
        self.assertFalse(result['data_complete'])
        self.assertTrue(all(value is None for value in result['metrics'].values()))
        self.assertIsNone(result['input_payload']['events'][0]['settlement_mark'])

    def test_call_does_not_mutate_source_manifest_or_bytes(self):
        blob = zip_bytes(); source = manifest(blob); original = copy.deepcopy(source)
        parse(blob, source)
        self.assertEqual(source, original)
        self.assertEqual(digest(blob), source['sha256'])

    def test_synthetic_declaration_never_inferred_or_treated_as_source_proof(self):
        for declared in [True, False]:
            result = parse(synthetic=declared)
            self.assertIs(result['kernel_payload']['synthetic'], declared)
            self.assertEqual(result['audit']['source_coverage'], 'UNKNOWN')
            self.assertIn('NOT_NETWORK_PROOF', result['audit']['source_origin'])
        for invalid in [None, 0, 'False']:
            with self.assertRaises(ContractError): parse(synthetic=invalid)


if __name__ == '__main__':
    unittest.main()
