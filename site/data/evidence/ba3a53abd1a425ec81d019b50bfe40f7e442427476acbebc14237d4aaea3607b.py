#!/usr/bin/env python3
"""Offline audit of an explicitly downloaded OKX funding CSV/ZIP. No network/API.
Original authored code: MIT. Upstream data is not relicensed by this file.
"""
import argparse,csv,datetime as dt,hashlib,io,json,zipfile
from collections import Counter
from decimal import Decimal
from pathlib import Path
D=Decimal
TARGETS={'aapl':'AAPL-USDT-SWAP','qqq':'QQQ-USDT-SWAP','btc':'BTC-USDT-SWAP','eth':'ETH-USDT-SWAP'}
def iso(ms): return dt.datetime.fromtimestamp(ms/1000,dt.timezone.utc).isoformat().replace('+00:00','Z')
def sha(b): return hashlib.sha256(b).hexdigest()
def analyze(path,protocol):
    raw=path.read_bytes(); member=None
    if path.suffix=='.zip':
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if z.testzip() is not None: raise ValueError('ZIP CRC failure')
            names=z.namelist()
            if len(names)!=1 or not names[0].endswith('.csv'): raise ValueError('Expected one CSV; no extraction performed')
            if z.getinfo(names[0]).file_size>50_000_000: raise ValueError('Sample exceeds safe audit size')
            member=names[0]; payload=z.read(member)
    else: payload=raw
    reader=csv.DictReader(io.StringIO(payload.decode('utf-8-sig')))
    if reader.fieldnames!=['instrument_name','funding_rate','funding_time']: raise ValueError('Unexpected schema')
    rows=list(reader); p=json.loads(protocol.read_text())
    start=int(dt.datetime.fromisoformat(p['sample_window']['start'].replace('Z','+00:00')).timestamp()*1000)
    end=int(dt.datetime.fromisoformat(p['sample_window']['end_exclusive'].replace('Z','+00:00')).timestamp()*1000)
    out={'schema_version':'1.0','analysis_kind':'REAL_HISTORICAL_DATA_AUDIT','synthetic':False,'protocol_sha256':sha(protocol.read_bytes()),'source_sha256':sha(raw),'source_bytes':len(raw),'member':member,'member_sha256':sha(payload),'member_bytes':len(payload),'total_rows':len(rows),'unique_instruments':len({r['instrument_name'] for r in rows}),'requested_utc_window':p['sample_window'],'products':{},'net_return':None,'current_execution_conditions':'UNKNOWN'}
    for product,symbol in TARGETS.items():
        selected=[r for r in rows if r['instrument_name']==symbol]
        pairs=sorted((int(r['funding_time']),D(r['funding_rate'])) for r in selected)
        if any(not rate.is_finite() for _,rate in pairs): raise ValueError('Non-finite rate')
        keys=[t for t,_ in pairs]; duplicate_count=len(keys)-len(set(keys))
        within=[(t,r) for t,r in pairs if start<=t<end]
        rates=[r for _,r in pairs]
        out['products'][product]={'instrument_ref':symbol,'row_count':len(pairs),'unique_event_count':len(set(keys)),'duplicate_timestamp_count':duplicate_count,'missing_value_count':sum(any(v=='' for v in r.values()) for r in selected),'first_event_at':iso(keys[0]) if keys else None,'last_event_at':iso(keys[-1]) if keys else None,'observed_intervals_hours':sorted({str(D(b-a)/D(3600000)) for a,b in zip(keys,keys[1:])}),'positive_count':sum(r>0 for r in rates),'negative_count':sum(r<0 for r in rates),'zero_count':sum(r==0 for r in rates),'sum_rates_diagnostic':str(sum(rates,D(0))),'sum_basis_points_diagnostic':str(sum(rates,D(0))*10000),'within_requested_utc_window_count':len(within),'outside_requested_utc_window_count':len(pairs)-len(within),'within_requested_window_sum_diagnostic':str(sum((r for _,r in within),D(0))),'requested_utc_day_complete':False,'quality_state':'FILENAME_UTC_WINDOW_MISMATCH' if any(not(start<=t<end) for t,_ in pairs) else 'NEEDS_EXPECTED_CALENDAR','cost_to_real_position':None}
    out['findings']={'all_four_native_ids_observed':all(x['row_count']>0 for x in out['products'].values()),'zero_interest_implies_zero_funding_refuted':any(out['products'][s]['positive_count']+out['products'][s]['negative_count']>0 for s in ('aapl','qqq')),'filename_as_utc_day_refuted':any(x['outside_requested_utc_window_count']>0 for x in out['products'].values()),'predictive_advantage':'NOT_TESTED','profitability':'UNKNOWN'}
    return out
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('input',type=Path);a.add_argument('--protocol',type=Path,default=Path(__file__).with_name('frozen_protocol.json'));a.add_argument('--out',type=Path);v=a.parse_args()
    result=json.dumps(analyze(v.input,v.protocol),ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    if v.out:v.out.write_text(result)
    else:print(result,end='')
