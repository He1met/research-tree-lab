"""Frozen exposed-history diagnostic; no economics, network or source writes.
Reproduce from a scratch copy: python3 calculate.py --data <exact ZIP> --output <new dir>.
"""
import argparse,csv,datetime,hashlib,io,json,zipfile
from decimal import Decimal,localcontext
from fractions import Fraction as F
from pathlib import Path
HASH='5595c6777328eb5f392520fdf6bd9c59518018991c7f92dd376ce04b1c353287'
HEADER=['instrument_name','open','high','low','close','vol','vol_ccy','vol_quote','open_time','confirm']
START=int(datetime.datetime(2026,9,20,16,tzinfo=datetime.timezone.utc).timestamp()*1000)
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def display(v):
 if v is None:return None
 with localcontext() as c:
  c.prec=50;return str(Decimal(v.numerator)/Decimal(v.denominator))
def stats(prices):
 pairs=[(prices[i]-prices[i-1],prices[i-1]-prices[i-2]) for i in range(2,len(prices)) if all(prices[j] is not None for j in (i,i-1,i-2))]
 n=len(pairs)
 if n<2:return n,None,pairs
 mx=sum(x for x,y in pairs)/n;my=sum(y for x,y in pairs)/n
 cov=sum((x-mx)*(y-my) for x,y in pairs)/(n-1)
 return n,cov,pairs

def grids(minutes,k,total):
 return [minutes.get(b+k-1) if all(i in minutes for i in range(b,b+k)) else None for b in range(0,total,k)]

def decode(rows,total=1440):
 out={};previous=None
 for row in rows:
  if row['instrument_name']!='BTC-USDT-SWAP':raise ValueError('contract mismatch')
  t=int(row['open_time']);delta=t-START
  if delta<0 or delta>=total*60000 or delta%60000:raise ValueError('timestamp outside aligned window')
  if previous is not None and t<=previous:raise ValueError('duplicate or decreasing timestamp')
  previous=t
  if row['confirm']!='1':raise ValueError('unconfirmed candle')
  d=Decimal(row['close'])
  if not d.is_finite() or d<=0:raise ValueError('invalid close')
  out[delta//60000]=F(d)
 return out

def selftest():
 checks=[]
 def ck(name,v):
  assert v,name;checks.append(name)
 ck('alternating hand covariance',stats(list(map(F,[100,102,100,102,100])))[1]==F(-16,3))
 ck('positive hand covariance',stats(list(map(F,[1,2,4,7,11])))[1]==1)
 ck('constant changes zero covariance',stats(list(map(F,[1,2,3,4])))[1]==0)
 ck('one pair insufficient',stats(list(map(F,[1,2,3])))[1] is None)
 ck('missing bars never bridged',stats([F(1),F(2),None,F(4),F(5),F(6),F(7)])[0:2]==(2,F(0)))
 ck('right endpoint grid',grids({i:F(i+1) for i in range(6)},2,6)==list(map(F,[2,4,6])))
 ck('internal missing invalidates bin',grids({0:F(1),2:F(3),3:F(4)},2,4)==[None,F(4)])
 base={'instrument_name':'BTC-USDT-SWAP','open_time':str(START),'confirm':'1','close':'100.1'}
 ck('decimal exact parse',decode([base],1)[0]==F(1001,10))
 for name,rows in [('duplicate',[base,base]),('wrong contract',[dict(base,instrument_name='ETH-USDT-SWAP')]),('nonfinite',[dict(base,close='NaN')]),('unaligned',[dict(base,open_time=str(START+1))]),('unconfirmed',[dict(base,confirm='0')])]:
  try:decode(rows,2)
  except ValueError:checks.append(name+' rejected')
  else:raise AssertionError(name)
 return {'kind':'AUTHOR_SYNTHETIC_SELFTEST_NOT_MARKET_EVIDENCE','completed_at':stamp(),'passed':len(checks),'checks':checks}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--data',required=True);ap.add_argument('--output',required=True);a=ap.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
 save(out/'selftest.json',selftest()) # complete before reading market bytes
 started=stamp();raw=Path(a.data).read_bytes();assert hashlib.sha256(raw).hexdigest()==HASH
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  assert z.namelist()==['BTC-USDT-SWAP-candlesticks-2026-09-21.csv'];assert z.testzip() is None
  reader=csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode('utf-8-sig')));assert reader.fieldnames==HEADER
  mins=decode(reader)
 results=[];checks=[]
 for k in (1,5,15):
  prices=grids(mins,k,1440);n,c,pairs=stats(prices)
  # Alternate direct moment estimator, exact rational; same author, not independent audit.
  alt=(sum(x*y for x,y in pairs)-sum(x for x,y in pairs)*sum(y for x,y in pairs)/n)/(n-1) if n>=2 else None
  assert c==alt
  # Separate direct endpoint loop validates pairing without calling grids/stats.
  independent=[]
  for endpoint in range(3*k-1,1440,k):
   if all(j in mins for j in range(endpoint-3*k+1,endpoint+1)):
    independent.append((mins[endpoint]-mins[endpoint-k],mins[endpoint-k]-mins[endpoint-2*k]))
  assert independent==pairs
  implied=None
  if c is not None and c<0:
   with localcontext() as context:
    context.prec=50;implied=str(2*(-Decimal(c.numerator)/Decimal(c.denominator)).sqrt())
  results.append({'grid_minutes':k,'bins':len(prices),'missing_bins':sum(p is None for p in prices),'valid_lag_pairs':n,'covariance_exact':str(c) if c is not None else None,'covariance':display(c),'covariance_unit':'(USDT/BTC)^2','sign':'NEGATIVE' if c is not None and c<0 else ('NONNEGATIVE' if c is not None else 'INSUFFICIENT'),'conditional_roll_proxy':implied,'proxy_unit':'USDT/BTC','spread_identification':'CONDITIONAL_MODEL_PROXY_ONLY' if implied is not None else 'NOT_IDENTIFIED','actual_cost':None})
  checks.append({'grid_minutes':k,'alternate_exact_moment_formula':'PASS','direct_endpoint_pairs':'PASS'})
 res={'started_at':started,'completed_at':stamp(),'data_sha256':HASH,'bytes':len(raw),'input_rows':len(mins),'missing_minutes':1440-len(mins),'prior_exposure':'EXPOSED_DEVELOPMENT_ONLY','window':['2026-09-20T16:00:00Z','2026-09-21T16:00:00Z'],'results':results,'all_three_strictly_negative':all(x['sign']=='NEGATIVE' for x in results),'economic_samples':0,'actual_net':None,'quote_attribution':'UNKNOWN_NOT_TESTED','source_completeness':'UNKNOWN','same_ms_chronology':'UNKNOWN','parameter_search':False}
 save(out/'results.json',res);save(out/'crosscheck.json',{'kind':'SAME_AUTHOR_ALTERNATE_FORMULA_AND_PAIR_CONSTRUCTION','checks':checks,'independent_audit':False});print(json.dumps(res,ensure_ascii=False))
if __name__=='__main__':main()
