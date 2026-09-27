"""Synthetic positive-fee component only. Copy to scratch before reproduction."""
from decimal import Decimal as D, ROUND_FLOOR, ROUND_HALF_UP
from fractions import Fraction as F
from pathlib import Path
import json,datetime
W=Path(__file__).resolve().parent
MODES={'FLOOR':ROUND_FLOOR,'HALF_UP':ROUND_HALF_UP}
def calc(parts,rate,quantum,mode):
 p=[D(x) for x in parts];r=D(rate);q=D(quantum)
 if not p or not all(x.is_finite() and x>0 for x in p) or not r.is_finite() or r<0 or not q.is_finite() or q<=0 or mode not in MODES:raise ValueError('invalid positive fee component input')
 quant=lambda x:(x/q).to_integral_value(rounding=MODES[mode])*q
 exact=sum(p)*r; per=sum(quant(x*r) for x in p); agg=quant(exact)
 assert F(exact)==sum(F(x) for x in p)*F(r)
 return {'partition':parts,'mode':mode,'exact':str(exact),'aggregate_rounded':str(agg),'per_fill_rounded':str(per),'difference':str(per-agg)}
def main():
 tests=[]
 for mode,expect in [('FLOOR','0.48'),('HALF_UP','0.51')]:
  assert D(calc(['333','333','334'],'0.0005','0.01',mode)['per_fill_rounded'])==D(expect);tests.append(mode+' hand counterexample')
 assert D(calc(['1000'],'0.0005','0.01','FLOOR')['difference'])==0;tests.append('one fill identity')
 assert D(calc(['100']*10,'0.0005','0.01','HALF_UP')['difference'])==0;tests.append('exact quantum identity')
 assert D(calc(['10'],'0','0.01','FLOOR')['exact'])==0;tests.append('zero specified rate')
 for parts,rate,q,mode in [([],'.1','.01','FLOOR'),(['-1'],'.1','.01','FLOOR'),(['1'],'-.1','.01','FLOOR'),(['1'],'.1','0','FLOOR'),(['1'],'.1','.01','UNKNOWN'),(['NaN'],'.1','.01','FLOOR')]:
  try:calc(parts,rate,q,mode)
  except ValueError:tests.append('invalid rejected')
  else:raise AssertionError('invalid accepted')
 (W/'selftest.json').write_text(json.dumps({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':len(tests),'tests':tests,'independent_audit':False},indent=2))
 p=json.loads((W/'protocol.json').read_text());out=[calc(v,p['rate'],p['quantum'],m) for v in p['comparison_set'] for m in p['rounding_modes']]
 (W/'results.json').write_text(json.dumps({'scope':'SYNTHETIC_POSITIVE_FEE_COMPONENT','cases':out,'actual_net':None,'economic_samples':0},indent=2));print(json.dumps(out))
if __name__=='__main__':main()
