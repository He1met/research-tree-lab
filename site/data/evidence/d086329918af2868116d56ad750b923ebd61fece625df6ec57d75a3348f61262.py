"""Data-qualification diagnostic only; no strategy or market return calculation."""
import csv,io,json,zipfile,hashlib,datetime
from pathlib import Path
from decimal import Decimal
HEADER=['instrument_name','trade_id','side','price','size','created_time','source']
def scan(stream):
 reader=csv.DictReader(stream)
 if reader.fieldnames!=HEADER:raise ValueError('schema mismatch')
 n=0;times=[];symbols=set();bad=0;previous=None;decreasing=0;ids=set();duplicates=0
 for row in reader:
  if None in row or any(v is None or v=='' for v in row.values()):raise ValueError('missing cell')
  price,size=Decimal(row['price']),Decimal(row['size'])
  if not price.is_finite() or not size.is_finite() or price<=0 or size<=0:raise ValueError('invalid numeric field')
  t=int(row['created_time']);assert t>0
  symbols.add(row['instrument_name']);times.append(t);n+=1
  decreasing+=int(previous is not None and t<previous);previous=t
  duplicates+=int(row['trade_id'] in ids);ids.add(row['trade_id'])
 def stamp(t):return datetime.datetime.fromtimestamp(t/1000,datetime.timezone.utc).isoformat()
 return {'rows':n,'instruments':sorted(symbols),'min_event_at':stamp(min(times)) if times else None,'max_event_at':stamp(max(times)) if times else None,'timestamp_decreases_in_file_order':decreasing,'duplicate_trade_id_rows':duplicates,'schema':HEADER,'source_completeness':'UNKNOWN','same_ms_exchange_order':'UNKNOWN','side_semantics':'NOT_QUALIFIED','size_unit':'NOT_QUALIFIED','mark_price':'NOT_PRESENT','economic_samples':0,'actual_net':None}
def selftest():
 head=','.join(HEADER)+'\n';row='AAPL-USDT-SWAP,1,buy,100,1,1790265600000,0\n'
 a=scan(io.StringIO(head+row));assert a['rows']==1 and a['min_event_at']=='2026-09-24T16:00:00+00:00'
 assert scan(io.StringIO(head))['min_event_at'] is None
 assert scan(io.StringIO(head+row+row))['duplicate_trade_id_rows']==1
 for bad in [head.replace('side','SIDE')+row,head+row.replace(',100,',',NaN,'),head+row.replace(',100,',',-1,'),head+row.replace(',buy,',',,')]:
  try:scan(io.StringIO(bad))
  except ValueError:pass
  else:raise AssertionError('bad input accepted')
 return {'tests':7,'state':'PASS','type':'AUTHOR_SYNTHETIC_SCHEMA_TESTS_NOT_MARKET_EVIDENCE','completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
if __name__=='__main__':
 import sys
 w=Path(__file__).resolve().parent
 if sys.argv[1]=='test':result=selftest();name='selftest.json'
 else:
  p=Path(sys.argv[2]);b=p.read_bytes()
  with zipfile.ZipFile(io.BytesIO(b)) as z:
   assert z.namelist()==['AAPL-USDT-SWAP-trades-2026-09-25.csv'];assert z.testzip() is None
   with z.open(z.namelist()[0]) as f:result=scan(io.TextIOWrapper(f,encoding='utf-8-sig',newline=''))
  assert result['instruments']==['AAPL-USDT-SWAP'];result.update(sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),zip_crc='PASS',completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat());name='results.json'
 (w/name).write_text(json.dumps(result,indent=2));print(json.dumps(result))
