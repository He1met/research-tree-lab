"""SYNTHETIC integration input. Uses real Store/projection only in a test directory."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from researchlib import Store, publish_snapshot
from researchlib.common import canonical, digest

parser = argparse.ArgumentParser()
parser.add_argument('phase', choices=['initial', 'append'])
parser.add_argument('directory')
args = parser.parse_args()
directory = Path(args.directory).resolve()
allowed = Path(__file__).resolve().parent / 'artifacts' / 'integration'
if not directory.is_relative_to(allowed.resolve()):
    raise ValueError('Integration fixture may write only its test directory')
at = '2026-09-21T00:00:00Z' if args.phase == 'initial' else '2026-09-22T00:00:00Z'
store = Store(directory, clock=lambda: at)

def record(kind, **fields):
    # False deliberately exercises production projection. Directory and receipts
    # mark the data SYNTHETIC; none of it may enter the production store.
    return {'schema_version': '1.0', 'record_type': kind, 'synthetic': False,
            'created_at': at, 'available_at': at,
            'disclosure': {'visibility': 'PUBLIC', 'license': 'OWN_ANALYSIS'}, **fields}

if args.phase == 'initial':
    root = record('round', round_id='C05-root', question='SYNTHETIC C05：原方案', mechanism='SYNTHETIC_CONTRACT_TEST',
                  parent_round_id=None, product_refs=[], plan_refs=['C05-plan@1'], selected_plan_ref='C05-plan@1')
    plan = record('plan', plan_id='C05-plan', version=1, round_id='C05-root', replay_eligibility='UNKNOWN',
                  research_question='仅验证追加机制，不是市场研究')
    store.commit_bundle('C05-first', 'research', [root, plan])
else:
    old, _, _ = store.load()
    review = record('review', review_id='C05-review', plan_ref='C05-plan@1', revision=1,
                    plan_hash=digest(canonical(old['C05-plan@1'])), review_method_ref='SYNTHETIC_REVIEWER',
                    data_cutoff=at, evaluation_stage='DATA_MISSING', limitations=['SYNTHETIC TEST ONLY'])
    feedback = record('feedback', feedback_id='C05-feedback', review_ref='C05-review',
                      supported_facts=['合成验收：反馈产生后继'], proposed_question='验证新一代')
    store.commit_bundle('C05-review-bundle', 'review', [review, feedback])
    child = record('round', round_id='C05-child', question='SYNTHETIC C05：反馈后继', mechanism='SYNTHETIC_SUCCESSOR',
                   parent_round_id='C05-root', product_refs=[], derived_from_feedback_refs=['C05-feedback'], plan_refs=[])
    independent = record('round', round_id='C05-independent', question='SYNTHETIC C05：独立新方向', mechanism='SYNTHETIC_INDEPENDENT',
                         parent_round_id=None, product_refs=[], plan_refs=[])
    store.commit_bundle('C05-followup', 'research', [child, independent])
result = publish_snapshot(store, directory / 'data', as_of=at)
print(json.dumps({'classification': 'SYNTHETIC_FILE_PIPELINE_TEST', **result}))
