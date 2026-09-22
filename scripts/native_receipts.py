#!/usr/bin/env python3
"""Read only known official automation config files; never edit scheduler state."""
import datetime
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TASKS = {'discovery':'research-tree-lab','research':'research-tree-lab-2',
         'review':'research-tree-lab-3','publish':'research-tree-lab-4'}
FIELDS = ('id','kind','name','prompt','status','rrule','model','reasoning_effort',
          'execution_environment','cwds','created_at','updated_at')

def read_installed():
    installation=json.loads((ROOT/'.local/installation.json').read_text())
    code_root=Path(installation['code_root']).resolve()
    receipts=[]
    for role, task_id in TASKS.items():
        path=Path.home()/'.codex/automations'/task_id/'automation.toml'
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
                      source_timezone='Asia/Tokyo',actual_timezone='Asia/Shanghai',
                      timezone_observation='host timezone; no explicit per-task zone field exposed',
                      native_next_run_at=None,next_run_observation='NOT_EXPOSED_BY_MANAGEMENT_TOOL')
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
    local.write_text(json.dumps({'observed_at':now,'readback_method':'official tool plus read-only named automation.toml files; no internal database','tasks':tasks},ensure_ascii=False,indent=2)+'\n')
    public=[]
    for t in tasks:
        public.append({k:t[k] for k in ('logical_key','name','status','model','reasoning_effort','source_timezone','actual_timezone','native_next_run_at')})
        public[-1].update(registered=True,natural_run=t.get('natural_run','WAITING_NATURAL_OUTCOME'),
                          manual_trial=t.get('manual_trial','PENDING'),
                          permission_enforcement='WEAK_ISOLATION_POLICY_AND_PROGRAM_ADMISSION')
    (ROOT/'config/native_task_status.json').write_text(json.dumps({'schema_version':'1.0','observed_at':now,'tasks':public},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([{'role':x['logical_key'],'id':x['id'],'status':x['status']} for x in tasks]))

if __name__=='__main__':main()
