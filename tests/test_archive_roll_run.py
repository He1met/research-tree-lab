"""Fixed authored run; disposable engineering fixtures, never production input."""
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

FIXTURE = Path(__file__).parent / 'fixtures/archive-roll-run/run.json'
SHA = 'b0c9eaf657c3e0120c81f76ff2e52dad8ae40fd8e2baa816375c5120fd54da69'


class RollRunArchiveTests(unittest.TestCase):
    def setUp(self):
        self.original = json.loads(FIXTURE.read_text()); self.assertEqual(digest(FIXTURE.read_bytes()), SHA)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)

    def good_archive(self):
        r = self.original; at = r['available_at']; store = Store(self.root / 'store', clock=lambda: at)
        deps = []
        for ref in semantic_refs(r):
            dep = dict(schema_version='1.0', record_type='evidence', evidence_id=ref, created_at=at, available_at=at,
                synthetic=False, disclosure={'visibility': 'PUBLIC', 'license': 'OWN_ANALYSIS'})
            if ref == r['round_id']:
                dep.pop('evidence_id'); dep.update(record_type='round', round_id=ref, question='Engineering stand-in', mechanism='Engineering only', parent_round_id=None)
            deps.append(dep)
        store.commit_bundle('dependencies', 'research', deps); store.commit_bundle('run', 'research', [r])
        path = self.root / 'good.zip'; return path, export_backup(store, path, [record_ref(r)])

    def test_exact_bytes_and_unchanged_projection(self):
        path, manifest = self.good_archive(); restore_backup(path, self.root / 'restored')
        self.assertEqual((self.root / 'restored/records' / (record_ref(self.original) + '.json')).read_bytes(), FIXTURE.read_bytes())
        self.assertEqual(inspect_backup(path)['archive_id'], manifest['archive_id'])
        self.assertEqual(set(self.original) - set(public_record(self.original)), {'verification'})
        self.assertEqual(semantic_refs(self.original), semantic_refs(public_record(self.original)))

    def test_all_scalar_mutations_rejected(self):
        def leaves(value, path=()):
            if isinstance(value, dict):
                for k, v in value.items(): yield from leaves(v, path + (k,))
            elif isinstance(value, list):
                for k, v in enumerate(value): yield from leaves(v, path + (k,))
            else: yield path, value
        for path, value in leaves(self.original):
            with self.subTest(path=path):
                r = copy.deepcopy(self.original); parent = r
                for k in path[:-1]: parent = parent[k]
                parent[path[-1]] = value + 'x' if isinstance(value, str) else not value if isinstance(value, bool) else value + 1 if isinstance(value, (int, float)) else 'UNKNOWN'
                with self.assertRaises((ContractError, KeyError)): _exact_public_export_policy(r)

    def test_closed_verification_types_disclosure_and_unknown_run(self):
        for value in (None, [], 'PASS', {}, {'unknown': True},
                      dict(self.original['verification'], independent_audit=0),
                      dict(self.original['verification'], synthetic_author_checks=True),
                      dict(self.original['verification'], synthetic_author_checks=13.0),
                      dict(self.original['verification'], synthetic_author_checks='13'),
                      dict(self.original['verification'], raw_prices=[1, 2]),
                      dict(self.original['verification'], alternate_formulas_and_pairs={'private': 'CANARY'})):
            r = copy.deepcopy(self.original); r['verification'] = value
            with self.assertRaises(ContractError): _exact_public_export_policy(r)
        for change in ({'run_id': 'unknown-run'}, {'attempt_id': 'attempt-2'}, {'caller_hash': SHA}):
            r = copy.deepcopy(self.original); r.update(change)
            with self.assertRaises(ContractError): _exact_public_export_policy(r)
        for change in ({'visibility': 'LOCAL_ONLY'}, {'license': 'LOCAL_ONLY'}, {'export_fields': []},
                       {'export_fields': list(self.original)}, {'export_fields': list(public_record(self.original))}):
            r = copy.deepcopy(self.original); r['disclosure'].update(change)
            with self.assertRaises(ContractError): _exact_public_export_policy(r)

    def test_rehashed_zip_cannot_grant_unknown_verification_or_original_bytes(self):
        path, _ = self.good_archive()
        with zipfile.ZipFile(path) as z: initial = {n: z.read(n) for n in z.namelist()}
        for attack in ('marker_missing', 'marker_calendar', 'whitespace', 'no_newline', 'duplicate_key', 'value', 'id', 'export_fields', 'caller_hash'):
            with self.subTest(attack=attack):
                files = dict(initial); manifest = json.loads(files['ARCHIVE_MANIFEST.json'])
                entry = next(e for e in manifest['records'] if e['record_ref'] == record_ref(self.original)); name = entry['path']
                if attack == 'marker_missing': entry.pop('exact_export_policy')
                elif attack == 'marker_calendar': entry['exact_export_policy'] = 'EXACT_STOCK_CALENDAR_EVIDENCE_V1'
                elif attack == 'whitespace': files[name] += b' '
                elif attack == 'no_newline': files[name] = files[name].rstrip(b'\n')
                elif attack == 'duplicate_key': files[name] = b'{"synthetic":false,' + files[name][1:]
                else:
                    r = copy.deepcopy(self.original)
                    if attack == 'value': r['verification']['independent_audit'] = True
                    elif attack == 'id': r['run_id'] = 'unknown-run'; entry['record_ref'] = record_ref(r)
                    elif attack == 'export_fields': r['disclosure']['export_fields'] = list(r)
                    else: r['caller_hash'] = SHA
                    files[name] = canonical(r)
                entry['original_record_hash'] = digest(files[name]); f = next(e for e in manifest['files'] if e['path'] == name)
                f.update(sha256=digest(files[name]), bytes=len(files[name])); manifest.pop('archive_id'); manifest['archive_id'] = digest(canonical(manifest))
                files['ARCHIVE_MANIFEST.json'] = canonical(manifest); bad = self.root / 'forged.zip'
                with zipfile.ZipFile(bad, 'w') as z:
                    for n, raw in files.items(): z.writestr(n, raw)
                with self.assertRaises(ContractError): inspect_backup(bad)
