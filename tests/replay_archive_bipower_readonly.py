"""Read known project originals and existing archives; write only temporary engineering outputs."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import shutil

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
    request = json.loads((root / 'docs/bipower-archive-maintenance-request-20260929-v2.json').read_text())
    refs = request['archive_pending']
    expected = ['0c87d67ecdf6be4c7cec60eac167e9b429c3d63b8595e5b85ae3ba3a48e47aa9', '83e9f039ed69cb7ee4de1b857028c7ec5c2b774dcd57431bbcb554fdae0d7c3f', '297e84fca931db648b0dc9380709ddc804e990b07a787fe7d9f811140ed4a445', 'b81bca611320803237868b26b3d0f96d562d6a32f22363a2f7ad6aaaa0860f82', 'e9411e4f2f6b468118e449d7c7ff0cf8455f49a2cfc6227dacc1c012ce64cca1', '4c3bcf8ee67e465cce5d0b87bcbd06b56a088db19b7ff9798897014ada03a137']
    for ref, sha in zip(refs, expected): assert digest(canonical(originals[ref])) == sha
    bundle_hashes = lambda: {str(p.relative_to(store.root)): digest(p.read_bytes()) for p in sorted((store.root / 'bundles').rglob('*')) if p.is_file()}
    before_files = bundle_hashes(); at = now_iso(); before_projection = digest(canonical(project(store, at)))
    with tempfile.TemporaryDirectory(prefix='bipower-archive-engineering-') as temporary:
        work = Path(temporary); archive = work / 'engineering.zip'
        copied_root = work / 'project'
        shutil.copytree(store.root / 'bundles', copied_root / '.local/store/bundles')
        copied = readonly_store(copied_root)
        copied_records, copied_metadata, copied_anomalies = copied.load(strict=True)
        assert not copied_anomalies and copied_records == originals and copied_metadata == metadata
        manifest = export_backup(copied, archive, refs); assert inspect_backup(archive)['archive_id'] == manifest['archive_id']
        receipt = restore_backup(archive, work / 'restored')
        for ref in refs: assert (work / 'restored/records' / (ref + '.json')).read_bytes() == canonical(originals[ref])
        restored_original = json.loads((work / 'restored/records' / (refs[0] + '.json')).read_text())
        assert restored_original['findings']['actual_net'] is None
        assert restored_original['status'] == 'PROPOSED_NOT_STARTED'
        decision_manifest = export_backup(copied, work / 'decision.zip', ['decision-bipower-closeout-20260929'])
        assert 'r-bipower-20260929' in decision_manifest['record_refs']
        inspect_backup(work / 'decision.zip')
        attachment_map = {}
        for relative in request['attachment_gaps']:
            raw = (work / 'restored/evidence' / relative).read_bytes()
            assert raw == (store.root / 'bundles' / relative).read_bytes()
            attachment_map[relative] = {'sha256': digest(raw), 'bytes': len(raw)}
        for entry in manifest['files']:
            raw = (work / 'restored' / entry['path']).read_bytes(); assert digest(raw) == entry['sha256'] and len(raw) == entry['bytes']
        archive_result = {'archive_sha256': manifest['archive_sha256'], 'archive_id': manifest['archive_id'], 'records': len(manifest['record_refs']), 'files_verified': receipt['files_verified'], 'original_bytes_exact': True, 'copied_store_records': len(copied_records), 'actual_net_restored': restored_original['findings']['actual_net'], 'proposal_status_restored': restored_original['status'], 'decision_only_related_round_included': True, 'gap_attachments_verified': attachment_map}
    inspected = []
    inventory = json.loads((root / 'docs/archive-inventory-20260928-v3.json').read_text())
    inventory['archives'].append({'name': 'public-research-increment-20260929-v2.zip', 'sha256': '2bcfe10146eb6683bfd9aba58e9cd20ae8609d7c50865f2ba82118cf6142f0cb'})
    for item in inventory['archives']:
        candidates = [root / '.local/archives' / item['name'], root / '.local/receipts' / item['name']]
        path = next(p for p in candidates if p.exists() and digest(p.read_bytes()) == item['sha256'])
        value = inspect_backup(path); assert digest(path.read_bytes()) == item['sha256']
        inspected.append(dict(item, files=len(value['files']), inspection='PASS'))
    bootstrap = root / '.local/receipts/public-records-bootstrap-v1.zip'
    bootstrap_sha = digest(bootstrap.read_bytes()); inspect_backup(bootstrap)
    assert digest(bootstrap.read_bytes()) == bootstrap_sha
    after, after_meta, anomalies = store.load(strict=True); assert not anomalies
    assert all(canonical(after[k]) == canonical(v) and after_meta[k] == metadata[k] for k, v in originals.items())
    assert bundle_hashes() == before_files
    assert digest(canonical(project(store, at))) == before_projection
    result = {'observed_at': at, 'scope': 'LOCAL_TEMPORARY_ENGINEERING_ONLY_NOT_NATIVE_ARCHIVE_COMPLETION',
        'original_sha256': dict(zip(refs, expected)), 'baseline_direct_rejections': request['direct_policy_rejections'], 'temporary_export_inspect_restore': archive_result,
        'existing_archives': inspected, 'old_archives_passed': len(inspected), 'additional_bootstrap_archive': {'name': bootstrap.name, 'sha256': bootstrap_sha, 'inspection': 'PASS'},
        'prior_originals_unchanged': len(originals), 'bundle_files_unchanged': len(before_files),
        'bundle_file_map_sha256': digest(canonical(before_files)), 'projection_and_graph_unchanged_sha256': before_projection,
        'omitted_fields_still_omitted': {ref: sorted(set(originals[ref]) - set(public_record(originals[ref]))) for ref in refs},
        'production_written': False, 'archive_retained': False, 'remote_uploaded': False, 'natural_or_economic_acceptance_upgraded': False,
        'scientific_reproduction': 'NOT_RUN', 'full_market_data_backup': False}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == '__main__': main()
