import json
from pathlib import Path
from researchlib import Store
from researchlib.common import canonical,digest,now_iso
from researchlib.review import verify_batch_coverage
root=Path.cwd();o=root/'review/daily-20260930';s=Store(root);r,m,a=s.load(strict=True)
b=json.loads((o/'frozen-batch.json').read_text());before=json.loads((o/'before-hashes.json').read_text());assert all(digest(canonical(r[k]))==v for k,v in before.items())
assert not (root/'.local/review-outbox/daily-20260930/formal-bundle.json').exists()
at=now_iso();install=json.loads((o/'installation-frozen.json').read_text())
for item in b['items']:
 item.update(disposition='TECHNICAL_FAILURE',reason_codes=['COMBINED_HISTORY_RESOURCE_LIMIT_EXCEEDED'],result_is_evaluable=False)
b['complete']=False;b['coverage']=verify_batch_coverage(b,r)
e={'schema_version':'1.0','verified_at':at,'batch_id':b['batch_id'],'frozen_at':b['frozen_at'],'coverage':b['coverage'],'registry_screened':2,'batch_preparation_failures':1,'affected_plans':2,'new_reviews':0,'new_feedback':0,'new_economic_results':0,'final_results':0,'final_reused':0,'status':'TECHNICAL_FAILURE_BATCH_INCOMPLETE','reason_code':'COMBINED_HISTORY_RESOURCE_LIMIT_EXCEEDED','failure_location':'researchlib/formal_review.py:863 final combined resource check','diagnosis':'Combined encoded/private/public replay bytes or union history nodes exceeded fixed bound. Exact branch/counters not observed; no claim of timeout. Final check rejected whole bundle.','previous_result_stage':'PATH_AMBIGUOUS','previous_revision':4,'prior_state_unchanged':True,'release_ref':install['release_ref'],'method_sha256':install['formal_method_code_sha256'],'method_sources_match_release':True,'actually_evaluated_market_cutoff':None,'actual_net':None,'new_market_files':0,'new_qualified_inputs':0,'input_manifest_scope':'Same registered four files requested; this failed run does not certify all decoding/history checks completed','trigger_origin':'UNKNOWN','natural_trigger':None,'official_view':'Rendered automation card only; no reliable run origin','reviewed_public_evidence_refs':['decision-adopt-daily-input-long-20260929','decision-adopt-daily-input-short-20260929'],'next_action':'Independent isolated diagnosis of combined byte/node accumulation and final batch failure isolation; preserve limits, original chains and method identity until separately reviewed version is installed.'}
(o/'evidence.json').write_bytes(canonical(e))
report='''本轮已冻结全部2份BTC原方案并核对新增证据，但固定评价器在最终历史资源检查触发COMBINED_HISTORY_RESOURCE_LIMIT_EXCEEDED，整批准备失败。新正式复核0，批次未完成；旧revision4的PATH_AMBIGUOUS与全部状态保留。无新经济结果，收益未知。自然触发UNKNOWN。

真实覆盖：batch-daily-review-20260930-v1于2026-09-30T00:16:52.037221Z冻结，登记p-btc-funding-long-control-20260923@1与p-btc-funding-short-20260923@1。清单筛查2/2，已提交新review 0/2；一个批次技术失败影响两项，不宣称全部通过。晚登记下一批。两原方案、八份既有复核、既有登记数据与新增资料/反馈记录已核对；固定程序未完成本轮全链验证。

原规则：0.01 BTC多空对照，2026-09-23 00:05至00:06 UTC入场窗，09-24同窗退出。窗口已结束，冻结信号满足；缺数不是未触发，未知库存不是空仓，不虚构零收益或日结平仓。public_visibility_ref仍null，不追认公开事前证据。

数据与结果：请求复用原09-23/24两份成交和两份资金费登记文件及09-27原取得时间，未新下载。原SHA/取得时间仍见前驱证据，本轮技术失败不认证所有解码已完成。实际可评价截止null。原窗口首笔顺序、源全集、精确结算mark、完整mark路径及原规则费用仍未合格；收益、成本、持有期、权益回撤和对照优劣不可评价。旧revision4作为历史结果保持，不计本轮最终复用。

失败证据：prepare.py调用受审prepare_outbox，在formal_review.py:863最终_check_time触发formal_review.py:101的COMBINED_HISTORY_RESOURCE_LIMIT_EXCEEDED，未生成formal-bundle.json。该检查联合已编码缓存、旧内核缓存、公开祖先重放字节和不同review节点数；没有记录具体触发分支/计数，不能称超时或断言某一精确大小。安装release_ref 752040094d40aa5d915270e7c696fe4065c01e05及正式方法19源已逐件核对，方法hash 34e0bcfce6515c0ccb5e2f742ab1936b440b6d06cf4b3670049c7993efa63be4保持。

事实与解释分开：新增资料筛查和昨日反馈采用没有提供新合格原窗口输入；这不证明外部不存在数据。此次失败是评价器资源拒绝，不是策略亏损或机制反例。没有按相同条件重跑或修改限额、删除历史。

诊断提议：隔离检查联合资源累计与最终检查的失败隔离语义，记录实际bytes/nodes及去重情况；反例要求完整历史增长时仍不丢前驱、不绕过公开祖先检查、不错误认证结果。任何修复需独立检查和新版本安装，再用明确修订原因接续本批。经济方向继续等待精确覆盖/顺序、mark与成本资格；保留同窗同数量多空对照，复用既有输入完整性后继，不调参追认旧成绩。

通过review角色只提交冻结未完成批次和失败证据；不伪造新评分或反馈。F07追加实际失败运行证据，官方view仅返回卡片，来源UNKNOWN、natural_trigger=null，已核实自然次数不增加。未改原件、公共源码、队列、页面或频率。需维护角色处理诊断提议，当前无需用户操作。
'''
(o/'REPORT.md').write_text(report)
record={'schema_version':'1.0','record_type':'evidence','evidence_id':'e-daily-review-failure-20260930-v1','created_at':at,'available_at':at,'synthetic':False,'title':'每日复核批次技术失败：固定历史资源限额拒绝','instrument_ref':'BTC-USDT-SWAP','input_record_refs':[b['batch_id']]+[x['previous_review_ref'] for x in b['items']]+e['reviewed_public_evidence_refs'],'results':e,'disclosure':{'visibility':'PUBLIC','license':'OWN_ANALYSIS','scope':'Own bounded failure report; no raw rows or private computation attachments','public_attachments':['attachments/REPORT.md','attachments/EVIDENCE.json']}}
bundle={'bundle_id':'review-daily-failure-20260930-v1','role':'review','request_key':'review-daily-failure-20260930-v1','records':[b,record],'attachments':{'REPORT.md':report,'EVIDENCE.json':canonical(e).decode()}}
p=root/'.local/review-outbox/daily-20260930/failure-bundle.json';p.write_bytes(canonical(bundle));print(p)
