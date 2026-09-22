#!/usr/bin/env python3
"""Read-only allowlist gate before adding or pushing public project files."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ROOTS = {'planning', '.agents', '.github', 'config', 'docs', 'scripts',
                 'researchlib', 'tests', 'web', 'site', 'records', 'research', 'review'}
ALLOWED_FILES = {'AGENTS.md', 'README.md', 'STATE.md', '.gitignore', 'PROJECT_SPEC.md',
                 'RESEARCH_PROGRAM.md', 'AUTOMATIONS.md', 'prompts', 'pyproject.toml'}
DENIED_PARTS = {'handoff', '.local', 'node_modules', 'incoming', 'private', '__pycache__',
                '.git', 'test-results', 'playwright-report'}
PATTERNS = [
    re.compile(rb'/(?:Users|home)/[A-Za-z0-9_.-]+/'),
    re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),
    re.compile(rb'sk-[A-Za-z0-9_-]{25,}'),
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'chatgpt-conversation://[a-zA-Z0-9-]{8,}'),
    re.compile(rb'(?i)(?:authorization:|api[_-]?key\s*[=:])\s*["\x27]?[A-Za-z0-9_./+-]{24,}'),
]

def check_paths(paths):
    failures = []
    for raw in paths:
        rel = Path(raw)
        if rel.is_absolute() or '..' in rel.parts:
            failures.append((raw, 'PATH_ESCAPE')); continue
        if rel.parts[0] not in ALLOWED_ROOTS and str(rel) not in ALLOWED_FILES:
            failures.append((raw, 'NOT_ALLOWLISTED')); continue
        if any(p in DENIED_PARTS for p in rel.parts) or rel.suffix.lower() in {'.zip', '.gz', '.tar', '.tgz', '.7z', '.sqlite', '.db', '.csv', '.parquet'}:
            failures.append((raw, 'RAW_OR_PRIVATE_OR_NESTED_ARCHIVE')); continue
        path = ROOT / rel
        cursor=ROOT
        bad_parent=False
        for part in rel.parts[:-1]:
            cursor=cursor/part
            if cursor.is_symlink():
                failures.append((raw,'SYMLINK_PARENT_REJECTED'));bad_parent=True;break
        if bad_parent:continue
        if path.is_symlink():
            target = path.resolve()
            if str(rel) not in {'PROJECT_SPEC.md','RESEARCH_PROGRAM.md','AUTOMATIONS.md','prompts'} or not target.is_relative_to(ROOT/'planning/current'):
                failures.append((raw, 'UNAPPROVED_SYMLINK'))
            continue
        if not path.exists():
            continue
        if not path.is_file():
            failures.append((raw, 'NOT_A_FILE')); continue
        data = path.read_bytes()
        if len(data) > 20 * 1024 * 1024:
            failures.append((raw, 'EXCEEDS_COMPACT_PUBLIC_FILE_LIMIT'))
        if any(p.search(data) for p in PATTERNS):
            failures.append((raw, 'SECRET_OR_PRIVATE_REFERENCE'))
        if data[:4] in (b'PK\x03\x04', b'PK\x05\x06') or data[:2] == b'\x1f\x8b':
            failures.append((raw, 'NESTED_ARCHIVE_MAGIC'))
    return failures

def tracked_paths():
    out = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT)
    return [p.decode() for p in out.split(b'\0') if p]

if __name__ == '__main__':
    paths = sys.argv[1:] or tracked_paths()
    failures = check_paths(paths)
    for name, reason in failures:
        print(f'{reason}: {name}')
    print(f'Public guard: {len(paths)} files; {len(failures)} rejected')
    raise SystemExit(bool(failures))
