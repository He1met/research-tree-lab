from pathlib import Path
import json
w=Path(__file__).resolve().parent
def ledger(o,c,t,initial=100):
 for x in (o,c,t,initial):
  if type(x) is not int or x<0:raise ValueError('nonnegative integer contracts required')
 if c>initial:raise ValueError('fixed close-first construction exceeds initial OI')
 return {'volume':o+c+t,'delta_oi':o-c,'ending_oi':initial+o-c,'both_open':o,'both_close':c,'transfer':t}
# Before study: independently specified hand results and invalid inputs.
assert ledger(1,0,0)=={'volume':1,'delta_oi':1,'ending_oi':101,'both_open':1,'both_close':0,'transfer':0}
assert ledger(0,1,0)['delta_oi']==-1
assert ledger(0,0,1)['delta_oi']==0
assert ledger(0,0,0)['volume']==0
invalid=[(-1,0,0),(0,101,0),(True,0,0),(1.0,0,0)]
for args in invalid:
 try:ledger(*args)
 except ValueError:pass
 else:raise AssertionError(args)
(w/'selftest.json').write_text(json.dumps({'state':'PASS','checks':8,'scope':'Author hand and invalid-input checks before fixed four diagnostic cases; no independent audit or market sample'},indent=2))
p=json.loads((w/'protocol.json').read_text());out=[]
for case in p['fixed_cases']:
 row=ledger(case['both_open'],case['both_close'],case['transfer'],p['initial_oi']);row['name']=case['name']
 # Separate event construction: closing removes equal long and short contracts;
 # opening adds equal sides; a transfer replaces a holder and changes neither total.
 long=short=p['initial_oi'];volume=0
 for event,n in [('close',case['both_close']),('open',case['both_open']),('transfer',case['transfer'])]:
  for _ in range(n):
   if event=='close':long-=1;short-=1
   elif event=='open':long+=1;short+=1
   volume+=1
   assert long==short and long>=0
 assert long==row['ending_oi'] and volume==row['volume']
 out.append(row)
assert (out[0]['volume'],out[0]['delta_oi'])==(out[1]['volume'],out[1]['delta_oi'])
assert (out[2]['volume'],out[2]['delta_oi'])==(out[3]['volume'],out[3]['delta_oi'])
result={'state':'NON_UNIQUE_COMPOSITION_PROVEN_IN_MATCHED_CONTRACT_MODEL','cases':out,'case_count':4,'pair_equalities':2,'event_construction_checks':40,'economic_samples':0,'actual_net':None,'historical_oi_acquired':False,'directional_predictive_value':'NOT_TESTED','synthetic_diagnostic':True,'scope':'Single-sided OI and single-count matched volume in fixed integer-contract model. Net long contracts minus short contracts remains zero by accounting; this does not rule out forecasting information conditional on price or other data.'}
(w/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
