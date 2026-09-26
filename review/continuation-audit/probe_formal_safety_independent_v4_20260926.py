"""Independent synthetic probes; writes only disposable fixture stores; no network."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import zipfile
from unittest.mock import patch

parser = argparse.ArgumentParser()
parser.add_argument('--candidate-root', required=True)
args = parser.parse_args()
root = Path(args.candidate_root).resolve()
sys.path[:0] = [str(root), str(root / 'tests')]
from test_formal_review import FormalReviewTests
from test_conditional_review import PRIVATE_NUMBER, old_waiting_material
from researchlib import formal_review as fr, conditional_review as cr, funding_review as waiting
from researchlib.archive import export_backup
from researchlib.snapshot import publish_snapshot
from researchlib.common import canonical, digest

initial = digest((root/'researchlib/formal_review.py').read_bytes())
assert initial == 'f542a221e0652d20da5570caecbad90464c103fdbbbf9a7c4f7ab56bb56f5071'
results = []
attacks = ['renamed_layout_unknown', 'nested_coverage', 'nested_results', 'sibling_feedback_extra',
           'batch_extra', 'extra_bundle_member', 'attachment_content', 'inventory_nested',
           'private_hash_nested', 'renamed_private_under_source', 'unknown_evaluator_only']
for attack in attacks:
    case = FormalReviewTests('test_real_decode_path_from_legacy_has_no_granted_business_capabilities')
    case.setUp()
    try:
        bundle = cr.prepare_bundle(case.store, 'parent', case.inputs(), '2026-09-23T12:00:00Z')
        review = case.reviews(bundle)[0]
        feedback = next(r for r in bundle['records'] if r.get('feedback_id') == review['feedback_refs'][0])
        if attack == 'renamed_layout_unknown':
            names = {n:n.replace('SOURCE/', 'moved/').replace('PRIVATE/', 'observations/') for n in bundle['attachments']}
            bundle['attachments'] = {names[n]:v for n,v in bundle['attachments'].items()}
            exposed = next(n for n in bundle['attachments'] if n.startswith('observations/'))
            for record in bundle['records']:
                record['disclosure'] = copy.deepcopy(record['disclosure'])
                record['disclosure']['public_attachments'] = ['attachments/'+names[n[12:]] for n in record['disclosure']['public_attachments']] + ['attachments/'+exposed]
            for record in case.reviews(bundle): record['evaluator_version'] = 'UNKNOWN_METHOD'
        elif attack == 'nested_coverage': review['coverage']['raw_prices'] = {'x':[PRIVATE_NUMBER]}
        elif attack == 'nested_results': review['results'] = {'x':[PRIVATE_NUMBER]}
        elif attack == 'sibling_feedback_extra': feedback['evidence'] = {'x':[PRIVATE_NUMBER]}
        elif attack == 'batch_extra': bundle['records'][0]['unexpected'] = {'x':[PRIVATE_NUMBER]}
        elif attack == 'extra_bundle_member':
            extra = copy.deepcopy(feedback); extra['feedback_id'] = 'extra-feedback'; extra['unexpected'] = PRIVATE_NUMBER
            bundle['records'].append(extra)
        elif attack == 'attachment_content': bundle['attachments']['SOURCE/researchlib/formal_extra.py'] = PRIVATE_NUMBER
        elif attack == 'inventory_nested': review['simulation_state']['inventory'] = {'x':[PRIVATE_NUMBER]}
        elif attack == 'private_hash_nested': review['simulation_state']['private_computation_sha256'] = {'x':[PRIVATE_NUMBER]}
        elif attack == 'renamed_private_under_source':
            n = 'SOURCE/observations.txt'; private = next(v for k,v in bundle['attachments'].items() if k.startswith('PRIVATE/'))
            bundle['attachments'][n] = private
            for record in bundle['records']:
                record['disclosure'] = copy.deepcopy(record['disclosure'])
                record['disclosure']['public_attachments'].append('attachments/'+n)
        elif attack == 'unknown_evaluator_only': review['evaluator_version'] = 'UNKNOWN_METHOD'
        try:
            case.commit(bundle)
        except Exception as exc:
            results.append({'probe':attack,'outcome':'STORE_REJECTED','reason':str(exc)}); continue
        case.now = '2026-09-23T19:00:00Z'
        try: output = fr.prepare_bundle(case.store, 'child', case.inputs(), '2026-09-23T12:00:00Z')
        except Exception as exc:
            results.append({'probe':attack,'outcome':'REJECTED_BEFORE_NEW_PUBLIC_ROOT','reason':str(exc)}); continue
        case.commit(output)
        archive = case.root/'probe.zip'; export_backup(case.store, archive, record_refs=['child'])
        with zipfile.ZipFile(archive) as z:
            leaked_archive = any(PRIVATE_NUMBER.encode() in z.read(n) for n in z.namelist())
        public = case.root/'public'; publish_snapshot(case.store, public, case.now)
        leaked_snapshot = any(PRIVATE_NUMBER.encode() in p.read_bytes() for p in public.rglob('*') if p.is_file())
        results.append({'probe':attack,'outcome':'RETURNED','archive_canary':leaked_archive,'snapshot_canary':leaked_snapshot})
    finally: case.doCleanups()

# Prove that waiting reconstruction neither mutates shared globals nor executes
# bundled source. The source is bound to a reviewed profile; a comment changes
# its digest and must be rejected before it could be evaluated.
for altered in (False, True):
    case = FormalReviewTests('test_real_decode_path_from_legacy_has_no_granted_business_capabilities'); case.setUp()
    try:
        with patch.object(waiting, 'method_material', side_effect=old_waiting_material):
            bundle = waiting.prepare_bundle(case.store, 'waiting-parent', '2026-09-23T12:00:00Z')
        if altered:
            name = next(n for n in bundle['attachments'] if n.endswith('funding_review.py'))
            bundle['attachments'][name] += '\nraise RuntimeError("BUNDLED_EXECUTION_CANARY")\n'
        case.commit(bundle); case.now = '2026-09-23T19:00:00Z'
        original = waiting.method_material
        try:
            output = case.prepare('waiting-child')
            outcome = [r['evaluation_stage'] for r in case.reviews(output)]
        except Exception as exc: outcome = str(exc)
        results.append({'probe':'waiting_altered_source' if altered else 'waiting_globals_isolation',
                        'outcome':outcome,'global_function_unchanged':waiting.method_material is original})
    finally: case.doCleanups()

# A semantic closure is not a review-node budget: many registered unsupported
# plans must receive explicit per-item results without consuming history nodes.
case = FormalReviewTests('test_real_decode_path_from_legacy_has_no_granted_business_capabilities'); case.setUp()
try:
    records, _, _ = case.store.load()
    template = next(r for r in records.values() if r['record_type']=='plan')
    additions=[]
    for i in range(127):
        plan=copy.deepcopy(template); plan['plan_id']='independent-extra-'+str(i)
        plan['plan_ref']=plan['plan_id']+'@1'; additions.append(plan)
    case.store.commit_bundle('many-unsupported', 'research', additions)
    try:
        output=case.prepare('many-plans')
        result={'outcome':'RETURNED','coverage':output['records'][0]['coverage']}
    except Exception as exc: result={'outcome':'REJECTED','reason':str(exc)}
    result.update(probe='semantic_closure_distinct_from_history_nodes', registered_plans=129,
                  documented_semantic_limit=4096, actual_history_reviews=2)
    results.append(result)
finally: case.doCleanups()

case = FormalReviewTests('test_real_decode_path_from_legacy_has_no_granted_business_capabilities'); case.setUp()
try:
    evidence = [dict(schema_version='1.0', record_type='evidence', evidence_id='independent-bound-'+str(i),
        created_at=case.now, available_at=case.now, synthetic=False,
        disclosure={'visibility':'PUBLIC','license':'OWN_ANALYSIS'}) for i in range(4097)]
    case.store.commit_bundle('independent-boundary', 'review', evidence)
    records, metadata, _ = case.store.load()
    for count in (4096, 4097):
        refs=[r['evidence_id'] for r in evidence[:count]]
        try:
            fr._ancestor_public_policy(case.store, records, metadata, refs, fr._context())
            outcome='ACCEPTED'
        except Exception as exc: outcome=str(exc)
        results.append({'probe':'committed_semantic_boundary','nodes':count,'outcome':outcome})
    plan=next(r for r in records.values() if r['record_type']=='plan')
    method,_=fr.method_material(case.now)
    def node(*args): return (None,None,'GUARD_TEST_ONLY')
    with patch.object(fr, '_previous_node', side_effect=node):
        context=fr._context()
        for i in range(128):
            fr._previous(None, {'review_id':'node-'+str(i),'plan_hash':fr.sha(plan)}, plan,{}, {},method,context)
        results.append({'probe':'history_node_128','outcome':'ACCEPTED','nodes':len(context['nodes'])})
        try:
            fr._previous(None, {'review_id':'node-129','plan_hash':fr.sha(plan)}, plan,{}, {},method,context)
            outcome='ACCEPTED'
        except Exception as exc: outcome=str(exc)
        results.append({'probe':'history_node_129','outcome':outcome})
        for existing_depth in (63,64):
            context=fr._context();context['visiting']={str(i) for i in range(existing_depth)}
            try:
                fr._previous(None, {'review_id':'depth-node','plan_hash':fr.sha(plan)},plan,{}, {},method,context)
                outcome='ACCEPTED'
            except Exception as exc: outcome=str(exc)
            results.append({'probe':'review_depth_guard','attempted_depth':existing_depth+1,'outcome':outcome,
                            'scope':'INJECTED_GUARD_STATE_NOT_FULL_ECONOMIC_CHAIN'})
finally: case.doCleanups()

assert initial == digest((root/'researchlib/formal_review.py').read_bytes())
print(json.dumps({'scope':'INDEPENDENT_SYNTHETIC_SECURITY_ONLY','source_sha256':initial,'results':results}, indent=2))
