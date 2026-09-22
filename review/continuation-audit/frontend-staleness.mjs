// Isolated, read-only F09 audit. No production or source writes.
import { chromium, webkit } from '../../web/node_modules/playwright/index.mjs';
import { expect } from '../../web/node_modules/@playwright/test/index.mjs';
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import crypto from 'node:crypto';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const output = path.join(root, 'review/continuation-audit');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
function filesIn(relative) {
  const found = [];
  function walk(p) { for (const e of fs.readdirSync(path.join(root,p), {withFileTypes:true})) { const n=path.posix.join(p,e.name); if(e.isDirectory()) walk(n); else if(e.isFile()) found.push(n); } }
  walk(relative); return found.sort();
}
function fingerprint() {
  const files = ['web/src','site/data','.local/store'].flatMap(filesIn);
  const rows=files.map(p=>[p,hash(fs.readFileSync(path.join(root,p)))]);
  return {files: rows.length, sha256: hash(JSON.stringify(rows))};
}
const before=fingerprint();
const memoryFiles=new Map();
for(const p of filesIn('web/dist')) memoryFiles.set('/'+p.slice('web/dist/'.length),fs.readFileSync(path.join(root,p)));
for(const p of filesIn('site/data')) memoryFiles.set('/data/'+p.slice('site/data/'.length),fs.readFileSync(path.join(root,p)));
const pointer=JSON.parse(memoryFiles.get('/data/latest.json'));
const asOf=Date.parse(pointer.as_of);
const requests=[];
const server=http.createServer((req,res)=>{
  let p=new URL(req.url,'http://audit.local').pathname;if(p==='/')p='/index.html';
  const data=memoryFiles.get(p); const status=data?200:404;
  if(p.startsWith('/data/')) requests.push({path:p.slice(1),status,sha256:data?hash(data):null});
  const ext=path.extname(p); const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.txt':'text/plain'}[ext]??'application/octet-stream';
  res.writeHead(status,{'Content-Type':mime,'Cache-Control':'no-store'});res.end(data??'Not found');
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const url=`http://127.0.0.1:${server.address().port}`;
const receipt={schema_version:'1.0',checked_at:new Date().toISOString(),kind:'SYNTHETIC_CLOCK_AUDIT_WITH_IMMUTABLE_PUBLIC_SNAPSHOT_COPY',natural_run:false,source_changed:false,production_changed:false,snapshot_id:pointer.snapshot_id,as_of:pointer.as_of,threshold_hours:36,comparison:'strictly greater than',fixture:'In-memory copy of existing public files; local server always returns the same bytes with HTTP 200. No new research records.',device:{platform:os.platform(),release:os.release(),arch:os.arch(),cpu:os.cpus()[0].model,memory_gib:Math.round(os.totalmem()/1024**3)},browsers:[],limitations:['Does not stop or inspect the Codex/ChatGPT application.','Does not measure native task operation or authentication.','Clock is simulated; this is not an actual 48-hour outage.','The successful 200 static response is distinct from publication liveness.']};
try {
 for(const [name,type] of Object.entries({chromium,webkit})) {
  const browser=await type.launch({headless:true});
  try {
   const page=await browser.newPage({viewport:{width:1280,height:900}});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   const requestStart=requests.length;
   await page.clock.install({time:new Date(asOf+60_000)});
   await page.goto(url);
   await expect(page.locator('.canvas')).toHaveAttribute('data-snapshot',pointer.snapshot_id);
   await expect(page.getByRole('button',{name:'刷新记录',exact:true})).toBeEnabled();
   const samples=[];
   async function sample(label,ageMs,expectedStale) {
    await page.clock.pauseAt(new Date(asOf+ageMs));
    await expect(page.getByRole('button',{name:'刷新记录',exact:true})).toBeEnabled();
    const bar=page.locator('[aria-label="数据新鲜度"]');
    if(expectedStale) await expect(bar).toHaveClass(/\bstale\b/); else await expect(bar).not.toHaveClass(/\bstale\b/);
    await expect(page.getByRole('alert')).toHaveCount(0);
    const result=await bar.evaluate(el=>({text:el.querySelector('div').innerText,stale:el.classList.contains('stale'),dot_color:getComputedStyle(el.querySelector('.freshness-dot')).backgroundColor,wall_now:new Date().toISOString()}));
    samples.push({label,snapshot_age_ms:ageMs,expected_stale:expectedStale,...result});
   }
   await sample('one_hour',3600_000,false);
   await sample('two_hours_multiple_publish_slots_missed',2*3600_000,false);
   await sample('thirty_five_hours',35*3600_000,false);
   await sample('two_seconds_before_36_hours',36*3600_000-2000,false);
   await sample('exactly_36_hours',36*3600_000,false);
   await sample('two_seconds_after_36_hours',36*3600_000+2000,true);
   const beforeRefresh=requests.length;
   await page.getByRole('button',{name:'刷新记录',exact:true}).click();
   await expect(page.getByRole('button',{name:'刷新记录',exact:true})).toBeEnabled();
   await expect(page.locator('.snapshot-bar')).toHaveClass(/\bstale\b/);
   await expect(page.locator('.canvas')).toHaveAttribute('data-snapshot',pointer.snapshot_id);
   const refreshRequests=requests.slice(beforeRefresh);
   if(!refreshRequests.some(r=>r.path==='data/latest.json'&&r.status===200))throw new Error('Refresh did not read latest with 200');
   await sample('forty_eight_hours',48*3600_000,true);
   await page.screenshot({path:path.join(output,`frontend-staleness.${name}.png`),fullPage:true});
   await page.getByLabel('历史快照').selectOption(pointer.snapshot_id);
   await expect(page.locator('.snapshot-bar')).toContainText('历史时点');
   await expect(page.locator('.snapshot-bar')).not.toHaveClass(/\bstale\b/);
   const historyLabel=await page.locator('.snapshot-bar').innerText();
   await page.getByLabel('历史快照').selectOption('');
   await expect(page.locator('.snapshot-bar')).toHaveClass(/\bstale\b/);
   await expect(page.getByRole('alert')).toHaveCount(0);
   const dataRequests=requests.slice(requestStart);
   if(dataRequests.some(r=>r.status!==200))throw new Error('Unexpected non-200 data request');
   if(errors.length)throw new Error('Unexpected browser page error');
   receipt.browsers.push({browser:name,version:browser.version(),samples,refresh_200_does_not_renew_snapshot:true,all_data_responses_http_200:true,data_requests:dataRequests.length,unique_response_hashes:[...new Map(dataRequests.map(r=>[r.path,r])).values()],history_view_explicitly_labeled:true,history_label:historyLabel,back_to_latest_still_stale:true,page_errors:errors,status:'PASS'});
  } finally {await browser.close();}
 }
 receipt.after=fingerprint();receipt.before=before;
 if(JSON.stringify(before)!==JSON.stringify(receipt.after))throw new Error('Protected source/data files changed during audit');
 receipt.status='PASS_SUCCESSFUL_200_STATIC_SNAPSHOT_AGES_TO_STALE_AFTER_36_HOURS';
 receipt.findings=[{id:'F09-G1',severity:'LIMITATION_NOT_MISSING_TIME_CHECK',summary:'The fixed 36-hour window leaves a green dot and timestamp-only label during earlier publication silence, even after multiple hourly slots. There is no independently attested producer heartbeat.'},{id:'F09-G2',severity:'TEST_COVERAGE_GAP_CLOSED_BY_THIS_AUDIT',summary:'The previous browser suite covered failed fetch and readiness expiry, but had no successful-200 unchanged-snapshot age-boundary test.'}];
 fs.writeFileSync(path.join(output,'frontend-staleness.json'),JSON.stringify(receipt,null,2)+'\n');
 console.log(JSON.stringify({status:receipt.status,browsers:receipt.browsers.map(b=>({browser:b.browser,version:b.version,samples:b.samples.length,data_requests:b.data_requests})),protected_files:before.files,unchanged:true}));
} catch(error) {
 receipt.status='AUDIT_FAILED';receipt.error=String(error).replaceAll(root,'<project>');fs.writeFileSync(path.join(output,'frontend-staleness.json'),JSON.stringify(receipt,null,2)+'\n');throw error;
} finally {await new Promise(resolve=>server.close(resolve));}
