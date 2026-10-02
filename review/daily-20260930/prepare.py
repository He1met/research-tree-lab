from pathlib import Path
from copy import deepcopy
import json, subprocess
from researchlib.funding_review import readonly_store
from researchlib.formal_review import prepare_outbox,method_material
from researchlib.common import canonical,digest,utc
root=Path.cwd(); out=root/'review/daily-20260930'
s=readonly_store(root); records,metadata,anomalies=s.load(strict=True)
frozen=json.loads((out/'frozen-batch.json').read_text()); at=frozen['frozen_at']
visible={k:v for k,v in records.items() if utc(v['available_at'])<=utc(at) and utc(metadata[k]['committed_at'])<=utc(at)}
class Snapshot:
 clock=staticmethod(lambda:at)
 def load(self,strict=True):return deepcopy(visible),{k:deepcopy(metadata[k]) for k in visible},[]
 def __getattr__(self,name):return getattr(s,name)
config=json.loads((root/'.local/installation.json').read_text()); method,_=method_material(at)
assert method['method_code_sha256']==config['formal_method_code_sha256']
for name,sha in method['source_sha256'].items():
 raw=subprocess.check_output(['git','show',config['release_ref']+':'+name]);assert digest(raw)==sha,name
(out/'installation-frozen.json').write_bytes(canonical(config))
manifest=json.loads((root/'.local/review-outbox/daily-20260927/input-manifest.json').read_text())
path=prepare_outbox(Snapshot(),frozen['batch_id'],manifest,'daily-20260930/formal-bundle.json','2026-09-24T00:06:00Z')
b=json.loads(path.read_text()); batch=b['records'][0]
assert batch['plan_refs']==frozen['plan_refs']
for new,old in zip(batch['items'],frozen['items']):
 for key in ['plan_ref','plan_hash','previous_review_ref','opening_state_hash']:assert new[key]==old[key]
print(str(path)); print(json.dumps(batch['coverage']))
for r in b['records']:
 if r['record_type']=='review':print(r['plan_ref'],r['evaluation_stage'],r['coverage']['reason_codes'])
