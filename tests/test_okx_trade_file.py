"""Synthetic engineering cases. No downloaded data and no economic acceptance."""
import hashlib
import io
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from researchlib import okx_trade_file as m

DAY = '2024-01-02'
START = 1704124800000  # 2024-01-01 16:00 UTC = Jan 2 00:00 UTC+8
INFO = '2024-01-03T00:00:00Z'
NAME = 'BTC-USDT-SWAP-trades-' + DAY


def row(trade_id=1, at=START, price='123.450', size='0.1', side='buy', source='0', instrument=m.TARGET):
    return ','.join((instrument, str(trade_id), side, price, size, str(at), source))


def csv_bytes(rows):
    return (','.join(m.HEADER) + '\r\n' + '\r\n'.join(rows) + ('\r\n' if rows else '')).encode()


def zip_bytes(content, name=NAME + '.csv', compression=zipfile.ZIP_DEFLATED):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=compression) as z:
        z.writestr(name, content)
    return out.getvalue()


def manifest(blob, fmt='zip'):
    return dict(schema_version=1, format=fmt, filename=NAME + '.' + fmt,
                sha256=hashlib.sha256(blob).hexdigest(), size_bytes=len(blob),
                source_url='https://www.okx.com/zh-hans/historical-data', obtained_at=INFO,
                declared_partition={'date': DAY, 'timezone': 'UTC+08:00'})


def window(lo=START, hi=START + 1000):
    return {'start_inclusive': m._iso(lo), 'end_exclusive': m._iso(hi)}


class TradeFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'private-source'

    def scan(self, rows=None, blob=None, fmt='zip', change=None, **kwargs):
        if blob is None:
            content = csv_bytes(rows if rows is not None else [row()])
            blob = zip_bytes(content) if fmt == 'zip' else content
        self.path.write_bytes(blob)
        receipt = manifest(blob, fmt)
        if change:
            change(receipt)
        return m.scan_trade_file(self.path, receipt, information_as_of=kwargs.pop('information_as_of', INFO),
                                 synthetic=True, **kwargs)

    def rejected(self, *args, **kwargs):
        with self.assertRaises(m.TradeFileError) as caught:
            self.scan(*args, **kwargs)
        self.assertFalse(caught.exception.validation_complete)
        self.assertEqual(caught.exception.status, 'FILE_DECODE_NOT_COMPLETE')
        self.assertNotIn(str(self.path), str(caught.exception))

    def test_realistic_full_decode_audit_is_not_coverage(self):
        result = self.scan(rows=[row(), row(3, START + 1, source='1')])
        a = result['audit']
        self.assertTrue(a['validation_complete'])
        self.assertEqual(a['status'], 'FILE_DECODE_COMPLETE')
        self.assertEqual(a['rows_read'], 2)
        self.assertEqual(a['zip_crc'], 'PASS')
        self.assertEqual(a['source_code_counts'], {'0': 1, '1': 1})
        self.assertEqual(a['selection']['mode'], 'AUDIT_ONLY_NO_EVENTS_REQUESTED')
        self.assertEqual(result['kernel_payload']['events'], [])
        self.assertEqual(a['source_coverage'], 'UNKNOWN')
        self.assertFalse(a['data_complete'])
        self.assertIsNone(a['expected_event_count'])
        # A gap in integer ID does not assert a missing market event.
        self.assertEqual(a['duplicate_policy'], 'REJECT_ANY_NONINCREASING_ID_NOT_DEDUPLICATION')

    def test_window_keeps_identity_raw_strings_and_null_sequence(self):
        result = self.scan(rows=[row(), row(2, START, price='123.45'), row(3, START + 1000)], window=window())
        events = result['kernel_payload']['events']
        self.assertEqual(len(events), 2)
        self.assertEqual([e['trade_id'] for e in events], ['1', '2'])
        self.assertEqual(events[0]['event_id'], 'okx-trade:BTC-USDT-SWAP:1')
        self.assertEqual(events[0]['price'], '123.45')
        self.assertEqual(events[0]['source_location']['raw_fields']['price'], '123.450')
        self.assertEqual([e['source_location']['line'] for e in events], [2, 3])
        self.assertTrue(all(e['sequence'] is None for e in events))
        self.assertTrue(all(e['evidence_status'] == 'PROVISIONAL_SOURCE_COVERAGE_UNKNOWN' for e in events))
        self.assertEqual(result['audit']['same_ms']['multiple_row_groups'], 1)
        self.assertEqual(result['audit']['same_ms']['multiple_price_groups'], 0)
        self.assertEqual(result['audit']['selection']['coverage'], 'UNKNOWN')

    def test_event_identity_stable_across_different_archives(self):
        first = self.scan(window=window())
        second = self.scan(rows=[row(), row(2, START + 1000)], window=window())
        a, b = first['kernel_payload']['events'][0], second['kernel_payload']['events'][0]
        self.assertEqual(a['event_id'], b['event_id'])
        self.assertNotEqual(a['source_sha256'], b['source_sha256'])

    def test_same_ms_aggregation_including_last_group(self):
        a = self.scan(rows=[row(), row(2, price='124'), row(3, START + 1), row(4, START + 1)])['audit']
        self.assertEqual(a['same_ms'], dict(multiple_row_groups=2, rows_in_multiple_row_groups=4,
            multiple_price_groups=1, rows_in_multiple_price_groups=2, max_rows_per_ms=2, exchange_chronology='UNKNOWN'))

    def test_empty_selected_window_not_proven_absence(self):
        result = self.scan(window=window(START + 1, START + 2))
        self.assertEqual(result['kernel_payload']['events'], [])
        self.assertEqual(result['audit']['selection']['presence'], 'NOT_OBSERVED_NOT_PROVEN_ABSENT')
        self.assertEqual(result['audit']['selection']['coverage'], 'UNKNOWN')

    def test_partial_declared_day_is_accepted_but_never_complete(self):
        r = self.scan(change=lambda d: d.update(obtained_at='2024-01-01T16:00:00Z'), information_as_of='2024-01-01T16:00:01Z')
        self.assertEqual(r['audit']['rows_read'], 1)
        self.assertFalse(r['audit']['data_complete'])

    def test_all_rows_outside_selection_still_validated(self):
        self.rejected(rows=[row(), row(2, START + 2, instrument='ETH-USDT-SWAP')], window=window(START, START + 1))
        self.rejected(rows=[row(), row(2, START + 2, price='NaN')], window=window(START, START + 1))
        self.rejected(rows=[row(), row(2, START + 2)], window=window(START, START + 1),
                      change=lambda d: d.update(obtained_at='2024-01-01T16:00:00.001Z'))

    def test_duplicate_conflicting_or_remote_ids_rejected(self):
        for rows in ([row(), row()], [row(), row(price='99')], [row(), row(2), row(1)], [row(2), row(1)]):
            with self.subTest(rows=rows):
                self.rejected(rows=rows)

    def test_decreasing_timestamp_rejected_even_increasing_id(self):
        self.rejected(rows=[row(1, START + 1), row(2, START)])

    def test_timestamp_integer_and_trade_id_encoding(self):
        for at in ('1e12', str(START) + '.0', '0' + str(START), '-1', ' 1', '１'):
            self.rejected(rows=[row(at=at)])
        for identifier in ('01', '-1', '1.0', '1e2', '１', '9' * 21):
            self.rejected(rows=[row(trade_id=identifier)])

    def test_partition_half_open_millisecond_edges(self):
        self.scan(rows=[row(at=START), row(2, START + 86_400_000 - 1)])
        self.rejected(rows=[row(at=START - 1)])
        self.rejected(rows=[row(at=START + 86_400_000)])

    def test_decimal_nonpositive_nonfinite_and_encoding_rejected(self):
        for value in ('NaN', 'Infinity', '-1', '0', '-0', '1_000', '1e1001', '1e-1001', ' 1', '1' * 129):
            with self.subTest(value=value):
                self.rejected(rows=[row(price=value)])
                self.rejected(rows=[row(size=value)])

    def test_decimal_exact_under_small_ambient_context(self):
        from decimal import localcontext
        with localcontext() as ctx:
            ctx.prec = 2
            e = self.scan(rows=[row(price='123456789.1234500')], window=window())['kernel_payload']['events'][0]
        self.assertEqual(e['price'], '123456789.12345')

    def test_unsupported_source_side_currency_rejected(self):
        for kwargs in ({'source': '2'}, {'side': 'BUY'}, {'instrument': 'BTC-USD-SWAP'}, {'instrument': 'BTC-USDC-SWAP'}):
            self.rejected(rows=[row(**kwargs)])

    def test_exact_header_and_observed_ascii_unquoted_profile(self):
        content = csv_bytes([row()])
        for bad in (content.replace(b'price,size', b'size,price'), b'\xef\xbb\xbf' + content,
                    content.replace(b'\r\n', b'\r\r\n', 1), content.replace(b'123.450', b'"123.450"'),
                    content + b'\r\n', content.replace(b'123.450', b'123.450,extra')):
            self.rejected(blob=zip_bytes(bad))
        self.rejected(rows=[])

    def test_plain_csv_and_stored_zip_supported(self):
        self.assertEqual(self.scan(fmt='csv')['audit']['zip_crc'], 'NOT_APPLICABLE')
        self.assertEqual(self.scan(blob=zip_bytes(csv_bytes([row()]), compression=zipfile.ZIP_STORED))['audit']['zip_crc'], 'PASS')
        self.scan(blob=csv_bytes([row()]).replace(b'\r\n', b'\n').rstrip(b'\n'), fmt='csv')

    def test_wrong_actual_hash_size_and_manifest_fields(self):
        self.rejected(change=lambda d: d.update(sha256='0' * 64))
        self.rejected(change=lambda d: d.update(size_bytes=d['size_bytes'] + 1))
        self.rejected(change=lambda d: d.update(source_coverage='COMPLETE'))
        self.rejected(change=lambda d: d.update(schema_version=True))
        self.rejected(change=lambda d: d.update(filename='../' + d['filename']))
        self.rejected(change=lambda d: d['declared_partition'].update(timezone='UTC'))

    def test_url_claim_scope_not_network_proof(self):
        for url in ('https://www.okx.com.evil.test/file.zip', 'https://user@www.okx.com/file.zip',
                    'https://www.okx.com:443/file.zip', 'https://www.okx.com/file.zip?token=x',
                    'http://www.okx.com/file.zip', 'https://www.okx.com/other', 'https://www.okx.com/\nfile.zip'):
            self.rejected(change=lambda d: d.update(source_url=url))
        self.assertIn('NOT_NETWORK_PROOF', self.scan()['audit']['source_origin'])

    def test_naive_future_and_backdated_cutoffs_rejected(self):
        for stamp in ('2024-01-03T00:00:00', '2999-01-03T00:00:00Z', '2024-01-01T00:00:00Z'):
            self.rejected(information_as_of=stamp)
        self.rejected(change=lambda d: d.update(obtained_at='2024-01-01T15:59:59.999Z'))
        self.rejected(change=lambda d: d.update(obtained_at='2024-01-03T00:00:00'))

    def test_window_scope_validation(self):
        for w in (window(START - 1, START + 1), window(START, START),
                  {'start_inclusive': '2024-01-01T16:00:00.000001Z', 'end_exclusive': m._iso(START + 1)},
                  {'start_inclusive': '2024-01-01T16:00:00', 'end_exclusive': m._iso(START + 1)}, {}):
            self.rejected(window=w)

    def test_selected_limit_is_failure_not_truncation(self):
        self.rejected(rows=[row(), row(2)], window=window(), max_selected_events=1)
        for cap in (0, True, 50_001):
            self.rejected(max_selected_events=cap)

    def test_row_line_and_expanded_limits_are_enforced(self):
        with patch.object(m, 'MAX_ROWS', 1):
            self.rejected(rows=[row(), row(2)])
        self.rejected(blob=zip_bytes(csv_bytes([row()]) + b'x' * 1025))
        with patch.object(m, 'MAX_CSV_BYTES', 80):
            self.rejected()

    def test_many_chunks_and_long_same_ms_group_use_bounded_state(self):
        rows = [row(i, START, price='1' if i % 2 else '2') for i in range(1, 3001)]
        with patch.object(m, 'CHUNK_BYTES', 97):
            a = self.scan(rows=rows)['audit']
        self.assertEqual(a['same_ms']['max_rows_per_ms'], 3000)
        self.assertEqual(a['same_ms']['multiple_price_groups'], 1)
        self.assertEqual(a['rows_read'], 3000)

    def test_cancellation_and_deadline_return_no_result(self):
        self.rejected(cancel=lambda: True)
        self.rejected(timeout_seconds=0)
        self.rejected(timeout_seconds=float('nan'))
        with patch.object(m.time, 'monotonic', side_effect=[0, 0, 181]):
            self.rejected()

    def test_cancellation_after_csv_and_at_final_hash_is_not_complete(self):
        calls = [0]
        original = m._hash
        def final_hash(*args):
            calls[0] += 1
            if calls[0] == 2:
                raise m.TradeFileError('cancel final hashing')
            return original(*args)
        with patch.object(m, '_hash', side_effect=final_hash):
            self.rejected(window=window())
        self.assertEqual(calls[0], 2)

    def test_content_change_before_final_hash_rejected(self):
        original = m._pieces
        def changed(*args):
            yield from original(*args)
            with self.path.open('r+b') as stream:
                stream.seek(5)
                stream.write(b'x')
        with patch.object(m, '_pieces', changed):
            self.rejected(window=window())

    def test_path_replacement_audits_original_fd_only(self):
        original = m._pieces
        def replaced(*args):
            yield from original(*args)
            replacement = self.path.with_name('replacement')
            replacement.write_bytes(b'another object')
            os.replace(replacement, self.path)
        # On some filesystems unlinking the open inode changes ctime: then fail
        # conservatively. Both outcomes must never bind result to replacement.
        with patch.object(m, '_pieces', replaced):
            try:
                result = self.scan()
            except m.TradeFileError:
                return
        self.assertEqual(result['audit']['path_scope'], 'OPENED_FD_ONLY_NOT_LATER_PATH_BINDING')

    def test_tail_bad_row_invalidates_selected_prefix(self):
        self.rejected(blob=zip_bytes(csv_bytes([row()]) + b'broken-final-row'), window=window())

    def test_bad_crc_rejected_after_valid_rows(self):
        blob = bytearray(zip_bytes(csv_bytes([row()])))
        central = blob.index(b'PK\x01\x02')
        struct.pack_into('<I', blob, 14, 0)
        struct.pack_into('<I', blob, central + 16, 0)
        self.rejected(blob=bytes(blob), window=window())

    def test_forged_short_expansion_not_clipped_to_valid_prefix(self):
        blob = bytearray(zip_bytes(csv_bytes([row(), row(2)])))
        central = blob.index(b'PK\x01\x02')
        short = len(csv_bytes([row()]))
        struct.pack_into('<I', blob, 22, short)
        struct.pack_into('<I', blob, central + 24, short)
        self.rejected(blob=bytes(blob), window=window())

    def test_compressed_trailing_data_and_incomplete_deflate_rejected(self):
        good = zip_bytes(csv_bytes([row()]))
        for tail in (b'\0', b'junk'):
            blob = bytearray(good)
            central = blob.index(b'PK\x01\x02')
            packed = struct.unpack_from('<I', blob, 18)[0]
            blob[central:central] = tail
            central += len(tail)
            struct.pack_into('<I', blob, 18, packed + len(tail))
            struct.pack_into('<I', blob, central + 20, packed + len(tail))
            struct.pack_into('<I', blob, len(blob) - 6, central)
            self.rejected(blob=bytes(blob))
        blob = bytearray(good)
        central = blob.index(b'PK\x01\x02')
        packed = struct.unpack_from('<I', blob, 18)[0]
        del blob[central - 1]
        central -= 1
        struct.pack_into('<I', blob, 18, packed - 1)
        struct.pack_into('<I', blob, central + 20, packed - 1)
        struct.pack_into('<I', blob, len(blob) - 6, central)
        self.rejected(blob=bytes(blob))

    def test_zip_unsafe_members_and_layout_rejected(self):
        self.rejected(blob=zip_bytes(csv_bytes([row()]), '../' + NAME + '.csv'))
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w') as z:
            z.writestr(NAME + '.csv', csv_bytes([row()]))
            z.writestr('extra.csv', b'x')
        self.rejected(blob=out.getvalue())
        good = zip_bytes(csv_bytes([row()]))
        self.rejected(blob=good + b'tail')
        self.rejected(blob=good[:50])
        self.rejected(blob=b'PK')
        info = zipfile.ZipInfo(NAME + '.csv')
        info.extra = b'\x01\x00\x00\x00'
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w') as z:
            z.writestr(info, csv_bytes([row()]))
        self.rejected(blob=out.getvalue())

    def test_local_central_mismatch_rejected(self):
        blob = bytearray(zip_bytes(csv_bytes([row()])))
        blob[14] ^= 1
        self.rejected(blob=bytes(blob))


if __name__ == '__main__':
    unittest.main()
