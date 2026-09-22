#!/usr/bin/env python3
"""Read back this project's public Pages snapshot; no market or model APIs."""
import argparse
import json
import re
from pathlib import Path
import sys
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from researchlib.common import atomic_write,canonical,digest,now_iso,read_json,safe_relative
from researchlib.snapshot import verify_snapshot

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--expected');args=parser.parse_args()
    config=read_json(ROOT/'.local/installation.json')
    base=config.get('pages_url') or config.get('planned_pages_url')
    if not base or urlparse(base).scheme!='https':raise RuntimeError('No verified project Pages destination configured')
    local=read_json(ROOT/'site/data/latest.json');expected=args.expected or local['snapshot_id']
    if not re.fullmatch(r'[a-f0-9]{64}',expected):raise RuntimeError('Invalid snapshot identity')
    verify_snapshot(ROOT/'site/data',expected)
    response_info=[]
    def fetch(path):
        safe_relative(path);url=urljoin(base,path)
        if not url.startswith(base):raise RuntimeError('Public path escaped allowed site')
        with urlopen(Request(url,headers={'Cache-Control':'no-cache','User-Agent':'ResearchTreePublicReadback/1.0'}),timeout=30) as response:
            if not response.url.startswith(base):raise RuntimeError('Unexpected readback redirect')
            raw=response.read(32*1024*1024+1)
            if len(raw)>32*1024*1024:raise RuntimeError('Public readback object too large')
            response_info.append({'path':path,'http_status':response.status,'sha256':digest(raw),'bytes':len(raw),'http_date':response.headers.get('Date'),'last_modified':response.headers.get('Last-Modified')})
            return raw
    index=fetch('index.html')
    if index!=(ROOT/'site/index.html').read_bytes():raise RuntimeError('Remote application shell differs from reviewed local shell')
    for asset in re.findall(r'(?:src|href)="\./(assets/[^"?#]+)"',index.decode('utf-8')):
        safe_relative(asset)
        if fetch(asset)!=(ROOT/'site'/asset).read_bytes():raise RuntimeError('Remote application asset differs from reviewed local asset')
    latest=json.loads(fetch('data/latest.json'))
    if latest['snapshot_id']!=expected:raise RuntimeError('REMOTE_SNAPSHOT_NOT_YET_CURRENT: '+latest['snapshot_id'])
    if latest['manifest_url']!='snapshots/'+expected+'/manifest.json' or latest['catalog_url']!='snapshots/'+expected+'/catalog.json':raise RuntimeError('Remote pointer path mismatch')
    manifest_raw=fetch('data/'+latest['manifest_url'])
    expected_manifest=(ROOT/'site/data/snapshots'/expected/'manifest.json').read_bytes()
    if manifest_raw!=expected_manifest:raise RuntimeError('Remote manifest differs from locally verified manifest')
    manifest=json.loads(manifest_raw)
    catalog_raw=fetch('data/'+latest['catalog_url']);catalog=json.loads(catalog_raw)
    if manifest['snapshot_id']!=expected or catalog['snapshot_id']!=expected:raise RuntimeError('Remote snapshot identity mismatch')
    if latest.get('as_of')!=manifest.get('as_of') or catalog.get('as_of')!=manifest.get('as_of'):raise RuntimeError('Remote cutoff mismatch')
    entry=next(f for f in manifest['files'] if f['path']=='catalog.json')
    if digest(catalog_raw)!=entry['sha256'] or len(catalog_raw)!=entry['bytes']:raise RuntimeError('Remote catalog integrity mismatch')
    for entry in manifest['object_refs']:
        raw=fetch('data/'+entry['path'])
        if digest(raw)!=entry['sha256'] or len(raw)!=entry['bytes']:raise RuntimeError('Remote object integrity mismatch')
    record={'schema_version':'1.0','verified_at':now_iso(),'status':'PUBLIC_SNAPSHOT_HTTP_VERIFIED','snapshot_id':expected,'pages_url':base,'round_count':catalog['round_count'],'record_count':catalog['record_count'],'readback':response_info,'browser_visual_acceptance':'SEPARATE_REQUIRED'}
    atomic_write(ROOT/'.local/receipts'/('pages-'+expected+'.json'),canonical(record))
    print(json.dumps({k:v for k,v in record.items() if k!='readback'},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
