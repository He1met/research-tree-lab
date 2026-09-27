"""Offline parsing of the observed OKX allswap funding file (schema v1).

This validates supplied bytes and declarations, not their network provenance or
event completeness. Output contains source rows: keep the whole result local.
No filesystem extraction, network access, settlement mark inference or calendar.
"""
import csv
import binascii
import io
import re
import stat
import struct
import zipfile
import zlib
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from .common import ContractError, digest, utc

VERSION = 'okx-allswap-funding-file-v1'
HEADER = ('instrument_name', 'funding_rate', 'funding_time')
MAX_SOURCE_BYTES = 10_000_000
MAX_CSV_BYTES = 20_000_000
MAX_ROWS = 250_000
OFFICIAL_HOSTS = frozenset({'www.okx.com', 'okx.com', 'static.okx.com'})
SUPPORTED_TARGET = 'BTC-USDT-SWAP'
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
LOCAL_ZONE = timezone(timedelta(hours=8))
MANIFEST_FIELDS = frozenset({'schema_version', 'format', 'filename', 'sha256',
                             'size_bytes', 'source_url', 'obtained_at', 'declared_partition'})


def _iso(at):
    return at.isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def _timestamp(value, field):
    # Common utc() rejects missing/naive timestamps; also exclude ISO date-only
    # and nonstandard separators, which have no place in acquisition receipts.
    if not isinstance(value, str) or not re.fullmatch(
            r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])', value):
        raise ContractError('Invalid timezone-aware timestamp: ' + field)
    return utc(value)


def _validate_manifest(blob, manifest, information_as_of):
    if not isinstance(blob, bytes) or not 0 < len(blob) <= MAX_SOURCE_BYTES:
        raise ContractError('Source must be nonempty bytes within 10 MB')
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_FIELDS:
        raise ContractError('Exact source manifest fields required')
    if type(manifest['schema_version']) is not int or manifest['schema_version'] != 1:
        raise ContractError('Source manifest schema_version must be integer 1')
    if type(manifest['size_bytes']) is not int or manifest['size_bytes'] != len(blob):
        raise ContractError('Source size_bytes does not match actual bytes')
    sha = manifest['sha256']
    if not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{64}', sha) or sha != digest(blob):
        raise ContractError('Source sha256 does not match actual bytes')
    fmt, filename = manifest['format'], manifest['filename']
    if fmt not in ('zip', 'csv') or not isinstance(filename, str):
        raise ContractError('Only observed ZIP/CSV format supported')
    match = re.fullmatch(r'allswap-fundingrates-([0-9]{4}-[0-9]{2}-[0-9]{2})\.' + fmt, filename)
    if not match:
        raise ContractError('Only observed allswap daily filename supported')
    partition = manifest['declared_partition']
    if not isinstance(partition, dict) or set(partition) != {'date', 'timezone'}:
        raise ContractError('Exact declared_partition fields required')
    if partition['timezone'] != 'UTC+08:00' or partition['date'] != match.group(1):
        raise ContractError('Declared partition must match filename date and UTC+08:00')
    try:
        day = date.fromisoformat(partition['date'])
        start = datetime.combine(day, datetime.min.time(), LOCAL_ZONE).astimezone(timezone.utc)
        end = start + timedelta(days=1)
    except (ValueError, OverflowError) as exc:
        raise ContractError('Invalid declared partition date') from exc
    url = manifest['source_url']
    if not isinstance(url, str) or not url.isascii() or any(ord(c) <= 32 for c in url) or '\\' in url:
        raise ContractError('Invalid declared source URL')
    try:
        parsed = urlsplit(url)
        permitted_path = (parsed.path in {'/historical-data', '/zh-hans/historical-data'}
                          or parsed.path.endswith(('.zip', '.csv')))
        if (parsed.scheme != 'https' or parsed.hostname not in OFFICIAL_HOSTS
                or parsed.netloc != parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or not permitted_path):
            raise ContractError('Declared source URL outside reviewed host/path scope')
    except ValueError as exc:
        raise ContractError('Invalid declared source URL') from exc
    obtained = _timestamp(manifest['obtained_at'], 'obtained_at')
    info = _timestamp(information_as_of, 'information_as_of')
    if obtained > info or info > datetime.now(timezone.utc):
        raise ContractError('Acquisition/information time is in the future or outside cutoff')
    return start, end, obtained, info


def _csv_bytes(blob, manifest):
    if manifest['format'] == 'csv':
        if len(blob) > MAX_CSV_BYTES:
            raise ContractError('CSV size outside bounded limit')
        return blob, manifest['filename'], 'NOT_APPLICABLE'
    expected = manifest['filename'][:-4] + '.csv'
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            members = archive.infolist()
            if len(members) != 1:
                raise ContractError('Exactly one expected CSV ZIP member required')
            member = members[0]
            mode = member.external_attr >> 16
            if (member.filename != expected or member.is_dir()
                    or stat.S_IFMT(mode) not in (0, stat.S_IFREG)
                    or member.flag_bits not in (0, 0x800)
                    or member.extra or member.header_offset != 0
                    or member.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                raise ContractError('Unsafe or unexpected ZIP member')
            if not 0 < member.file_size <= MAX_CSV_BYTES or member.compress_size > len(blob):
                raise ContractError('ZIP member size outside bounded CSV limit')
            # The observed format has no ZIP64 extras or data descriptor. Match
            # local/central sizes before bounded inflation; ZipExtFile alone can
            # stop at a forged short central size, hiding decompressed tail data.
            header = struct.unpack('<4s5H3I2H', blob[:30])
            signature, _, flags, codec, _, _, crc, packed, expanded, namesize, extrasize = header
            offset = 30 + namesize + extrasize
            if (signature != b'PK\x03\x04' or flags != member.flag_bits
                    or codec != member.compress_type or crc != member.CRC
                    or packed != member.compress_size or expanded != member.file_size
                    or extrasize or blob[30:offset] != expected.encode('ascii')
                    or offset + packed > len(blob)):
                raise ContractError('ZIP local and central declarations disagree')
            compressed = blob[offset:offset + packed]
            if codec == zipfile.ZIP_STORED:
                content = compressed
            else:
                inflater = zlib.decompressobj(-15)
                content = inflater.decompress(compressed, MAX_CSV_BYTES + 1)
                if not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
                    raise ContractError('ZIP compressed stream exceeds limit or has trailing data')
            if len(content) > MAX_CSV_BYTES or len(content) != member.file_size:
                raise ContractError('Expanded CSV size differs from ZIP declaration')
            if binascii.crc32(content) & 0xffffffff != member.CRC:
                raise ContractError('ZIP CRC verification failed')
            return content, member.filename, 'PASS'
    except (zipfile.BadZipFile, zlib.error, struct.error, RuntimeError,
            NotImplementedError, OSError, EOFError) as exc:
        raise ContractError('ZIP decoding or CRC verification failed') from exc


def _rate(value):
    if len(value) > 128 or not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?', value):
        raise ContractError('Invalid finite decimal funding_rate')
    try:
        number = Decimal(value)
        if not number.is_finite() or abs(number.as_tuple().exponent) > 1000:
            raise ContractError('Funding decimal outside bounded encoding')
        # Canonicalize without normalize(), which uses ambient decimal precision.
        if number == 0:
            return number, '0'
        sign, digits, exponent = number.as_tuple()
        digits = list(digits)
        while digits[-1] == 0:
            digits.pop()
            exponent += 1
        return number, str(Decimal((sign, tuple(digits), exponent)))
    except InvalidOperation as exc:
        raise ContractError('Invalid finite decimal funding_rate') from exc


def _event_time(value):
    if not re.fullmatch(r'(?:0|[1-9][0-9]{0,14})', value):
        raise ContractError('funding_time must be a nonnegative integer millisecond string')
    try:
        return EPOCH + timedelta(milliseconds=int(value))
    except OverflowError as exc:
        raise ContractError('funding_time outside representable UTC range') from exc


def normalize_funding_file(blob, manifest, *, information_as_of, synthetic,
                           target_instrument=SUPPORTED_TARGET):
    """Return {kernel_payload, audit}; both must remain LOCAL_ONLY.

    The exact manifest binds supplied bytes, a declared URL, obtained_at and UTC+8
    day. The caller provides information_as_of separately. Neither declared
    timestamps nor URL allowlisting prove actual acquisition or official origin.
    All rows, including excluded instruments, are checked before any result is
    returned. Unsupported target expansions require a new reviewed adapter.
    synthetic is a required caller declaration, never inferred from byte hashes.
    """
    if type(synthetic) is not bool:
        raise ContractError('Explicit boolean synthetic declaration required')
    if target_instrument != SUPPORTED_TARGET:
        raise ContractError('Only reviewed BTC-USDT-SWAP / USDT target supported')
    start, end, obtained, info = _validate_manifest(blob, manifest, information_as_of)
    content, member_name, crc = _csv_bytes(blob, manifest)
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ContractError('CSV must be UTF-8 with optional leading BOM') from exc
    member_sha = digest(content)
    rows, count, target_count = {}, 0, 0
    reader = csv.reader(io.StringIO(text, newline=''), strict=True)
    try:
        if tuple(next(reader, ())) != HEADER:
            raise ContractError('CSV header must exactly match observed field order')
        for fields in reader:
            count += 1
            line = reader.line_num
            if count > MAX_ROWS or len(fields) != 3 or any(len(v) > 128 for v in fields):
                raise ContractError('CSV row count, column count or field size invalid')
            instrument, rate_text, time_text = fields
            if not re.fullmatch(r'[A-Z0-9]{1,32}-(?:USD|USDT|USDC)-SWAP', instrument):
                raise ContractError('Invalid perpetual instrument_name')
            number, normalized_rate = _rate(rate_text)
            at = _event_time(time_text)
            if not start <= at < end:
                raise ContractError('Event outside declared UTC+8 partition')
            if at > obtained:
                raise ContractError('Acquisition precedes source event (backdated or future row)')
            # Each accepted field excludes newline characters; row numbers thus
            # locate the actual source line, even when the file uses CRLF.
            location = {'line': line, 'raw_fields': dict(zip(HEADER, fields))}
            key = (instrument, int(time_text))
            if key in rows:
                if rows[key]['number'] != number:
                    raise ContractError('Conflicting funding values for same instrument and timestamp')
                rows[key]['locations'].append(location)
            else:
                rows[key] = {'number': number, 'rate': normalized_rate,
                             'event_at': _iso(at), 'locations': [location]}
            if instrument == target_instrument:
                target_count += 1
    except csv.Error as exc:
        raise ContractError('Malformed CSV syntax or oversized field') from exc
    if not count:
        raise ContractError('Header-only CSV is not evidence of no funding')
    events, duplicates = [], []
    for (instrument, milliseconds), record in sorted(rows.items()):
        if len(record['locations']) > 1:
            duplicates.append({'instrument': instrument, 'funding_time_ms': milliseconds,
                               'policy': 'NUMERIC_EQUAL_VALUES_DEDUPLICATED_NOT_IDENTICAL_BYTES',
                               'source_rows': record['locations']})
        if instrument == target_instrument:
            events.append({'event_id': 'okx-funding:%s:%s' % (instrument, milliseconds),
                           'kind': 'funding', 'instrument': instrument, 'currency': 'USDT',
                           'event_at': record['event_at'], 'available_at': manifest['obtained_at'],
                           'rate': record['rate'], 'settlement_mark': None,
                           'source_sha256': manifest['sha256'],
                           'source_location': {'member': member_name, 'member_sha256': member_sha,
                                               'source_rows': record['locations']}})
    audit = {'adapter_version': VERSION, 'disclosure': 'LOCAL_ONLY_CONTAINS_SOURCE_ROWS',
             'synthetic_declared_by_caller': synthetic,
             'information_as_of': information_as_of, 'source_manifest': deepcopy(manifest),
             'source_bytes_sha256_verified': True, 'source_bytes_size_verified': True,
             'zip_crc': crc, 'csv_member': member_name, 'csv_bytes': len(content),
             'csv_sha256': member_sha, 'source_origin': 'DECLARED_URL_ALLOWLIST_ONLY_NOT_NETWORK_PROOF',
             'acquisition_time': 'DECLARED_OBTAINED_AT_CONSTRAINTS_CHECKED_NOT_INDEPENDENTLY_PROVEN',
             'partition_scope': 'DECLARED_LOCAL_DAY_NOT_EVENT_COMPLETENESS_PROOF',
             'partition_utc': {'start_inclusive': _iso(start), 'end_exclusive': _iso(end)},
             'rows_read': count, 'target_rows_read': target_count,
             'excluded_rows': count - target_count, 'unique_rows_all_instruments': len(rows),
             'duplicate_rows_removed_all_instruments': count - len(rows),
             'duplicate_groups': duplicates, 'target_events': len(events),
             'source_coverage': 'UNKNOWN', 'data_complete': False,
             'target_presence': 'OBSERVED' if events else 'NOT_OBSERVED_NOT_PROVEN_ABSENT',
             'settlement_marks': 'MISSING', 'expected_event_count': None,
             'settlement_schedule_inferred': False}
    return {'kernel_payload': {'instrument': target_instrument, 'currency': 'USDT',
                               'synthetic': synthetic,
                               'source_coverage': 'UNKNOWN', 'data_complete': False,
                               'disclosure': 'LOCAL_ONLY_CONTAINS_SOURCE_ROWS', 'events': events},
            'audit': audit}
