"""Fixed authored null result; disposable stores and attack archives only."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from researchlib.archive import _exact_public_export_policy, export_backup, inspect_backup, restore_backup
from researchlib.common import canonical, digest, ContractError
from researchlib.contracts import semantic_refs, record_ref
from researchlib.public import public_record
from researchlib.store import Store

FIXTURE = Path(__file__).parent / 'fixtures/archive-async/decision.json'
SHA = '26361666a255e0e96e2e72e39d6b1f64b8c4fe0e3404c18a6a8aad87c9ab09ac'


class AsyncArchiveTests(unittest.TestCase):
    def setUp(self):
        self.original = json.loads(FIXTURE.read_text()); self.assertEqual(digest(FIXTURE.read_bytes()), SHA)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)

    def archive(self):
        r = self.original; at = r['available_at']; store = Store(self.root / 'store', clock=lambda: at)
        deps = [dict(schema_version='1.0', record_type='evidence', evidence_id=ref, created_at=at, available_at=at,
                     synthetic=False, disclosure={'visibility': 'PUBLIC', 'license': 'OWN_ANALYSIS'}) for ref in semantic_refs(r)]
        store.commit_bundle('deps', 'research', deps); store.commit_bundle('original', 'research', [r])
        path = self.root / 'good.zip'; return path, export_backup(store, path, [record_ref(r)])

    def test_exact_null_export_and_restore(self):
        path, manifest = self.archive(); self.assertEqual(inspect_backup(path)['archive_id'], manifest['archive_id'])
        restore_backup(path, self.root / 'restored')
        self.assertEqual((self.root / 'restored/records' / (record_ref(self.original) + '.json')).read_bytes(), FIXTURE.read_bytes())
        self.assertEqual(set(self.original) - set(public_record(self.original)), {'actual_net'})

    def mutations(self):
        for value in (False, True, 0, 0.0, 'null', '', [], {}, {'private': 'CANARY'}, 1):
            r = copy.deepcopy(self.original); r['actual_net'] = value; yield r
        for key, value in [('decision_id', 'unknown'), ('record_type', 'evidence'), ('reason', 'changed'), ('caller_hash', SHA)]:
            r = copy.deepcopy(self.original); r[key] = value; yield r
        for policy in ({'visibility': 'LOCAL_ONLY'}, {'license': 'LOCAL_ONLY'}, {'export_fields': []}, {'export_fields': list(self.original)}, {'export_fields': list(public_record(self.original))}):
            r = copy.deepcopy(self.original); r['disclosure'].update(policy); yield r

    def test_changed_values_types_ids_and_disclosure_rejected(self):
        for i, r in enumerate(self.mutations()):
            with self.subTest(mutation=i), self.assertRaises(ContractError): _exact_public_export_policy(r)

    def test_rehashed_manifest_cannot_grant_exception_or_change_bytes(self):
        path, _ = self.archive()
        with zipfile.ZipFile(path) as z: initial = {n: z.read(n) for n in z.namelist()}
        payloads = [canonical(r) for r in self.mutations()] + [FIXTURE.read_bytes() + b' ', FIXTURE.read_bytes().rstrip(b'\n'), b'{"actual_net":null,' + FIXTURE.read_bytes()[1:]]
        for i, content in enumerate(payloads):
            with self.subTest(payload=i):
                files = dict(initial); m = json.loads(files['ARCHIVE_MANIFEST.json'])
                entry = next(e for e in m['records'] if e['record_ref'] == record_ref(self.original)); name = entry['path']
                files[name] = content; entry['original_record_hash'] = digest(content)
                for f in m['files']:
                    if f['path'] == name: f.update(sha256=digest(content), bytes=len(content))
                m.pop('archive_id'); m['archive_id'] = digest(canonical(m)); files['ARCHIVE_MANIFEST.json'] = canonical(m)
                bad = self.root / 'forged.zip'
                with zipfile.ZipFile(bad, 'w') as z:
                    for n, raw in files.items(): z.writestr(n, raw)
                with self.assertRaises(ContractError): inspect_backup(bad)
