"""Independent synthetic probes; never read installed native task config files."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from unittest.mock import patch


def main():
    source = Path(sys.argv[1]).resolve() / 'scripts/native_receipts.py'
    spec = importlib.util.spec_from_file_location('audited_native_timezone', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    at = datetime(2026, 9, 23, tzinfo=timezone.utc)
    cases = []

    def check(name, condition):
        assert condition, name
        cases.append({'case': name, 'result': 'PASS'})

    def tzif(offset):
        chars = b'TST\0'
        return (b'TZif\0' + b'\0' * 15
                + struct.pack('>6l', 0, 0, 0, 0, 1, len(chars))
                + struct.pack('>lbb', offset, 0, 0) + chars)

    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
        root = Path(temporary)
        file = root / 'localtime'
        file.write_bytes(tzif(-12600))
        with patch.dict(os.environ, {'TZ': 'Asia/Tokyo'}):
            observation = module.observe_host_timezone(file, at)
        check('raw_negative_half_hour_offset_ignores_TZ', observation['utc_offset'] == '-03:30')
        check('unlabelled_tzif_does_not_infer_IANA', observation['state'] == 'OFFSET_ONLY' and observation['timezone'] is None)
        check('raw_hash_binds_actual_bytes', observation['tzif_sha256'] == hashlib.sha256(file.read_bytes()).hexdigest())
        named = root / 'zoneinfo/Asia/Shanghai'
        named.parent.mkdir(parents=True)
        named.write_bytes(tzif(32400))
        file.unlink()
        file.symlink_to(named)
        observation = module.observe_host_timezone(file, at)
        check('name_offset_disagreement_fails_closed', observation['state'] == 'OFFSET_ONLY' and observation['timezone'] is None and observation['reason'] == 'NAMED_ZONE_AND_LOCALTIME_OFFSET_DISAGREE')
        named.unlink()
        check('broken_localtime_link_unknown', module.observe_host_timezone(file, at)['state'] == 'UNKNOWN')
        try:
            module.observe_host_timezone(file, datetime(2026, 9, 23))
        except ValueError:
            check('naive_observation_time_rejected', True)
        else:
            raise AssertionError('naive observation accepted')
        host = module.observe_host_timezone(file, at)
        report = module.timezone_report({'source_timezone': 'Europe/Berlin', 'actual_timezone': 'Asia/Shanghai'}, host)
        check('unknown_host_not_no_drift', report['host_timezone_drift'] == 'UNKNOWN')
        check('native_scheduler_timezone_and_effect_remain_unknown', report['native_task_timezone'] is None and report['schedule_timezone_effect'] == 'UNKNOWN_NOT_INFERRED_FROM_HOST')
        check('source_zone_from_declared_history', report['source_timezone'] == 'Europe/Berlin' and report['source_timezone_observation'] == 'INSTALLATION_DECLARATION')
        check('no_schedule_action', report['schedule_action'] == 'NONE_OBSERVATION_ONLY')
    live_host = module.observe_host_timezone()
    check('live_host_observation_has_timestamp_and_raw_identity', bool(live_host['observed_at']) and (live_host['state'] == 'UNKNOWN' or bool(live_host['tzif_sha256'])))
    result = {'scope': 'timezone observation only; synthetic boundary probes plus read-only host TZif observation',
              'decision': 'PASS_SCOPED_TIMEZONE_MAINTENANCE',
              'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'cases': cases, 'host_observation': live_host,
              'native_task_files_read': False, 'native_task_mutation': False,
              'native_schedule_timezone_verified': False,
              'future_natural_run_verified': False}
    output = Path(__file__).with_name('timezone-independent-receipt.json')
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'decision': result['decision'], 'cases': len(cases), 'source_sha256': result['source_sha256']}))


if __name__ == '__main__':
    main()
