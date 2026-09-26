"""Independent real-original read-only / disposable archive attack audit."""
import argparse, copy, json, sys, tempfile, zipfile
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--candidate-root',required=True);p.add_argument('--project-root',required=True);a=p.parse_args()
candidate=Path(a.candidate_root);main=Path(a.project_root)
sys.path.insert(0,str(candidate))
from researchlib.archive import export_backup,inspect_backup,restore_backup,_exact_public_export_policy
from researchlib.common import canonical,digest,now_iso
from researchlib.funding_review import readonly_store
from researchlib.public import public_record
from researchlib.snapshot import project

manifest_path=candidate/'docs/archive-compatibility-v1-candidate.json'
assert digest(manifest_path.read_bytes())=='c0e4b65b253a4f6d0ec221f10a6443a64126cd5b23f5373b000f7b4b00b47a6b'
frozen=json.loads(manifest_path.read_text())
assert all(digest((candidate/n).read_bytes())==h for n,h in frozen['delivery_files'].items())
store=readonly_store(main);records,metadata,anomalies=store.load(strict=True);assert not anomalies
ref='decision-numeraire-boundary-20260927';original=records[ref]
assert digest(canonical(original))=='6b5ec5278a5d5bdc3945d483035a4d6c9e1f9ffad8871bf71933ce109aa7c64c'
at=now_iso();graph=digest(canonical(project(store,at)));original_hashes={k:digest(canonical(v)) for k,v in records.items()}
answers=[]
mutations={
 'new_id':lambda r:r.update(decision_id='different-reviewed-id'),
 'changed_question':lambda r:r['future_child'].update(question='Unreviewed but innocuous question'),
 'nested_secret':lambda r:r['future_child'].update(question='Bearer '+'Q'*32),
 'nested_raw':lambda r:r['future_child'].update(question={'raw':[137.25]}),
 'unknown_field':lambda r:r.update(unapproved={'row':[137.25]}),
 'child_extra':lambda r:r['future_child'].update(row=[137.25]),
 'executed_child':lambda r:r['future_child'].update(state='EXECUTED'),
 'created_child':lambda r:r.update(new_feedback_successor_created=True),
 'numeric_false':lambda r:r.update(new_feedback_successor_created=0),
 'trial_active':lambda r:r.update(trial_state='ACTIVE'),
 'limited_exports':lambda r:r['disclosure'].update(export_fields=['decision_id']),
 'empty_exports':lambda r:r['disclosure'].update(export_fields=[]),
 'widen_exports':lambda r:r['disclosure'].update(export_fields=list(r)),
 'caller_hash':lambda r:r.update(approved_original_sha256=digest(canonical(r))),
 'local_only':lambda r:r['disclosure'].update(visibility='LOCAL_ONLY'),
 'synthetic':lambda r:r.update(synthetic=True),
}
with tempfile.TemporaryDirectory(prefix='independent-archive-compat-') as temp:
 root=Path(temp);good=root/'good.zip';receipt=export_backup(store,good,[ref]);inspect_backup(good)
 recovered=restore_backup(good,root/'restored');assert (root/'restored'/'records'/(ref+'.json')).read_bytes()==canonical(original)
 with zipfile.ZipFile(good) as z: pristine={n:z.read(n) for n in z.namelist()}
 for name,mutate in mutations.items():
  altered=copy.deepcopy(original);mutate(altered)
  # Directly spoof a Store's canonical hash metadata as an untrusted producer
  # might. The gate must use its own fixed source identity.
  class SpoofedStore:
   def load(self,strict=True):
    rr=copy.deepcopy(records);mm=copy.deepcopy(metadata);rr[ref]=altered
    mm[ref]['record_hash']=digest(canonical(altered));return rr,mm,[]
   def __getattr__(self,key):return getattr(store,key)
  try: export_backup(SpoofedStore(),root/(name+'-export.zip'),[ref]);outcome='UNEXPECTED_ACCEPTANCE'
  except Exception as exc: outcome='REJECTED:'+str(exc)
  assert outcome.startswith('REJECTED:');answers.append({'probe':name,'stage':'export_spoofed_metadata','outcome':outcome})
  files=copy.deepcopy(pristine);target='records/'+ref+'.json';files[target]=canonical(altered)
  manifest=json.loads(files['ARCHIVE_MANIFEST.json'])
  for e in manifest['files']:
   if e['path']==target:e.update(sha256=digest(files[target]),bytes=len(files[target]))
  for e in manifest['records']:
   if e['record_ref']==ref:e['original_record_hash']=digest(files[target])
  manifest.pop('archive_id');manifest['archive_id']=digest(canonical(manifest));files['ARCHIVE_MANIFEST.json']=canonical(manifest)
  bad=root/(name+'-rehash.zip')
  with zipfile.ZipFile(bad,'w') as z:
   for n,raw in files.items():z.writestr(n,raw)
  try:inspect_backup(bad);outcome='UNEXPECTED_ACCEPTANCE'
  except Exception as exc:outcome='REJECTED:'+str(exc)
  assert outcome.startswith('REJECTED:');answers.append({'probe':name,'stage':'inspector_all_hashes_recomputed','outcome':outcome})
 result={'real_closure_records':len(receipt['record_refs']),'real_closure_files':recovered['files_verified'],
  'exact_original_restored':True,'archive_sha256':receipt['archive_sha256'],'temporary_only':True}
old=[]
for path in sorted((main/'.local/archives').glob('*.zip'))+[main/'.local/receipts/public-research-v1.zip']:
 before=digest(path.read_bytes());m=inspect_backup(path);assert before==digest(path.read_bytes())
 old.append({'name':path.name,'sha256':before,'records':len(m['record_refs']),'unchanged':True})
again,_,anomalies=store.load(strict=True);assert not anomalies
assert all(digest(canonical(again[k]))==v for k,v in original_hashes.items())
assert digest(canonical(project(store,at)))==graph
assert set(original)-set(public_record(original))=={'future_child','new_feedback_successor_created','trial_state'}
assert all(digest((candidate/n).read_bytes())==h for n,h in frozen['delivery_files'].items())
print(json.dumps({'scope':'INDEPENDENT_TEMPORARY_ARCHIVE_SECURITY_AND_COMPATIBILITY_ONLY','original_records_unchanged':len(original_hashes),
 'graph_unchanged':True,'projection_unchanged':True,'exact_restore':result,'attacks':answers,'old_archives':old},indent=2))
