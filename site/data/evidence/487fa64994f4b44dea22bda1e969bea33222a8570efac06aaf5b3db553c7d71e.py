"""Timestamp-only development diagnostic; no prices, economic returns or fills."""
import bisect,csv,datetime,hashlib,io,json,sys,zipfile
from pathlib import Path

def diagnose(ts,start,end,width=60000):
 if end<=start or width<=0 or (end-start)%width:raise ValueError('invalid grid')
 if any(type(t)!=int or not start<=t<end for t in ts):raise ValueError('out of range timestamp')
 if any(a>b for a,b in zip(ts,ts[1:])):raise ValueError('decreasing timestamps')
 n=(end-start)//width;counts=[0]*n
 for t in ts:counts[(t-start)//width]+=1
 ages=[]
 for t in range(start+width,end+1,width):
  j=bisect.bisect_left(ts,t)-1;ages.append(t-ts[j] if j>=0 else None)
 empty_runs=[];run=0
 for count in counts+[1]:
  if count==0:run+=1
  elif run:empty_runs.append(run);run=0
 return {'counts':counts,'endpoint_age_ms':ages,'summary':{'rows':len(ts),'minutes':n,'occupied_minutes':sum(c>0 for c in counts),'empty_minutes':counts.count(0),'empty_run_count':len(empty_runs),'max_empty_run_minutes':max(empty_runs,default=0),'endpoints_without_prior_observation':ages.count(None),'max_endpoint_age_ms':max((v for v in ages if v is not None),default=None),'endpoint_age_strictly_greater_than_ms':{str(x):sum(v is not None and v>x for v in ages) for x in [60000,300000,900000]},'max_adjacent_event_gap_ms':max((b-a for a,b in zip(ts,ts[1:])),default=None)}}

def test():
 x=diagnose([0,60000,60000,179999],0,180000)
 assert x['counts']==[1,2,1] and x['endpoint_age_ms']==[60000,60000,1]
 x=diagnose([1,180001],0,240000)
 assert x['counts']==[1,0,0,1] and x['endpoint_age_ms']==[59999,119999,179999,59999]
 assert x['summary']['max_empty_run_minutes']==2 and x['summary']['endpoint_age_strictly_greater_than_ms']['60000']==2
 x=diagnose([120000],0,180000)
 assert x['counts']==[0,0,1] and x['endpoint_age_ms']==[None,None,60000]
 x=diagnose([],0,180000);assert x['summary']['max_empty_run_minutes']==3 and x['summary']['max_endpoint_age_ms'] is None
 for ts,s,e in [([180000],0,180000),([-1],0,180000),([2,1],0,180000),([1.0],0,180000),([],0,1)]:
  try:diagnose(ts,s,e)
  except ValueError:pass
  else:raise AssertionError('invalid input accepted')
 return {'state':'PASS','cases':10,'scope':'AUTHOR_HAND_BOUNDARY_AND_INVALID_INPUT_TESTS_NOT_INDEPENDENT_AUDIT','completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}

if __name__=='__main__':
 w=Path(__file__).resolve().parent
 if sys.argv[1]=='test':
  result=test();(w/'selftest.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));sys.exit()
 protocol=json.loads((w/'protocol.json').read_text());b=Path(sys.argv[2]).read_bytes();assert hashlib.sha256(b).hexdigest()==protocol['sha256']
 with zipfile.ZipFile(io.BytesIO(b)) as z:
  assert z.namelist()==['AAPL-USDT-SWAP-trades-2026-09-25.csv'];assert z.testzip() is None
  with z.open(z.namelist()[0]) as f:
   reader=csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig',newline=''))
   assert reader.fieldnames==['instrument_name','trade_id','side','price','size','created_time','source']
   ts=[]
   for row in reader:
    assert row['instrument_name']=='AAPL-USDT-SWAP';ts.append(int(row['created_time']))
 start,end=[int(datetime.datetime.fromisoformat(x.replace('Z','+00:00')).timestamp()*1000) for x in protocol['interval']]
 x=diagnose(ts,start,end);(w/'private-minute-diagnostic.json').write_text(json.dumps(x,indent=2))
 # A separate simple loop checks all bin counts and strict endpoint event selection.
 for i,(count,age) in enumerate(zip(x['counts'],x['endpoint_age_ms'])):
  lo=start+i*60000;hi=lo+60000
  assert count==sum(lo<=t<hi for t in ts)
  prior=[t for t in ts if t<hi];assert age==(hi-max(prior) if prior else None)
 result=dict(x['summary'],dataset_ref=protocol['dataset_ref'],sha256=protocol['sha256'],interval=protocol['interval'],completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_completeness='UNKNOWN',economic_samples=0,actual_net=None,price_return_computation='NOT_PERFORMED',crosscheck='ALL_BINS_AND_AGES_MATCH_SIMPLE_LOOP',hypothesis='REJECTED' if x['summary']['empty_minutes'] else 'NOT_REJECTED_IN_THIS_FILE')
 (w/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
