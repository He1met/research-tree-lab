from fractions import Fraction as F
from pathlib import Path
import json,datetime
w=Path(__file__).resolve().parent
p=json.loads((w/'protocol.json').read_text())
def mean(xs,ws):
 if not xs or len(xs)!=len(ws) or any(x<=0 for x in ws):raise ValueError('invalid positive weights or shape')
 return sum(F(x)*F(y) for x,y in zip(xs,ws))/sum(map(F,ws))
assert mean([2,4],[1,1])==3
assert mean([12,-6,0],[1,2,3])==0
assert mean([-12,6,0],[1,2,3])==0
assert mean([0,0,0],[1,2,3])==0
for xs,ws in [([],[]),([1],[1,2]),([1],[0])]:
 try:mean(xs,ws);raise AssertionError('accepted invalid input')
 except ValueError:pass
(w/'selftest.json').write_text(json.dumps({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':7,'status':'PASS','scope':'AUTHOR_ARITHMETIC_NOT_INDEPENDENT_AUDIT'}))
rows=[]
for xs in p['cases']:
 vals=[mean(xs[:k],p['weights'][:k]) for k in range(1,4)]
 assert vals[-1]==F(sum(x*y for x,y in zip(xs,p['weights'])),sum(p['weights']))
 rows.append({'premium_bps':xs,'prefix_weighted_premium_bps':[str(v) for v in vals]})
assert len(set(x['prefix_weighted_premium_bps'][0] for x in rows))==3
assert len(set(x['prefix_weighted_premium_bps'][-1] for x in rows))==1
(w/'results.json').write_text(json.dumps({'synthetic_only':True,'not_exchange_replica':True,'rows':rows,'same_terminal':'0','distinct_first_prefixes':3,'inference':'Terminal weighted mean cannot uniquely identify prefix state. Any deterministic function of equal terminal mean and equal other inputs remains equal.','economic_samples':0,'actual_net':None},indent=2))
print((w/'results.json').read_text())
