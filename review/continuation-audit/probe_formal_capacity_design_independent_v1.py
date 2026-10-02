"""Design-only check: hash/ledger reconciliation, no evaluator or Store imports."""
import argparse,ast,hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--candidate-root',required=True);p.add_argument('--project-root',required=True);a=p.parse_args();c=Path(a.candidate_root);main=Path(a.project_root)
h=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
manifest=c/'docs/formal-capacity-design-v1-candidate.json'
assert h(manifest)=='33b5797abee5f7a9d052a95a258ec569940376fa7c0bfd2f1643254e9afd424c'
m=json.loads(manifest.read_text())
for group in ['delivery_files','engineering_receipts']:
 assert all(h(c/n)==v for n,v in m[group].items())
for group in ['baseline_publishing_source_map','old16_source_sha256','formal19_source_sha256']:
 assert all(h(main/n)==v for n,v in m[group].items())
result=json.loads(subprocess.check_output([sys.executable,str(c/'tests/probe_formal_capacity_design.py')],cwd=c))
assert result==json.loads((c/'review/continuation-audit/formal-capacity-design-experiment.json').read_text())
trace=json.loads((c/'review/continuation-audit/formal-resource-real-diagnosis.json').read_text())
own={r['batch_id']:r['counters']['current_encoded_bytes']+r['counters']['old_encoded_bytes'] for r in trace['history_contexts']}
assert sum(own.values())==130760540
assert 130760540-128000000==2760540
# This independently calculates the symbolic stated sequence. Economic is never eligible.
def account(slots):
 cache=[];total=0;events=[]
 for domain,key,cost in [('PUBLIC','A',50),('PUBLIC','B',40),('PUBLIC','A',50),('ECONOMIC','A',50)]:
  eligible=domain=='PUBLIC';hit=eligible and key in cache;total+=1 if hit else cost
  if eligible and not hit:
   if len(cache)==slots:cache.pop(0)
   cache.append(key)
  events.append((domain,hit,total))
 return total,events
assert account(2)[0]==141 and account(1)[0]==190
# Execute only the candidate's standalone arithmetic ledger, extracted unchanged.
tree=ast.parse((c/'tests/probe_formal_capacity_design.py').read_text())
ledger=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='ledger')
namespace={};exec(compile(ast.Module(body=[ledger],type_ignores=[]),'candidate-symbolic-ledger','exec'),namespace)
economic=namespace['ledger']([('ECONOMIC:A',50),('ECONOMIC:A',50)],75,2)
assert economic[0]==51 and economic[1] is True
# No byte-saving claim is valid when all old charges are retained.
assert sum([50,40,50,50])>150
spec=importlib.util.spec_from_file_location('guard',main/'scripts/public_guard.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g);g.ROOT=c
paths=list(m['delivery_files'])+list(m['engineering_receipts'])+['docs/formal-capacity-design-v1-candidate.json'];assert not g.check_paths(paths)
print(json.dumps({'scope':'DESIGN_ONLY_NO_EVALUATOR_STORE_OR_MARKET_EXECUTION','manifest_verified':True,'all_bound_delivery_and_evidence_verified':True,'baseline_source_unchanged':True,'author_symbolic_output_exactly_reproduced':True,'independent_symbolic_public_only_cache_totals':{'resident':141,'evicted':190,'unchanged_old':190},'counterexample':{'sequence':[['ECONOMIC:A',50],['ECONOMIC:A',50]],'cap':75,'slots':2,'candidate_result':economic,'required_charge':100,'required_admission':False,'finding':'ECONOMIC_DOMAIN_INCORRECTLY_ELIGIBLE_FOR_REUSE'},'historical_own_bytes':own,'old_global_excess_bytes':2760540,'candidate_public_guard_files':len(paths),'candidate_public_guard_failures':[],'old_shadow_equivalence_proved':False,'real_complete_key_reuse_proved':False,'implementation_authorized':False},indent=2))
