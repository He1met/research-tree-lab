#!/usr/bin/env python3
"""Explicit local engineering replay of one frozen failure; never prepare an outbox.

Reads the selected project, copies its immutable bundles and the four registered
inputs to a disposable project, observes existing gates, and emits only counters.
No Store commit, network, rule change, raised limit, or natural-run attestation.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from researchlib import formal_review as formal
from researchlib.common import canonical, digest, utc
from researchlib.funding_review import readonly_store


def resource_counters(context):
    old = context.get('old_context', {})
    current = context['encoded_bytes']; historical = old.get('encoded_bytes', 0)
    replay = context.get('public_replay_bytes', 0)
    nodes = len(context['nodes'] | old.get('nodes', set()))
    return {'current_encoded_bytes': current, 'old_encoded_bytes': historical,
            'public_replay_bytes': replay, 'combined_bytes': current + historical + replay,
            'combined_nodes': nodes, 'bytes_limit': formal.legacy.MAX_CONTEXT_BYTES,
            'nodes_limit': formal.MAX_HISTORY_NODES,
            'bytes_exceeded': current + historical + replay > formal.legacy.MAX_CONTEXT_BYTES,
            'nodes_exceeded': nodes > formal.MAX_HISTORY_NODES}


def observe_replay(store, batch_id, inputs, cutoff):
    """Instrumentation delegates unchanged checks and always restores globals."""
    original_check = formal._check_time; original_prepare = formal._prepare_bundle
    original_reserve = formal._reserve; old_reserve = formal.legacy._reserve
    contexts = {}; history = []; failures = []; reservations = []; stack = []
    def label(ctx):
        identity = id(ctx)
        if identity not in contexts: contexts[identity] = len(contexts) + 1
        return contexts[identity]
    def check(ctx):
        try: return original_check(ctx)
        except formal.Rejected as exc:
            failures.append(dict(resource_counters(ctx), context=label(ctx),
                                 reason=str(exc), caller=sys._getframe(1).f_code.co_name))
            raise
    def reserve(delegate, ctx, value):
        before = ctx['encoded_bytes']
        try: return delegate(ctx, value)
        finally:
            reservations.append({'context': label(ctx), 'bytes': ctx['encoded_bytes'] - before,
                                 'caller': sys._getframe(2).f_code.co_name})
    def prepare(store, batch, manifest, requested, ctx):
        ident = label(ctx); parent = stack[-1] if stack else None; stack.append(ident)
        row = {'context': ident, 'parent_context': parent, 'batch_id': batch}
        try:
            result = original_prepare(store, batch, manifest, requested, ctx)
            row['outcome'] = 'RETURNED_ENGINEERING_VALUE_NOT_COMMITTED'
            row['review_stages'] = [r['evaluation_stage'] for r in result['records'] if r['record_type'] == 'review']
            return result
        except formal.Rejected as exc:
            row['outcome'] = str(exc); raise
        finally:
            row['counters'] = resource_counters(ctx)
            row['verified_public_bundles'] = sorted(ctx.get('public_verified_bundles', set()))
            row['cache_counts'] = {k:len(ctx.get(k, {})) for k in ('verified','decode','formal_resolution')}
            history.append(row); stack.pop()
    formal._check_time = check; formal._prepare_bundle = prepare
    formal._reserve = lambda ctx, value: reserve(original_reserve, ctx, value)
    formal.legacy._reserve = lambda ctx, value: reserve(old_reserve, ctx, value)
    root_context = formal._context()
    try:
        try:
            prepare(store, batch_id, inputs, cutoff, root_context)
            outcome = 'RETURNED_ENGINEERING_VALUE_NOT_COMMITTED'
        except formal.Rejected as exc: outcome = str(exc)
    finally:
        formal._check_time = original_check; formal._prepare_bundle = original_prepare
        formal._reserve = original_reserve; formal.legacy._reserve = old_reserve
    # Every nested completed replay contributes exactly once to its parent.
    # This is cumulative validation work, not process resident memory.
    for row in history:
        children = [r for r in history if r['parent_context'] == row['context']]
        row['direct_child_combined_bytes'] = sum(r['counters']['combined_bytes'] for r in children)
        row['child_accounting_equal'] = row['counters']['public_replay_bytes'] == row['direct_child_combined_bytes']
    return {'outcome': outcome, 'checks_rejected': failures, 'history_contexts': history,
            'reservations': reservations, 'final_counters': resource_counters(root_context),
            'all_child_accounting_equal': all(r['child_accounting_equal'] for r in history),
            'limits_unchanged': True, 'outbox_written': False, 'store_committed': False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', required=True)
    args=parser.parse_args(); root=Path(args.project_root); source=readonly_store(root)
    records, metadata, anomalies=source.load(strict=True); assert not anomalies
    installation=json.loads((root/'.local/installation.json').read_text())
    frozen=json.loads((root/'review/daily-20260930/frozen-batch.json').read_text())
    inputs=json.loads((root/'.local/review-outbox/daily-20260927/input-manifest.json').read_text())
    at=frozen['frozen_at']; method,_=formal.method_material(at)
    assert method['method_code_sha256']==installation['formal_method_code_sha256']=='34e0bcfce6515c0ccb5e2f742ab1936b440b6d06cf4b3670049c7993efa63be4'
    visible={k:v for k,v in records.items() if utc(v['available_at'])<=utc(at) and utc(metadata[k]['committed_at'])<=utc(at)}
    files=lambda:{str(p.relative_to(source.root)):digest(p.read_bytes()) for p in sorted((source.root/'bundles').rglob('*')) if p.is_file()}
    before=files(); dataset_ids={request['dataset_ref'] for p in inputs['plans'].values() for request in p['sources']}
    data={}
    for ref in sorted(dataset_ids):
        record=records[ref]; raw=(source.data_root/'objects'/record['sha256']).read_bytes()
        assert digest(raw)==record['sha256'] and len(raw)==record['bytes']
        data[ref]={'sha256':record['sha256'],'bytes':len(raw)}
    with tempfile.TemporaryDirectory(prefix='formal-resource-engineering-') as directory:
        scratch=Path(directory);shutil.copytree(source.root/'bundles',scratch/'.local/store/bundles')
        (scratch/'.local/data/objects').mkdir(parents=True)
        for item in data.values():shutil.copyfile(source.data_root/'objects'/item['sha256'],scratch/'.local/data/objects'/item['sha256'])
        copied=readonly_store(scratch);copy_records,copy_metadata,copy_anomalies=copied.load(strict=True)
        assert not copy_anomalies and copy_records==records and copy_metadata==metadata
        class Snapshot:
            clock=staticmethod(lambda:at)
            def load(self, strict=True):return deepcopy(visible),{k:deepcopy(metadata[k]) for k in visible},[]
            def __getattr__(self,name):return getattr(copied,name)
        result=observe_replay(Snapshot(),frozen['batch_id'],inputs,'2026-09-24T00:06:00Z')
        assert not (scratch/'.local/review-outbox').exists()
    after, after_meta, anomalies=source.load(strict=True)
    assert not anomalies and after==records and after_meta==metadata and files()==before
    for item in data.values():assert digest((source.data_root/'objects'/item['sha256']).read_bytes())==item['sha256']
    result.update(scope='ISOLATED_ENGINEERING_DIAGNOSIS_NOT_NATURAL_REVIEW',
        observed_original_count=len(records),visible_original_count=len(visible),bundle_files_unchanged=len(before),
        bundle_map_sha256=digest(canonical(before)),data_files=data,input_manifest_sha256=digest(canonical(inputs)),
        frozen_batch_sha256=digest(canonical(frozen)),formal_method_sha256=method['method_code_sha256'],
        formal_source_sha256=method['source_sha256'],natural_trigger='UNKNOWN',actual_net=None,
        capacity_unit='CUMULATIVE_CANONICAL_VALIDATION_WORK_NOT_RSS_OR_DISTINCT_RAW_BYTES')
    print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))


if __name__=='__main__':main()
