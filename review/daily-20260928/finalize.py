import json
from pathlib import Path
from researchlib import Store
from researchlib.common import canonical,digest,now_iso
from researchlib.contracts import validate_relationships
root=Path.cwd(); out=root/'review/daily-20260928';s=Store(root)
r,m,a=s.load(strict=True);validate_relationships(r)
b=json.loads((root/'.local/review-outbox/daily-20260928/formal-bundle.json').read_text());batch=r['batch-daily-review-20260928-v1']
before=json.loads((out/'before-hashes.json').read_text()); assert all(digest(canonical(r[k]))==v for k,v in before.items())
reviews=[v for v in b['records'] if v['record_type']=='review']; continuity=[]
for v in reviews:
 old=r[v['previous_review_ref']]; assert v['revision']==old['revision']+1 and v['opening_state_hash']==digest(canonical(old['simulation_state']))
 assert v['metrics']==old['metrics'] and all(x is None for x in v['metrics'].values())
 assert v['input_fingerprint']==old['input_fingerprint']
 newp=json.loads(b['attachments']['PRIVATE/'+v['review_id']+'.json'])
 oldp=json.loads((s.root/'bundles'/m[old['review_id']]['bundle_id']/'attachments/PRIVATE'/(old['review_id']+'.json')).read_text())
 assert newp['kernel_result']['simulation_state']==oldp['kernel_result']['simulation_state']
 continuity.append({'plan_ref':v['plan_ref'],'previous_review_ref':old['review_id'],'review_ref':v['review_id'],'revision':v['revision'],'same_input_fingerprint':True,'kernel_state_identical':True,'opening_state_verified':True,'evaluation_stage':v['evaluation_stage'],'coverage':v['coverage']})
old_e=json.loads((root/'review/daily-20260927/evidence.json').read_text()); install=json.loads((out/'installation-frozen.json').read_text()); at=now_iso()
e={'schema_version':'1.0','verified_at':at,'automation_id':'research-tree-lab-3','batch_id':batch['batch_id'],'frozen_at':batch['frozen_at'],'coverage':batch['coverage'],'stage_counts':{'PATH_AMBIGUOUS':2},'items':continuity,'release_ref':install['release_ref'],'method_sha256':install['formal_method_code_sha256'],'method_sources_match_release':True,'formal_bundle_payload_hash':json.loads((s.root/'bundles'/b['bundle_id']/'manifest.json').read_text())['payload_hash'],'original_records_hash_unchanged':len(before),'files':old_e['files'],'files_scope':'Existing registered files rehashed and decoded this run; acquired_at is retained original acquisition time; no new downloads','decode_audits':[{k:x[k] for k in ['adapter_version','partition_utc','rows_read','source_bytes_sha256_verified','source_bytes_size_verified','source_coverage','zip_crc'] if k in x} for x in newp['decode_audits']],'new_market_files':0,'new_economic_samples':0,'actually_evaluated_market_cutoff':None,'requested_market_cutoff':'2026-09-24T00:06:00Z','trigger_origin':'UNKNOWN','natural_trigger':None,'official_view':'Rendered automation card only; run origin not exposed','helper_origin_scope':'OFFICIAL_APP_HELPER_NOT_NATIVE_ATTESTATION is not proof of manual invocation','public_forward_proof':'Original public_visibility_ref null; no independent historical timing evidence added','new_qualified_inputs':0,'reviewed_new_evidence_refs':['e-rpi-source-mixture-20260927','e-funding-information-20260927','e-fee-rounding-20260927','decision-async-qualification-20260928'],'feedback_disposition':'Prior adopted feedback remains valid; no correction or duplicate successor. New daily feedback reiterates evidence qualification only.','new_reviews':2,'new_feedback':2,'final_reused':0,'input_files_reused':4,'late_plan_refs':sorted(k for k,v in r.items() if v['record_type']=='plan' and k not in batch['plan_refs']),'next_action':'Await qualified exact order, source coverage, settlement/full mark and cost evidence; explicit revision for changed old-window facts; no rule change.'}
(out/'evidence.json').write_bytes(canonical(e))
report=(out/'REPORT.md').read_text()+'\n实际提交结果：覆盖2/2；PATH_AMBIGUOUS 2；可评价0、最终0、最终复用0、技术失败0。两份新review均revision=3，前驱内核状态逐字节语义一致，原180条记录哈希不变。四个源文件复用不计最终复用或新样本。\n'
(out/'REPORT.md').write_text(report)
record={'schema_version':'1.0','record_type':'evidence','evidence_id':'e-daily-review-20260928-v1','created_at':at,'available_at':at,'synthetic':False,'title':'每日复核：两方案原规则状态连续，资格缺项未变','instrument_ref':'BTC-USDT-SWAP','input_record_refs':[batch['batch_id']]+e['reviewed_new_evidence_refs'],'results':e,'disclosure':{'visibility':'PUBLIC','license':'OWN_ANALYSIS','scope':'Own review summaries and source hashes only; no upstream rows or private paths.','public_attachments':['attachments/REPORT.md','attachments/EVIDENCE.json']}}
receipt=s.commit_bundle('review-daily-evidence-20260928-v1','review',[record],{'REPORT.md':report,'EVIDENCE.json':canonical(e).decode()},request_key='review-daily-evidence-20260928-v1')
r,m,a=s.load(strict=True);validate_relationships(r);assert all(digest(canonical(r[k]))==v for k,v in before.items())
verification={'verified_at':now_iso(),'records':len(r),'anomalies':a,'old_records_unchanged':len(before),'new_record_refs':sorted(k for k in r if k not in before),'evidence_bundle_payload_hash':receipt['payload_hash'],'coverage':batch['coverage'],'state':'VALIDATED'}
(out/'commit-verification.json').write_bytes(canonical(verification))
accept_path=root/'docs/acceptance.json';acc=json.loads(accept_path.read_text());f=next(x for x in acc['checks'] if x['id']=='F07')
for name in ['REPORT.md','evidence.json','commit-verification.json']:
 ref='review/daily-20260928/'+name
 if ref not in f['evidence']:f['evidence'].append(ref)
f['verified_scope']+=' 2026-09-28本角色冻结并覆盖2/2原方案，追加revision=3及反馈，状态仍PATH_AMBIGUOUS，经济结果0；见本日证据。'
f['limitations']+=' 2026-09-28官方view仍只返回卡片，来源UNKNOWN，不增加已验证自然日复核次数。'
accept_path.write_bytes(canonical(acc))
print(json.dumps(verification,ensure_ascii=False))
