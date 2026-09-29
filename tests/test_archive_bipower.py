"""Fixed Bipower originals: exact identity, reference closure and adversarial ZIPs."""
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

FIXTURES = Path(__file__).parent / 'fixtures/archive-bipower'

class BipowerArchiveTests(unittest.TestCase):
    def setUp(self):
        self.records = [json.loads((FIXTURES / (n + '.json')).read_text()) for n in ('discovery', 'evidence', 'decision', 'round')]
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)

    def archive(self, roots=None):
        earliest = min(r['available_at'] for r in self.records)
        store = Store(self.root / 'store', clock=lambda: max(r['available_at'] for r in self.records))
        refs = {record_ref(r) for r in self.records}
        deps = sorted({ref for r in self.records for ref in semantic_refs(r)} - refs)
        generic = [dict(schema_version='1.0', record_type='evidence', evidence_id=ref, created_at=earliest, available_at=earliest,
                        synthetic=False, disclosure={'visibility':'PUBLIC','license':'OWN_ANALYSIS'}) for ref in deps]
        store.commit_bundle('deps', 'research', generic)
        store.commit_bundle('discovery-bipower-20260929-v1', 'discovery', self.records[:2],
                            attachments={'proposal.json': (FIXTURES / 'proposal.json').read_bytes()})
        store.commit_bundle('research-bipower-20260929-v1', 'research', self.records[2:])
        path = self.root / 'good.zip'
        return path, export_backup(store, path, roots or sorted(refs))

    def mutations(self, original):
        def leaves(value, path=()):
            if isinstance(value, dict):
                for k, v in value.items(): yield from leaves(v, path + (k,))
            elif isinstance(value, list):
                for k, v in enumerate(value): yield from leaves(v, path + (k,))
            else: yield path, value
        for path, value in leaves(original):
            changed = copy.deepcopy(original); parent = changed
            for k in path[:-1]: parent = parent[k]
            parent[path[-1]] = 'MUTATED' if not isinstance(value, str) else value + ' MUTATED'
            yield changed
        for value in (0, False, True, 'null', [], {}, 1.5):
            changed = copy.deepcopy(original); changed.setdefault('findings', {})['actual_net'] = value; yield changed
        for key, value in [('private_note', 'CANARY'), ('raw_prices', [123]), ('caller_hash', digest(canonical(original)))]:
            changed = copy.deepcopy(original); changed[key] = value; yield changed
        for policy in ({'visibility':'LOCAL_ONLY'}, {'license':'LOCAL_ONLY'}, {'export_fields':[]}, {'export_fields':list(original)}, {'export_fields':list(public_record(original))}):
            changed = copy.deepcopy(original); changed['disclosure'].update(policy); yield changed
        for key in set(original) - set(public_record(original)):
            for value in (None, False, 0, [], {}, 'unknown'):
                changed = copy.deepcopy(original); changed[key] = value; yield changed

    def rewrite(self, initial, ref=None, content=None, remove=None, marker=None):
        files = dict(initial); m = json.loads(files['ARCHIVE_MANIFEST.json'])
        if ref:
            entry = next(e for e in m['records'] if e['record_ref'] == ref)
            if content is not None:
                name = entry['path']; files[name] = content; entry['original_record_hash'] = digest(content)
                for f in m['files']:
                    if f['path'] == name: f.update(sha256=digest(content), bytes=len(content))
            if marker: entry['exact_export_policy'] = marker
        if remove:
            files.pop(remove); m['files'] = [e for e in m['files'] if e['path'] != remove]
            removed = [e['record_ref'] for e in m['records'] if e['path'] == remove]
            m['records'] = [e for e in m['records'] if e['path'] != remove]
            m['record_refs'] = [r for r in m['record_refs'] if r not in removed]
        m.pop('archive_id'); m['archive_id'] = digest(canonical(m)); files['ARCHIVE_MANIFEST.json'] = canonical(m)
        bad = self.root / 'forged.zip'
        with zipfile.ZipFile(bad, 'w') as z:
            for n, raw in files.items(): z.writestr(n, raw)
        return bad

    def test_exact_export_restore_and_decision_only_closure(self):
        path, manifest = self.archive(['decision-bipower-closeout-20260929'])
        self.assertIn('r-bipower-20260929', manifest['record_refs'])
        self.assertEqual(inspect_backup(path)['archive_id'], manifest['archive_id'])
        restore_backup(path, self.root / 'restored')
        for r in self.records:
            self.assertEqual((self.root / 'restored/records' / (record_ref(r) + '.json')).read_bytes(), canonical(r))
        discovery = json.loads((self.root / 'restored/records/discovery-bipower-20260929.json').read_text())
        self.assertEqual(discovery['status'], 'PROPOSED_NOT_STARTED')
        self.assertIsNone(discovery['findings']['actual_net'])
        self.assertEqual(set(discovery) - set(public_record(discovery)), {'problem_key','proposal_ref','resource_expectation'})

    def test_all_scalar_fields_types_private_fields_and_disclosure_fail_closed(self):
        for original in self.records[:3]:
            for i, changed in enumerate(self.mutations(original)):
                with self.subTest(ref=record_ref(original), mutation=i), self.assertRaises(ContractError):
                    _exact_public_export_policy(changed)

    def test_rehashed_zip_mutations_duplicates_and_policy_forgery(self):
        path, _ = self.archive()
        with zipfile.ZipFile(path) as z: initial = {n:z.read(n) for n in z.namelist()}
        for original in self.records[:3]:
            raw = canonical(original); ref = record_ref(original)
            payloads = [canonical(r) for r in self.mutations(original)]
            key = next(iter(original)); duplicate = json.dumps(key).encode() + b':' + json.dumps(original[key], ensure_ascii=False).encode() + b','
            payloads += [raw + b' ', raw.rstrip(b'\n'), b'{' + duplicate + raw[1:]]
            for i, payload in enumerate(payloads):
                with self.subTest(ref=ref, payload=i), self.assertRaises(ContractError):
                    inspect_backup(self.rewrite(initial, ref=ref, content=payload))
            with self.assertRaises(ContractError): inspect_backup(self.rewrite(initial, ref=ref, marker='CALLER_APPROVED'))

    def test_reference_and_proposal_closure_cannot_be_stripped_or_replaced(self):
        path, _ = self.archive()
        with zipfile.ZipFile(path) as z: initial = {n:z.read(n) for n in z.namelist()}
        for remove in ('records/r-bipower-20260929.json', 'evidence/discovery-bipower-20260929-v1/attachments/proposal.json'):
            with self.subTest(remove=remove), self.assertRaises(ContractError): inspect_backup(self.rewrite(initial, remove=remove))
        changed = copy.deepcopy(self.records[3]); changed['title'] = 'Substituted round'
        with self.assertRaises(ContractError): inspect_backup(self.rewrite(initial, ref=record_ref(changed), content=canonical(changed)))
        with self.assertRaises(ContractError): inspect_backup(self.rewrite(initial, ref=record_ref(self.records[3]), content=canonical(self.records[3]) + b' '))
        files = dict(initial); name='evidence/discovery-bipower-20260929-v1/attachments/proposal.json'; files[name]=b'{}'
        m=json.loads(files['ARCHIVE_MANIFEST.json'])
        for f in m['files']:
            if f['path']==name: f.update(sha256=digest(files[name]),bytes=len(files[name]))
        files['ARCHIVE_MANIFEST.json']=canonical(m)
        with self.assertRaises(ContractError): inspect_backup(self.rewrite(files))
