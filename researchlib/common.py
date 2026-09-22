"""Strict, deterministic primitives shared by writer and read-only projection."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


class ContractError(ValueError):
    pass


class ConflictError(ContractError):
    pass


class BusyError(ContractError):
    pass


def utc(value):
    if not isinstance(value, str) or not value:
        raise ContractError("Timezone-aware timestamp required")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("Invalid timestamp") from exc
    if result.tzinfo is None:
        raise ContractError("Naive timestamps are forbidden")
    return result.astimezone(timezone.utc)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@:-]{0,159}", value):
        raise ContractError("Invalid stable ID (use letters, numbers, _, -, ., @, :)")
    if value in {".", ".."}:
        raise ContractError("Invalid stable ID")
    return value


def safe_relative(value):
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ContractError("Invalid relative path")
    p = PurePosixPath(value)
    if p.is_absolute() or any(part in {"..", "."} for part in value.split("/")) or "//" in value or ":" in value:
        raise ContractError("Path escape rejected")
    return p


def under(root, relative):
    root = Path(root).resolve()
    p = root.joinpath(safe_relative(relative))
    # Reject symlinks even if they happen to resolve within the root today.
    cursor = p
    while cursor != root:
        if cursor.is_symlink():
            raise ContractError("Symlink path rejected")
        cursor = cursor.parent
    if not p.resolve().is_relative_to(root):
        raise ContractError("Path escape rejected")
    return p


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ContractError("Symlink destination rejected")
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ContractError("Duplicate JSON key")
            result[key] = value
        return result
    def invalid(value):
        raise ContractError("Non-finite JSON number")
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique, parse_constant=invalid)
