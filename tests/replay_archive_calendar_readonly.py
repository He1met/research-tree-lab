"""Read known project originals and existing archives; write only temporary engineering outputs."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from researchlib.archive import export_backup, inspect_backup, restore_backup
from researchlib.common import canonical, digest, now_iso
from researchlib.funding_review import readonly_store
from researchlib.public import public_record
from researchlib.snapshot import project


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--project-root', required=True)
    root = Path(parser.parse_args().project_root); store = readonly_store(root)
    originals, metadata, anomalies = store.load(strict=True); assert not anomalies
    refs = ['decision-stock-session-calendar-20260927', 'e-stock-session-calendar-20260927']
    expected = ['18c5cfbf2df82e5bc8d8b9f78cb861c9a2e68bbbd3e2d2cd9af7c7a3efc3e527', 'e4d1b106b95fa2a3e0f56c08c34966b1eb6ad4854a895dd0c0cc9da743acfdbb']
    for ref, sha in zip(refs, expected): assert digest(canonical(originals[ref])) == sha
    bundle_hashes = lambda: {str(p.relative_to(store.root)): digest(p.read_bytes()) for p in sorted((store.root / 'bundles').rglob('*')) if p.is_file()}
    before_files = bundle_hashes(); at = now_iso(); before_projection = digest(canonical(project(store, at)))
    with tempfile.TemporaryDirectory(prefix='calendar-archive-engineering-') as temporary:
        work = Path(temporary); archive = work / 'engineering.zip'
        manifest = export_backup(store, archive, refs); assert inspect_backup(archive)['archive_id'] == manifest['archive_id']
        receipt = restore_backup(archive, work / 'restored')
        for ref in refs: assert (work / 'restored/records' / (ref + '.json')).read_bytes() == canonical(originals[ref])
        for item in originals[refs[0]]['feedback_dispositions']:
            for key in ('feedback_ref', 'source_review_ref', 'existing_successor_round_id'): assert item[key] in manifest['record_refs']
        for entry in manifest['files']:
            raw = (work / 'restored' / entry['path']).read_bytes(); assert digest(raw) == entry['sha256'] and len(raw) == entry['bytes']
        archive_result = {'archive_sha256': manifest['archive_sha256'], 'archive_id': manifest['archive_id'], 'records': len(manifest['record_refs']), 'files_verified': receipt['files_verified'], 'original_bytes_exact': True, 'nested_feedback_targets_in_existing_semantic_closure': True}
    inspected = []
    inventory = json.loads((root / 'docs/archive-inventory-20260927-v7.json').read_text())
    for item in inventory['archives']:
        candidates = [root / '.local/archives' / item['name'], root / '.local/receipts' / item['name']]
        path = next(p for p in candidates if p.exists() and digest(p.read_bytes()) == item['sha256'])
        value = inspect_backup(path); assert digest(path.read_bytes()) == item['sha256']
        inspected.append(dict(item, files=len(value['files']), inspection='PASS'))
    after, after_meta, anomalies = store.load(strict=True); assert not anomalies
    assert all(canonical(after[k]) == canonical(v) and after_meta[k] == metadata[k] for k, v in originals.items())
    assert bundle_hashes() == before_files
    assert digest(canonical(project(store, at))) == before_projection
    result = {'observed_at': at, 'scope': 'LOCAL_TEMPORARY_ENGINEERING_ONLY_NOT_NATIVE_ARCHIVE_COMPLETION',
        'original_sha256': dict(zip(refs, expected)), 'temporary_export_inspect_restore': archive_result,
        'existing_archives': inspected, 'old_archives_passed': len(inspected),
        'prior_originals_unchanged': len(originals), 'bundle_files_unchanged': len(before_files),
        'bundle_file_map_sha256': digest(canonical(before_files)), 'projection_and_graph_unchanged_sha256': before_projection,
        'omitted_fields_still_omitted': {ref: sorted(set(originals[ref]) - set(public_record(originals[ref]))) for ref in refs},
        'production_written': False, 'archive_retained': False, 'remote_uploaded': False, 'natural_or_economic_acceptance_upgraded': False,
        'scientific_reproduction': 'NOT_RUN', 'full_market_data_backup': False}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == '__main__': main()
