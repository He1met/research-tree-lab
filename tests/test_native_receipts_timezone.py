"""Synthetic timezone/config fixtures; never read or write installed task files."""
import datetime
import importlib.util
import json
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('native_receipts_timezone_under_test', Path(__file__).resolve().parents[1] / 'scripts/native_receipts.py')
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)
UTC = datetime.timezone.utc
AT = datetime.datetime(2026, 9, 23, 0, 0, tzinfo=UTC)


def tzif(offset, abbreviation='TST'):
    chars = abbreviation.encode() + b'\0'
    return (b'TZif\0' + b'\0' * 15 + struct.pack('>6l', 0, 0, 0, 0, 1, len(chars))
            + struct.pack('>lbb', offset, 0, 0) + chars)


class NativeTimezoneTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()

    def tearDown(self):
        self.temporary.cleanup()

    def observation(self, name, offset, at=AT):
        target = self.root / 'zoneinfo' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(tzif(offset))
        link = self.root / 'localtime'
        if link.is_symlink():
            link.unlink()
        link.symlink_to(target)
        return native.observe_host_timezone(link, at)

    def test_actual_tzif_name_and_offset_ignore_process_tz(self):
        with patch.dict(os.environ, {'TZ': 'UTC'}):
            host = self.observation('Asia/Shanghai', 28800)
        self.assertEqual(host['state'], 'OBSERVED')
        self.assertEqual(host['timezone'], 'Asia/Shanghai')
        self.assertEqual(host['utc_offset'], '+08:00')
        self.assertEqual(host['utc_offset_seconds'], 28800)
        self.assertIsNotNone(host['tzif_sha256'])

    def test_host_drift_is_reported_without_claiming_native_timezone(self):
        host = self.observation('Asia/Tokyo', 32400)
        report = native.timezone_report({'source_timezone': 'Europe/Berlin', 'actual_timezone': 'Asia/Shanghai'}, host)
        self.assertEqual(report['source_timezone'], 'Europe/Berlin')
        self.assertEqual(report['actual_timezone'], 'Asia/Tokyo')
        self.assertEqual(report['actual_timezone_scope'], 'HOST_ONLY_NOT_NATIVE_TASK_TIMEZONE')
        self.assertTrue(report['host_timezone_name_changed'])
        self.assertTrue(report['host_utc_offset_changed'])
        self.assertEqual(report['host_timezone_drift'], 'HOST_TIMEZONE_NAME_CHANGED')
        self.assertIsNone(report['native_task_timezone'])
        self.assertEqual(report['schedule_timezone_effect'], 'UNKNOWN_NOT_INFERRED_FROM_HOST')
        self.assertEqual(report['schedule_action'], 'NONE_OBSERVATION_ONLY')

    def test_same_offset_does_not_hide_changed_zone_name(self):
        host = self.observation('Asia/Singapore', 28800)
        report = native.timezone_report({'actual_timezone': 'Asia/Shanghai'}, host)
        self.assertTrue(report['host_timezone_name_changed'])
        self.assertFalse(report['host_utc_offset_changed'])
        self.assertEqual(report['host_timezone_drift'], 'HOST_TIMEZONE_NAME_CHANGED')

    def test_offset_only_or_unreadable_host_remains_unknown(self):
        file = self.root / 'regular-localtime'
        file.write_bytes(tzif(28800))
        host = native.observe_host_timezone(file, AT)
        self.assertEqual(host['state'], 'OFFSET_ONLY')
        self.assertIsNone(host['timezone'])
        report = native.timezone_report({'actual_timezone': 'Asia/Shanghai'}, host)
        self.assertEqual(report['host_timezone_drift'], 'UNKNOWN')
        self.assertIsNone(report['host_timezone_name_changed'])
        for raw in (b'not a TZif file', b'TZif\0'):
            file.write_bytes(raw)
            unknown = native.observe_host_timezone(file, AT)
            self.assertEqual(unknown['state'], 'UNKNOWN')
            self.assertIsNone(unknown['utc_offset_seconds'])
        absent = native.observe_host_timezone(self.root / 'missing', AT)
        self.assertEqual(absent['state'], 'UNKNOWN')
        report = native.timezone_report({}, absent)
        self.assertIsNone(report['source_timezone'])
        self.assertIsNone(report['actual_timezone'])
        self.assertEqual(report['host_timezone_drift'], 'INSTALLATION_BASELINE_UNKNOWN')

    def test_expected_offset_uses_observation_date_not_installation_season(self):
        for month, offset in ((1, -18000), (7, -14400)):
            host = self.observation('America/New_York', offset, datetime.datetime(2026, month, 1, tzinfo=UTC))
            report = native.timezone_report({'actual_timezone': 'America/New_York'}, host)
            self.assertEqual(report['installation_zone_offset_at_observation_seconds'], offset)
            self.assertEqual(report['host_timezone_drift'], 'NO_HOST_DRIFT_OBSERVED')
            self.assertIsNone(report['native_task_timezone'])

    def test_invalid_installation_name_never_becomes_a_verified_baseline(self):
        host = self.observation('Asia/Shanghai', 28800)
        report = native.timezone_report({'actual_timezone': 'Unrecognized/Fixture'}, host)
        self.assertEqual(report['host_timezone_drift'], 'INSTALLATION_BASELINE_UNVERIFIED')
        self.assertFalse(report['installation_timezone_name_validated'])
        self.assertIsNone(report['installation_zone_offset_at_observation_seconds'])

    def test_readback_preserves_user_schedule_model_state_and_all_task_bytes(self):
        (self.root / '.local').mkdir()
        installation = {'code_root': str(self.root), 'project_id': 'fixture-project',
                        'source_timezone': 'Europe/Berlin', 'actual_timezone': 'Asia/Shanghai'}
        installation_file = self.root / '.local/installation.json'
        installation_file.write_text(json.dumps(installation))
        automations = self.root / 'fixture-automations'
        originals = {}
        expected = {}
        for index, (role, task_id) in enumerate(native.TASKS.items()):
            fields = {'id': task_id, 'kind': 'cron', 'name': role, 'prompt': 'Fixture prompt',
                      'status': 'PAUSED', 'rrule': f'FREQ=WEEKLY;BYHOUR={index + 10};BYMINUTE=17',
                      'model': 'user-existing-model', 'reasoning_effort': 'medium',
                      'execution_environment': 'local', 'cwds': [str(self.root)], 'project_id': 'fixture-project'}
            file = automations / task_id / 'automation.toml'
            file.parent.mkdir(parents=True)
            file.write_text('\n'.join(k + ' = ' + json.dumps(v) for k, v in fields.items()) + '\n')
            originals[file] = file.read_bytes()
            expected[role] = fields
        installation_bytes = installation_file.read_bytes()
        rows = native.read_installed(self.root, automations, self.observation('Asia/Tokyo', 32400))
        self.assertEqual(len(rows), 4)
        for row in rows:
            for field in ('rrule', 'status', 'model', 'reasoning_effort', 'prompt'):
                self.assertEqual(row[field], expected[row['logical_key']][field])
            self.assertEqual(row['host_timezone_drift'], 'HOST_TIMEZONE_NAME_CHANGED')
            self.assertIsNone(row['native_next_run_at'])
            self.assertIsNone(row['native_task_timezone'])
        self.assertEqual(originals, {file: file.read_bytes() for file in originals})
        self.assertEqual(installation_bytes, installation_file.read_bytes())
        self.assertFalse((self.root / '.local/receipts').exists())


if __name__ == '__main__':
    unittest.main()
