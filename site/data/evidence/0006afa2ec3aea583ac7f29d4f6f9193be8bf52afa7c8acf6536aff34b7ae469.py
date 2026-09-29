"""Frozen single-grid file-proxy diagnostic. Run a scratch copy, never sealed originals."""
import math, csv, io, zipfile, json, hashlib, datetime, argparse
from decimal import Decimal as D, localcontext
from pathlib import Path
HASH='5595c6777328eb5f392520fdf6bd9c59518018991c7f92dd376ce04b1c353287'
START=1600000000000 # replaced below by explicit UTC partition boundary
START=int(datetime.datetime(2026,9,20,16,tzinfo=datetime.timezone.utc).timestamp()*1000)
HEADER=['instrument_name','open','high','low','close','vol','vol_ccy','vol_quote','open_time','confirm']
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def decode(rows,total=1440):
 result=[]
 for i,row in enumerate(rows):
  if row['instrument_name']!='BTC-USDT-SWAP': raise ValueError('CONTRACT')
  if row['open_time']!=str(START+i*60000): raise ValueError('TIME_SEQUENCE')
  if row['confirm']!='1': raise ValueError('UNCONFIRMED')
  p=D(row['close'])
  if not p.is_finite() or p<=0: raise ValueError('INVALID_CLOSE')
  result.append(p)
 if len(result)!=total: raise ValueError('COUNT')
 return result

def fstats(r):
 rv=math.fsum(x*x for x in r); bv=math.pi/2*math.fsum(abs(a)*abs(b) for a,b in zip(r[1:],r[:-1]))
 return rv,bv,rv-bv

def dpi():
 # Chudnovsky, 6 terms (>80 decimal digits), evaluated under caller's 60-digit context.
 s=D(0)
 for k in range(6):
  s+=D((-1)**k*math.factorial(6*k)*(13591409+545140134*k))/D(math.factorial(3*k)*math.factorial(k)**3*640320**(3*k))
 return D(426880)*D(10005).sqrt()/s

def tests():
 checks=[]
 def ck(n,v):
  if not v: raise AssertionError(n)
  checks.append(n)
 ck('constant returns zero',fstats([0.,0.,0.])==(0.,0.,0.))
 ck('single isolated impulse',fstats([0.,2.,0.])==(4.,0.,4.))
 v=fstats([1.,-1.,1.]);ck('negative difference retained',v==(3.,math.pi,3.-math.pi) and v[2]<0)
 base={'instrument_name':'BTC-USDT-SWAP','open_time':str(START),'confirm':'1','close':'100'}
 ck('exact close parse',decode([base],1)==[D(100)])
 for name,rows,total in [('missing',[],1),('duplicate',[base,base],2),('wrong contract',[dict(base,instrument_name='ETH-USDT-SWAP')],1),('invalid',[dict(base,close='NaN')],1),('nonpositive',[dict(base,close='0')],1),('unaligned',[dict(base,open_time=str(START+1))],1),('unconfirmed',[dict(base,confirm='0')],1)]:
  try: decode(rows,total)
  except ValueError: checks.append(name+' rejected')
  else: raise AssertionError(name)
 ck('five-minute endpoints',list(range(15))[4::5]==[4,9,14])
 with localcontext() as c:
  c.prec=60
  ck('decimal pi independent',abs(dpi()-D('3.14159265358979323846264338327950288419716939937510582097494459'))<D('1e-57'))
  ck('decimal logarithm hand case',abs(D(2).ln()*2-D(4).ln())<D('1e-58'))
 return {'completed_at':now(),'kind':'AUTHOR_SYNTHETIC_SELFTEST_NOT_MARKET_EVIDENCE','passed':len(checks),'checks':checks}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--data',required=True);ap.add_argument('--output',required=True);args=ap.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
 save(out/'selftest.json',tests())
 started=now();raw=Path(args.data).read_bytes()
 if hashlib.sha256(raw).hexdigest()!=HASH: raise ValueError('HASH')
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  if z.namelist()!=['BTC-USDT-SWAP-candlesticks-2026-09-21.csv'] or z.testzip() is not None: raise ValueError('ZIP')
  text=z.read(z.namelist()[0]).decode('utf-8-sig');reader=csv.DictReader(io.StringIO(text))
  if reader.fieldnames!=HEADER: raise ValueError('HEADER')
  prices=decode(reader)
 endpoints=prices[4::5];r=[math.log(float(b)/float(a)) for a,b in zip(endpoints[:-1],endpoints[1:])];f=fstats(r)
 with localcontext() as c:
  c.prec=60
  # Separate CSV loop and index selection, log differences instead of log ratio.
  rows=list(csv.DictReader(io.StringIO(text))); logs=[]
  for j,row in enumerate(rows):
   if (j+1)%5==0: logs.append(D(row['close']).ln())
  dr=[logs[j]-logs[j-1] for j in range(1,len(logs))]
  rv=sum((x*x for x in dr),D(0));bv=dpi()/2*sum((abs(dr[j])*abs(dr[j-1]) for j in range(1,len(dr))),D(0));d=rv-bv
  tol=D('1e-12')*max(rv,bv,D('1e-12'));delta=[abs(D.from_float(a)-b) for a,b in zip(f,[rv,bv,d])]
  if len(endpoints)!=288 or len(r)!=287 or any(x>tol for x in delta): raise ValueError('CROSSCHECK')
  sign='POSITIVE' if d>tol else ('NEGATIVE' if d < -tol else 'NUMERICALLY_UNRESOLVED')
  res={'started_at':started,'completed_at':now(),'data_sha256':HASH,'bytes':len(raw),'input_rows':len(prices),'endpoints':len(endpoints),'returns':len(r),'adjacent_return_pairs':len(r)-1,'grid_minutes':5,'partition':['2026-09-20T16:00:00Z','2026-09-21T16:00:00Z'],'selected_candle_open_support':['2026-09-20T16:04:00Z','2026-09-21T15:59:00Z'],'nominal_candle_close_support':['2026-09-20T16:05:00Z','2026-09-21T16:00:00Z'],'exact_last_trade_timestamps':'UNKNOWN','boundary_note':'First selected close is minute index4, nominal end16:05; no earlier return and no out-of-window price. Last selected close is minute1439.','RV':str(rv),'BV':str(bv),'D':str(d),'unit':'squared log return, dimensionless','float64':dict(zip(['RV','BV','D'],f)),'crosscheck_absolute_differences':[str(x) for x in delta],'tolerance':str(tol),'sign':sign,'exposure':'EXPOSED_DEVELOPMENT_ONLY','actual_net':None,'economic_samples':0,'jump_attribution':'NOT_IDENTIFIED','source_completeness':'UNKNOWN','same_ms_chronology':'UNKNOWN','independent_audit':False,'parameter_search':False}
 save(out/'results.json',res); print(json.dumps(res,ensure_ascii=False))
if __name__=='__main__': main()
