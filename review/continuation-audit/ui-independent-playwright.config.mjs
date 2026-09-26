import path from 'node:path';
const root=process.env.UI_CANDIDATE_ROOT;
export default {
 testDir:process.env.UI_INDEPENDENT_TEST_DIR || path.join(root,'tests/browser'),
 outputDir:path.resolve('.local/receipts/ui-independent-v1/results'),
 timeout:40000,expect:{timeout:8000},workers:1,
 reporter:[['list'],['json',{outputFile:path.resolve('.local/receipts/ui-independent-v1/results.json')}]],
 use:{baseURL:process.env.UI_INDEPENDENT_BASE_URL || 'http://127.0.0.1:5197',viewport:{width:1440,height:1000}},
 projects:[{name:'chromium',use:{browserName:'chromium'}},{name:'webkit',use:{browserName:'webkit'}}]
};
