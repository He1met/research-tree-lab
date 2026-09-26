import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const root=resolve(process.argv[2]);
const {chromium,webkit}=await import(pathToFileURL(root+'/web/node_modules/@playwright/test/index.mjs'));
const outputs=[];
for(const [name,engine] of [['chromium',chromium],['webkit',webkit]]){
 const browser=await engine.launch();
 try{
 const page=await browser.newPage();
 await page.route('**/data/**',route=>{
  const part=new URL(route.request().url()).pathname.split('/data/')[1];
  try{return route.fulfill({contentType:'application/json',body:readFileSync(resolve(root,'replay-data',part))});}
  catch{return route.fulfill({status:404,body:'{}'});}
 });
 await page.goto('http://127.0.0.1:5197/');
 await page.locator('.canvas[data-snapshot]').waitFor();
 const result=await page.evaluate(async()=>{
  const d=await import('/src/data.ts');const r=await import('/src/related.ts');
  const snapshot=await d.loadSnapshot();
  const ref='run-tier-history-probe-20260927@attempt-1';
  const first=await d.loadRecord(ref,snapshot);
  const reject=async(fn)=>{try{await fn();return 'UNEXPECTED_ACCEPTANCE';}catch(e){return String(e);}};
  const cacheLimit=await reject(()=>d.loadRecord(ref,snapshot,{maxBytes:1}));
  const cacheMissing=await reject(()=>d.loadRecord(ref,{...snapshot,catalog:{...snapshot.catalog,details:{}}}));
  const cacheOld=await reject(()=>d.loadRecord(ref,{...snapshot,catalog:{...snapshot.catalog,as_of:'2000-01-01T00:00:00Z'}}));
  const stop=new AbortController();stop.abort();const cachedAbort=await reject(()=>d.loadRecord(ref,snapshot,{signal:stop.signal}));
  const pathGate=await reject(()=>d.loadRecord(ref,{...snapshot,catalog:{...snapshot.catalog,details:{[ref]:'../private.json'}}}));
  const associations={
   exact:r.relatedFields({round_id:'r'},'r'),
   partial:r.relatedFields({round_id:'r-old',input_record_refs:['prefix-r']},'r'),
   nested:r.relatedFields({input_record_refs:[{round_id:'r'}]},'r'),
   hypothetical:r.relatedFields({future_child:{parent_round_id:'r'}},'r'),
   explicit:r.relatedFields({source_round_ref:'r',input_record_refs:['r']},'r'),
   tabs:[r.relatedTab({run_id:'x'}),r.relatedTab({evidence_id:'x'}),r.relatedTab({decision_id:'x'}),r.relatedTab({review_id:'x'})??null]
  };
  return{cacheLimit,cacheMissing,cacheOld,cachedAbort,pathGate,associations,ref,snapshot:snapshot.pointer.snapshot_id,hasRun:typeof first.run_id==='string'};
 });
 for(const k of ['cacheLimit','cacheMissing','cacheOld','cachedAbort','pathGate'])assert.notEqual(result[k],'UNEXPECTED_ACCEPTANCE',k);
 assert.deepEqual(result.associations.partial,[]);assert.deepEqual(result.associations.nested,[]);assert.deepEqual(result.associations.hypothetical,[]);
 assert.deepEqual(result.associations.tabs,['plan','plan','feedback',null]);
 assert.deepEqual(result.associations.explicit,['source_round_ref','input_record_refs']);
 assert.equal(result.hasRun,true);
 outputs.push({browser:name,...result});
 }finally{await browser.close();}
}
console.log(JSON.stringify({scope:'INDEPENDENT_LOCAL_BROWSER_GATES_NOT_REMOTE',outputs},null,2));
