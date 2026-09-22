"""Late-commit historical batch regression in a disposable test-only store."""
import json
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from test_storage_contracts import round_record,plan_record,review_record,T0,T1,T2,T3
from researchlib.store import Store
from researchlib.review import freeze_batch
from researchlib.common import canonical,now_iso


def main():
    with tempfile.TemporaryDirectory() as temp:
        time=[T0]
        store=Store(temp,clock=lambda:time[0])
        plan=plan_record(entry_valid_until=T1,evaluation_end=T1)
        store.commit_bundle('base','research',[round_record(),plan])
        time[0]=T3
        review=review_record(plan,at=T1,evaluation_stage='FINAL',data_complete=True)
        store.commit_bundle('late','review',[review])
        batch=freeze_batch(store,'historical',cutoff=T2)
        result={'test_only':True,'production_writes':False,'checked_at':now_iso(),'review_created':T1,'review_committed':T3,'batch_cutoff':T2,'observed_previous_review_ref':batch['items'][0]['previous_review_ref'],'observed_disposition':batch['items'][0]['disposition'],'expected_previous_review_ref':None,'passed':batch['items'][0]['previous_review_ref'] is None}
    Path(__file__).with_name('batch-cutoff-recheck.json').write_bytes(canonical(result))
    print(json.dumps(result,indent=2))
    if not result['passed']:
        raise SystemExit(1)

if __name__=='__main__':
    main()
