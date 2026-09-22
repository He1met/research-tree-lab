"""Check release identity in an isolated copy; never builds or uses Git."""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'scripts'))
from researchlib.common import canonical, now_iso
spec = importlib.util.spec_from_file_location('isolated_publisher', ROOT/'scripts/publish.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


def main():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        for path in ('researchlib','scripts','web/src','.agents/skills','config','web/public'):
            (root/path).mkdir(parents=True,exist_ok=True)
        (root/'web/src/main.tsx').write_text('export const fixture = true;\n')
        (root/'web/index.html').write_text('<div>original fixture</div>\n')
        (root/'web/public/static.txt').write_text('original fixture\n')
        with patch.object(publisher,'ROOT',root):
            initial = publisher.source_hash()
            (root/'web/index.html').write_text('<div>changed executable entry template</div>\n')
            index_changed = publisher.source_hash() != initial
            after_index = publisher.source_hash()
            (root/'web/public/static.txt').write_text('changed static public asset\n')
            public_changed = publisher.source_hash() != after_index
    result={'test_only':True,'checked_at':now_iso(),'production_writes':False,'git_used':False,'build_used':False,'index_change_changes_approved_hash':index_changed,'public_asset_change_changes_approved_hash':public_changed,'passed':index_changed and public_changed}
    Path(__file__).with_name('publisher-hash-recheck.json').write_bytes(canonical(result))
    print(json.dumps(result,indent=2))
    if not result['passed']:
        raise SystemExit(1)

if __name__=='__main__':
    main()
