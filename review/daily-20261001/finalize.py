from pathlib import Path
import json,subprocess
from researchlib import Store
from researchlib.common import canonical,digest,now_iso,utc
from researchlib.formal_review import method_material
from researchlib.review import verify_batch_coverage
root=Path.cwd(); o=root/'review/daily-20261001'; s=Store(root); r,m,a=s.load(strict=True)
b=json.loads((o/'frozen-batch.json').read_text()); before=json.loads((o/'before-hashes.json').read_text())
assert all(digest(canonical(r[k]))==v for k,v in before.items())
install=json.loads((root/'.local/installation.json').read_text()); method,_=method_material(b['frozen_at'])
assert method['method_code_sha256']==install['formal_method_code_sha256']
for name,sha in method['source_sha256'].items():
 assert digest(subprocess.check_output(['git','show',install['release_ref']+':'+name]))==sha,name
(o/'installation-frozen.json').write_bytes(canonical(install))
datasets=[]
for k,v in r.items():
 if k.startswith('d-review-btc-'):
  raw=(s.data_root/'objects'/v['sha256']).read_bytes();assert digest(raw)==v['sha256']; assert len(raw)==v['bytes']
  datasets.append({key:v.get(key) for key in ['dataset_id','version','sha256','bytes','acquired_at','data_available_at','available_at','published_at','quality']})
prior=[]
for item in b['items']:
 p=r[item['plan_ref']]; rev=r[item['previous_review_ref']]
 assert digest(canonical(p))==item['plan_hash'];assert digest(canonical(rev['simulation_state']))==item['opening_state_hash']
 item.update(disposition='TECHNICAL_FAILURE',reason_codes=['KNOWN_EVALUATOR_CAPACITY_BLOCKER_NOT_RETRIED'],result_is_evaluable=False,evaluator_executed=False)
 prior.append({'plan_ref':item['plan_ref'],'previous_review_ref':item['previous_review_ref'],'revision':rev['revision'],'evaluation_stage':rev['evaluation_stage'],'opening_state_hash':item['opening_state_hash'],'actually_evaluated_market_cutoff':rev['coverage']['actually_evaluated_market_cutoff'],'missing':rev['coverage']['reason_codes'],'metrics':rev['metrics']})
b['complete']=False;b['coverage']=verify_batch_coverage(b,r)
diagpath='review/continuation-audit/formal-resource-independent-v1-20260930.json';diag=json.loads((root/diagpath).read_text());assert diag['capacity_bottleneck_fixed'] is False
at=now_iso()
e={'schema_version':'1.0','verified_at':at,'batch_id':b['batch_id'],'frozen_at':b['frozen_at'],'status':'KNOWN_TECHNICAL_BLOCKER_NOT_RETRIED','coverage':b['coverage'],'registry_screened':len(b['items']),'new_reviews':0,'new_feedback':0,'new_economic_results':0,'final_results':0,'final_reused':0,'evaluator_executed':False,'new_failure_observed':False,'inherited_failure':'COMBINED_HISTORY_RESOURCE_LIMIT_EXCEEDED','diagnostic_receipt':diagpath,'diagnostic_receipt_sha256':digest((root/diagpath).read_bytes()),'historical_diagnostic_counters':diag['checks']['final_counters'],'historical_counters_not_current_measurement':True,'release_ref':install['release_ref'],'method_sha256':method['method_code_sha256'],'method_sources_match_release':True,'source_count':len(method['source_sha256']),'prior_results_preserved':prior,'data_files_rehashed':datasets,'new_market_files':0,'new_qualified_inputs':0,'actually_evaluated_market_cutoff':None,'actual_net':None,'trigger_origin':'UNKNOWN','natural_trigger':None,'official_view':'Rendered automation card in the app; no run-origin attestation returned.','next_action':'Wait for separately reviewed and installed capacity method and qualified original-window inputs; preserve failed September 30 batch and all original revisions. No unchanged replay.'}
(o/'evidence.json').write_bytes(canonical(e))
report=f'''今日全部2份BTC原方案已冻结并逐项核对；容量故障尚未修复，未重跑已知失败的评价器。受控提交未完成批次与阻塞处置证据，新review 0/2、最终0、最终复用0。旧revision4的PATH_AMBIGUOUS及跨日状态保持；actual_net=null。自然触发UNKNOWN，不升级验收。

真实覆盖：{b['batch_id']}，冻结时点{b['frozen_at']}。纳入p-btc-funding-long-control-20260923@1和p-btc-funding-short-20260923@1，逐项计划哈希、前驱及状态哈希见批次与EVIDENCE.json。全部八份既有复核及登记数据已读取；晚于冻结的登记下一批处理。

阶段/最终结果：两项均为既有技术故障阻塞，本次evaluator_executed=false，不将其报告为今天重新观察到的程序异常。原先PATH_AMBIGUOUS是历史评价阶段，不能计作今日成功复核或最终复用。毛/净、费用、已实现/未实现、回撤、持有期和基线优劣均未知，不制造0收益交易，不重置仓位。

原规则：0.01 BTC同窗多空对照，入场为2026-09-23 00:05至00:06 UTC第一笔合格成交，退出为09-24同窗；最多一次入场和退出。窗口已结束，冻结信号已满足，但首笔成交资格未知。public_visibility_ref=null，仍不能追认为公开事前预测。

数据与路径：四份原成交/资金费文件本次重新校验SHA256和长度；取得与可得时点保留09-27原值，公开发布时间未知。完整哈希/原取得时间见EVIDENCE.json。文件一致只证明完整性；未重解码、未新下载，实际可评价截止null。原窗口事件全集、同毫秒先后、精确结算mark、完整mark路径与适用费用仍缺。后续新增资料筛查未提供本方案合格新输入；不推断外部不存在数据。

工程证据：安装release_ref={install['release_ref']}，正式方法{method['method_code_sha256']}的{len(method['source_sha256'])}份源文件与release逐项一致。当前安装仅诊断，不是容量修复。已读取受审历史诊断：累计验证工作量130760540超过128000000，节点4未超128；计数属于昨日隔离诊断，本轮未重测。设计审查文件为CHANGES_REQUIRED，未获实施/安装批准；不修改公共评价器、阈值或历史链，也不重派既有维护。

反馈：事实为无合格新输入且技术阻塞保持；原因解释为容量规则阻止当前方法完成全链校验，不是策略亏损或机制反例。优化假设沿用既有输入完整性后继，不新造重复feedback、不事后调参数。下一可检验变化是新版本在独立审查后证明完整旧链可验证；反例为缓存绕过ECONOMIC检查、跨计划污染或限额边界不等价，任一成立则停止。经济评价继续保留同窗同量多空对照，待合法完整路径与成本资格后按新修订原因追加，不能相加为账户收益。

官方管理入口本次仍仅返回automation card，未提供scheduled/manual来源；trigger_origin=UNKNOWN，natural_trigger=null。F07仅追加本次真实处置证据，自然次数不增加。未改原方案、旧评分、研究队列、页面、任务频率或共享源码。当前无用户操作要求；由既有维护流程解决技术门槛，发布职责消费完整提交。
'''
(o/'REPORT.md').write_text(report)
record={'schema_version':'1.0','record_type':'evidence','evidence_id':'e-daily-review-blocked-20261001-v1','created_at':at,'available_at':at,'synthetic':False,'title':'每日复核：已知容量阻塞保持，未重复回放','instrument_ref':'BTC-USDT-SWAP','input_record_refs':[b['batch_id'],'e-daily-review-failure-20260930-v1']+[x['previous_review_ref'] for x in b['items']],'results':e,'disclosure':{'visibility':'PUBLIC','license':'OWN_ANALYSIS','scope':'Own blocked-batch disposition; no raw rows or restricted source records','public_attachments':['attachments/REPORT.md','attachments/EVIDENCE.json']}}
bundle={'bundle_id':'review-daily-blocked-20261001-v1','role':'review','request_key':'review-daily-blocked-20261001-v1','records':[b,record],'attachments':{'REPORT.md':report,'EVIDENCE.json':canonical(e).decode()}}
p=root/'.local/review-outbox/daily-20261001/blocked-bundle.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(canonical(bundle));print(p)
