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
manifest=c/'docs/bipower-archive-v1-candidate.json'
assert digest(manifest.read_bytes())=='bd49c66ab3ff9eb7d87b479dd7667bd7935aeb66e40414bf2de0779e3201ec55'
freeze=json.loads(manifest.read_text())
for group in ['source_sha256','delivery_files','engineering_receipts']:
 assert all(digest((c/n).read_bytes())==h for n,h in freeze[group].items())
store=readonly_store(main);records,metadata,anomalies=store.load(strict=True);assert not anomalies
refs=json.loads((main/'docs/bipower-archive-maintenance-request-20260929-v3.json').read_text())['archive_pending']
for ref,sha in freeze['original_sha256'].items():assert digest(canonical(records[ref]))==sha
asof=now_iso();graph=digest(canonical(project(store,asof)));hashes={k:digest(canonical(v)) for k,v in records.items()}
bundle_hashes={str(p.relative_to(store.root)):digest(p.read_bytes()) for p in (store.root/'bundles').rglob('*') if p.is_file()}
results=[]
with tempfile.TemporaryDirectory(prefix='roll_run-independent-') as t:
 root=Path(t);archive=root/'good.zip'
 shutil.copytree(store.root/'bundles',root/'copy/.local/store/bundles')
 copied=readonly_store(root/'copy');assert copied.load(strict=True)==(records,metadata,[])
 m=export_backup(copied,archive,refs)
 standalone=export_backup(copied,root/'closeout-only.zip',['decision-bipower-closeout-20260929'])
 assert 'r-bipower-20260929' in standalone['record_refs']
 inspect_backup(root/'closeout-only.zip')
 restored=restore_backup(archive,root/'restored');assert inspect_backup(archive)['archive_id']==m['archive_id']
 gap_attachments=json.loads((main/'docs/bipower-archive-maintenance-request-20260929-v3.json').read_text())['attachment_gaps']
 for n in gap_attachments:assert (root/'restored/evidence'/n).read_bytes()==(store.root/'bundles'/n).read_bytes()
 for ref in refs:assert (root/'restored/records'/(ref+'.json')).read_bytes()==canonical(records[ref])
 with zipfile.ZipFile(archive) as z:base={n:z.read(n) for n in z.namelist()}
 for ref in ['discovery-bipower-20260929','e-bipower-20260929','decision-bipower-closeout-20260929']:
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
  mutations.update({
   'non_null_net':lambda r:r.update(actual_net=1),
   'private_path':lambda r:r.update(resource_expectation='/'+'Users'+'/audit/private'),
   'trial':lambda r:r['provenance'].update(trial_state='ACTIVE'),
  })
  if original['record_type'] in ['discovery','evidence']:
   mutations.update({'nested_net':lambda r:r['findings'].update(actual_net=0),'nested_bool':lambda r:r['findings'].update(actual_net=False)})
  if original['record_type']=='discovery':
   mutations.update({'proposal':lambda r:r.update(proposal_ref='bundle:other/attachments/proposal.json'),'status':lambda r:r.update(status='EXECUTED')})
  if original['record_type']=='decision':
   mutations.update({'related':lambda r:r.update(related_round_id='r-roll-scale-20260927'),'successor':lambda r:r.update(successor_round_id='r-roll-scale-20260927')})
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
 for target in ['evidence/discovery-bipower-20260929-v1/attachments/proposal.json','records/r-bipower-20260929.json']:
  for mode in ['remove','alter','noncanonical']:
   files=dict(base);mm=json.loads(files['ARCHIVE_MANIFEST.json'])
   if mode=='remove':
    del files[target];mm['files']=[e for e in mm['files'] if e['path']!=target]
    if target.startswith('records/'):
     rr=target[len('records/'):-5];mm['records']=[e for e in mm['records'] if e['record_ref']!=rr];mm['record_refs'].remove(rr)
   else:
    if mode=='noncanonical':files[target]+=b' '
    else:
     value=json.loads(files[target]);value['title']='unreviewed replacement';files[target]=canonical(value)
    for entry in mm['files']:
     if entry['path']==target:entry.update(sha256=digest(files[target]),bytes=len(files[target]))
    for entry in mm['records']:
     if entry['path']==target:entry['original_record_hash']=digest(files[target])
   mm.pop('archive_id');mm['archive_id']=digest(canonical(mm));files['ARCHIVE_MANIFEST.json']=canonical(mm)
   bad=root/'forged-binding.zip'
   with zipfile.ZipFile(bad,'w') as z:
    for n,v in files.items():z.writestr(n,v)
   try:restore_backup(bad,root/'unsafe-binding');raise AssertionError('binding forgery accepted')
   except ValueError as exc:results.append({'ref':target,'attack':mode,'phase':'bound_dependency_all_hashes_recomputed','rejection':str(exc)})
   assert not (root/'unsafe-binding').exists()
 outcome={'records':len(m['record_refs']),'files':restored['files_verified'],'archive_sha256':m['archive_sha256'],'exact_original_bytes':True}
archives=[]
for path in sorted((main/'.local/archives').glob('*.zip'))+[main/'.local/receipts/public-research-v1.zip']:
 before=digest(path.read_bytes());old=inspect_backup(path);assert before==digest(path.read_bytes());archives.append({'name':path.name,'sha256':before,'records':len(old['record_refs'])})
again,_,anomalies=store.load(strict=True);assert not anomalies
assert all(digest(canonical(again[k]))==h for k,h in hashes.items())
assert all(digest((store.root/n).read_bytes())==h for n,h in bundle_hashes.items())
assert digest(canonical(project(store,asof)))==graph
assert 'related_round_id' not in public_record(records['decision-bipower-closeout-20260929'])
assert all(digest((c/n).read_bytes())==h for n,h in freeze['source_sha256'].items())
print(json.dumps({'scope':'LOCAL_TEMPORARY_ENGINEERING_ONLY','restore':outcome,'attacks':results,'old_archives':archives,
 'original_records_unchanged':len(hashes),'bundle_files_unchanged':len(bundle_hashes),'graph_projection_unchanged':True,'gap_originals_exact':len(refs),'gap_attachments_exact':len(gap_attachments),'standalone_closeout_includes_related_round':True},indent=2))
