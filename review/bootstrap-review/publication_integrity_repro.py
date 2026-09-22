"""Corrupt-but-matching local/remote snapshot test; all HTTP is mocked."""
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
spec=importlib.util.spec_from_file_location('readback_review',ROOT/'scripts/verify_publication.py')
readback=importlib.util.module_from_spec(spec);spec.loader.exec_module(readback)


def main():
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);store=Store(root,clock=lambda:T0)
        store.commit_bundle('base','research',[round_record()])
        pointer=publish_snapshot(store,root/'site/data',T0)
        index=b'<div id="root"></div>'
        (root/'site/index.html').write_bytes(index)
        base='https://public-fixture.example/project/'
        (root/'.local/installation.json').write_bytes(canonical({'planned_pages_url':base}))
        directory=root/'site/data/snapshots'/pointer['snapshot_id']
        catalog=json.loads((directory/'catalog.json').read_text());catalog['round_count']=999
        raw=canonical(catalog);(directory/'catalog.json').write_bytes(raw)
        manifest=json.loads((directory/'manifest.json').read_text())
        entry=next(e for e in manifest['files'] if e['path']=='catalog.json')
        entry.update(sha256=digest(raw),bytes=len(raw))
        (directory/'manifest.json').write_bytes(canonical(manifest))
        class Response:
            status=200;headers={}
            def __init__(self,url):
                self.url=url;self.raw=(root/'site'/url.removeprefix(base)).read_bytes()
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return self.raw[:n]
        rejected=False;reason=None
        with patch.object(readback,'ROOT',root),patch.object(readback,'urlopen',side_effect=lambda req,timeout:Response(req.full_url)),patch.object(sys,'argv',['verify_publication.py']),redirect_stdout(io.StringIO()):
            try:readback.main()
            except (ValueError,RuntimeError) as exc:rejected=True;reason=str(exc)
    result={'schema_version':'1.0','checked_at':now_iso(),'test_only':True,'network':'MOCKED_NO_HTTP_REQUESTS','production_writes':False,'scenario':'Local and remote catalog changed with matching manifest object hash but old content-addressed snapshot ID','expected':'REJECT','observed':'REJECTED' if rejected else 'PUBLIC_SNAPSHOT_HTTP_VERIFIED','reason':reason,'passed':rejected}
    Path(__file__).with_name('publication-integrity-recheck.json').write_bytes(canonical(result))
    print(result)
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
