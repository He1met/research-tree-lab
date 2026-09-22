"""The publication gate must reject private material even when misnamed."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('public_guard', Path(__file__).resolve().parents[1] / 'scripts/public_guard.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

class PublicGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = guard.ROOT
        guard.ROOT = Path(self.tmp.name)

    def tearDown(self):
        guard.ROOT = self.old
        self.tmp.cleanup()

    def write(self, name, data):
        p = guard.ROOT/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return name

    def test_private_and_path_escape_rejected(self):
        for name in ['handoff/chat.md', '.local/installation.json', '../outside.json', 'research/private/raw.json']:
            self.assertTrue(guard.check_paths([name]), name)

    def test_nested_archive_magic_rejected(self):
        name=self.write('research/result.json', b'PK\x03\x04concealed archive')
        self.assertTrue(guard.check_paths([name]))

    def test_private_path_and_secret_not_printed(self):
        value=b'ghp_'+b'a'*36
        name=self.write('docs/leak.md', value)
        result=guard.check_paths([name])
        self.assertEqual(result, [(name,'SECRET_OR_PRIVATE_REFERENCE')])
        self.assertNotIn(value.decode(), str(result))

    def test_unapproved_symlink_rejected(self):
        p=guard.ROOT/'README.md'; p.symlink_to('/nonexistent-private-target')
        self.assertTrue(guard.check_paths(['README.md']))

    def test_symlink_parent_rejected(self):
        (guard.ROOT/'records').mkdir()
        with tempfile.TemporaryDirectory() as outside:
            Path(outside,'safe.json').write_text('{}')
            (guard.ROOT/'records'/'escape').symlink_to(outside,target_is_directory=True)
            self.assertEqual(guard.check_paths(['records/escape/safe.json']), [('records/escape/safe.json','SYMLINK_PARENT_REJECTED')])

    def test_owned_safe_summary_allowed(self):
        name=self.write('research/result.json', b'{"purpose":"own factual calculation","net_profit":null}')
        self.assertFalse(guard.check_paths([name]))

if __name__=='__main__': unittest.main()
