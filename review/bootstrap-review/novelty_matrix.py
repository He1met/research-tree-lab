"""Combined A03 perturbations in one disposable store, never production."""
import copy
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from test_storage_novelty import NoveltyTests,candidate,NOW,record
from researchlib.snapshot import project
from researchlib.common import canonical,now_iso


def main():
    fixture=NoveltyTests();fixture.setUp()
    try:
        base=candidate('base')
        renamed=candidate('renamed',dataset='D-renamed',method='M-renamed')
        renamed[0].update(title='A completely different display name',mechanism='Renamed prose cannot manufacture a mechanism',mechanism_fingerprint='invented-new-family')
        varied=candidate('varied',lookback=37)
        product=candidate('eth',product='ETH',dataset='D-ETH')
        sample=candidate('new-sample',dataset='D2')
        base[0]['additional_source_refs']=['background-a','background-b','background-c']
        fixture.store.commit_bundle('all-candidates','research',[item for pair in (base,renamed,varied,product,sample) for item in pair])
        catalog,details,_,_=project(fixture.store,NOW)
        nodes={n['id']:n for n in catalog['nodes']}
        checks={
          'renamed_is_duplicate':nodes['Rrenamed']['originality']=='DUPLICATE_RULES_AND_INPUTS',
          'parameter_tuning_is_variant':nodes['Rvaried']['originality']=='PARAMETER_OR_RULE_VARIANT',
          'cross_product_is_replication_candidate':nodes['Reth']['originality']=='CROSS_PRODUCT_REPLICATION_CANDIDATE',
          'new_sample_is_replication_candidate':nodes['Rnew-sample']['originality']=='NEW_SAMPLE_REPLICATION_CANDIDATE',
          'multiple_sources_do_not_duplicate_rounds':catalog['round_count']==5,
          'all_candidates_share_structural_family':catalog['mechanism_family_count']==1 and len({n['mechanism_fingerprint'] for n in nodes.values()})==1,
          'not_scientific_independence':catalog['scientifically_independent_mechanism_count'] is None and all(n['novelty_comparison']['scientific_independence']=='NOT_ESTABLISHED' for n in nodes.values()),
          'detail_agrees_with_catalog':all(details[k]['originality']==n['originality'] for k,n in nodes.items()),
        }
        opaque=record('round',round_id='opaque',question='Unstructured idea',mechanism='unseen words',product_refs=['BTC'],parent_round_id=None,plan_refs=[])
        fixture.store.commit_bundle('opaque-round','research',[opaque])
        updated,_,_,_=project(fixture.store,NOW)
        node=next(n for n in updated['nodes'] if n['id']=='opaque')
        checks['opaque_new_name_is_unknown']=node['originality']=='UNKNOWN_NOVELTY' and node['mechanism_fingerprint'] is None
        result={'schema_version':'1.0','checked_at':now_iso(),'test_only':True,'production_writes':False,'cases':checks,'all_passed':all(checks.values()),'candidate_states':{k:n['originality'] for k,n in nodes.items()},'evidence_scope':'Engineering structural deduplication hints only; no scientific or economic independence asserted.'}
    finally:fixture.tearDown()
    Path(__file__).with_name('novelty-matrix.json').write_bytes(canonical(result))
    print(json.dumps(result,indent=2))
    if not result['all_passed']:raise SystemExit(1)

if __name__=='__main__':main()
