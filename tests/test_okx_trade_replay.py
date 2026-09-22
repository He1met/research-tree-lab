"""Synthetic helper output-path safety cases; no real source access."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('trade_replay_helper', Path(__file__).with_name('replay_okx_trade_sample.py'))
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class ReplayReceiptSafetyTests(unittest.TestCase):
    def setUp(self):
        # Resolve the system temp prefix once; macOS /var may itself be a link.
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / 'source.zip'
        self.dataset = self.root / 'dataset.json'
        self.source.write_bytes(b'original source bytes')
        self.dataset.write_bytes(b'original dataset bytes')
        self.args = ['--source', str(self.source), '--dataset', str(self.dataset)]

    def reject_without_scan(self, output):
        before = (self.source.read_bytes(), self.dataset.read_bytes())
        with patch.object(helper, 'run') as run:
            with self.assertRaises((OSError, ValueError)):
                helper.main(self.args + ['--receipt', str(output)])
            run.assert_not_called()
        self.assertEqual(before, (self.source.read_bytes(), self.dataset.read_bytes()))

    def test_source_and_dataset_same_path_rejected(self):
        self.reject_without_scan(self.source)
        self.reject_without_scan(self.dataset)
        self.reject_without_scan(self.root / '.' / 'source.zip')

    def test_existing_regular_or_hardlinked_output_never_overwritten(self):
        existing = self.root / 'existing.json'
        existing.write_bytes(b'existing receipt')
        self.reject_without_scan(existing)
        self.assertEqual(existing.read_bytes(), b'existing receipt')
        alias = self.root / 'hardlink.json'
        os.link(self.source, alias)
        self.reject_without_scan(alias)
        self.assertEqual(alias.read_bytes(), b'original source bytes')

    def test_leaf_and_parent_symlinks_rejected(self):
        alias = self.root / 'alias.json'
        alias.symlink_to(self.source)
        self.reject_without_scan(alias)
        dangling = self.root / 'dangling.json'
        dangling.symlink_to(self.root / 'not-created.json')
        self.reject_without_scan(dangling)
        self.assertFalse((self.root / 'not-created.json').exists())
        alias_dir = self.root / 'linked-parent'
        alias_dir.symlink_to(self.root, target_is_directory=True)
        self.reject_without_scan(alias_dir / 'new.json')
        self.assertFalse((self.root / 'new.json').exists())

    def test_competing_creator_race_fails_exclusive_open(self):
        destination = self.root / 'race.json'
        original_open = os.open
        def raced(path, flags, *args, **kwargs):
            if path == destination.name and flags & os.O_EXCL:
                destination.write_bytes(b'competing creator')
            return original_open(path, flags, *args, **kwargs)
        with patch.object(helper.os, 'open', side_effect=raced):
            self.reject_without_scan(destination)
        self.assertEqual(destination.read_bytes(), b'competing creator')

    def test_replacement_after_reservation_cannot_redirect_writes(self):
        destination = self.root / 'new.json'
        held = self.root / 'reserved-inode.json'
        with helper.new_receipt(destination, self.source, self.dataset) as output:
            os.rename(destination, held)
            destination.symlink_to(self.source)
            output.write('new output only')
        self.assertEqual(self.source.read_bytes(), b'original source bytes')
        self.assertEqual(held.read_text(), 'new output only')
        self.assertTrue(destination.is_symlink())

    def test_parent_replacement_after_directory_open_cannot_redirect_creation(self):
        parent = self.root / 'out'
        parent.mkdir()
        held = self.root / 'held-directory'
        original_open = os.open
        def raced(path, flags, *args, **kwargs):
            if path == 'new.json' and flags & os.O_EXCL:
                os.rename(parent, held)
                parent.symlink_to(self.root, target_is_directory=True)
            return original_open(path, flags, *args, **kwargs)
        with patch.object(helper.os, 'open', side_effect=raced):
            with helper.new_receipt(parent / 'new.json', self.source, self.dataset) as output:
                output.write('held directory')
        self.assertFalse((self.root / 'new.json').exists())
        self.assertEqual((held / 'new.json').read_text(), 'held directory')

    def test_failed_scan_leaves_only_empty_new_reservation_no_success(self):
        destination = self.root / 'new.json'
        with patch.object(helper, 'run', side_effect=ValueError('synthetic scan failed')):
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                with self.assertRaises(ValueError):
                    helper.main(self.args + ['--receipt', str(destination)])
        self.assertEqual(destination.read_bytes(), b'')
        self.assertEqual(stdout.getvalue(), '')
        self.assertEqual(self.source.read_bytes(), b'original source bytes')
        self.assertEqual(self.dataset.read_bytes(), b'original dataset bytes')

    def test_new_output_is_held_before_scan_and_private(self):
        destination = self.root / 'new.json'
        def write(args, output):
            self.assertTrue(destination.exists())
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            output.write('{"synthetic_test":true}\n')
            return 0
        with patch.object(helper, 'run', side_effect=write):
            self.assertEqual(helper.main(self.args + ['--receipt', str(destination)]), 0)
        self.assertEqual(destination.read_text(), '{"synthetic_test":true}\n')


if __name__ == '__main__':
    unittest.main()
