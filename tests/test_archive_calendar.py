"""Pinned authored originals; disposable engineering stores, never production."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from researchlib.archive import export_backup, inspect_backup, restore_backup, _exact_public_export_policy
from researchlib.common import canonical, digest, ContractError
from researchlib.contracts import semantic_refs, record_ref
from researchlib.public import public_record
from researchlib.store import Store

FIXTURES = Path(__file__).parent / 'fixtures/archive-calendar'
HASHES = {'decision': '18c5cfbf2df82e5bc8d8b9f78cb861c9a2e68bbbd3e2d2cd9af7c7a3efc3e527',
          'evidence': 'e4d1b106b95fa2a3e0f56c08c34966b1eb6ad4854a895dd0c0cc9da743acfdbb'}


class CalendarArchiveTests(unittest.TestCase):
    def setUp(self):
        self.originals = [json.loads((FIXTURES / (kind + '.json')).read_text()) for kind in HASHES]
        for original in self.originals:
            self.assertEqual(digest(canonical(original)), HASHES[original['record_type']])
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def good_archive(self):
        at = self.originals[0]['available_at']; store = Store(self.root / 'store', clock=lambda: at)
        refs = set().union(*(semantic_refs(r) for r in self.originals))
        # Stand-ins isolate archive mechanics; real dependency closure is replayed separately.
        dependencies = [dict(schema_version='1.0', record_type='evidence', evidence_id=ref,
            available_at=at, created_at=at, synthetic=False,
            disclosure={'visibility': 'PUBLIC', 'license': 'OWN_ANALYSIS'}) for ref in sorted(refs)]
        store.commit_bundle('dependencies', 'research', dependencies)
        store.commit_bundle('originals', 'research', self.originals)
        path = self.root / 'good.zip'
        manifest = export_backup(store, path, [record_ref(r) for r in self.originals])
        return path, manifest

    def test_two_exact_originals_export_inspect_restore_without_projection_changes(self):
        path, manifest = self.good_archive()
        self.assertEqual(inspect_backup(path)['archive_id'], manifest['archive_id'])
        restore_backup(path, self.root / 'restored')
        for original in self.originals:
            ref = record_ref(original); projection = public_record(original)
            self.assertEqual((self.root / 'restored/records' / (ref + '.json')).read_bytes(), canonical(original))
            self.assertNotIn('round_id', projection)
            self.assertNotIn('feedback_dispositions', projection)
            self.assertEqual(semantic_refs(original), semantic_refs(projection))
            entry = next(e for e in manifest['records'] if e['record_ref'] == ref)
            self.assertEqual(entry['exact_export_policy'], 'EXACT_STOCK_CALENDAR_' + original['record_type'].upper() + '_V1')

    def test_every_scalar_leaf_mutation_rejected(self):
        def leaves(value, path=()):
            if isinstance(value, dict):
                for k, v in value.items(): yield from leaves(v, path + (k,))
            elif isinstance(value, list):
                for k, v in enumerate(value): yield from leaves(v, path + (k,))
            else: yield path, value
        for original in self.originals:
            for path, value in leaves(original):
                with self.subTest(kind=original['record_type'], path=path):
                    changed = copy.deepcopy(original); parent = changed
                    for k in path[:-1]: parent = parent[k]
                    parent[path[-1]] = value + 'x' if isinstance(value, str) else not value if isinstance(value, bool) else value + 1 if isinstance(value, (int, float)) else 'UNKNOWN'
                    with self.assertRaises((ContractError, KeyError)): _exact_public_export_policy(changed)

    def test_closed_shapes_private_payloads_and_explicit_export_restrictions(self):
        for original in self.originals:
            for fields in ([], list(public_record(original)), list(original)):
                changed = copy.deepcopy(original); changed['disclosure']['export_fields'] = fields
                with self.assertRaises(ContractError): _exact_public_export_policy(changed)
            for extra in ({'raw_prices': [12.3]}, {'caller_approved_sha256': digest(canonical(original))}):
                changed = copy.deepcopy(original); changed.update(extra)
                with self.assertRaises(ContractError): _exact_public_export_policy(changed)
        decision = self.originals[0]
        for payload in ([], {}, [decision['feedback_dispositions'][0]], decision['feedback_dispositions'][::-1],
                        [dict(decision['feedback_dispositions'][0], raw_prices=[123.4]), decision['feedback_dispositions'][1]],
                        [dict(decision['feedback_dispositions'][0], actual_application={'secret': 'CANARY'}), decision['feedback_dispositions'][1]]):
            changed = copy.deepcopy(decision); changed['feedback_dispositions'] = payload
            with self.assertRaises(ContractError): _exact_public_export_policy(changed)

    def test_rehashed_manifest_does_not_authorize_byte_or_content_or_policy_mutations(self):
        path, _ = self.good_archive()
        with zipfile.ZipFile(path) as archive: initial = {n: archive.read(n) for n in archive.namelist()}
        for original in self.originals:
            for attack in ('marker_missing', 'marker_other', 'extra_space', 'no_newline', 'duplicate_key', 'field_value', 'explicit_fields', 'caller_hash'):
                with self.subTest(kind=original['record_type'], attack=attack):
                    files = dict(initial); manifest = json.loads(files['ARCHIVE_MANIFEST.json'])
                    entry = next(e for e in manifest['records'] if e['record_ref'] == record_ref(original)); name = entry['path']
                    if attack == 'marker_missing': entry.pop('exact_export_policy')
                    elif attack == 'marker_other': entry['exact_export_policy'] = 'EXACT_NUMERAIRE_DECISION_METADATA_V1'
                    elif attack == 'extra_space': files[name] += b' '
                    elif attack == 'no_newline': files[name] = files[name].rstrip(b'\n')
                    elif attack == 'duplicate_key': files[name] = b'{"synthetic":false,' + files[name][1:]
                    else:
                        changed = copy.deepcopy(original)
                        if attack == 'field_value': changed['round_id'] = 'unreviewed-round'
                        elif attack == 'explicit_fields': changed['disclosure']['export_fields'] = list(changed)
                        else: changed['caller_approved_sha256'] = digest(canonical(changed))
                        files[name] = canonical(changed)
                    entry['original_record_hash'] = digest(files[name])
                    file_entry = next(e for e in manifest['files'] if e['path'] == name)
                    file_entry.update(sha256=digest(files[name]), bytes=len(files[name]))
                    manifest.pop('archive_id'); manifest['archive_id'] = digest(canonical(manifest))
                    files['ARCHIVE_MANIFEST.json'] = canonical(manifest)
                    bad = self.root / 'forged.zip'
                    with zipfile.ZipFile(bad, 'w') as archive:
                        for n, raw in files.items(): archive.writestr(n, raw)
                    with self.assertRaises(ContractError): inspect_backup(bad)
