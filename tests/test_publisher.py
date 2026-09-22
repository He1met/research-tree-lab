"""Publication authorization gates must run before any external mutation."""
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
spec=importlib.util.spec_from_file_location('publisher',Path(__file__).resolve().parents[1]/'scripts/publish.py')
publisher=importlib.util.module_from_spec(spec);spec.loader.exec_module(publisher)

class PublisherGateTests(unittest.TestCase):
    def test_html_and_public_assets_invalidate_source_and_shell(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'web/public').mkdir(parents=True);(root/'web/src').mkdir()
            html=root/'web/index.html';asset=root/'web/public/static.txt'
            html.write_text('<div>first</div>');asset.write_text('first')
            with patch.object(publisher,'ROOT',root):
                before=(publisher.source_hash(),publisher.shell_hash())
                html.write_text('<div>second</div>')
                after=(publisher.source_hash(),publisher.shell_hash())
                self.assertNotEqual(before[0],after[0]);self.assertNotEqual(before[1],after[1])
                asset.write_text('second')
                final=(publisher.source_hash(),publisher.shell_hash())
                self.assertNotEqual(after[0],final[0]);self.assertNotEqual(after[1],final[1])

    def test_changed_source_stops_before_git_or_build(self):
        with patch.object(publisher,'read_json',return_value={'approved_source_sha256':'approved'}), patch.object(publisher,'source_hash',return_value='changed'), patch.object(publisher,'command') as command, patch.object(publisher,'build_shell') as build:
            with self.assertRaisesRegex(RuntimeError,'PUBLIC_CODE_NOT_APPROVED'):
                publisher.publish(SimpleNamespace(push=True,build=False))
            command.assert_not_called();build.assert_not_called()

    def test_foreign_remote_stops_before_build_or_push(self):
        cfg={'approved_source_sha256':'approved','allowed_remote':'https://github.com/example/authorized.git'}
        with patch.object(publisher,'read_json',return_value=cfg), patch.object(publisher,'source_hash',return_value='approved'), patch.object(publisher,'command',return_value='https://github.com/example/foreign.git') as command, patch.object(publisher,'build_shell') as build:
            with self.assertRaisesRegex(RuntimeError,'PUBLIC_REMOTE_MISMATCH'):
                publisher.publish(SimpleNamespace(push=True,build=False))
            command.assert_called_once_with(['git','remote','get-url','origin']);build.assert_not_called()

if __name__=='__main__':unittest.main()
