from fractions import Fraction as F
from pathlib import Path
import json,datetime
w=Path(__file__).resolve().parent
def mean(p,v):
 if len(p)!=len(v) or not p or any(x<=0 for x in v):raise ValueError('invalid positive weights')
 return sum(F(x)*F(y) for x,y in zip(p,v))/sum(map(F,v))
def remove(p,v,k):
 if len(p)<2 or not 0<=k<len(p):raise ValueError('invalid removal')
 b=mean(p,v);a=mean([x for j,x in enumerate(p) if j!=k],[x for j,x in enumerate(v) if j!=k]);f=F(v[k])/sum(map(F,v));return b,a,f/(1-f)*(b-F(p[k]))
def save(n,x):(w/n).write_text(json.dumps(x,ensure_ascii=False,indent=2))
checks=[]
for label,p,v,k,expected in [('low',[90,100,110],[1,1,1],0,F(5)),('high',[90,100,110],[1,1,1],2,F(-5)),('middle',[90,100,110],[1,1,1],1,F(0)),('flat',[100,100,100],[1,2,1],0,F(0))]:
 b,a,d=remove(p,v,k);assert a-b==d==expected;checks.append(label)
for p,v,k in [([100],[1],0),([90,100],[1,0],0),([90,100],[1,1],2)]:
 try:remove(p,v,k)
 except ValueError:checks.append('invalid_rejected')
 else:raise AssertionError('invalid accepted')
save('selftest.json',{'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':len(checks),'labels':checks,'result':'PASS','scope':'Synthetic arithmetic only; same author, no independent audit'})
p=json.loads((w/'protocol.json').read_text());rows=[]
for prices in [p['cases']['prices'],p['cases']['flat_control_prices']]:
 for weights in p['cases']['weight_sets']:
  for k in p['cases']['removal_indices']:
   b,a,d=remove(prices,weights,k);assert a-b==d
   # Separate original-sum accounting identity, exact rationals.
   total=sum(F(x)*y for x,y in zip(prices,weights));remain=sum(weights)-weights[k]
   assert a==(total-F(prices[k])*weights[k])/remain
   rows.append({'prices':prices,'weights':weights,'removed_index':k,'index_before':str(b),'index_after':str(a),'difference':str(a-b),'identity_matches':True})
save('results.json',{'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'data_kind':'SYNTHETIC_DIAGNOSTIC_NOT_MARKET','cases':rows,'total_cases':len(rows),'nonzero_differences':sum(x['difference']!='0' for x in rows),'economic_samples':0,'actual_net':None,'independent_audit':False})
print(json.dumps({'selftests':len(checks),'fixed_cases':len(rows),'nonzero_differences':sum(x['difference']!='0' for x in rows)}))
