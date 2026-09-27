from pathlib import Path
import csv,io,zipfile,json,hashlib,datetime
from collections import Counter
from fractions import Fraction
w=Path(__file__).resolve().parent

def census(rows,start,bins):
 out=[[0,0] for _ in range(bins)];n=0
 for ts,source in rows:
  if source not in ('0','1'):raise ValueError('UNKNOWN_SOURCE_CODE')
  b=(ts-start)//60000
  if b<0 or b>=bins:raise ValueError('OUTSIDE_PARTITION')
  out[b][int(source)]+=1;n+=1
 assert sum(map(sum,out))==n
 return out
cases=[([],[[0,0],[0,0]]), ([(0,'0')],[[1,0],[0,0]]), ([(0,'1'),(59999,'0'),(60000,'1')],[[1,1],[0,1]]), ([(0,'1'),(0,'1')],[[0,2],[0,0]])]
for rows,expected in cases:assert census(rows,0,2)==expected
for rows in [[(0,'2')],[(120000,'0')],[(-1,'0')]]:
 try:census(rows,0,2)
 except ValueError:pass
 else:raise AssertionError('expected refusal')
(w/'selftest.json').write_text(json.dumps({'passed':7,'synthetic_only':True,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'deviation':'Official search and two documentary page reads occurred before these tests; no real raw row analysis occurred before tests. Frozen count scope unchanged.'},indent=2))
protocol=json.loads((w/'protocol.json').read_text()); results=[]
root=Path.cwd()/'.local/data/objects'
for item in protocol['inputs']:
 d=item['dataset'];path=root/d['sha256'];raw=path.read_bytes();assert len(raw)==d['bytes'];assert hashlib.sha256(raw).hexdigest()==d['sha256']
 day=d['quality']['declared_partition']['date'];dt=datetime.datetime.fromisoformat(day).replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8)));start=int(dt.timestamp()*1000)
 direct=Counter();rows_read=0;min_ts=None;max_ts=None
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  assert len(z.namelist())==1
  with z.open(z.namelist()[0]) as f:
   reader=csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig'));header=reader.fieldnames
   assert header==['instrument_name','trade_id','side','price','size','created_time','source'],header
   def rows():
    global rows_read,min_ts,max_ts
    for r in reader:
     assert r['instrument_name']=='BTC-USDT-SWAP'
     ts=int(r['created_time']);source=r['source'];rows_read+=1;direct[source]+=1
     min_ts=ts if min_ts is None else min(min_ts,ts);max_ts=ts if max_ts is None else max(max_ts,ts)
     yield ts,source
   bins=census(rows(),start,1440)
 totals=[sum(x[i] for x in bins) for i in (0,1)];assert totals==[direct['0'],direct['1']];assert sum(totals)==rows_read
 fractions=[Fraction(b,a+b) for a,b in bins if a+b];maximum=max(fractions) if fractions else None
 result={'dataset_ref':item['dataset_ref'],'sha256':d['sha256'],'partition_label_utc8':day,'rows':rows_read,'source0_rows':totals[0],'source1_rows':totals[1],'source1_fraction':str(Fraction(totals[1],rows_read)),'source1_percent':100*totals[1]/rows_read,'bins':1440,'file_empty_bins':sum(a+b==0 for a,b in bins),'source1_present_bins':sum(b>0 for a,b in bins),'source1_only_bins':sum(a==0 and b>0 for a,b in bins),'max_minute_source1_fraction':str(maximum),'max_minute_source1_percent':float(maximum*100) if maximum is not None else None,'source_pooling_changes_count_bins':sum(b!=0 for a,b in bins),'min_timestamp':min_ts,'max_timestamp':max_ts,'header':header,'zip_crc':'FULL_MEMBER_READ_OK','secondary_check':'Direct source Counter equals sum of minute bins; same-author structural check, not independent audit'}
 results.append(result)
 with (w/('minute-counts-'+day+'.csv')).open('w') as f:
  out=csv.writer(f);out.writerow(['minute_start_epoch_ms','source0_rows','source1_rows','all_rows'])
  for j,(a,b) in enumerate(bins):out.writerow([start+j*60000,a,b,a+b])
(w/'results.json').write_text(json.dumps({'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':results,'actual_net':None,'economic_samples':0,'scope':'Archived row-count census; not true market coverage, aggressor flow or matching-engine execution count'},indent=2))
print(json.dumps(results,ensure_ascii=False))
