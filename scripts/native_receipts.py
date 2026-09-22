#!/usr/bin/env python3
"""Read known task configs plus observable host timezone, never repair schedules.

Field boundary: source/installation timezone values are historical installation
claims. Host name/offset come only from the current OS localtime TZif (not TZ or
the process default). No supported task field exposes the scheduler timezone or
next trigger; both remain unknown even when host and installation agree.
"""
import datetime
import hashlib
import io
import json
from pathlib import Path
import re
import struct
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
TASKS = {'discovery':'research-tree-lab','research':'research-tree-lab-2',
         'review':'research-tree-lab-3','publish':'research-tree-lab-4'}
FIELDS = ('id','kind','name','prompt','status','rrule','model','reasoning_effort',
          'execution_environment','cwds','created_at','updated_at')

def _utc_offset_text(seconds):
    sign='+' if seconds >= 0 else '-'
    hours, remainder=divmod(abs(seconds),3600)
    minutes, trailing=divmod(remainder,60)
    return f'{sign}{hours:02d}:{minutes:02d}' + (f':{trailing:02d}' if trailing else '')

def observe_host_timezone(localtime_path=None, observed_at=None):
    """Read the host setting without sudo, mutations, TZ overrides or shell.

    A regular localtime file may reveal an offset but no IANA name. That partial
    result never becomes a named zone merely because its offset matches one.
    """
    at=observed_at or datetime.datetime.now(datetime.timezone.utc)
    if at.tzinfo is None:
        raise ValueError('Timezone observation requires an aware timestamp')
    at=at.astimezone(datetime.timezone.utc)
    result={'observed_at':at.isoformat(),'state':'UNKNOWN','timezone':None,
            'utc_offset_seconds':None,'utc_offset':None,'abbreviation':None,
            'source':'OS_LOCALTIME_TZIF','tzif_sha256':None,'reason':None}
    path=Path(localtime_path) if localtime_path is not None else Path('/etc/localtime')
    try:
        resolved=path.resolve(strict=True)
        raw=resolved.read_bytes()
        zone=ZoneInfo.from_file(io.BytesIO(raw))
        local=at.astimezone(zone)
        offset=local.utcoffset()
        if offset is None:
            result['reason']='LOCALTIME_OFFSET_UNAVAILABLE'
            return result
        seconds=int(offset.total_seconds())
        result.update(state='OFFSET_ONLY',utc_offset_seconds=seconds,
                      utc_offset=_utc_offset_text(seconds),abbreviation=local.tzname(),
                      tzif_sha256=hashlib.sha256(raw).hexdigest(),
                      reason='IANA_NAME_NOT_OBSERVABLE')
        # macOS and typical Unix installations resolve to .../zoneinfo/<IANA>.
        # Do not use an abbreviation such as CST as a timezone identity.
        indices=[i for i,part in enumerate(resolved.parts) if part=='zoneinfo']
        if indices:
            name='/'.join(resolved.parts[indices[-1]+1:])
            try:
                named=ZoneInfo(name)
                if at.astimezone(named).utcoffset()==offset:
                    result.update(state='OBSERVED',timezone=name,reason=None)
                else:
                    result['reason']='NAMED_ZONE_AND_LOCALTIME_OFFSET_DISAGREE'
            except (ZoneInfoNotFoundError,ValueError):
                result['reason']='IANA_NAME_NOT_VALIDATED'
    except (OSError,ValueError,EOFError,struct.error):
        result['reason']='LOCALTIME_UNAVAILABLE_OR_INVALID'
    return result

def timezone_report(installation, host):
    """Compare observable host state to the installation claim; never reschedule."""
    baseline=installation.get('actual_timezone')
    source=installation.get('source_timezone')
    current=host.get('timezone')
    seconds=host.get('utc_offset_seconds')
    expected_offset=None
    baseline_valid=False
    try:
        if baseline:
            at=datetime.datetime.fromisoformat(host['observed_at'])
            if at.tzinfo is None:
                raise ValueError('Observation timestamp has no timezone')
            delta=at.astimezone(ZoneInfo(baseline)).utcoffset()
            expected_offset=int(delta.total_seconds()) if delta is not None else None
            baseline_valid=delta is not None
    except (KeyError,TypeError,ValueError,ZoneInfoNotFoundError):
        pass
    offset_changed=(seconds!=expected_offset) if seconds is not None and expected_offset is not None else None
    name_changed=(current!=baseline) if current is not None and baseline is not None else None
    if not baseline:
        drift='INSTALLATION_BASELINE_UNKNOWN'
    elif not baseline_valid:
        drift='INSTALLATION_BASELINE_UNVERIFIED'
    elif name_changed is True:
        drift='HOST_TIMEZONE_NAME_CHANGED'
    elif offset_changed is True:
        drift='HOST_UTC_OFFSET_DIFFERS_FROM_INSTALLATION_ZONE'
    elif name_changed is False and offset_changed is False:
        drift='NO_HOST_DRIFT_OBSERVED'
    else:
        drift='UNKNOWN'
    return {'source_timezone':source,
            'source_timezone_observation':'INSTALLATION_DECLARATION' if source else 'UNKNOWN',
            # Kept for existing consumers, with explicit scope to avoid treating
            # this host reading as the native scheduler's own timezone setting.
            'actual_timezone':current,'actual_timezone_scope':'HOST_ONLY_NOT_NATIVE_TASK_TIMEZONE',
            'host_timezone_observation':host,
            'installation_actual_timezone':baseline,
            'installation_timezone_observation':'HISTORICAL_DECLARATION_NOT_REVERIFIED',
            'installation_timezone_name_validated':baseline_valid,
            'installation_zone_offset_at_observation_seconds':expected_offset,
            'host_timezone_name_changed':name_changed,'host_utc_offset_changed':offset_changed,
            'host_timezone_drift':drift,
            'native_task_timezone':None,'native_task_timezone_observation':'NOT_EXPOSED_BY_SUPPORTED_TASK_FIELDS',
            'timezone_observation':'HOST_AND_INSTALLATION_ONLY; NATIVE_TASK_TIMEZONE_UNKNOWN',
            'schedule_timezone_effect':'UNKNOWN_NOT_INFERRED_FROM_HOST',
            'schedule_action':'NONE_OBSERVATION_ONLY'}

def read_installed(project_root=None,automations_root=None,host_observation=None):
    root=Path(project_root) if project_root is not None else ROOT
    automation_directory=Path(automations_root) if automations_root is not None else Path.home()/'.codex/automations'
    installation=json.loads((root/'.local/installation.json').read_text())
    code_root=Path(installation['code_root']).resolve()
    host=host_observation if host_observation is not None else observe_host_timezone()
    timezone=timezone_report(installation,host)
    receipts=[]
    for role, task_id in TASKS.items():
        path=automation_directory/task_id/'automation.toml'
        raw=path.read_text(); record={}
        for field in FIELDS:
            match=re.search(r'^'+field+r' = (.*)$',raw,re.M)
            if match:
                record[field]=json.loads(match[1])
        if record.get('id')!=task_id or [str(code_root)]!=record.get('cwds'):
            raise ValueError('Native task identity/project drift; do not repair frequency automatically')
        project=re.search(r'project_id = "([^"]+)"',raw)
        if not project or project[1]!=installation['project_id']:
            raise ValueError('Native project binding mismatch')
        record.update(logical_key=role,project_id=project[1],config_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                      prompt_sha256=hashlib.sha256(record['prompt'].encode()).hexdigest(),
                      native_next_run_at=None,next_run_observation='NOT_EXPOSED_BY_MANAGEMENT_TOOL')
        record.update(timezone)
        receipts.append(record)
    return receipts

def main():
    tasks=read_installed(); now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    local=ROOT/'.local/receipts/native-tasks.json'
    old=json.loads(local.read_text()) if local.exists() else {'tasks':[]}
    earlier={t['logical_key']:t for t in old['tasks']}
    for task in tasks:
        for field in ('manual_trial','natural_run','permission_enforcement','trial_evidence'):
            if field in earlier.get(task['logical_key'],{}):task[field]=earlier[task['logical_key']][field]
    local.write_text(json.dumps({'observed_at':now,'readback_method':'read-only named automation.toml files plus host localtime TZif; no scheduler execution or internal database','tasks':tasks},ensure_ascii=False,indent=2)+'\n')
    public=[]
    for t in tasks:
        public.append({k:t[k] for k in ('logical_key','name','status','model','reasoning_effort','source_timezone',
                      'source_timezone_observation','actual_timezone','actual_timezone_scope',
                      'host_timezone_observation','installation_actual_timezone','installation_timezone_observation',
                      'installation_timezone_name_validated',
                      'installation_zone_offset_at_observation_seconds','host_timezone_name_changed',
                      'host_utc_offset_changed','host_timezone_drift','native_task_timezone',
                      'native_task_timezone_observation','schedule_timezone_effect','schedule_action','native_next_run_at')})
        public[-1].update(registered=True,natural_run=t.get('natural_run','WAITING_NATURAL_OUTCOME'),
                          manual_trial=t.get('manual_trial','PENDING'),
                          permission_enforcement='WEAK_ISOLATION_POLICY_AND_PROGRAM_ADMISSION')
    (ROOT/'config/native_task_status.json').write_text(json.dumps({'schema_version':'1.0','observed_at':now,'tasks':public},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([{'role':x['logical_key'],'id':x['id'],'status':x['status']} for x in tasks]))

if __name__=='__main__':main()
