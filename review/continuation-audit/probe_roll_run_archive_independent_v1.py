"""Independent temporary roll_run archive audit. Stable inputs are read-only."""
import argparse,copy,json,sys,tempfile,zipfile,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--candidate-root',required=True);p.add_argument('--project-root',required=True);a=p.parse_args()
c=Path(a.candidate_root);main=Path(a.project_root);sys.path.insert(0,str(c))
from researchlib.archive import export_backup,inspect_backup,restore_backup
from researchlib.funding_review import readonly_store
from researchlib.common import canonical,digest,now_iso
from researchlib.public import public_record
from researchlib.snapshot import project
manifest=c/'docs/roll-run-archive-v1-candidate.json'
assert digest(manifest.read_bytes())=='baab759902fe6bddc760fe1436d869ac3928c01274149d10688a82da1e6228ad'
freeze=json.loads(manifest.read_text())
for group in ['complete_source_sha256','delivery_files','engineering_receipts']:
 assert all(digest((c/n).read_bytes())==h for n,h in freeze[group].items())
store=readonly_store(main);records,metadata,anomalies=store.load(strict=True);assert not anomalies
refs=list(freeze['frozen_original_sha256'])
for ref in refs:assert digest(canonical(records[ref]))==freeze['frozen_original_sha256'][ref]
asof=now_iso();graph=digest(canonical(project(store,asof)));hashes={k:digest(canonical(v)) for k,v in records.items()}
bundle_hashes={str(p.relative_to(store.root)):digest(p.read_bytes()) for p in (store.root/'bundles').rglob('*') if p.is_file()}
results=[]
with tempfile.TemporaryDirectory(prefix='roll_run-independent-') as t:
 root=Path(t);archive=root/'good.zip'
 shutil.copytree(store.root/'bundles',root/'copy/.local/store/bundles')
 copied=readonly_store(root/'copy');assert copied.load(strict=True)==(records,metadata,[])
 m=export_backup(copied,archive,refs)
 restored=restore_backup(archive,root/'restored');assert inspect_backup(archive)['archive_id']==m['archive_id']
 assert json.loads((root/'restored/records'/(refs[0]+'.json')).read_text())['verification']['independent_audit'] is False
 for ref in refs:assert (root/'restored/records'/(ref+'.json')).read_bytes()==canonical(records[ref])
 with zipfile.ZipFile(archive) as z:base={n:z.read(n) for n in z.namelist()}
 for ref in refs:
  original=records[ref];mutations={
   'round':lambda r:r.update(round_id='r-boundary-sensitivity-20260923'),
   'caller_hash':lambda r:r.update(approved_sha256=digest(canonical(r))),
   'nested':lambda r:r.update(verification={'raw':[42.42]}),
   'secret':lambda r:r.update(verification={'payload':'Bearer '+'Q'*32}),
   'export_empty':lambda r:r['disclosure'].update(export_fields=[]),
   'export_all':lambda r:r['disclosure'].update(export_fields=list(r)),
   'local':lambda r:r['disclosure'].update(visibility='LOCAL_ONLY'),
   'license':lambda r:r['disclosure'].update(license='CC0-1.0'),
   'synthetic':lambda r:r.update(synthetic=True),
  }
  if original['record_type']=='run':
   mutations.update({
    'run_id':lambda r:r.update(run_id='run-other'),
    'attempt_id':lambda r:r.update(attempt_id='attempt-2'),
    'record_type':lambda r:r.update(record_type='evidence'),
    'audit_true':lambda r:r['verification'].update(independent_audit=True),
    'audit_zero':lambda r:r['verification'].update(independent_audit=0),
    'audit_string':lambda r:r['verification'].update(independent_audit='false'),
    'check_float':lambda r:r['verification'].update(synthetic_author_checks=13.0),
    'check_bool':lambda r:r['verification'].update(synthetic_author_checks=True),
    'check_string':lambda r:r['verification'].update(synthetic_author_checks='13'),
    'formula_fail':lambda r:r['verification'].update(alternate_formulas_and_pairs='FAIL'),
    'nested_private':lambda r:r['verification'].update(private={'secret':[42.42]}),
    'verification_list':lambda r:r.update(verification=list(r['verification'])),
    'trial_upgrade':lambda r:r['provenance'].update(trial_state='ACTIVE'),
    'actual_net':lambda r:r['results'].update(actual_net=13),
   })
  for label,change in mutations.items():
   altered=copy.deepcopy(original);change(altered)
   class AlteredStore:
    def load(self,strict=True):
     rr=copy.deepcopy(records);mm=copy.deepcopy(metadata);rr[ref]=altered;mm[ref]['record_hash']=digest(canonical(altered));return rr,mm,[]
    def __getattr__(self,n):return getattr(store,n)
   try:export_backup(AlteredStore(),root/'unexpected.zip',refs);raise AssertionError('unsafe export accepted')
   except ValueError as exc:results.append({'ref':ref,'attack':label,'phase':'spoofed_metadata_export','rejection':str(exc)})
  attacks={k:canonical((lambda r:(f(r),r)[1])(copy.deepcopy(original))) for k,f in mutations.items()}
  raw=canonical(original)
  attacks.update({'noncanonical_space':raw+b' ','noncanonical_order':json.dumps(original).encode(),
   'duplicate_false':b'{"synthetic":false,'+raw[1:],
   'duplicate_hidden_payload':b'{"round_id":{"payload":[42.42]},'+raw[1:]})
  for label,content in attacks.items():
   files=dict(base);mm=json.loads(files['ARCHIVE_MANIFEST.json']);entry=next(e for e in mm['records'] if e['record_ref']==ref);name=entry['path'];files[name]=content
   entry['original_record_hash']=digest(content)
   for e in mm['files']:
    if e['path']==name:e.update(sha256=digest(content),bytes=len(content))
   mm.pop('archive_id');mm['archive_id']=digest(canonical(mm));files['ARCHIVE_MANIFEST.json']=canonical(mm)
   bad=root/'forged.zip'
   with zipfile.ZipFile(bad,'w') as z:
    for n,v in files.items():z.writestr(n,v)
   try:restore_backup(bad,root/'unsafe-restore');raise AssertionError('unsafe restore accepted')
   except ValueError as exc:results.append({'ref':ref,'attack':label,'phase':'all_hashes_recomputed_restore','rejection':str(exc)})
   assert not (root/'unsafe-restore').exists()
 outcome={'records':len(m['record_refs']),'files':restored['files_verified'],'archive_sha256':m['archive_sha256'],'exact_original_bytes':True}
archives=[]
for path in sorted((main/'.local/archives').glob('*.zip'))+[main/'.local/receipts/public-research-v1.zip']:
 before=digest(path.read_bytes());old=inspect_backup(path);assert before==digest(path.read_bytes());archives.append({'name':path.name,'sha256':before,'records':len(old['record_refs'])})
again,_,anomalies=store.load(strict=True);assert not anomalies
assert all(digest(canonical(again[k]))==h for k,h in hashes.items())
assert all(digest((store.root/n).read_bytes())==h for n,h in bundle_hashes.items())
assert digest(canonical(project(store,asof)))==graph
assert all('verification' not in public_record(records[r]) for r in refs)
assert all(digest((c/n).read_bytes())==h for n,h in freeze['complete_source_sha256'].items())
print(json.dumps({'scope':'LOCAL_TEMPORARY_ENGINEERING_ONLY','restore':outcome,'attacks':results,'old_archives':archives,
 'original_records_unchanged':len(hashes),'bundle_files_unchanged':len(bundle_hashes),'graph_projection_unchanged':True},indent=2))
