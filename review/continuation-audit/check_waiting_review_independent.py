"""Independent temporary-store probes; no production commit or economic input."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile


def main():
    code = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(code))
    from researchlib import Store
    from researchlib.common import ContractError, canonical, digest
    from researchlib.funding_review import prepare_bundle, write_outbox, method_material
    from researchlib.public import scan_bytes
    research = json.loads((code / 'research/bootstrap-v1/research_bundle.json').read_text())['records']
    legacy = json.loads((code / 'review/bootstrap-review/review_bundle.json').read_text())['records']
    cases = []

    def reviews(b):
        return [r for r in b['records'] if r['record_type'] == 'review']

    def commit(s, b):
        s.commit_bundle(b['bundle_id'], b['role'], b['records'], b['attachments'], request_key=b['request_key'])

    def case(name, function):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            now = ['2026-09-22T18:07:00Z']
            s = Store(temp, clock=lambda: now[0])
            s.commit_bundle('fixture-research', 'research', deepcopy(research))
            now[0] = '2026-09-22T18:14:00Z'
            s.commit_bundle('fixture-legacy', 'review', deepcopy(legacy))
            now[0] = '2026-09-22T20:00:00Z'
            function(s, now, Path(temp))
        cases.append({'case': name, 'result': 'PASS'})

    def repeated_batch(s, now, root):
        first = prepare_bundle(s, 'same-batch'); file = write_outbox(root, 'first.json', first)
        before = file.read_bytes(); now[0] = '2026-09-22T20:01:00Z'
        second = prepare_bundle(s, 'same-batch')
        try:
            write_outbox(root, 'other-name.json', second)
        except (ContractError, FileExistsError):
            pass
        else:
            raise AssertionError('Same batch acquired two distinct prepared identities')
        assert file.read_bytes() == before
    case('same_batch_cannot_change_freeze_by_output_alias', repeated_batch)

    def temporal(s, now, root):
        before, _, _ = s.load(strict=True)
        initial_hashes = {ref: digest(canonical(r)) for ref, r in before.items()}
        a = prepare_bundle(s, 'a'); commit(s, a)
        assert all(r['evaluation_stage'] == 'NOT_YET_EFFECTIVE' for r in reviews(a))
        now[0] = '2026-09-23T08:00:00Z'; b = prepare_bundle(s, 'b'); commit(s, b)
        now[0] = '2026-09-25T08:00:00Z'; c = prepare_bundle(s, 'c'); commit(s, c)
        prev = {r['plan_ref']: r for r in reviews(b)}
        for r in reviews(c):
            assert r['evaluation_stage'] == 'WAITING_DATA' and not r['data_complete']
            assert r['simulation_state']['inventory'] is None and all(v is None for v in r['metrics'].values())
            assert r['opening_state_hash'] == digest(canonical(prev[r['plan_ref']]['simulation_state']))
            assert r['previous_review_ref'] == prev[r['plan_ref']]['review_id']
            assert r['provenance']['method_available_at'] == now[0]
            assert r['provenance']['natural_trigger'] is False and r['provenance']['native_task_ref'] is None
        after, _, _ = s.load(strict=True)
        assert all(digest(canonical(after[ref])) == h for ref, h in initial_hashes.items())
    case('legacy_bridge_cross_day_unknown_inventory_endpoint_waiting_immutable_old', temporal)

    def clone_legacy(s, now, root):
        original = deepcopy(next(r for r in legacy if r['record_type'] == 'review'))
        original.update(review_id='forged-legacy-label', revision=2, supersedes=original['review_id'],
                        correction_reason='SYNTHETIC_PROBE', created_at='2026-09-22T19:00:00Z',
                        available_at='2026-09-22T19:00:00Z', feedback_refs=[])
        s.commit_bundle('forged-label', 'review', [original])
        b = prepare_bundle(s, 'check-clone')
        assert next(r for r in reviews(b) if r['plan_ref'] == original['plan_ref'])['evaluation_stage'] == 'TECHNICAL_FAILURE'
        assert sum(r['evaluation_stage'] == 'NOT_YET_EFFECTIVE' for r in reviews(b)) == 1
    case('legacy_method_string_and_empty_state_cannot_impersonate_original', clone_legacy)

    def fake_method(s, now, root):
        first = prepare_bundle(s, 'first'); commit(s, first)
        original = reviews(first)[0]; bad = deepcopy(original)
        now[0] = '2026-09-22T20:01:00Z'
        bad.update(review_id='fake-method', revision=original['revision'] + 1,
                   supersedes=original['review_id'], correction_reason='SYNTHETIC_PROBE',
                   created_at=now[0], available_at=now[0], review_method_ref='unresolved-method', feedback_refs=[])
        s.commit_bundle('fake-method', 'review', [bad])
        now[0] = '2026-09-22T20:02:00Z'; b = prepare_bundle(s, 'next')
        r = next(r for r in reviews(b) if r['plan_ref'] == original['plan_ref'])
        assert r['evaluation_stage'] == 'TECHNICAL_FAILURE' and r['simulation_state'] is None
        assert r['opening_state_hash'] == digest(canonical(bad['simulation_state']))
    case('dangling_previous_method_is_item_failure_not_accepted_continuation', fake_method)

    def unknown_plan(s, now, root):
        p = deepcopy(next(r for r in research if r['record_type'] == 'plan'))
        p.update(plan_id='unknown-plan'); p.pop('plan_ref', None)
        s.commit_bundle('unknown-plan', 'research', [p])
        b = prepare_bundle(s, 'all-plans')
        assert b['records'][0]['coverage']['registered'] == 3
        assert len(reviews(b)) == 3
        assert sum(r['evaluation_stage'] == 'RULES_INCOMPLETE' for r in reviews(b)) == 1
        assert b['records'][0]['coverage']['evaluable_results'] == 0
        assert b['records'][0]['coverage']['final_results'] == 0
    case('unknown_plan_in_full_registry_fails_separately_no_economic_coverage', unknown_plan)

    def late_plan(s, now, root):
        p = deepcopy(next(r for r in research if r['record_type'] == 'plan'))
        p.update(plan_id='late-commit'); p.pop('plan_ref', None)
        now[0] = '2026-09-22T21:00:00Z'; s.commit_bundle('late-plan', 'research', [p])
        now[0] = '2026-09-22T20:00:00Z'
        b = prepare_bundle(s, 'historical-freeze')
        assert b['records'][0]['coverage']['registered'] == 2
        assert 'late-commit@1' not in b['records'][0]['plan_refs']
    case('late_commit_does_not_leak_via_backdated_available_at', late_plan)

    def privacy(s, now, root):
        b = prepare_bundle(s, 'private-check')
        for r in b['records']:
            scan_bytes('record.json', canonical(r))
            assert r['provenance']['natural_trigger'] is False
        for name, content in b['attachments'].items():
            scan_bytes(name, content.encode())
        raw = canonical(b)
        assert str(root).encode() not in raw
        assert b'raw_fields' not in raw
        for kwargs in ({'native_task_ref': 'forged'}, {'information_as_of': '2020-01-01T00:00:00Z'}):
            try:
                prepare_bundle(s, 'bad-identity', **kwargs)
            except TypeError:
                pass
            else:
                raise AssertionError('Free native identity or backdating accepted')
    case('public_outputs_have_no_private_or_raw_data_no_free_native_backdate', privacy)

    material, _ = method_material('2026-09-22T20:00:00Z')
    sources = material['source_sha256']
    for required in ('__init__.py', 'snapshot.py', 'readiness.py', 'public.py', 'novelty.py', 'funding_review.py', 'prepare_funding_review.py'):
        assert any(Path(name).name == required for name in sources), 'Missing dependency: ' + required
    cases.append({'case': 'local_python_import_hash_closure_includes_package_side_imports', 'result': 'PASS'})
    files = ['researchlib/funding_review.py', 'scripts/prepare_funding_review.py', 'tests/test_funding_review.py']
    result = {'decision': 'PASS_WAITING_REVIEW_OUTBOX_ONLY', 'synthetic_temporary_store_probe_groups': cases,
              'source_sha256': {f: hashlib.sha256((code / f).read_bytes()).hexdigest() for f in files},
              'formal_economic_results': False, 'natural_review_proven': False,
              'production_store_writes': False, 'new_real_market_data': False}
    Path(__file__).with_name('waiting-review-independent-receipt.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'decision': result['decision'], 'probe_groups': len(cases)}))


if __name__ == '__main__':
    main()
