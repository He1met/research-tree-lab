"""Append-only bundles with manifest barrier, explicit claims and fencing.

These are program-entry controls, not a filesystem sandbox. A process with OS
write access can bypass them; readers independently check all committed hashes.
"""
from __future__ import annotations

import fcntl
import os
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

from .common import (BusyError, ConflictError, ContractError, atomic_write,
                     canonical, digest, now_iso, read_json, safe_id, under, utc)
from .contracts import (ROLE_TYPES, record_ref, validate_record,
                        validate_relationships, semantic_refs)


class Store:
    def __init__(self, code_root, store_root=None, data_root=None, clock=now_iso):
        self.code_root = Path(code_root).resolve()
        installation = self.code_root / ".local/installation.json"
        config = read_json(installation) if installation.exists() else {}
        self.root = self._stable_root(store_root or config.get("store_root") or ".local/store")
        self.data_root = self._stable_root(data_root or config.get("data_root") or ".local/data")
        self.clock = clock
        for path in (self.root / "bundles", self.root / "staging", self.root / "claims", self.data_root / "objects"):
            path.mkdir(parents=True, exist_ok=True)

    def _stable_root(self, value):
        path = Path(value)
        if not path.is_absolute():
            path = self.code_root / path
        if path.is_symlink():
            raise ContractError("Stable data root cannot be a symlink")
        path = path.resolve()
        if "worktrees" in path.parts or path == Path("/tmp") or path.is_relative_to(Path("/private/tmp")):
            raise ContractError("Temporary/worktree roots cannot hold unique evidence")
        return path

    @contextmanager
    def writer_lock(self):
        lock_path = self.root / ".writer.lock"
        if lock_path.is_symlink():
            raise ContractError("Lock symlink rejected")
        with lock_path.open("a+b") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def _claim_path(self, request_key):
        if not isinstance(request_key, str) or not request_key or len(request_key) > 1000:
            raise ContractError("request_key required")
        return self.root / "claims" / (digest(request_key.encode()) + ".json")

    def _find_request(self, request_key):
        for bundle in sorted((self.root / "bundles").iterdir()):
            manifest_path = bundle / "manifest.json"
            if manifest_path.exists():
                try:
                    manifest = read_json(manifest_path)
                except (ValueError, TypeError, OSError):
                    continue
                if not isinstance(manifest, dict):
                    continue
                if manifest.get("request_key") == request_key:
                    self._read_bundle(bundle)
                    return manifest
        return None

    def claim(self, request_key, owner, role):
        safe_id(owner)
        if role not in ROLE_TYPES:
            raise ContractError("Unknown producer role")
        with self.writer_lock():
            committed = self._find_request(request_key)
            if committed:
                return {"state": "COMMITTED", "bundle_id": committed["bundle_id"], "request_key": request_key}
            path = self._claim_path(request_key)
            if path.exists():
                existing = read_json(path)
                if existing["owner"] != owner or existing["role"] != role:
                    raise BusyError("LOCK_BUSY: existing owner must be investigated, never removed by timeout")
                return existing
            claim = {"schema_version": "1.0", "state": "CLAIMED", "request_key": request_key,
                     "owner": owner, "role": role, "generation": 1, "token": uuid.uuid4().hex,
                     "claimed_at": self.clock(), "progress": []}
            atomic_write(path, canonical(claim))
            return claim

    def transfer_claim(self, request_key, previous_owner, owner, investigation_ref, reason):
        """Explicit audited recovery only; elapsed time never grants ownership."""
        safe_id(owner)
        if not investigation_ref or not reason:
            raise ContractError("An owner investigation and reason are required")
        with self.writer_lock():
            if self._find_request(request_key):
                raise ConflictError("Committed request cannot be reassigned")
            path = self._claim_path(request_key)
            old = read_json(path)
            if old["owner"] != previous_owner:
                raise ConflictError("Owner changed during investigation")
            history_path = self.root / "claims" / (path.stem + f".g{old['generation']}.history.json")
            if history_path.exists():
                raise ConflictError("Claim history conflict")
            atomic_write(history_path, canonical(old))
            new = dict(old, owner=owner, generation=old["generation"] + 1, token=uuid.uuid4().hex,
                       claimed_at=self.clock(), investigation_ref=investigation_ref, transfer_reason=reason)
            atomic_write(path, canonical(new))
            return new

    def checkpoint(self, request_key, token, stage, artifact_refs=None):
        with self.writer_lock():
            path = self._claim_path(request_key)
            claim = read_json(path)
            if claim["token"] != token:
                raise ConflictError("FENCED: stale owner cannot checkpoint")
            claim["progress"].append({"at": self.clock(), "stage": stage, "artifact_refs": artifact_refs or []})
            atomic_write(path, canonical(claim))
            return claim

    def _read_bundle(self, directory):
        if directory.is_symlink():
            raise ContractError("Bundle symlink rejected")
        manifest = read_json(under(directory, "manifest.json"))
        if not isinstance(manifest, dict):
            raise ContractError("Invalid manifest object")
        if manifest.get("schema_version") not in {1, "1", "1.0"}:
            raise ContractError("UNSUPPORTED_SCHEMA: manifest")
        if manifest.get("commit_state") != "COMMITTED":
            raise ContractError("Bundle lacks complete commit barrier")
        if manifest.get("bundle_id") != directory.name:
            raise ContractError("Bundle identity mismatch")
        records, seen = [], set()
        for entry in manifest.get("files", []):
            relative = entry["path"]
            if relative in seen:
                raise ContractError("Manifest repeats a file")
            seen.add(relative)
            file_path = under(directory, relative)
            raw = file_path.read_bytes()
            if len(raw) != entry["bytes"] or digest(raw) != entry["sha256"]:
                raise ContractError("INTEGRITY_FAILURE: committed bytes changed")
            if entry.get("kind") == "record":
                record = read_json(file_path)
                if validate_record(record, manifest["producer_role"]) != entry["record_ref"]:
                    raise ContractError("Record identity mismatch")
                records.append(record)
        # Undeclared files are not silently included in export or backup.
        actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
        if actual != seen | {"manifest.json"}:
            raise ContractError("Manifest does not cover complete bundle")
        return manifest, records

    def load(self, strict=False):
        records, metadata, anomalies = {}, {}, []
        for directory in sorted((self.root / "bundles").iterdir()):
            if not directory.is_dir() or not (directory / "manifest.json").exists():
                anomalies.append({"bundle_id": directory.name, "code": "UNCOMMITTED_IGNORED"})
                continue
            try:
                manifest, bundle_records = self._read_bundle(directory)
                pending = {}
                for record in bundle_records:
                    ref = record_ref(record)
                    if ref in records or ref in pending:
                        raise ConflictError("Duplicate record identity across bundles")
                    pending[ref] = record
                records.update(pending)
                for ref in pending:
                    metadata[ref] = {"bundle_id": manifest["bundle_id"], "committed_at": manifest["completed_at"],
                                     "producer_role": manifest["producer_role"], "record_hash": digest(canonical(pending[ref]))}
            except (ValueError, KeyError, OSError, TypeError) as exc:
                if strict:
                    raise ContractError(f"Invalid bundle {directory.name}: {exc}") from exc
                anomalies.append({"bundle_id": directory.name, "code": "INVALID_BUNDLE", "reason": str(exc)})
        return records, metadata, anomalies

    def commit_bundle(self, bundle_id, role, records, attachments=None, request_key=None,
                      claim_token=None, owner=None, fail_before_commit=False):
        safe_id(bundle_id)
        request_key = request_key or bundle_id
        attachments = attachments or {}
        if not records:
            raise ContractError("A bundle must contain at least one formal record")
        incoming = {}
        for record in records:
            ref = validate_record(record, role)
            if ref in incoming:
                raise ConflictError("Duplicate record in bundle")
            incoming[ref] = record
        files = {}
        for ref, record in sorted(incoming.items()):
            path = f"records/{record['record_type']}/{ref}.json"
            files[path] = (canonical(record), {"kind": "record", "record_ref": ref})
        for relative, content in sorted(attachments.items()):
            relative = str(under(self.root / "staging", relative).relative_to(self.root / "staging"))
            path = "attachments/" + relative
            if isinstance(content, str):
                content = content.encode()
            if not isinstance(content, bytes):
                raise ContractError("Attachment value must be bytes or text")
            files[path] = (content, {"kind": "attachment"})
        payload_hash = digest(canonical({p: digest(raw) for p, (raw, _) in files.items()}))
        if not claim_token:
            claim = self.claim(request_key, owner or "writer-" + uuid.uuid4().hex, role)
            claim_token = claim.get("token")
        # Research computation happens outside this short publication barrier.
        with self.writer_lock():
            existing_request = self._find_request(request_key)
            destination = self.root / "bundles" / bundle_id
            if existing_request:
                if existing_request["payload_hash"] != payload_hash or existing_request["producer_role"] != role:
                    raise ConflictError("Same request_key has different immutable contents")
                return dict(existing_request, replayed=True)
            if destination.exists():
                old, _ = self._read_bundle(destination)
                if old["payload_hash"] == payload_hash and old["producer_role"] == role:
                    return dict(old, replayed=True)
                raise ConflictError("Same bundle ID has different immutable contents")
            claim = read_json(self._claim_path(request_key))
            if claim["token"] != claim_token or claim["role"] != role:
                raise ConflictError("FENCED: stale/mismatched owner cannot commit")
            existing, _, _ = self.load(strict=False)
            # A corrupt unrelated bundle must not halt independent work. Keep all
            # sealed IDs reserved, and exclude only broken reference closures.
            reserved_refs = set(existing)
            for original_path in (self.root / "bundles").glob("*/records/*/*.json"):
                reserved_refs.add(original_path.stem)
            for manifest_path in (self.root / "bundles").glob("*/manifest.json"):
                try:
                    manifest_record = read_json(manifest_path)
                    if isinstance(manifest_record, dict):
                        reserved_refs.update(manifest_record.get("record_refs", []))
                except (ValueError, TypeError, OSError):
                    continue
            while True:
                broken = {ref for ref, record in existing.items() if any(target not in existing for target in semantic_refs(record))}
                if not broken:
                    break
                existing = {ref: record for ref, record in existing.items() if ref not in broken}
            for ref in incoming:
                if ref in reserved_refs:
                    raise ConflictError("Record already sealed; write a new version/revision")
            validate_relationships(dict(existing, **incoming))
            committed_at = self.clock()
            if any(utc(r["available_at"]) > utc(committed_at) for r in incoming.values()):
                raise ContractError("Cannot commit future-created information")
            staging = Path(tempfile.mkdtemp(prefix=bundle_id + "-", dir=self.root / "staging"))
            manifest_files = []
            for relative, (raw, extra) in sorted(files.items()):
                atomic_write(under(staging, relative), raw)
                manifest_files.append(dict(path=relative, sha256=digest(raw), bytes=len(raw), **extra))
            if fail_before_commit:
                raise InterruptedError("Injected test interruption before manifest; staging preserved")
            manifest = {"schema_version": "1.0", "bundle_id": bundle_id, "producer_role": role,
                        "owner_ref": claim["owner"], "claim_generation": claim["generation"],
                        "request_key": request_key, "payload_hash": payload_hash,
                        "files": manifest_files, "record_refs": sorted(incoming),
                        "completed_at": committed_at, "commit_state": "COMMITTED"}
            atomic_write(staging / "manifest.json", canonical(manifest))
            # Rename is atomic on the stable store filesystem, after every file fsync.
            os.rename(staging, destination)
            parent_fd = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
            claim.update(state="COMMITTED", bundle_id=bundle_id, committed_at=committed_at)
            atomic_write(self._claim_path(request_key), canonical(claim))
            return manifest

    def put_data(self, data, metadata, role):
        if role not in {"discovery", "research", "review"}:
            raise ContractError("Role cannot acquire data")
        if not isinstance(data, bytes):
            raise ContractError("Shared data must be exact bytes")
        for field in ("source_url", "acquired_at", "license", "data_role"):
            if not metadata.get(field):
                raise ContractError("Data provenance missing " + field)
        utc(metadata["acquired_at"])
        sha = digest(data)
        target = self.data_root / "objects" / sha
        with self.writer_lock():
            if target.exists() and target.read_bytes() != data:
                raise ConflictError("Shared data hash collision/corruption")
            if not target.exists():
                atomic_write(target, data)
            receipt = dict(metadata, sha256=sha, bytes=len(data), record_state="IMMUTABLE_RAW")
            receipt_hash = digest(canonical(receipt))
            receipt_path = self.data_root / "receipts" / (receipt_hash + ".json")
            if not receipt_path.exists():
                atomic_write(receipt_path, canonical(receipt))
        return dict(receipt, data_ref="sha256:" + sha, receipt_ref=receipt_hash)

    def resolve_evidence(self, ref, records=None):
        records = records if records is not None else self.load(strict=True)[0]
        if ref in records:
            return {"kind": "record", "record": records[ref], "sha256": digest(canonical(records[ref]))}
        if isinstance(ref, str) and ref.startswith("sha256:"):
            sha = ref.split(":", 1)[1]
            if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
                raise ContractError("Invalid evidence digest")
            data = under(self.data_root, "objects/" + sha)
            if data.exists() and digest(data.read_bytes()) == sha:
                return {"kind": "data", "sha256": sha, "bytes": data.stat().st_size}
        if isinstance(ref, str) and ref.startswith("bundle:"):
            try:
                bundle_id, relative = ref[7:].split("/", 1)
            except ValueError as exc:
                raise ContractError("Invalid bundle evidence ref") from exc
            directory = self.root / "bundles" / safe_id(bundle_id)
            manifest, _ = self._read_bundle(directory)
            for entry in manifest["files"]:
                if entry["path"] == relative:
                    return dict(entry, kind="attachment")
        raise ContractError("Unresolved evidence reference")

    def status(self):
        records, _, anomalies = self.load()
        claims = [read_json(p) for p in (self.root / "claims").glob("*.json") if ".history." not in p.name]
        return {"schema_version": "1.0", "record_count": len(records), "anomalies": anomalies,
                "in_progress": [{"request_key": c["request_key"], "owner": c["owner"], "generation": c["generation"],
                                 "claimed_at": c["claimed_at"], "last_progress": c.get("progress", [])[-1:]} for c in claims if c["state"] != "COMMITTED"],
                "uncommitted_staging_count": len(list((self.root / "staging").iterdir())),
                "enforcement": "PROGRAM_ENTRY_CONTROLS_AND_HASH_DETECTION_NOT_OS_SANDBOX"}
