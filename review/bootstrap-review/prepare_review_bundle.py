"""Prepare manual review outbox; does not commit or mutate original records."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from researchlib.common import canonical, digest, now_iso, utc
from researchlib.contracts import record_ref, validate_record, validate_relationships
from researchlib.public import public_record
from researchlib.review import verify_batch_coverage
from researchlib.store import Store

HERE = Path(__file__).parent
BUNDLE = 'review-bootstrap-manual-20260923-v1'


def main():
    if (HERE / 'review_bundle.json').exists():
        raise RuntimeError('Prepared review bundle is immutable; inspect existing outbox, do not regenerate timestamps.')
    store = Store(ROOT)
    originals, meta, anomalies = store.load(strict=True)
    batch = json.loads((HERE / 'frozen_batch.json').read_text())
    audit = json.loads((HERE / 'independent_arithmetic.json').read_text())
    at = now_iso()
    method_hash = digest((HERE / 'REVIEW_METHOD.md').read_bytes())
    code_hash = digest((HERE / 'independent_audit.py').read_bytes())
    method = 'independent-forward-status-v1@sha256:' + method_hash
    files = ('REVIEW_METHOD.md', 'independent_audit.py', 'independent_arithmetic.json')
    public_attachments = ['attachments/' + f for f in files]
    common = {'schema_version':'1.0','created_at':at,'available_at':at,'synthetic':False,'disclosure':{'visibility':'PUBLIC','license':'OWN_ANALYSIS','scope':'Original independent review and aggregate diagnostics; no upstream raw data redistributed.','public_attachments':public_attachments}}
    reviews, feedback = [], []
    for item in batch['items']:
        ref = item['plan_ref']; plan = originals[ref]
        assert digest(canonical(plan)) == item['plan_hash']
        assert utc(batch['frozen_at']) < utc(plan['effective_from']), 'This v1 preparation only handles actually pre-effective plans.'
        assert item['previous_review_ref'] is None
        suffix = 'long-control' if plan['rules']['quantity_or_inventory']['direction'] == 1 else 'short'
        review_id = 'review-btc-funding-' + suffix + '-manual-20260923-v1'
        feedback_id = 'feedback-btc-funding-' + suffix + '-manual-20260923-v1'
        review = dict(common, record_type='review', review_id=review_id, plan_ref=ref, plan_hash=item['plan_hash'],
            batch_ref=batch['batch_id'], revision=1, review_method_ref=method, evaluator_version=method,
            evidence_refs=['bundle:' + BUNDLE + '/attachments/REVIEW_METHOD.md','bundle:' + BUNDLE + '/attachments/independent_arithmetic.json'],
            data_cutoff=batch['frozen_at'], evaluation_stage='NOT_YET_EFFECTIVE', data_complete=False,
            previous_review_ref=None, opening_state_hash=None,
            input_fingerprint=digest(canonical({'plan_hash':item['plan_hash'],'frozen_at':batch['frozen_at'],'audit_source_hash':audit['source_sha256'],'method_hash':method_hash,'audit_code_hash':code_hash,'subsequent_market_inputs':[]})),
            dataset_refs=plan['dataset_refs'], feedback_refs=[feedback_id],
            summary='手动安全复核：尚未到原计划生效时点，未模拟成交或收益；后续所需目标行情、结算标记及实际费用仍缺。',
            simulation_state={'state':'NOT_STARTED_BEFORE_EFFECTIVE','inventory':'0','entry_fill':None,'exit_fill':None,'processed_event_ids':[],'last_event_at':None,'funding_cashflow':None,'entry_fee':None,'exit_fee':None,'slippage_cost':None,'currency':'USDT','continuation':'At legal effective time retain original plan; absence of target trade path means WAITING_DATA, never infer no trigger, fill or forced close.'},
            metrics={'gross_price_pnl':None,'net_pnl':None,'funding_cashflow':None,'actual_total_cost':None,'realized_pnl':None,'unrealized_pnl':None,'equity_path':None,'observed_path_drawdown':None,'holding_period':None,'trade_count':None},
            baseline_comparison={'state':'NOT_EVALUATED','scope':'Opposite direction matches absolute BTC quantity and window only; market beta differs. Independent hypothetical capital must not be summed.'},
            coverage={'frozen_plan_included':True,'original_hash_verified':True,'effective_from':plan['effective_from'],'evaluation_end':plan['evaluation_end'],'subsequent_market_event_count':0,'future_data_acquisition':'NOT_ATTEMPTED_BEFORE_EVENT_EXISTS','missing_inputs':plan['replay_missing']},
            provenance={'trigger_origin':'OFFICIAL_APP_SUBAGENT_MANUAL_SAFE_TRIAL','native_task_ref':None,'natural_trigger':False,'public_forward_proof':'NONE_LOCAL_SEAL_ONLY','method_code_sha256':code_hash},
            limitations=['Pre-effective status verification is not a forward performance observation.','46 independent arithmetic/provenance assertions cover existing research input only.','No research plan, original review, task frequency, browser, Git or trading account was modified.'])
        f = dict(common, record_type='feedback',feedback_id=feedback_id, review_ref=review_id,
            supported_facts=['原计划与canonical哈希一致，合法生效为2026-09-23T00:05:00Z，本次批次截止更早。','独立复算确认原历史资金费汇总及预先费用情景；费率和不是该未来仓位现金流。','没有随后目标交易/完整标记路径；实际净收益未知，尚无公开事前证明。'],
            interpretation='现阶段只支持规则和数据边界结论；没有证据判断方向选择有效或无效。',
            alternative_explanations=['相反方向对照的差异会同时包含价格beta与资金费，不能将差额全部归为资金费预测能力。','40小时5分钟前的已结算正资金费只是封存输入，不代表入场时当前资金费仍为正。'],
            proposed_question='先实证核验官方目标成交、结算标记与资金费资料的完整性和发布时间，再检验成本后资金费贡献及共同方向暴露。',
            what_changes='后继可建立输入完整性与成本分解的可证伪检验；不改变旧方案信号、入退场窗口、费用情景或评分。',
            comparison='保留原短仓与同绝对数量长仓；另需同信息截止的无资金费信号基线或暴露匹配研究，新增规则必须新版本和新前向窗口。',
            required_data=plan['replay_missing'], status='AVAILABLE_FOR_RESEARCH_NOT_YET_ADOPTED',
            provenance={'trigger_origin':'OFFICIAL_APP_SUBAGENT_MANUAL_SAFE_TRIAL','natural_trigger':False},
            limitations=['反馈可由后续研究采用；本次没有实际后继采用记录，不能据此通过A06/F07。'])
        reviews.append(review); feedback.append(f)
        item.update(disposition='NOT_YET_EFFECTIVE',review_ref=review_id,result_is_evaluable=False)
    batch.update(available_at=at, complete=True, coverage={'registered':len(batch['plan_refs']),'reviewed':len(reviews),'missing':[],'not_yet_effective':len(reviews),'evaluable_results':0,'final_results':0},
                 summary='手动安全批次全部2个正式版本均有处置；两者尚未生效，无经济结果或自然复核。',
                 provenance={'natural_trigger':False,'native_task_ref':None,'manual_trial':True},disclosure=common['disclosure'])
    records = [batch] + reviews + feedback
    for r in records:
        validate_record(r, 'review')
        assert public_record(r) is not None
    combined = dict(originals, **{record_ref(r):r for r in records})
    validate_relationships(combined)
    coverage = verify_batch_coverage(batch, combined)
    assert coverage['coverage_complete'] and coverage['registered'] == 2
    bundle={'bundle_id':BUNDLE,'role':'review','request_key':'manual-independent-bootstrap-review-20260923-v1','records':records,'attachments':{f:(HERE/f).read_text() for f in files}}
    (HERE/'review_bundle.json').write_bytes(canonical(bundle))
    (HERE/'outbox_receipt.json').write_bytes(canonical({'schema_version':'1.0','prepared_at':at,'bundle_id':BUNDLE,'bundle_sha256':digest(canonical(bundle)),'record_count':len(records),'coverage':coverage,'state':'VALIDATED_OUTBOX_NOT_COMMITTED_BY_REVIEWER','trigger_origin':'OFFICIAL_APP_SUBAGENT_MANUAL_SAFE_TRIAL','natural_trigger':False,'native_task_ref':None,'method_ref':method}))
    print(json.dumps({'bundle_id':BUNDLE,'records':len(records),'coverage':coverage,'sha256':digest(canonical(bundle))},indent=2))

if __name__ == '__main__':
    main()
