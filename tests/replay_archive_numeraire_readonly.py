"""Read real original bytes; export/restore only into a disposable temp directory.

No production mutation, publication, task dispatch or remote archive action.
Print an engineering receipt; this is not a native archive completion receipt.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from researchlib.archive import export_backup, inspect_backup, restore_backup
from researchlib.common import canonical, digest, now_iso
from researchlib.funding_review import readonly_store
from researchlib.public import public_record
from researchlib.snapshot import project


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root',required=True)
    args=parser.parse_args()
    store=readonly_store(args.project_root)
    records,metadata,anomalies=store.load(strict=True)
    assert not anomalies
    ref='decision-numeraire-boundary-20260927'
    original=records[ref]
    expected='6b5ec5278a5d5bdc3945d483035a4d6c9e1f9ffad8871bf71933ce109aa7c64c'
    assert digest(canonical(original))==expected
    as_of=now_iso()
    before=digest(canonical(project(store,as_of)))
    projection=public_record(original)
    assert set(original)-set(projection)=={'future_child','new_feedback_successor_created','trial_state'}
    with tempfile.TemporaryDirectory(prefix='archive-numeraire-readonly-') as temporary:
        root=Path(temporary);archive=root/'engineering-only.zip'
        manifest=export_backup(store,archive,[ref])
        inspected=inspect_backup(archive)
        receipt=restore_backup(archive,root/'restore')
        assert inspected['archive_id']==manifest['archive_id']
        target=root/'restore'/'records'/(ref+'.json')
        assert target.read_bytes()==canonical(original)
        verified=0
        for entry in manifest['files']:
            raw=(root/'restore'/entry['path']).read_bytes()
            assert digest(raw)==entry['sha256'] and len(raw)==entry['bytes'];verified+=1
        after_records,after_meta,after_anomalies=store.load(strict=True)
        assert not after_anomalies
        assert all(digest(canonical(after_records[k]))==digest(canonical(v)) and after_meta[k]==metadata[k] for k,v in records.items())
        assert digest(canonical(project(store,as_of)))==before
        result={'observed_at':as_of,'scope':'REAL_ORIGINAL_READONLY_TEMPORARY_ENGINEERING_EXPORT_RESTORE',
            'record_ref':ref,'original_sha256':expected,'archive_id':manifest['archive_id'],
            'archive_sha256':manifest['archive_sha256'],'record_count':len(manifest['record_refs']),
            'files_verified':verified,'exact_original_bytes_restored':True,'prior_records_unchanged':len(records),
            'projection_and_graph_sha256_unchanged':before,'projection_still_omits_three_extensions':True,
            'compatibility_policy':'EXACT_NUMERAIRE_DECISION_METADATA_V1',
            'recovery_scientific_reproduction':receipt['scientific_reproduction'],
            'production_store_written':False,'remote_uploaded':False,'native_archive_completion':False,
            'archive_retained':False,'restore_retained':False,'economic_or_natural_acceptance_upgraded':False}
    print(json.dumps(result,sort_keys=True,indent=2))


if __name__=='__main__':main()
