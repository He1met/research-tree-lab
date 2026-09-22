#!/usr/bin/env python3
"""Synthetic early-review probes in a temporary, byte-captured candidate copy.

Reads fixed code/fixture paths only, never a production Store/data/installation.
Writes only temporary directories; prints a receipt to stdout, no output switch.
This is diagnostic review code, not production admission or a final approval.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch
import zipfile


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-root', required=True)
    args = parser.parse_args()
    candidate = Path(args.candidate_root).resolve()
    selected = []
    for directory in ('researchlib', 'scripts', 'tests/fixtures/waiting-d21'):
        selected.extend(p for p in (candidate / directory).rglob('*')
                        if p.is_file() and '__pycache__' not in p.parts)
    selected.extend(candidate / name for name in (
        'research/bootstrap-v1/research_bundle.json',
        'review/bootstrap-review/review_bundle.json',
        'tests/test_conditional_review.py', 'tests/test_formal_review.py',
        'tests/test_formal_funding.py'))
    captured = {}
    for path in sorted(set(selected)):
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('FIXED_SOURCE_FILE_REQUIRED')
        captured[str(path.relative_to(candidate))] = path.read_bytes()
    hashes = {name: digest(raw) for name, raw in captured.items()}
    with tempfile.TemporaryDirectory(prefix='formal-independent-capture-') as temporary:
        frozen = Path(temporary)
        for name, raw in captured.items():
            destination = frozen / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
        sys.path[:0] = [str(frozen), str(frozen / 'tests')]
        from test_conditional_review import ConditionalReviewTests, PRIVATE_NUMBER
        from test_formal_review import FormalReviewTests, INFO, END
        from researchlib import formal_review as formal
        from researchlib.archive import export_backup
        from researchlib.snapshot import publish_snapshot

        results = []

        def fixture(cls=ConditionalReviewTests):
            case = cls('test_real_decode_path_from_legacy_has_no_granted_business_capabilities'
                       if cls is FormalReviewTests else
                       'test_decoded_legacy_migration_preserves_formal_hash_and_unknown_actuals')
            case.setUp()
            return case

        mutations = [
            ('method_hash', 'review', 'provenance.method_code_sha256', '0' * 64),
            ('natural', 'review', 'provenance.natural_trigger', True),
            ('native', 'review', 'provenance.native_task_ref', 'forged-native'),
            ('origin', 'review', 'provenance.trigger_origin', 'SCHEDULED'),
            ('method_time', 'review', 'provenance.method_available_at', '2026-09-22T20:00:00Z'),
            ('complete', 'review', 'data_complete', True),
            ('metric', 'review', 'metrics.gross_price_pnl', '123'),
            ('coverage', 'review', 'coverage.result_is_evaluable', True),
            ('summary', 'review', 'summary', 'FORMAL FINAL PROFIT VERIFIED'),
            ('limitations', 'review', 'limitations', []),
            ('feedback_facts', 'feedback', 'supported_facts', ['FINAL_PROFIT_VERIFIED']),
            ('feedback_native', 'feedback', 'provenance.natural_trigger', True),
            ('batch_coverage', 'review_batch', 'coverage.evaluable_results', 999),
            ('batch_origin', 'review_batch', 'trigger_origin', 'SCHEDULED'),
            ('batch_complete', 'review_batch', 'complete', False),
        ]
        for name, kind, field, value in mutations:
            case = fixture()
            try:
                case.now = '2026-09-23T19:00:00Z'
                bundle = formal.prepare_bundle(case.store, 'formal-a', case.inputs(), '2026-09-23T12:00:00Z')
                index = next(i for i, record in enumerate(bundle['records']) if record['record_type'] == kind)
                # Break aliases, so changing feedback cannot silently change its review.
                target = copy.deepcopy(bundle['records'][index])
                bundle['records'][index] = target
                parent = target
                for key in field.split('.')[:-1]:
                    parent = parent[key]
                parent[field.split('.')[-1]] = value
                case.commit(bundle)
                case.now = '2026-09-23T20:00:00Z'
                following = formal.prepare_bundle(case.store, 'formal-b', case.inputs(), '2026-09-23T12:00:00Z')
                reviews = case.reviews(following)
                results.append({'probe': name, 'outcome': 'NEW_BUNDLE_RETURNED',
                    'review_stages': [r['evaluation_stage'] for r in reviews],
                    'reason_codes': [r['coverage']['reason_codes'] for r in reviews],
                    'changed_ancestor_accepted_without_failure': all(r['evaluation_stage'] != 'TECHNICAL_FAILURE' for r in reviews)})
            except Exception as error:
                results.append({'probe': name, 'outcome': 'REJECTED', 'error_type': type(error).__name__, 'reason': str(error)})
            finally:
                case.doCleanups()

        for unknown in (False, True):
            case = fixture()
            name = 'old_private_permission_unknown_method' if unknown else 'old_private_permission'
            try:
                bundle = case.prepare('old-c1')
                old = case.reviews(bundle)[0]
                if unknown:
                    for record in case.reviews(bundle):
                        record['evaluator_version'] = 'UNKNOWN_METHOD'
                target = next(r for r in bundle['records'] if r['record_type'] == 'feedback')
                target['disclosure'] = copy.deepcopy(target['disclosure'])
                target['disclosure']['public_attachments'].append('attachments/PRIVATE/' + old['review_id'] + '.json')
                case.commit(bundle)
                case.now = '2026-09-23T19:00:00Z'
                following = formal.prepare_bundle(case.store, 'formal-a', case.inputs(), '2026-09-23T12:00:00Z')
                case.commit(following)
                review = next(r for r in case.reviews(following) if r['plan_ref'] == old['plan_ref'])
                archive_path = case.root / 'new-review.zip'
                export_backup(case.store, archive_path, record_refs=[review['review_id']])
                with zipfile.ZipFile(archive_path) as archive:
                    names = archive.namelist()
                    private = [n for n in names if '/PRIVATE/' in n]
                    canary = any(PRIVATE_NUMBER.encode() in archive.read(n) for n in names)
                public_root = case.root / 'public'
                publish_snapshot(case.store, public_root, case.now)
                results.append({'probe': name, 'outcome': 'NEW_BUNDLE_RETURNED',
                    'review_stage': review['evaluation_stage'], 'archive_private_members': private,
                    'archive_price_canary': canary,
                    'snapshot_price_canary': any(PRIVATE_NUMBER.encode() in p.read_bytes() for p in public_root.rglob('*') if p.is_file())})
            except Exception as error:
                results.append({'probe': name, 'outcome': 'REJECTED_BEFORE_NEW_DANGEROUS_BUNDLE',
                    'error_type': type(error).__name__, 'reason': str(error)})
            finally:
                case.doCleanups()

        case = fixture()
        try:
            case.commit(case.prepare('old-c1'))
            for name, hour in [('a', 19), ('b', 20), ('c', 21)]:
                case.now = '2026-09-23T%02d:00:00Z' % hour
                bundle = formal.prepare_bundle(case.store, 'formal-' + name, case.inputs(), '2026-09-23T12:00:00Z')
                case.commit(bundle)
            case.now = '2026-09-23T22:00:00Z'
            records, metadata, _ = case.store.load(strict=True)
            method, _ = formal.method_material(case.now)
            previous = case.reviews(bundle)[0]
            context = formal._context()
            formal._previous(case.store, previous, records[previous['plan_ref']], records, metadata, method, context)
            old_bytes = context.get('old_context', {}).get('encoded_bytes', 0)
            total = context['encoded_bytes'] + old_bytes
            threshold = max(context['encoded_bytes'], old_bytes) + max(1, min(context['encoded_bytes'], old_bytes) // 2)
            try:
                with patch('researchlib.conditional_review.MAX_CONTEXT_BYTES', threshold):
                    context = formal._context()
                    formal._previous(case.store, previous, records[previous['plan_ref']], records, metadata, method, context)
                outcome = 'ACCEPTED_OVER_COMBINED_TEST_BUDGET'
            except Exception as error:
                outcome = 'REJECTED:' + str(error)
            results.append({'probe': 'combined_cache_budget', 'outcome': outcome,
                'baseline_combined_bytes': total, 'lowered_test_threshold': threshold,
                'production_limit_changed': False})
        except Exception as error:
            results.append({'probe': 'combined_cache_budget', 'outcome': 'SETUP_OR_CHAIN_REJECTED', 'reason': str(error)})
        finally:
            case.doCleanups()

        case = fixture(FormalReviewTests)
        try:
            case.now = INFO
            with patch.object(formal, '_resolve_sources', side_effect=case.fixture_resolver):
                first = case.prepare(sources=[], cutoff=END)
                case.commit(first)
                case.now = '2026-09-25T01:00:00Z'
                reused = case.prepare('reuse', sources=[], cutoff=END)
                case.commit(reused)
                public_root = case.root / 'public-reuse'
                publish_snapshot(case.store, public_root, case.now)
                catalog = json.loads(next(public_root.rglob('catalog.json')).read_text())
                projected = next(b for b in catalog['review_batches'] if b['batch_id'] == 'reuse')
                manifest = export_backup(case.store, case.root / 'reuse.zip', record_refs=['reuse'])
                wanted = {r['review_id'] for r in case.reviews(first)}
                results.append({'probe': 'final_reuse_snapshot_archive', 'outcome': 'EXECUTED',
                    'new_review_count': len(case.reviews(reused)), 'record_coverage': reused['records'][0]['coverage'],
                    'projected_coverage': projected['coverage'], 'projected_review_refs': projected['review_refs'],
                    'archived_original_final_count': len(wanted & set(manifest['record_refs'])),
                    'expected_original_final_count': len(wanted)})
        except Exception as error:
            results.append({'probe': 'final_reuse_snapshot_archive', 'outcome': 'SETUP_OR_REVIEW_REJECTED', 'reason': str(error)})
        finally:
            case.doCleanups()

    drift = [name for name, raw in captured.items() if (candidate / name).read_bytes() != raw]
    print(json.dumps({'schema_version': '1.0', 'status': 'DIAGNOSTIC_UNFROZEN_NOT_APPROVAL',
        'source_capture_mode': 'READ_FIXED_PATHS_ONCE_THEN_EXECUTE_TEMPORARY_COPY',
        'candidate_source_files_changed_after_capture': drift,
        'captured_file_sha256': hashes,
        'captured_map_sha256': digest(json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode()),
        'production_read_or_write': False, 'network_or_native_actions': False,
        'synthetic_fixture_only': True, 'results': results}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
