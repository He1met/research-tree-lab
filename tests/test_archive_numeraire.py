"""Exact authored original fixture; all test stores/dependencies are disposable.

The production compatibility gate never reads this fixture or a caller hash list.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from researchlib.archive import export_backup, inspect_backup, restore_backup, _exact_public_export_policy
from researchlib.common import canonical, digest, ContractError
from researchlib.contracts import semantic_refs
from researchlib.public import public_record
from researchlib.store import Store

FIXTURE = Path(__file__).parent/'fixtures/archive-numeraire/decision.json'
EXPECTED_HASH = '6b5ec5278a5d5bdc3945d483035a4d6c9e1f9ffad8871bf71933ce109aa7c64c'


class ArchiveNumeraireTests(unittest.TestCase):
    def setUp(self):
        self.original=json.loads(FIXTURE.read_text())
        self.assertEqual(digest(canonical(self.original)),EXPECTED_HASH)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_exact_original_export_inspect_restore_and_projection_stay_separate(self):
        at=self.original['available_at'];store=Store(self.root,clock=lambda:at)
        # Synthetic stand-ins only isolate archive byte preservation. Real
        # dependency closure is checked separately using the read-only store.
        dependencies=[dict(schema_version='1.0',record_type='evidence',evidence_id=ref,
            created_at=at,available_at=at,synthetic=False,
            disclosure={'visibility':'PUBLIC','license':'OWN_ANALYSIS'}) for ref in semantic_refs(self.original)]
        store.commit_bundle('dependencies','research',dependencies)
        store.commit_bundle('original','research',[copy.deepcopy(self.original)])
        before=canonical(self.original);projection=public_record(self.original)
        self.assertNotIn('future_child',projection)
        self.assertNotIn('new_feedback_successor_created',projection)
        self.assertNotIn('trial_state',projection)
        self.assertEqual(semantic_refs(self.original),semantic_refs(projection))
        path=self.root/'exact.zip';manifest=export_backup(store,path,[self.original['decision_id']])
        entry=next(r for r in manifest['records'] if r['record_ref']==self.original['decision_id'])
        self.assertEqual(entry['exact_export_policy'],'EXACT_NUMERAIRE_DECISION_METADATA_V1')
        self.assertEqual(inspect_backup(path)['archive_id'],manifest['archive_id'])
        recovered=self.root/'restored';restore_backup(path,recovered)
        self.assertEqual((recovered/entry['path']).read_bytes(),before)
        self.assertEqual(canonical(store.load()[0][self.original['decision_id']]),before)
        self.assertEqual(public_record(self.original),projection)

    def test_closed_extension_rejects_mutation_and_unreviewed_decisions(self):
        mutations=[
            lambda r:r['future_child'].update(state='EXECUTED'),
            lambda r:r['future_child'].update(raw_rows=[['2026-09-27',123.45]]),
            lambda r:r['future_child'].update(question={'rows':[123.45]}),
            lambda r:r['future_child'].update(question='another unreviewed question'),
            lambda r:r['future_child'].update(parent_round_id='unrelated-round'),
            lambda r:r.update(new_feedback_successor_created=True),
            lambda r:r.update(new_feedback_successor_created=0),
            lambda r:r.update(trial_state='ACTIVE'),
            lambda r:r.update(extra_metadata={'private':'SYNTHETIC_CANARY'}),
            lambda r:r.update(decision_id='unreviewed-decision'),
            lambda r:r.update(reason='changed base field'),
            lambda r:r['disclosure'].update(visibility='LOCAL_ONLY'),
            lambda r:r['disclosure'].update(license='LOCAL_ONLY'),
            lambda r:r['disclosure'].update(export_fields=list(public_record(r))),
            lambda r:r['disclosure'].update(export_fields=list(r)),
            lambda r:r.update(synthetic=True),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                record=copy.deepcopy(self.original);mutate(record)
                with self.assertRaises(ContractError):_exact_public_export_policy(record)

    def test_nested_secret_and_encoded_payload_are_not_approved_by_scanner_alone(self):
        fake_private_path=str(Path('/').joinpath('Users','test','private','raw.csv'))
        for content in (fake_private_path, 'Bearer '+'A'*32,
                        '{"raw_prices":[12345.6789]}', 'SYNTHETIC_PRIVATE_CANARY'):
            record=copy.deepcopy(self.original);record['future_child']['question']=content
            with self.assertRaises(ContractError):_exact_public_export_policy(record)

    def test_other_records_and_explicit_export_field_restrictions_unchanged(self):
        record=dict(schema_version='1.0',record_type='decision',decision_id='ordinary',
            created_at='2026-01-01T00:00:00Z',available_at='2026-01-01T00:00:00Z',synthetic=False,
            reason='ordinary public reason',disclosure={'visibility':'PUBLIC','license':'OWN_ANALYSIS'})
        self.assertIsNone(_exact_public_export_policy(record))
        record['disclosure']['export_fields']=[k for k in record if k!='reason']
        with self.assertRaises(ContractError):_exact_public_export_policy(record)

    def test_inspector_rejects_rehashed_policy_marker_tampering(self):
        # Reconstructing manifest digests does not grant a policy identity.
        store=Store(self.root,clock=lambda:self.original['available_at'])
        dependencies=[dict(schema_version='1.0',record_type='evidence',evidence_id=ref,
            created_at=self.original['available_at'],available_at=self.original['available_at'],synthetic=False,
            disclosure={'visibility':'PUBLIC','license':'OWN_ANALYSIS'}) for ref in semantic_refs(self.original)]
        store.commit_bundle('deps','research',dependencies)
        store.commit_bundle('original','research',[self.original])
        path=self.root/'good.zip';export_backup(store,path,[self.original['decision_id']])
        with zipfile.ZipFile(path) as z:files={n:z.read(n) for n in z.namelist()}
        manifest=json.loads(files['ARCHIVE_MANIFEST.json'])
        for entry in manifest['records']:entry.pop('exact_export_policy',None)
        manifest.pop('archive_id');manifest['archive_id']=digest(canonical(manifest))
        files['ARCHIVE_MANIFEST.json']=canonical(manifest)
        bad=self.root/'bad.zip'
        with zipfile.ZipFile(bad,'w') as z:
            for name,raw in files.items():z.writestr(name,raw)
        with self.assertRaisesRegex(ContractError,'Recovery exact-export policy mismatch'):inspect_backup(bad)
