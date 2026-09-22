"""Independent publication HTTP contract matrix; no network, Git or browser."""
import importlib.util
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from researchlib import Store,publish_snapshot
from researchlib.common import canonical,digest,now_iso
from test_storage_contracts import round_record,T0
spec=importlib.util.spec_from_file_location('readback_matrix',ROOT/'scripts/verify_publication.py')
readback=importlib.util.module_from_spec(spec);spec.loader.exec_module(readback)


def one_case(case):
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);store=Store(root,clock=lambda:T0)
        store.commit_bundle('base','research',[round_record()])
        pointer=publish_snapshot(store,root/'site/data',T0)
        (root/'site/assets').mkdir()
        (root/'site/index.html').write_text('<div id="root"></div><script src="./assets/test.js"></script><link href="./assets/test.css">')
        (root/'site/assets/test.js').write_text('/* fixture only */')
        (root/'site/assets/test.css').write_text('/* fixture only */')
        base='https://public-fixture.example/project/'
        (root/'.local/installation.json').write_bytes(canonical({'planned_pages_url':base}))
        remote={p.relative_to(root/'site').as_posix():p.read_bytes() for p in (root/'site').rglob('*') if p.is_file()}
        if case=='wrong_pointer':
            latest=json.loads(remote['data/latest.json']);latest['catalog_url']='snapshots/wrong/catalog.json';remote['data/latest.json']=canonical(latest)
        elif case=='wrong_asset':remote['assets/test.js']=b'changed script fixture'
        elif case=='wrong_shell':remote['index.html']=b'<div id="root">changed shell</div>'
        elif case=='wrong_object':
            object_path=next(k for k in remote if k.startswith('data/objects/'));remote[object_path]=b'{}'
        elif case=='wrong_cutoff':
            latest=json.loads(remote['data/latest.json']);latest['as_of']='2026-01-02T00:00:00Z';remote['data/latest.json']=canonical(latest)
        elif case=='local_false_identity':
            directory=root/'site/data/snapshots'/pointer['snapshot_id']
            catalog=json.loads((directory/'catalog.json').read_text());catalog['round_count']=999;raw=canonical(catalog)
            (directory/'catalog.json').write_bytes(raw)
            manifest=json.loads((directory/'manifest.json').read_text());entry=next(e for e in manifest['files'] if e['path']=='catalog.json');entry.update(sha256=digest(raw),bytes=len(raw));(directory/'manifest.json').write_bytes(canonical(manifest))
        calls=[]
        class Response:
            status=200;headers={}
            def __init__(self,url):
                path=url.removeprefix(base);calls.append(path);self.url='https://different-fixture.example/' if case=='foreign_redirect' else url;self.raw=remote[path]
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return self.raw[:n]
        rejected=False;reason=None
        with patch.object(readback,'ROOT',root),patch.object(readback,'urlopen',side_effect=lambda req,timeout:Response(req.full_url)),patch.object(sys,'argv',['verify_publication.py']),redirect_stdout(io.StringIO()):
            try:readback.main()
            except (ValueError,RuntimeError) as exc:rejected=True;reason=str(exc)
        expected_rejection=case!='success'
        passed=rejected==expected_rejection and (bool(calls) if case=='success' else True)
        if case=='local_false_identity':passed=passed and not calls
        if case=='success':passed=passed and {'assets/test.js','assets/test.css'}.issubset(set(calls))
        return {'rejected':rejected,'reason':reason,'mock_request_count':len(calls),'passed':passed}


def main():
    cases={name:one_case(name) for name in ('success','local_false_identity','wrong_pointer','wrong_asset','wrong_shell','wrong_object','wrong_cutoff','foreign_redirect')}
    result={'schema_version':'1.0','checked_at':now_iso(),'test_only':True,'production_writes':False,'network':'MOCKED_NO_HTTP_REQUESTS','cases':cases,'all_passed':all(c['passed'] for c in cases.values()),'not_actual_publication_evidence':True}
    Path(__file__).with_name('publication-readback-matrix.json').write_bytes(canonical(result))
    print(json.dumps(result,indent=2))
    if not result['all_passed']:raise SystemExit(1)

if __name__=='__main__':main()
