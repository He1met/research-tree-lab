"""Produce a publishable browser receipt without local paths or trace payloads."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / 'tests/browser/artifacts'
raw = json.loads((ARTIFACTS / 'playwright-results.json').read_text())
cases = []

def walk(suite):
    for spec in suite.get('specs', []):
        for test in spec.get('tests', []):
            cases.append({'title': spec['title'], 'file': Path(spec['file']).name,
                          'browser': test['projectName'], 'outcome': test['status'],
                          'results': [{'status': item['status'], 'duration_ms': item['duration']}
                                      for item in test.get('results', [])]})
    for child in suite.get('suites', []):
        walk(child)

for suite in raw['suites']:
    walk(suite)
sources = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
           for path in sorted((ROOT / 'web/src').glob('*')) if path.is_file()}
sources['web/package-lock.json'] = hashlib.sha256((ROOT / 'web/package-lock.json').read_bytes()).hexdigest()
receipt = {'schema_version': '1.0', 'classification': 'ENGINEERING_BROWSER_VERIFICATION',
           'stats': raw['stats'], 'source_sha256': sources,
           'dependencies': json.loads((ROOT / 'web/package.json').read_text())['dependencies'],
           'cases': cases,
           'scale': [json.loads(p.read_text()) for p in sorted((ARTIFACTS / 'scale').glob('*.json'))],
           'genuine_projection_checks': [json.loads(p.read_text()) for p in sorted(ARTIFACTS.glob('*-genuine-projection.json'))],
           'limitations': ['Synthetic cases do not establish economic evidence or natural task execution.',
                           'Genuine projection checks load immutable generated files locally, not public Pages.',
                           'Scale counts are actual rendered React Flow nodes; the viewport may show a subset at readable zoom.']}
(ARTIFACTS / 'verification.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
screenshots = ARTIFACTS / 'screenshots'
screenshots.mkdir(exist_ok=True)
for name in ['genuine-research-desktop.png', 'genuine-research-mobile.png', 'genuine-evidence-drawer.png']:
    candidates = list((ARTIFACTS / 'results').glob(f'*chromium/{name}'))
    if candidates:
        shutil.copyfile(candidates[0], screenshots / name)
print(json.dumps({'receipt': 'tests/browser/artifacts/verification.json', 'cases': len(cases), 'stats': raw['stats']}))
