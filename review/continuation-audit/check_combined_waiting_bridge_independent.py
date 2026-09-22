"""Synthetic bridge attacks using real frozen source bytes; no production write."""
import argparse
import copy
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--code-root', required=True, type=Path)
    parser.add_argument('--old-code-root', required=True, type=Path)
    parser.add_argument('--installed-root', required=True, type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.code_root))
    from researchlib import conditional_review as cr, funding_review as waiting
    from researchlib.common import canonical, digest
    from tests.test_conditional_review import ConditionalReviewTests, old_waiting_material
    at = '2026-09-23T18:00:00Z'
    old_method, old_sources = json.loads(subprocess.check_output([sys.executable, '-B', '-c',
        'import json;from researchlib.funding_review import method_material;print(json.dumps(method_material('+repr(at)+')))'],
        cwd=args.installed_root, text=True))
    old_bundle = json.loads(subprocess.check_output([sys.executable, '-B', '-c',
        "import json;from tests.test_conditional_review import ConditionalReviewTests;"
        "t=ConditionalReviewTests();t.setUp();b=t.prepare('actual-fourth-identity',[]);"
        "print(json.dumps(b));t.doCleanups()"], cwd=args.old_code_root, text=True))
    checks = []
    methods = {'old': (old_method, old_sources), 'combined': waiting.method_material(at)}
    for name, (method, sources) in methods.items():
        identity = method['method_code_sha256']
        assert method == dict(cr.APPROVED_WAITING_PROFILES[identity], available_at=at, created_at=at)
        assert cr.sha({'sources': method['source_sha256'], 'runtime': method['runtime']}) == identity
        assert len(method['source_sha256']) == 11 and len(sources) == 7
        assert all(digest(sources[n].encode()) == method['source_sha256'][p] for n,p in cr.WAITING_SOURCE_ATTACHMENTS.items())
    assert old_waiting_material(at) == (old_method, old_sources)
    checks.append('both_full_profiles_and_actual_six_sources_match_independently_observed_source_material')

    @contextmanager
    def fixture():
        t = ConditionalReviewTests(); t.setUp()
        try:
            # Bridge and reconstruction must need no Git, network, or subprocess.
            with patch('subprocess.Popen', side_effect=AssertionError('No subprocess allowed')), \
                 patch('socket.create_connection', side_effect=AssertionError('No network allowed')):
                yield t
        finally:
            t.doCleanups()

    def material_factory(method, sources):
        def observed(when):
            m = dict(copy.deepcopy(method), available_at=when, created_at=when)
            a = copy.deepcopy(sources); a['METHOD.json'] = canonical(m).decode()
            return m, a
        return observed

    def initial(t, label):
        method, sources = methods[label]
        with patch.object(waiting, 'method_material', side_effect=material_factory(method, sources)):
            return waiting.prepare_bundle(t.store, 'waiting-'+label, '2026-09-23T12:00:00Z')

    for profile in methods:
        with fixture() as t:
            b = initial(t, profile); t.commit(b); t.now = '2026-09-23T19:00:00Z'
            output = cr.prepare_outbox(t.store, 'after-'+profile, t.inputs([]), 'new.json', '2026-09-23T12:00:00Z')
            prepared = output.read_bytes(); bridged = json.loads(prepared)
            assert bridged['records'][0]['coverage']['technical_failures'] == 0
            assert all(r['simulation_state']['inventory'] is None and all(v is None for v in r['metrics'].values()) for r in t.reviews(bridged))
            t.commit(bridged); t.now = '2026-09-23T20:00:00Z'
            assert cr.prepare_outbox(t.store, 'after-'+profile, t.inputs([]), 'unused.json', '2026-09-23T12:00:00Z').read_bytes() == prepared
            continued = t.prepare('continue-'+profile, [])
            assert continued['records'][0]['coverage']['technical_failures'] == 0
        checks.append(profile+'_exact_bridge_committed_recovery_and_continuation_without_git_or_network')
        for source in cr.WAITING_SOURCE_ATTACHMENTS:
            for operation in ('missing', 'corrupt'):
                with fixture() as t:
                    b = initial(t, profile)
                    if operation == 'missing': del b['attachments'][source]
                    else: b['attachments'][source] += '\n# synthetic corruption\n'
                    t.commit(b); t.now = '2026-09-23T19:00:00Z'
                    result = t.prepare('refuse-'+profile+'-'+source.replace('.','-')+'-'+operation, [])
                    assert all(r['evaluation_stage'] == 'TECHNICAL_FAILURE' for r in t.reviews(result))
        checks.append(profile+'_all_six_source_attachments_missing_or_changed_rejected')
        for field in ('runtime', 'unbundled-source-map', 'extra-template-field', 'created-at', 'evaluator'):
            with fixture() as t:
                b = initial(t, profile); m = json.loads(b['attachments']['METHOD.json'])
                if field == 'runtime': m['runtime']['python_version'] = '3.12.0'
                elif field == 'unbundled-source-map': m['source_sha256']['researchlib/public.py'] = '0'*64
                elif field == 'extra-template-field': m['source_complete'] = True
                elif field == 'created-at': m['created_at'] = '2026-09-23T17:59:59Z'
                else:
                    for r in t.reviews(b): r['evaluator_version'] = waiting.VERSION+'@sha256:'+'0'*64
                b['attachments']['METHOD.json'] = canonical(m).decode()
                t.commit(b); t.now = '2026-09-23T19:00:00Z'
                result = t.prepare('reject-'+profile+'-'+field, [])
                assert all(r['evaluation_stage'] == 'TECHNICAL_FAILURE' for r in t.reviews(result))
        checks.append(profile+'_runtime_full_map_template_time_and_evaluator_mutations_rejected')

    assert json.loads(old_bundle['attachments']['METHOD.json'])['method_code_sha256'] == 'a1f6f384e885176dbc1680ca4b720ec13c96e2361b84b3f4512ff721cd0c88ae'
    with fixture() as t:
        t.commit(old_bundle); t.now = '2026-09-23T19:00:00Z'
        rejected = t.prepare('reject-actual-fourth', [])
        assert all(r['coverage']['reason_codes'] == ['PREVIOUS_CONDITIONAL_METHOD_NOT_SUPPORTED'] for r in t.reviews(rejected))
    checks.append('actual_self_consistent_fourth_conditional_bundle_rejected_not_only_a_changed_label')
    method, _ = cr.method_material(at)
    print(json.dumps({'state': 'PASS_INDEPENDENT_COMBINED_WAITING_BRIDGE', 'checks': checks,
        'groups': len(checks), 'source_mutation_cases': 24, 'method_mutation_cases': 10,
        'module_sha256': digest((args.code_root/'researchlib/conditional_review.py').read_bytes()),
        'method_code_sha256': method['method_code_sha256'], 'runtime': method['runtime'],
        'production_modified': False, 'real_economic_result': False,
        'scope': 'SYNTHETIC_TEMPORARY_STORES_REAL_CODE_BYTES_NO_GIT_OR_NETWORK_DURING_BRIDGE'}))


if __name__ == '__main__':
    main()
