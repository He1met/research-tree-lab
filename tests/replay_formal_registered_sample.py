"""Read existing registered bytes through the fixed formal resolver, decode only.

No plan computation, production writes, network, or copied raw data. A new
redacted receipt is reserved with the previously audited create-only helper.
"""
import argparse
import json
from pathlib import Path
import platform
import sys
import time
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from researchlib.common import canonical, digest, under
from researchlib import formal_review as fr
from researchlib.funding_review import readonly_store
from replay_okx_trade_sample import new_receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root',required=True)
    parser.add_argument('--receipt',required=True,type=Path,help='New path; never an existing receipt')
    args=parser.parse_args()
    store=readonly_store(args.project_root)
    records,metadata,anomalies=store.load(strict=True)
    if anomalies:raise ValueError('Store integrity anomaly')
    dataset_ref='d-btc-trades-20260921@1';dataset=records[dataset_ref]
    source=under(store.data_root,'objects/'+dataset['sha256'])
    dataset_file=under(store.root/'bundles'/metadata[dataset_ref]['bundle_id'], 'records/dataset/'+dataset_ref+'.json')
    before={key:digest(canonical(value)) for key,value in records.items()}
    at=store.clock();method,_=fr.method_material(at)
    request={'dataset_ref':dataset_ref,'adapter':fr.legacy.TRADE_ADAPTER,
        'filename':'BTC-USDT-SWAP-trades-2026-09-21.zip',
        'declared_partition':{'date':'2026-09-21','timezone':'UTC+08:00'},
        'window':{'start_inclusive':'2026-09-20T16:00:00Z','end_exclusive':'2026-09-20T16:00:01Z'}}
    with new_receipt(args.receipt,source,dataset_file) as stream:
        started=time.monotonic()
        with patch.object(fr,'_compute',side_effect=AssertionError('Economic computation forbidden')):
            resolved=fr._resolve_sources(store,records[sorted(fr.PLAN_HASHES)[0]],[request],records,metadata,at,
                                         '2026-09-20T16:00:01Z',fr._context())
        elapsed=time.monotonic()-started
        after,_,_=store.load(strict=True);audit=resolved.audits[0]
        checks={'complete_decode':audit['rows_read']==4_969_733 and audit['csv_bytes']==295_527_908,
            'selected_count':len(resolved.payload['events'])==112,
            'all_sequence_null':all(e['sequence'] is None for e in resolved.payload['events']),
            'no_formal_capabilities':not resolved.capabilities and resolved.actual_costs is None,
            'coverage_unknown':resolved.payload['source_coverage']=='UNKNOWN' and not resolved.payload['data_complete'],
            'existing_record_bytes_unchanged':all(digest(canonical(after[k]))==v for k,v in before.items()),
            'no_kernel_or_review_preparation':True}
        receipt={'state':'PASS_SCOPED_REGISTERED_DECODE_ONLY' if all(checks.values()) else 'FAILED',
            'evidence_class':'REAL_EXISTING_FILE_READ_ONLY_NOT_ECONOMIC_REVIEW',
            'information_as_of':at,'method_code_sha256':method['method_code_sha256'],
            'method_source_files':len(method['source_sha256']),
            'module_sha256':digest(Path(fr.__file__).read_bytes()),
            'dataset_ref':dataset_ref,'binding':resolved.bindings[0],
            'rows_decoded':audit['rows_read'],'csv_bytes':audit['csv_bytes'],'csv_sha256':audit['csv_sha256'],
            'zip_crc':audit['zip_crc'],'selected_event_count':len(resolved.payload['events']),
            'source_coverage':'UNKNOWN','granted_business_capabilities':[],
            'formal_plan_evaluation_run':False,'production_write':False,'raw_output_saved':False,
            'checks':checks,'elapsed_seconds':round(elapsed,3),'python':platform.python_version(),
            'independent_review':'PENDING'}
        stream.write(canonical(receipt).decode());stream.flush()
    print(json.dumps({'state':receipt['state'],'rows_decoded':receipt['rows_decoded'],'economic_review':False}))
    return 0 if all(checks.values()) else 1


if __name__=='__main__':raise SystemExit(main())
