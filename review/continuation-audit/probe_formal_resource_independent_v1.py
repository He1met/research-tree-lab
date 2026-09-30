"""Independent fixed-bound telemetry and delivery review; no business output."""
import argparse,importlib.util,json,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--candidate-root',required=True);p.add_argument('--project-root',required=True);a=p.parse_args()
c=Path(a.candidate_root);main=Path(a.project_root);sys.path[:0]=[str(c),str(c/'scripts')]
from researchlib.common import digest,canonical
from researchlib import formal_review as fr
from diagnose_formal_resources import observe_replay,resource_counters
manifest=c/'docs/formal-resource-v1-candidate.json'
assert digest(manifest.read_bytes())=='7d105a04d282ebcfdac5482a7cc71b424edb30195bfe91d93a42f9db6f3349aa'
m=json.loads(manifest.read_text())
for group in ['source_sha256','delivery_files','engineering_receipts']:
 assert all(digest((c/n).read_bytes())==h for n,h in m[group].items())
for group in ['old16_source_sha256','formal19_source_sha256']:
 assert all(digest((main/n).read_bytes())==h for n,h in m[group].items())
saved=(fr._check_time,fr._reserve,fr.legacy._reserve,fr._prepare_bundle)
def fake(store,batch,inputs,at,ctx):
 ctx['encoded_bytes']=127999998;ctx['old_context']=fr._context();ctx['old_context']['encoded_bytes']=1;ctx['public_replay_bytes']=1
 fr._check_time(ctx)
 ctx['public_replay_bytes']+=1
 fr._check_time(ctx)
 raise AssertionError('budget was bypassed')
fr._prepare_bundle=fake
try:
 result=observe_replay(None,'independent-exact-bound',{},None)
 assert result['outcome']=='COMBINED_HISTORY_RESOURCE_LIMIT_EXCEEDED'
 assert result['final_counters']['combined_bytes']==128000001
 assert fr._prepare_bundle is fake
finally:fr._prepare_bundle=saved[3]
assert saved==(fr._check_time,fr._reserve,fr.legacy._reserve,fr._prepare_bundle)
def broken(*args):raise RuntimeError('INDEPENDENT_UNEXPECTED_FAILURE')
fr._prepare_bundle=broken
try:
 try:observe_replay(None,'independent-unexpected',{},None);raise AssertionError('unexpected exception hidden')
 except RuntimeError as e:assert str(e)=='INDEPENDENT_UNEXPECTED_FAILURE'
finally:fr._prepare_bundle=saved[3]
assert saved==(fr._check_time,fr._reserve,fr.legacy._reserve,fr._prepare_bundle)
actual=json.loads((main/'review/continuation-audit/formal-resource-independent-v1-replay-20260930.json').read_text())
assert actual['outcome']=='COMBINED_HISTORY_RESOURCE_LIMIT_EXCEEDED'
assert actual['final_counters']['combined_bytes']==130760540
assert not actual['outbox_written'] and not actual['store_committed']
rows={r['context']:r for r in actual['history_contexts']};assert len(rows)==4
for ident,row in rows.items():
 direct=[r for r in rows.values() if r['parent_context']==ident]
 amount=sum(r['counters']['combined_bytes'] for r in direct)
 assert row['counters']['public_replay_bytes']==amount==row['direct_child_combined_bytes']
 assert row['counters']['combined_bytes']==sum(row['counters'][k] for k in ['current_encoded_bytes','old_encoded_bytes','public_replay_bytes'])
assert all(r['bytes_exceeded'] and not r['nodes_exceeded'] for r in actual['checks_rejected'])
assert sorted(r['batch_id'] for r in rows.values())==['batch-daily-review-20260927-v1','batch-daily-review-20260928-v1','batch-daily-review-20260929-v1','batch-daily-review-20260930-v1']
spec=importlib.util.spec_from_file_location('guard',c/'scripts/public_guard.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
paths=list(m['delivery_files'])+list(m['engineering_receipts'])+['docs/formal-resource-v1-candidate.json'];assert not g.check_paths(paths)
print(json.dumps({'scope':'INDEPENDENT_ENGINEERING_ONLY','exact_boundary_and_global_restoration':'PASS','unexpected_exception_propagation_and_restoration':'PASS','independently_reconciled_history_contexts':len(rows),'real_replay_sha256':digest((main/'review/continuation-audit/formal-resource-independent-v1-replay-20260930.json').read_bytes()),'final_counters':actual['final_counters'],'byte_rejections':len(actual['checks_rejected']),'complete_source_and_delivery_verified':True,'old16_formal19_unchanged':True,'public_guard_files':len(paths),'public_guard_failures':[],'capacity_bottleneck_fixed':False},indent=2))
