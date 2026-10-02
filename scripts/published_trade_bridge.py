"""Fixed native bridge. Verify installed bytes before any method imports."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = '.local/methods/published-trade/counterfactual-v2'
BASE = ROOT / RELATIVE
NAMESPACE = 'published_trade_counterfactual_v2'
VERSION = 'btc-published-trade-sliced-counterfactual-v2'


def _canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n').encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(path, maximum=4_000_000):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError('NOT_REGULAR_OR_LIMIT')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('DUPLICATE_KEY')
            result[key] = value
        return result
    raw = path.read_bytes()
    return json.loads(raw.decode(), object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_JSON'))), raw


def _owned(root, relative):
    if not isinstance(relative, str) or relative.startswith('/') or '\\' in relative or ':' in relative or any(x in ('', '.', '..') for x in relative.split('/')):
        raise ValueError('UNSAFE_OWNED_PATH')
    result = root / relative
    cursor = result
    while cursor != root:
        if cursor.is_symlink():
            raise ValueError('OWNED_PATH_SYMLINK')
        cursor = cursor.parent
    return result


def verify_before_import():
    if sys.version_info[:3] != (3, 9, 6) or sys.implementation.name != 'cpython':
        raise ValueError('EXACT_RUNTIME_REQUIRED')
    if BASE != _owned(ROOT, RELATIVE):
        raise ValueError('FIXED_INSTALLED_HELPER_PATH_REQUIRED')
    installation, _ = _json(ROOT / '.local/installation.json')
    if installation.get('code_root') != str(ROOT.resolve()):
        raise ValueError('INSTALLATION_ROOT_BINDING')
    binding = installation.get(NAMESPACE, {})
    manifest, raw = _json(BASE / 'MANIFEST.json')
    if _sha(raw) != binding.get('method_manifest_sha256') or manifest.get('version') != VERSION:
        raise ValueError('INSTALLED_MANIFEST_HASH')
    files = manifest.get('files')
    if not isinstance(files, dict) or not files:
        raise ValueError('EMPTY_SOURCE_CLOSURE')
    if _sha(_canonical({'version': VERSION, 'files': files})) != binding.get('source_identity') or manifest.get('source_identity') != binding['source_identity']:
        raise ValueError('INSTALLED_SOURCE_IDENTITY')
    for relative, item in files.items():
        p = _owned(BASE, relative)
        if not p.is_file() or p.stat().st_size != item['bytes'] or _sha(p.read_bytes()) != item['sha256']:
            raise ValueError('INSTALLED_SOURCE_BYTES')
    integration, _ = _json(BASE / 'INTEGRATION.json')
    if _sha(_canonical(integration)) != binding.get('integration_sha256') or integration.get('helper_relative') != RELATIVE:
        raise ValueError('EXACT_INTEGRATION_REQUIRED')
    for relative, expected in integration['public_files'].items():
        p = _owned(ROOT, relative)
        if _sha(p.read_bytes()) != expected['sha256'] or p.stat().st_size != expected['bytes']:
            raise ValueError('INSTALLED_NATIVE_BRIDGE_OR_PROMPT_CHANGED')
    return installation


def main():
    parser = argparse.ArgumentParser(description='Fixed installed native bridge; no caller helper/backend/registry/worker override.')
    parser.add_argument('role', choices=['discovery', 'research', 'daily-review'])
    parser.add_argument('--batch-id')
    parser.add_argument('--cutoff', required=True)
    parser.add_argument('--dispatch-installed-worker', action='store_true')
    parser.add_argument('--advance-successor', action='store_true')
    args = parser.parse_args()
    config = verify_before_import()
    # Only these exact verified modules can now execute.
    sys.path.insert(0, str(BASE))
    from native_entry import discovery_entry, research_entry, daily_entry
    binding = config[NAMESPACE]
    if args.role == 'daily-review':
        if not args.batch_id or args.dispatch_installed_worker or args.advance_successor:
            parser.error('daily-review requires --batch-id, never download dispatch')
        output = daily_entry(args.batch_id, args.cutoff, 'research-tree-lab-3')
    elif args.role == 'research':
        if args.batch_id or (args.advance_successor and args.dispatch_installed_worker):
            parser.error('research has no batch override; successor and download dispatch are distinct fixed actions')
        output = research_entry(binding['plan_ref'], args.cutoff, args.dispatch_installed_worker, args.advance_successor)
    else:
        if args.batch_id or args.dispatch_installed_worker or args.advance_successor:
            parser.error('discovery only observes the existing acquisition request')
        output = discovery_entry(binding['plan_ref'], args.cutoff)
    if 'attachments' in output:
        output['attachments'] = {p: raw.decode() if isinstance(raw, bytes) else raw for p, raw in output['attachments'].items()}
    print(_canonical(output).decode(), end='')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(_canonical({'status': 'FIXED_BRIDGE_REJECTED', 'reason': str(exc), 'actual_net': None}).decode(), end='')
        sys.exit(2)
