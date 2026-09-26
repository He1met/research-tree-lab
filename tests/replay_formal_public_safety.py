"""Synthetic archive/snapshot regression; no production store or network access.

Compare the preserved failed candidate with current candidate source bytes.
All stores, intentionally unsafe exports and captured source copies are temporary.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def worker(root):
    sys.path[:0] = [str(root), str(root/'tests')]
    from test_formal_review import FormalReviewTests
    from test_conditional_review import PRIVATE_NUMBER
    from researchlib import conditional_review as old
    from researchlib import formal_review as current
    from researchlib.archive import export_backup
    from researchlib.snapshot import publish_snapshot
    import zipfile
    answers=[]
    for attack in ('renamed_layout_unknown_method','coverage_nested_extra'):
        case=FormalReviewTests('test_real_decode_path_from_legacy_has_no_granted_business_capabilities')
        case.setUp()
        try:
            bundle=old.prepare_bundle(case.store,'attack-parent',case.inputs(),'2026-09-23T12:00:00Z')
            if attack=='renamed_layout_unknown_method':
                names={name:name.replace('SOURCE/','renamed-source/').replace('PRIVATE/','renamed-input/') for name in bundle['attachments']}
                bundle['attachments']={names[name]:value for name,value in bundle['attachments'].items()}
                exposed=next(name for name in bundle['attachments'] if name.startswith('renamed-input/'))
                for record in bundle['records']:
                    record['disclosure']=copy.deepcopy(record['disclosure'])
                    record['disclosure']['public_attachments']=['attachments/'+names[name[len('attachments/'):]] for name in record['disclosure']['public_attachments']]+['attachments/'+exposed]
                for record in case.reviews(bundle):record['evaluator_version']='UNKNOWN_METHOD'
            else:
                case.reviews(bundle)[0]['coverage']['raw_prices']={'nested':[PRIVATE_NUMBER]}
            case.commit(bundle);case.now='2026-09-23T19:00:00Z'
            before=set(case.store.load()[0])
            result={'attack':attack}
            try:
                output=current.prepare_bundle(case.store,'attack-child',case.inputs(),'2026-09-23T12:00:00Z')
            except Exception as exc:
                result.update(outcome='REJECTED_BEFORE_NEW_PUBLIC_ROOT',reason=str(exc),store_unchanged=before==set(case.store.load()[0]))
            else:
                case.commit(output)
                archive=case.root/'child.zip';export_backup(case.store,archive,record_refs=['attack-child'])
                with zipfile.ZipFile(archive) as z:
                    result['single_root_archive_contains_canary']=any(PRIVATE_NUMBER.encode() in z.read(n) for n in z.namelist())
                public=case.root/'published';publish_snapshot(case.store,public,case.now)
                result['snapshot_contains_canary']=any(PRIVATE_NUMBER.encode() in p.read_bytes() for p in public.rglob('*') if p.is_file())
                result['outcome']='UNSAFE_NEW_PUBLIC_ROOT_RETURNED'
            answers.append(result)
        finally:
            case.doCleanups()
    return {'formal_review_sha256':sha((root/'researchlib/formal_review.py').read_bytes()),'probes':answers}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker')
    parser.add_argument('--preserved-archive')
    args=parser.parse_args()
    if args.worker:
        print(json.dumps(worker(Path(args.worker)),sort_keys=True));return
    root=Path(__file__).resolve().parents[1]
    archive=Path(args.preserved_archive)
    if sha(archive.read_bytes())!='93ea2b74ab4265f8ad94a5801b274d4776cec536a52708e7a5cc265619383620':
        raise RuntimeError('PRESERVED_FAILED_CANDIDATE_ARCHIVE_HASH_MISMATCH')
    outputs={}
    with tempfile.TemporaryDirectory(prefix='formal-public-safety-') as directory:
        for version in ('preserved_failed','repair_candidate'):
            target=Path(directory)/version;target.mkdir()
            for name in ('researchlib','scripts','tests/fixtures/waiting-d21'):
                shutil.copytree(root/name,target/name,ignore=shutil.ignore_patterns('__pycache__'))
            for name in ('tests/test_conditional_review.py','tests/test_formal_review.py','tests/test_formal_funding.py',
                         'research/bootstrap-v1/research_bundle.json','review/bootstrap-review/review_bundle.json'):
                path=target/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,path)
            if version=='preserved_failed':
                with tarfile.open(archive) as tar:
                    for member in tar.getmembers():
                        path=Path(member.name)
                        if not member.isfile() or path.is_absolute() or '..' in path.parts:
                            raise RuntimeError('UNEXPECTED_ARCHIVED_MEMBER')
                        destination=target/path;destination.parent.mkdir(parents=True,exist_ok=True)
                        destination.write_bytes(tar.extractfile(member).read())
            completed=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker',str(target)],check=True,capture_output=True,text=True)
            outputs[version]=json.loads(completed.stdout)
    print(json.dumps({'scope':'SYNTHETIC_SECURITY_REGRESSION_ONLY','preserved_archive_sha256':sha(archive.read_bytes()),'results':outputs},sort_keys=True,indent=2))


if __name__=='__main__':main()
