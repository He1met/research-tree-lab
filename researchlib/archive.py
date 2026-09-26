"""Public-scope research backup and exact-byte recovery in a new directory."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from .common import ContractError, atomic_write, canonical, digest, now_iso, read_json, under
from .contracts import record_ref, semantic_refs, validate_record, validate_relationships
from .public import attachment_allowed, public_record, scan_bytes


def _calendar_original_policy(original, extra):
    """Two fixed authored originals; the omitted fields carry no new license.

    Round membership duplicates an already exported input reference. The two
    feedback dispositions describe bounded diagnostic use, not economic review
    or a newly executed successor. Full original identity is pinned below.
    """
    if original.get('round_id') != 'r-stock-session-mechanism-20260923':
        return None
    inputs = original.get('input_record_refs')
    if not isinstance(inputs, list) or original['round_id'] not in inputs:
        return None
    if (original.get('record_type') == 'evidence'
            and original.get('evidence_id') == 'e-stock-session-calendar-20260927'
            and extra == {'round_id'}
            and digest(canonical(original)) == 'e4d1b106b95fa2a3e0f56c08c34966b1eb6ad4854a895dd0c0cc9da743acfdbb'):
        return 'EXACT_STOCK_CALENDAR_EVIDENCE_V1'
    if (original.get('record_type') != 'decision'
            or original.get('decision_id') != 'decision-stock-session-calendar-20260927'
            or extra != {'round_id', 'feedback_dispositions'}):
        return None
    dispositions = original.get('feedback_dispositions')
    if not isinstance(dispositions, list) or len(dispositions) != 2:
        return None
    for item, side in zip(dispositions, ('long-control', 'short')):
        if not isinstance(item, dict) or set(item) != {
                'actual_application', 'disposition', 'existing_successor_round_id',
                'feedback_ref', 'source_review_ref'}:
            return None
        feedback = 'feedback-btc-funding-' + side + '-manual-20260923-v1'
        review = 'review-btc-funding-' + side + '-manual-20260923-v1'
        if (item['feedback_ref'] != feedback or item['source_review_ref'] != review
                or feedback not in inputs or review not in inputs
                or item['existing_successor_round_id'] != 'r-feedback-input-completeness-20260923'
                or item['disposition'] != 'ADOPT_DATA_ROLE_TIME_AND_UNKNOWN_COST_BOUNDARIES; WAIT_ECONOMIC_INPUT'
                or item['actual_application'] != 'Calendar labels not substituted for actual quotes, price coverage or costs; retrieved sources not backdated.'):
            return None
    if digest(canonical(original)) == '18c5cfbf2df82e5bc8d8b9f78cb861c9a2e68bbbd3e2d2cd9af7c7a3efc3e527':
        return 'EXACT_STOCK_CALENDAR_DECISION_V1'
    return None


def _exact_public_export_policy(original):
    """Versioned, source-reviewed original exceptions, never caller policy.

    Public projection and graph semantics stay unchanged. This does not allow
    arbitrary decision metadata, a configurable hash list, or restricted fields.
    """
    projection = public_record(original)
    if projection is None:
        raise ContractError("Recovery closure includes non-public/synthetic original")
    if any(projection[key] != original[key] for key in projection):
        raise ContractError("Public projection changed original values")
    if set(projection) == set(original):
        return None
    policy = original.get('disclosure', {})
    extra = set(original) - set(projection)
    child = original.get('future_child')
    approved = (
        'export_fields' not in policy
        and policy.get('visibility') == 'PUBLIC' and policy.get('license') == 'OWN_ANALYSIS'
        and original.get('record_type') == 'decision'
        and original.get('decision_id') == 'decision-numeraire-boundary-20260927'
        and extra == {'future_child', 'new_feedback_successor_created', 'trial_state'}
        and isinstance(child, dict) and set(child) == {'parent_round_id', 'question', 'state'}
        and child['parent_round_id'] == original.get('source_round_ref')
        and child['state'] == 'PROPOSED_NOT_EXECUTED'
        and isinstance(child['question'], str) and 0 < len(child['question']) <= 512
        and original.get('new_feedback_successor_created') is False
        and original.get('trial_state') == 'PREPARATION_ONLY'
        and digest(canonical(original)) == '6b5ec5278a5d5bdc3945d483035a4d6c9e1f9ffad8871bf71933ce109aa7c64c'
    )
    exact_policy = 'EXACT_NUMERAIRE_DECISION_METADATA_V1' if approved else None
    if (exact_policy is None and 'export_fields' not in policy
            and policy.get('visibility') == 'PUBLIC' and policy.get('license') == 'OWN_ANALYSIS'):
        exact_policy = _calendar_original_policy(original, extra)
    if exact_policy is None:
        raise ContractError("Original has non-whitelisted fields; cannot claim exact public backup")
    scan_bytes('approved-original.json', canonical(original))
    return exact_policy


def export_backup(store, destination, record_refs=None, extra_files=None):
    records, metadata, anomalies = store.load(strict=True)
    selected = set(record_refs or records)
    missing = selected - set(records)
    if missing:
        raise ContractError("Requested backup record does not exist")
    todo = list(selected)
    while todo:
        ref = todo.pop()
        for target in semantic_refs(records[ref]):
            if target not in selected:
                selected.add(target)
                todo.append(target)
    files, record_entries, excluded = {}, [], []
    bundle_cache = {}
    for ref in sorted(selected):
        original = records[ref]
        exact_policy = _exact_public_export_policy(original)
        relative = "records/" + ref + ".json"
        raw = canonical(original)
        scan_bytes(relative, raw)
        files[relative] = raw
        record_entries.append({"record_ref": ref, "path": relative, "producer_role": metadata[ref]["producer_role"],
                               "original_record_hash": metadata[ref]["record_hash"], "original_committed_at": metadata[ref]["committed_at"]})
        if exact_policy is not None:
            record_entries[-1]['exact_export_policy'] = exact_policy
        bundle_id = metadata[ref]["bundle_id"]
        directory = store.root / "bundles" / bundle_id
        if bundle_id not in bundle_cache:
            bundle_cache[bundle_id] = store._read_bundle(directory)[0]
        for entry in bundle_cache[bundle_id]["files"]:
            if entry.get("kind") != "attachment":
                continue
            if attachment_allowed(original, entry["path"]):
                name = "evidence/" + bundle_id + "/" + entry["path"]
                content = under(directory, entry["path"]).read_bytes()
                scan_bytes(name, content)
                files[name] = content
    for relative, content in (extra_files or {}).items():
        name = "extras/" + str(relative)
        if isinstance(content, str):
            content = content.encode()
        scan_bytes(name, content)
        if name in files and files[name] != content:
            raise ContractError("Backup file name conflict")
        files[name] = content
    manifest = {"schema_version": "1.0", "archive_kind": "PUBLIC_RESEARCH_SCOPE_V1",
                "record_refs": sorted(selected), "records": record_entries,
                "files": [{"path": path, "sha256": digest(raw), "bytes": len(raw)} for path, raw in sorted(files.items())],
                "coverage": "EXACT_PUBLIC_RECORDS_AND_EXPLICITLY_LICENSED_ATTACHMENTS",
                "limitations": ["Restricted upstream originals and local-only material are not included or claimed backed up.",
                                "Recovery verifies stored bytes and contracts; scientific reproduction must be run separately."]}
    manifest["archive_id"] = digest(canonical(manifest))
    files["ARCHIVE_MANIFEST.json"] = canonical(manifest)
    destination = Path(destination)
    if destination.exists():
        old = inspect_backup(destination)
        if old["archive_id"] != manifest["archive_id"]:
            raise ContractError("Backup destination already contains different evidence")
        return dict(manifest, archive_state="EXISTING_VERIFIED_LOCAL_ARCHIVE")
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)
    scan_bytes("archive.zip", stream.getvalue())
    atomic_write(destination, stream.getvalue())
    inspect_backup(destination)
    return dict(manifest, archive_state="LOCAL_ARCHIVE_VERIFIED_NOT_REMOTE_CONFIRMED",
                archive_sha256=digest(stream.getvalue()), archive_bytes=len(stream.getvalue()))


def inspect_backup(path):
    raw = Path(path).read_bytes()
    scan_bytes("archive.zip", raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ContractError("Archive contains duplicate paths")
        manifest = json.loads(archive.read("ARCHIVE_MANIFEST.json"))
        if manifest.get("schema_version") not in {1, "1", "1.0"} or manifest.get("archive_kind") != "PUBLIC_RESEARCH_SCOPE_V1":
            raise ContractError("Unsupported recovery archive schema")
        payload = dict(manifest)
        payload.pop("archive_id", None)
        if digest(canonical(payload)) != manifest.get("archive_id"):
            raise ContractError("Archive manifest identity mismatch")
        expected = {entry["path"] for entry in manifest["files"]} | {"ARCHIVE_MANIFEST.json"}
        if set(names) != expected:
            raise ContractError("Archive contains unmanifested or missing files")
        for entry in manifest["files"]:
            content = archive.read(entry["path"])
            if digest(content) != entry["sha256"] or len(content) != entry["bytes"]:
                raise ContractError("Recovery bytes do not match manifest")
        records = {}
        for entry in manifest["records"]:
            content = archive.read(entry["path"])
            record = json.loads(content)
            ref = validate_record(record, entry["producer_role"])
            if ref != entry["record_ref"] or digest(content) != entry["original_record_hash"]:
                raise ContractError("Recovery original identity/hash mismatch")
            exact_policy = _exact_public_export_policy(record)
            if entry.get('exact_export_policy') != exact_policy:
                raise ContractError("Recovery exact-export policy mismatch")
            if exact_policy is not None and content != canonical(record):
                raise ContractError("Recovery reviewed original bytes mismatch")
            records[ref] = record
        validate_relationships(records)
        return manifest


def restore_backup(path, new_directory):
    manifest = inspect_backup(path)
    new_directory = Path(new_directory)
    if new_directory.exists():
        raise ContractError("Recovery requires a new directory; never overwrite existing work")
    new_directory.mkdir(parents=True)
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            atomic_write(under(new_directory, name), archive.read(name))
    for entry in manifest["files"]:
        raw = under(new_directory, entry["path"]).read_bytes()
        if digest(raw) != entry["sha256"] or len(raw) != entry["bytes"]:
            raise ContractError("Recovered file verification failed")
    receipt = {"schema_version": "1.0", "archive_id": manifest["archive_id"],
               "restored_at": now_iso(), "record_refs": manifest["record_refs"],
               "files_verified": len(manifest["files"]), "state": "EXACT_PUBLIC_BYTES_RECOVERED",
               "scientific_reproduction": "NOT_RUN", "source_archive_sha256": digest(Path(path).read_bytes()),
               "limitations": manifest["limitations"]}
    atomic_write(new_directory / "RECOVERY_RECEIPT.json", canonical(receipt))
    return receipt
