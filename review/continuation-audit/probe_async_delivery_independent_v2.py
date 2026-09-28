"""Read-only exact evidence-redaction audit; no functional work is replayed."""
import argparse, copy, hashlib, importlib.util, json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--candidate-root',required=True);p.add_argument('--previous-root',required=True);p.add_argument('--project-root',required=True);a=p.parse_args()
c,old,project=map(Path,(a.candidate_root,a.previous_root,a.project_root))
h=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
manifest='docs/async-delivery-v2-candidate.json';previous='docs/async-delivery-v1-candidate.json'
assert h(c/manifest)=='ae670056da2b7791b7de652c6db37fa28c3f99af43e9e8832d31ea2193cd9af1'
assert h(old/previous)=='cdd788de69f001fc8fe3e02e12150b7a288cc53aebad1b6167a6f85e5435b529'
m=json.loads((c/manifest).read_text());v1=json.loads((old/previous).read_text())
for root,freeze in [(c,m),(old,v1)]:
 for group in ['complete_source_sha256','delivery_files','engineering_receipts']:
  assert all(h(root/n)==sha for n,sha in freeze[group].items())
assert m['complete_source_sha256']==v1['complete_source_sha256']
assert all(h(project/n)==sha for g in ['old16_source_sha256','formal19_source_sha256'] for n,sha in m[g].items())
receipt='tests/receipts/async-delivery-v1/browser-58-results.json'
redaction=json.loads((c/'tests/receipts/async-delivery-v2/evidence-redaction.json').read_text())
before=json.loads((old/receipt).read_text());after=json.loads((c/receipt).read_text());normalized=copy.deepcopy(before)
assert len(redaction['changed_json_values'])==8
for item in redaction['changed_json_values']:
 node=normalized
 for key in item['json_path'][:-1]:node=node[key]
 key=item['json_path'][-1];assert node[key]!=item['replacement'];node[key]=item['replacement']
assert normalized==after and before['stats']==after['stats']
old_paths=set(v1['delivery_files'])|set(v1['engineering_receipts'])
new_paths=set(m['delivery_files'])|set(m['engineering_receipts'])
assert old_paths<=new_paths
changed=[n for n in sorted(old_paths) if h(old/n)!=h(c/n)]
assert changed==[receipt]
assert new_paths-old_paths=={'tests/receipts/async-delivery-v2/evidence-redaction.json'}
spec=importlib.util.spec_from_file_location('guard',c/'scripts/public_guard.py');guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
paths=sorted(new_paths|{manifest});assert not guard.check_paths(paths)
dependencies=[
 'review/continuation-audit/async-delivery-independent-v1-20260928.json',
 'review/continuation-audit/probe_async_delivery_independent_v1.py',
 'review/continuation-audit/async-delivery-independent-v1-execution-20260928.json',
 'review/continuation-audit/probe_async_browser_independent_v1.mjs',
 'review/continuation-audit/async-browser-independent-v1-execution-20260928.json',
 'review/continuation-audit/async-independent-playwright.config.mjs']
guard.ROOT=project;assert not guard.check_paths(dependencies)
print(json.dumps({'scope':'INDEPENDENT_REDACTION_ONLY_REVIEW','candidate_manifest_sha256':h(c/manifest),
 'source_map_identical':True,'v1_frozen_files_unchanged':True,'changed_json_values':redaction['changed_json_values'],
 'browser_stats_unchanged':before['stats'],'only_changed_existing_delivery':changed,'all_candidate_public_guard_files':len(paths),
 'candidate_public_guard_failures':[],'reused_independent_evidence':{n:h(project/n) for n in dependencies},
 'reused_evidence_public_guard_failures':[],'functional_tests_rerun':False},indent=2))
