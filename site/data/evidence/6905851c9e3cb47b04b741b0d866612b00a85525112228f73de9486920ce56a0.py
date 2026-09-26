from fractions import Fraction as F
from pathlib import Path
import json,datetime
w=Path(__file__).resolve().parent

def component(path,q,entry):
 if not path or any(F(p)<=0 for p in path) or F(entry)<=0:raise ValueError('positive prices required')
 return F(q)*(sum(map(F,path))/len(path)-F(entry))
checks=0
for path,q,e,expected in [(['90','110'],'1','100',0),(['100','120'],'1','100',10),(['100','120'],'-1','100',-10),(['110'],'2','100',20)]:
 assert component(path,q,e)==expected;checks+=1
for path in [[],['0'],['-1']]:
 try:component(path,1,100)
 except ValueError:checks+=1
 else:raise AssertionError('invalid accepted')
(w/'selftest.json').write_text(json.dumps({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'synthetic':True,'checks_passed':checks,'independent_review':False},indent=2))
p=json.loads((w/'protocol.json').read_text());c=p['synthetic_cases'];rows=[]
for path in c['equal_weight_index_paths']:
 for q in c['signed_quantity']:
  exact=component(path,q,c['entry']);proxy=F(q)*(F(path[-1])-F(c['entry']))
  rows.append({'path':path,'q':q,'averaged_index_price_component':str(exact),'terminal_index_proxy_component':str(proxy),'proxy_error':str(proxy-exact),'actual_net':None})
(w/'results.json').write_text(json.dumps({'scope':'SIX_SYNTHETIC_PRICE_ROLE_CASES_ONLY','cases':rows,'different_cases':sum(x['proxy_error']!='0' for x in rows),'real_economic_samples':0,'actual_net':None,'complete_cost_scenario':False},indent=2))
print(json.dumps({'checks_passed':checks,'cases':len(rows),'different_cases':4,'actual_net':None}))
