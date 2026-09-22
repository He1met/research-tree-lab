"""SYNTHETIC receipt-path attacks only; never read or write production evidence."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "public_fields_v2_helper", Path(__file__).with_name("verify_public_fields_v2.py"))
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class PublicFieldsV2HelperSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-receipt-boundary-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "candidate"
        self.receipts = self.root / "tests/receipts"
        self.receipts.mkdir(parents=True)
        self.outside = self.base / "outside"
        self.outside.mkdir()
        root_patch = patch.object(helper, "ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        self.result = {"state": "SYNTHETIC_TEST_ONLY", "old_public_records_unchanged": 0,
                       "new_public_records_exact": 0, "former_failures_now_exact": 0, "cases": []}
        self.args = ["--code-root", str(self.base / "never-read-installed-root")]

    def invoke(self, receipt, effect=None):
        verify_patch = patch.object(helper, "verify", side_effect=effect) if effect else patch.object(
            helper, "verify", return_value=self.result)
        with verify_patch as verify, contextlib.redirect_stdout(io.StringIO()) as stdout:
            helper.main(self.args + ["--receipt", str(receipt)])
        return verify, stdout.getvalue()

    def rejected_before_verify(self, receipt):
        with patch.object(helper, "verify") as verify, contextlib.redirect_stdout(io.StringIO()) as stdout:
            with self.assertRaises((OSError, ValueError)):
                helper.main(self.args + ["--receipt", str(receipt)])
            verify.assert_not_called()
            self.assertEqual(stdout.getvalue(), "")

    def test_relative_and_absolute_receipts_are_reserved_before_verify(self):
        for receipt in (Path("tests/receipts/relative.json"), self.receipts / "absolute.json"):
            target = self.root / receipt if not receipt.is_absolute() else receipt
            def check(_):
                self.assertEqual(target.read_bytes(), b"")
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)
                return self.result
            verify, stdout = self.invoke(receipt, check)
            verify.assert_called_once()
            self.assertEqual(json.loads(target.read_bytes()), self.result)
            self.assertEqual(json.loads(stdout)["state"], "SYNTHETIC_TEST_ONLY")

    def test_outside_and_traversal_paths_are_rejected_before_verify(self):
        for receipt in (self.outside / "new.json", "new.json", "tests/elsewhere/new.json",
                        "tests/receipts/../new.json", self.receipts / "../new.json",
                        self.receipts):
            self.rejected_before_verify(receipt)
        self.assertEqual(list(self.outside.iterdir()), [])

    def test_receipts_allowed_root_symlink_cannot_move_boundary(self):
        self.receipts.rmdir()
        self.receipts.symlink_to(self.outside, target_is_directory=True)
        self.rejected_before_verify("tests/receipts/new.json")
        self.rejected_before_verify(self.receipts / "new.json")
        self.assertEqual(list(self.outside.iterdir()), [])

    def test_tests_parent_symlink_is_rejected(self):
        self.receipts.rmdir()
        self.receipts.parent.rmdir()
        (self.outside / "receipts").mkdir()
        self.receipts.parent.symlink_to(self.outside, target_is_directory=True)
        self.rejected_before_verify("tests/receipts/new.json")
        self.assertEqual(list((self.outside / "receipts").iterdir()), [])

    def test_nested_parent_and_leaf_symlinks_are_rejected(self):
        (self.receipts / "nested").symlink_to(self.outside, target_is_directory=True)
        self.rejected_before_verify(self.receipts / "nested/new.json")
        target = self.outside / "existing.json"
        target.write_bytes(b"OUTSIDE_UNCHANGED")
        (self.receipts / "alias.json").symlink_to(target)
        self.rejected_before_verify(self.receipts / "alias.json")
        (self.receipts / "dangling.json").symlink_to(self.outside / "absent.json")
        self.rejected_before_verify(self.receipts / "dangling.json")
        self.assertEqual(target.read_bytes(), b"OUTSIDE_UNCHANGED")
        self.assertFalse((self.outside / "absent.json").exists())

    def test_existing_regular_and_hardlinked_files_are_preserved(self):
        target = self.receipts / "existing.json"
        target.write_bytes(b"EXISTING_RECEIPT")
        self.rejected_before_verify(target)
        source = self.outside / "source.json"
        source.write_bytes(b"OUTSIDE_SOURCE")
        alias = self.receipts / "hardlink.json"
        os.link(source, alias)
        self.rejected_before_verify(alias)
        self.assertEqual(target.read_bytes(), b"EXISTING_RECEIPT")
        self.assertEqual(source.read_bytes(), b"OUTSIDE_SOURCE")

    def test_competing_creator_at_exclusive_open_is_preserved(self):
        target = self.receipts / "race.json"
        original_open = helper.os.open
        def raced(path, flags, *args, **kwargs):
            if path == target.name and flags & os.O_EXCL:
                target.write_bytes(b"COMPETING_CREATOR")
            return original_open(path, flags, *args, **kwargs)
        with patch.object(helper.os, "open", side_effect=raced):
            self.rejected_before_verify(target)
        self.assertEqual(target.read_bytes(), b"COMPETING_CREATOR")

    def test_parent_replacement_after_open_cannot_redirect_creation(self):
        held = self.root / "held-receipts"
        target = self.receipts / "new.json"
        original_open = helper.os.open
        def raced(path, flags, *args, **kwargs):
            if path == target.name and flags & os.O_EXCL:
                self.receipts.rename(held)
                self.receipts.symlink_to(self.outside, target_is_directory=True)
            return original_open(path, flags, *args, **kwargs)
        with patch.object(helper.os, "open", side_effect=raced):
            self.invoke(target)
        self.assertFalse((self.outside / target.name).exists())
        self.assertEqual(json.loads((held / target.name).read_bytes()), self.result)

    def test_parent_replacement_during_verify_cannot_redirect_write(self):
        held = self.root / "held-receipts"
        target = self.receipts / "new.json"
        outside = self.outside / target.name
        outside.write_bytes(b"OUTSIDE_UNCHANGED")
        def replace(_):
            self.receipts.rename(held)
            self.receipts.symlink_to(self.outside, target_is_directory=True)
            return self.result
        self.invoke(target, replace)
        self.assertEqual(outside.read_bytes(), b"OUTSIDE_UNCHANGED")
        self.assertEqual(json.loads((held / target.name).read_bytes()), self.result)

    def test_leaf_replacement_during_verify_cannot_redirect_write(self):
        target = self.receipts / "new.json"
        held = self.receipts / "reserved-inode.json"
        outside = self.outside / "source.json"
        outside.write_bytes(b"OUTSIDE_UNCHANGED")
        def replace(_):
            target.rename(held)
            target.symlink_to(outside)
            return self.result
        self.invoke(target, replace)
        self.assertEqual(outside.read_bytes(), b"OUTSIDE_UNCHANGED")
        self.assertEqual(json.loads(held.read_bytes()), self.result)
        self.assertTrue(target.is_symlink())

    def test_failed_verification_leaves_empty_reservation_and_no_success_output(self):
        target = self.receipts / "new.json"
        with patch.object(helper, "verify", side_effect=ValueError("SYNTHETIC_FAILURE")):
            with contextlib.redirect_stdout(io.StringIO()) as stdout, self.assertRaises(ValueError):
                helper.main(self.args + ["--receipt", str(target)])
        self.assertEqual(target.read_bytes(), b"")
        self.assertEqual(stdout.getvalue(), "")

    def test_public_scan_failure_leaves_no_success_receipt(self):
        self.result["unexpected"] = "/" + "Users/fixture/private"
        target = self.receipts / "new.json"
        with patch.object(helper, "verify", return_value=self.result):
            with contextlib.redirect_stdout(io.StringIO()) as stdout, self.assertRaisesRegex(ValueError, "PRIVATE_LOCAL_PATH"):
                helper.main(self.args + ["--receipt", str(target)])
        self.assertEqual(target.read_bytes(), b"")
        self.assertEqual(stdout.getvalue(), "")

    def test_malformed_verifier_result_cannot_leave_a_success_receipt(self):
        target = self.receipts / "new.json"
        with patch.object(helper, "verify", return_value={"state": "SYNTHETIC_TEST_ONLY"}):
            with contextlib.redirect_stdout(io.StringIO()) as stdout, self.assertRaises(KeyError):
                helper.main(self.args + ["--receipt", str(target)])
        self.assertEqual(target.read_bytes(), b"")
        self.assertEqual(stdout.getvalue(), "")

    def test_write_flush_failure_clears_only_owned_inode(self):
        target = self.receipts / "new.json"
        held = self.receipts / "held.json"
        outside = self.outside / "source.json"
        outside.write_bytes(b"OUTSIDE_UNCHANGED")
        def replace(_):
            target.rename(held)
            target.symlink_to(outside)
            return self.result
        with patch.object(helper, "verify", side_effect=replace), patch.object(
                helper.os, "fsync", side_effect=OSError("SYNTHETIC_FSYNC_FAILURE")):
            with contextlib.redirect_stdout(io.StringIO()) as stdout, self.assertRaises(OSError):
                helper.main(self.args + ["--receipt", str(target)])
        self.assertEqual(held.read_bytes(), b"")
        self.assertEqual(outside.read_bytes(), b"OUTSIDE_UNCHANGED")
        self.assertTrue(target.is_symlink())
        self.assertEqual(stdout.getvalue(), "")

    def test_short_write_leaves_no_success_receipt(self):
        target = self.receipts / "new.json"
        original_reservation = helper.new_receipt
        class ShortWriter:
            def __init__(self, output):
                self.output = output
            def write(self, data):
                return self.output.write(data[:3])
            def fileno(self):
                return self.output.fileno()
        @contextlib.contextmanager
        def short_reservation(path):
            with original_reservation(path) as output:
                yield ShortWriter(output)
        with patch.object(helper, "verify", return_value=self.result), patch.object(
                helper, "new_receipt", side_effect=short_reservation):
            with contextlib.redirect_stdout(io.StringIO()) as stdout, self.assertRaisesRegex(OSError, "Incomplete receipt"):
                helper.main(self.args + ["--receipt", str(target)])
        self.assertEqual(target.read_bytes(), b"")
        self.assertEqual(stdout.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
