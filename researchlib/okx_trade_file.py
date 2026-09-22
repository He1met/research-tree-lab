"""Bounded offline scan of the observed OKX BTC daily trade ZIP/CSV profile.

Only a complete scan returns data. File integrity is not network provenance,
source completeness, exchange chronology, execution evidence, or an economic result.
"""
import binascii
import hashlib
import math
import os
import re
import stat
import struct
import time
import zlib
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from .common import ContractError

VERSION = 'okx-btc-trade-file-v1'
HEADER = ('instrument_name', 'trade_id', 'side', 'price', 'size', 'created_time', 'source')
TARGET = 'BTC-USDT-SWAP'
MAX_ZIP_BYTES = 64_000_000
MAX_CSV_BYTES = 512_000_000
MAX_ROWS = 8_000_000
MAX_LINE_BYTES = 1024
MAX_SELECTED_EVENTS = 50_000
MAX_SECONDS = 180
CHUNK_BYTES = 262_144
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
ZONE = timezone(timedelta(hours=8))
MANIFEST_FIELDS = frozenset({'schema_version', 'format', 'filename', 'sha256',
                             'size_bytes', 'source_url', 'obtained_at', 'declared_partition'})
TIMESTAMP = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])\Z')
INTEGER = re.compile(r'(?:0|[1-9][0-9]{0,19})\Z')
MILLISECONDS = re.compile(r'(?:0|[1-9][0-9]{0,14})\Z')
DECIMAL = re.compile(r'[+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z')


class TradeFileError(ContractError):
    """No result or partial payload is valid when this exception is raised."""
    validation_complete = False
    status = 'FILE_DECODE_NOT_COMPLETE'


def _fail(message):
    raise TradeFileError(message)


def _timestamp(value, field):
    if not isinstance(value, str) or not TIMESTAMP.fullmatch(value):
        _fail('Invalid timezone-aware timestamp: ' + field)
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    except (ValueError, OverflowError):
        _fail('Invalid timestamp: ' + field)


def _ms(at):
    delta = at - EPOCH
    return delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000


def _iso(milliseconds):
    return (EPOCH + timedelta(milliseconds=milliseconds)).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def _decimal(value):
    if len(value) > 128 or not DECIMAL.fullmatch(value):
        _fail('Invalid positive finite decimal price or size')
    try:
        number = Decimal(value)
        if not number.is_finite() or number <= 0 or abs(number.as_tuple().exponent) > 1000:
            _fail('Price or size outside positive bounded decimal encoding')
        return number
    except InvalidOperation:
        _fail('Invalid positive finite decimal price or size')


def _canonical(number):
    # No normalize(): that method rounds under the ambient Decimal context.
    sign, digits, exponent = number.as_tuple()
    digits = list(digits)
    while digits[-1] == 0:
        digits.pop()
        exponent += 1
    return str(Decimal((sign, tuple(digits), exponent)))


def _manifest(manifest, information_as_of):
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_FIELDS:
        _fail('Exact source manifest fields required')
    if type(manifest['schema_version']) is not int or manifest['schema_version'] != 1:
        _fail('Source schema_version must be integer 1')
    fmt, name = manifest['format'], manifest['filename']
    if fmt not in ('zip', 'csv') or not isinstance(name, str):
        _fail('Only observed ZIP/CSV format supported')
    match = re.fullmatch(r'BTC-USDT-SWAP-trades-([0-9]{4}-[0-9]{2}-[0-9]{2})\.' + fmt, name)
    if not match:
        _fail('Only reviewed BTC-USDT-SWAP daily filename supported')
    limit = MAX_ZIP_BYTES if fmt == 'zip' else MAX_CSV_BYTES
    if type(manifest['size_bytes']) is not int or not 0 < manifest['size_bytes'] <= limit:
        _fail('Declared source size outside resource limit')
    if not isinstance(manifest['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', manifest['sha256']):
        _fail('Invalid source sha256')
    part = manifest['declared_partition']
    if (not isinstance(part, dict) or set(part) != {'date', 'timezone'}
            or part['date'] != match.group(1) or part['timezone'] != 'UTC+08:00'):
        _fail('Partition must match filename date and UTC+08:00')
    try:
        day = date.fromisoformat(part['date'])
        start = datetime.combine(day, datetime.min.time(), ZONE).astimezone(timezone.utc)
        end = start + timedelta(days=1)
    except (ValueError, OverflowError):
        _fail('Invalid partition date')
    url = manifest['source_url']
    if (not isinstance(url, str) or len(url) > 2048 or not url.isascii()
            or any(ord(c) <= 32 for c in url) or '\\' in url):
        _fail('Invalid declared source URL')
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname not in {'www.okx.com', 'okx.com', 'static.okx.com'}
                or parsed.netloc != parsed.hostname or parsed.query or parsed.fragment
                or not (parsed.path in {'/historical-data', '/zh-hans/historical-data'}
                        or parsed.path.endswith(('.zip', '.csv')))):
            _fail('Declared URL outside reviewed host/path scope')
    except ValueError:
        _fail('Invalid declared source URL')
    obtained = _timestamp(manifest['obtained_at'], 'obtained_at')
    info = _timestamp(information_as_of, 'information_as_of')
    if obtained > info or info > datetime.now(timezone.utc):
        _fail('Acquisition/information time is future or outside cutoff')
    return _ms(start), _ms(end), _ms(obtained)


def _window(window, start, end):
    if window is None:
        return None
    if not isinstance(window, dict) or set(window) != {'start_inclusive', 'end_exclusive'}:
        _fail('Window requires exact half-open UTC timestamp fields')
    lo = _timestamp(window['start_inclusive'], 'window.start_inclusive')
    hi = _timestamp(window['end_exclusive'], 'window.end_exclusive')
    if lo.microsecond % 1000 or hi.microsecond % 1000 or not start <= _ms(lo) < _ms(hi) <= end:
        _fail('Window must be millisecond aligned and inside the declared partition')
    return _ms(lo), _ms(hi)


def _identity(stream):
    info = os.fstat(stream.fileno())
    if not stat.S_ISREG(info.st_mode):
        _fail('Source must be an opened regular file')
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _hash(stream, expected_size, check):
    stream.seek(0)
    sha, size = hashlib.sha256(), 0
    while True:
        check()
        block = stream.read(CHUNK_BYTES)
        if not block:
            break
        size += len(block)
        if size > expected_size:
            _fail('Source size changed or exceeds manifest')
        sha.update(block)
    if size != expected_size:
        _fail('Actual source size differs from manifest')
    return sha.hexdigest()


def _zip_profile(stream, manifest):
    """Parse only the single-member, no-extra/comment/descriptor observed profile.

    Reading the fixed EOCD before the directory avoids allocating attacker-chosen
    numbers of ZipInfo objects. No extraction and no trust in ZipExtFile clipping.
    """
    expected = manifest['filename'][:-4] + '.csv'
    stream.seek(-22, 2)
    end = stream.read(22)
    signature, disk, cd_disk, disk_entries, entries, cd_size, cd_offset, comment = struct.unpack('<4s4H2IH', end)
    if (signature != b'PK\x05\x06' or disk or cd_disk or disk_entries != 1 or entries != 1
            or comment or cd_size != 46 + len(expected)
            or cd_offset + cd_size != manifest['size_bytes'] - 22):
        _fail('Unsupported ZIP directory, members, comments, or trailing bytes')
    stream.seek(cd_offset)
    fields = struct.unpack('<4s6H3I5H2I', stream.read(46))
    (signature, made, needed, flags, codec, clock, day, crc, packed, expanded,
     name_size, extra_size, comment_size, disk, internal, external, offset) = fields
    if (signature != b'PK\x01\x02' or needed not in (10, 20) or flags != 0
            or codec not in (0, 8) or name_size != len(expected) or extra_size or comment_size
            or disk or offset or external & 0x10
            or stat.S_IFMT(external >> 16) not in (0, stat.S_IFREG)
            or stream.read(name_size) != expected.encode('ascii')
            or not 0 < expanded <= MAX_CSV_BYTES or not 0 < packed <= MAX_ZIP_BYTES):
        _fail('Unsafe or unsupported ZIP member profile')
    stream.seek(0)
    local = struct.unpack('<4s5H3I2H', stream.read(30))
    if (local != (b'PK\x03\x04', needed, flags, codec, clock, day, crc, packed, expanded, name_size, 0)
            or stream.read(name_size) != expected.encode('ascii')
            or stream.tell() + packed != cd_offset):
        _fail('ZIP local and central declarations disagree')
    return expected, codec, packed, expanded, crc


def _pieces(stream, manifest, check, stats):
    if manifest['format'] == 'zip':
        name, codec, remaining, expanded, expected_crc = _zip_profile(stream, manifest)
    else:
        name, codec, remaining, expanded, expected_crc = (manifest['filename'], 0,
            manifest['size_bytes'], manifest['size_bytes'], None)
        stream.seek(0)
    stats['csv_member'] = name
    sha, crc, count = hashlib.sha256(), 0, 0
    inflater = zlib.decompressobj(-15) if codec == 8 else None
    while remaining:
        check()
        block = stream.read(min(CHUNK_BYTES, remaining))
        if not block:
            _fail('Truncated source content')
        remaining -= len(block)
        pending = block
        while True:
            check()
            piece = inflater.decompress(pending, CHUNK_BYTES) if inflater else pending
            pending = inflater.unconsumed_tail if inflater else b''
            if inflater and inflater.unused_data:
                _fail('ZIP deflate stream has trailing compressed data')
            count += len(piece)
            if count > MAX_CSV_BYTES or count > expanded:
                _fail('Actual expanded size exceeds limit or ZIP declaration')
            sha.update(piece)
            crc = binascii.crc32(piece, crc)
            if piece:
                yield piece
            if inflater and inflater.eof and (remaining or pending):
                _fail('ZIP has bytes after deflate end-of-stream')
            if pending or (inflater and len(piece) == CHUNK_BYTES and not inflater.eof):
                continue
            break
    if inflater and (not inflater.eof or inflater.unused_data or inflater.unconsumed_tail):
        _fail('ZIP deflate stream did not terminate exactly')
    if count != expanded:
        _fail('Actual expanded size differs from declaration')
    if expected_crc is not None and crc & 0xffffffff != expected_crc:
        _fail('ZIP CRC verification failed')
    stats.update(csv_bytes=count, csv_sha256=sha.hexdigest(), zip_crc='PASS' if expected_crc is not None else 'NOT_APPLICABLE')


def _lines(pieces):
    buffer, line_number = b'', 0
    for piece in pieces:
        buffer += piece
        begin = 0
        while True:
            end = buffer.find(b'\n', begin)
            if end < 0:
                break
            line = buffer[begin:end + 1]
            if len(line) > MAX_LINE_BYTES:
                _fail('CSV physical line exceeds limit')
            line_number += 1
            yield line_number, line
            begin = end + 1
        buffer = buffer[begin:]
        if len(buffer) > MAX_LINE_BYTES:
            _fail('CSV physical line exceeds limit')
    if buffer:
        line_number += 1
        yield line_number, buffer


def scan_trade_file(path, manifest, *, information_as_of, synthetic, window=None,
                    max_selected_events=20_000, timeout_seconds=MAX_SECONDS, cancel=None):
    """Return LOCAL_ONLY {kernel_payload, audit} only after full validation.

    window=None scans for an audit and selects no events. A half-open window
    selects a bounded list; its completeness remains UNKNOWN. All rows outside
    it still undergo validation. No partial results escape on failure/cancel.
    cancel, if supplied, is a zero-argument cooperative cancellation predicate.
    Monotonic timestamps/strictly increasing numeric IDs restrict file layout;
    they do not establish market chronology. The opened FD is the audited object.
    """
    begin = time.monotonic()
    if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= MAX_SECONDS or (cancel is not None and not callable(cancel))):
        _fail('Invalid timeout or cancellation predicate')
    def check():
        if time.monotonic() - begin >= timeout_seconds:
            _fail('Cooperative resource deadline exceeded; no complete result')
        if cancel is not None and cancel():
            _fail('Cooperatively cancelled; no complete result')
    check()
    if type(synthetic) is not bool:
        _fail('Explicit boolean synthetic declaration required')
    if type(max_selected_events) is not int or not 1 <= max_selected_events <= MAX_SELECTED_EVENTS:
        _fail('Invalid bounded selected-event limit')
    manifest = deepcopy(manifest)
    start, end, obtained = _manifest(manifest, information_as_of)
    selection = _window(window, start, end)
    stats, events = {}, []
    count = 0
    previous_time, previous_id = None, None
    first_time, first_id, last_id = None, None, None
    group_size, group_price, group_multprice = 0, None, False
    multiple_groups = multiple_rows = multiple_price_groups = multiple_price_rows = max_group = 0
    side_counts, source_counts = {'buy': 0, 'sell': 0}, {'0': 0, '1': 0}
    try:
        with open(path, 'rb') as stream:
            identity = _identity(stream)
            if identity[2] != manifest['size_bytes']:
                _fail('Actual source size differs from manifest')
            if _hash(stream, manifest['size_bytes'], check) != manifest['sha256']:
                _fail('Actual source SHA-256 differs from manifest')
            if _identity(stream) != identity:
                _fail('Opened source changed during initial hash')
            lines = _lines(_pieces(stream, manifest, check, stats))
            first = next(lines, None)
            header = first[1] if first else b''
            header = header[:-2] if header.endswith(b'\r\n') else header[:-1] if header.endswith(b'\n') else header
            if header != ','.join(HEADER).encode('ascii'):
                _fail('CSV header must exactly match observed field order')
            for line_number, raw in lines:
                count += 1
                if count % 1024 == 0:
                    check()
                if count > MAX_ROWS:
                    _fail('CSV row limit exceeded')
                # Observed profile: unquoted ASCII fields, one physical line per
                # record. Quoting/embedded newlines/BOM are unsupported, not repaired.
                body = raw[:-2] if raw.endswith(b'\r\n') else raw[:-1] if raw.endswith(b'\n') else raw
                try:
                    fields = body.decode('ascii').split(',')
                except UnicodeDecodeError:
                    _fail('CSV fields must be ASCII in observed profile')
                if len(fields) != 7 or any(len(v) > 128 for v in fields):
                    _fail('CSV column count or field limit invalid')
                instrument, trade_id, side, price_text, size_text, at_text, source = fields
                if instrument != TARGET or side not in side_counts or source not in source_counts:
                    _fail('Unsupported instrument, side, or source code')
                if not INTEGER.fullmatch(trade_id) or not MILLISECONDS.fullmatch(at_text):
                    _fail('trade_id and created_time must be strict integer strings')
                number_id, at = int(trade_id), int(at_text)
                if not start <= at < end or at > obtained:
                    _fail('Trade outside partition or after declared acquisition')
                if previous_id is not None and (number_id <= previous_id or at < previous_time):
                    _fail('Unsupported layout: duplicate/nonincreasing ID or decreasing timestamp')
                price, size = _decimal(price_text), _decimal(size_text)
                if at != previous_time:
                    if group_size > 1:
                        multiple_groups += 1
                        multiple_rows += group_size
                        if group_multprice:
                            multiple_price_groups += 1
                            multiple_price_rows += group_size
                    max_group = max(max_group, group_size)
                    group_size, group_price, group_multprice = 0, price, False
                group_size += 1
                group_multprice = group_multprice or price != group_price
                if first_time is None:
                    first_time, first_id = at, trade_id
                previous_time, previous_id, last_id = at, number_id, trade_id
                side_counts[side] += 1
                source_counts[source] += 1
                if selection and selection[0] <= at < selection[1]:
                    if len(events) >= max_selected_events:
                        _fail('Selected-event limit exceeded; no truncated success')
                    events.append({'event_id': 'okx-trade:%s:%s' % (TARGET, trade_id),
                        'kind': 'trade', 'instrument': TARGET, 'currency': 'USDT',
                        'event_at': _iso(at), 'available_at': manifest['obtained_at'],
                        'price': _canonical(price), 'size': _canonical(size), 'side': side,
                        'trade_id': trade_id, 'sequence': None,
                        'evidence_status': 'PROVISIONAL_SOURCE_COVERAGE_UNKNOWN',
                        'source_sha256': manifest['sha256'],
                        'source_location': {'line': line_number, 'raw_fields': dict(zip(HEADER, fields))}})
            if not count:
                _fail('Header-only file is not evidence of no trades')
            if group_size > 1:
                multiple_groups += 1
                multiple_rows += group_size
                if group_multprice:
                    multiple_price_groups += 1
                    multiple_price_rows += group_size
            max_group = max(max_group, group_size)
            check()
            if _identity(stream) != identity or _hash(stream, manifest['size_bytes'], check) != manifest['sha256'] or _identity(stream) != identity:
                _fail('Opened source changed during scan or final hash')
            check()
    except (OSError, ValueError, struct.error, zlib.error) as exc:
        # Do not expose a local path or retain a partial result in the exception.
        if isinstance(exc, TradeFileError):
            raise
        raise TradeFileError('Source read or ZIP/CSV decoding failed; no complete result') from None
    for event in events:
        event['source_location'].update(member=stats['csv_member'], member_sha256=stats['csv_sha256'])
    check()
    audit = dict(stats, adapter_version=VERSION, status='FILE_DECODE_COMPLETE', validation_complete=True,
        disclosure='LOCAL_ONLY_CONTAINS_SOURCE_ROWS', synthetic_declared_by_caller=synthetic,
        information_as_of=information_as_of, source_manifest=manifest,
        source_bytes_sha256_verified=True, source_bytes_size_verified=True,
        same_open_fd_pre_post_sha256='MATCH', opened_file_stat_unchanged=True,
        path_scope='OPENED_FD_ONLY_NOT_LATER_PATH_BINDING',
        source_origin='DECLARED_URL_ALLOWLIST_ONLY_NOT_NETWORK_PROOF',
        acquisition_time='DECLARED_OBTAINED_AT_CONSTRAINTS_CHECKED_NOT_INDEPENDENTLY_PROVEN',
        partition_scope='DECLARED_LOCAL_DAY_NOT_EVENT_COMPLETENESS_PROOF',
        partition_utc={'start_inclusive': _iso(start), 'end_exclusive': _iso(end)},
        rows_read=count, target_rows_read=count, excluded_rows=0,
        observed_event_start=_iso(first_time), observed_event_end=_iso(previous_time),
        first_observed_trade_id=first_id, last_observed_trade_id=last_id,
        side_counts=side_counts, source_code_counts=source_counts,
        layout='NONDECREASING_TIMESTAMP_STRICT_NUMERIC_ID_NOT_EXCHANGE_CHRONOLOGY',
        duplicate_policy='REJECT_ANY_NONINCREASING_ID_NOT_DEDUPLICATION',
        same_ms={'multiple_row_groups': multiple_groups, 'rows_in_multiple_row_groups': multiple_rows,
                 'multiple_price_groups': multiple_price_groups, 'rows_in_multiple_price_groups': multiple_price_rows,
                 'max_rows_per_ms': max_group, 'exchange_chronology': 'UNKNOWN'},
        selection={'mode': 'WINDOW' if selection else 'AUDIT_ONLY_NO_EVENTS_REQUESTED',
                   'window': {'start_inclusive': _iso(selection[0]), 'end_exclusive': _iso(selection[1])} if selection else None,
                   'events_returned': len(events), 'coverage': 'UNKNOWN',
                   'presence': ('OBSERVED' if events else 'NOT_OBSERVED_NOT_PROVEN_ABSENT') if selection else 'NOT_REQUESTED'},
        limits={'zip_bytes': MAX_ZIP_BYTES, 'csv_bytes': MAX_CSV_BYTES, 'rows': MAX_ROWS,
                'physical_line_bytes': MAX_LINE_BYTES, 'chunk_bytes': CHUNK_BYTES,
                'selected_events': max_selected_events, 'timeout_seconds': timeout_seconds},
        source_coverage='UNKNOWN', data_complete=False, expected_event_count=None,
        exchange_sequence_available=False, settlement_marks='NOT_PROVIDED', funding_events='NOT_PROVIDED')
    return {'kernel_payload': {'instrument': TARGET, 'currency': 'USDT', 'synthetic': synthetic,
                              'source_coverage': 'UNKNOWN', 'data_complete': False,
                              'disclosure': 'LOCAL_ONLY_CONTAINS_SOURCE_ROWS', 'events': events}, 'audit': audit}
