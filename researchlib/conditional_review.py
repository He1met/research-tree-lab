"""Prepare conditional reviews from registered, decoded files; no production writes.

Only exact frozen plans and reviewed predecessor schemas are understood. Private
kernel inputs/results stay in non-public same-bundle attachments. Official event
completeness, execution order, marks and actual costs remain unproven.
"""
import ast
import json
import platform
import time
from copy import deepcopy
from pathlib import Path

from .common import ContractError, canonical, digest, read_json, safe_id, under, utc
from .contracts import record_ref, validate_record, validate_relationships
from . import funding_review as waiting
from .funding_forward import evaluate, PLAN_HASHES
from .okx_funding_file import normalize_funding_file, VERSION as FUNDING_ADAPTER
from .okx_trade_file import scan_trade_file, VERSION as TRADE_ADAPTER
from .review import freeze_batch, verify_batch_coverage
from .public import public_record, scan_bytes

VERSION = 'funding-conditional-review-v1'
STATE_VERSION = 'conditional-public-state-v1'
PRIVATE_VERSION = 'conditional-private-computation-v1'
# Immutable reviewed profiles, not regenerated from the installed checkout.
# Old profile: approved 9a5259b7 tree; combined profile: e65bb32e field candidate.
APPROVED_WAITING_PROFILES = {'7718ec0e6f94d2c71a8cd66b0baf6b7a77b39c99312b81e744d8095ae34d3115': {'availability_basis': 'SOURCE_BYTES_OBSERVED_AT_PREPARATION_NOT_BACKDATED',
                                                                      'dependency_scope': 'Recursive static '
                                                                                          'local import '
                                                                                          'closure including '
                                                                                          'package '
                                                                                          'initializer; '
                                                                                          'standard library '
                                                                                          'bound by Python '
                                                                                          'version',
                                                                      'method_code_sha256': '7718ec0e6f94d2c71a8cd66b0baf6b7a77b39c99312b81e744d8095ae34d3115',
                                                                      'method_version': 'funding-review-waiting-v1',
                                                                      'native_identity': 'NOT_ATTESTED',
                                                                      'plan_hashes': {'p-btc-funding-long-control-20260923@1': 'a8dd9a25bd4a5353bc8ed479ec41056bcf07704fccb285f2d014a9615358d02c',
                                                                                      'p-btc-funding-short-20260923@1': '65ff62c3603d257b82b3274785fd1bfe2c5a784d215786be4775fe7fa076bce4'},
                                                                      'runtime': {'implementation': 'CPython',
                                                                                  'python_version': '3.9.6',
                                                                                  'third_party_runtime_dependencies': []},
                                                                      'schema_version': '1.0',
                                                                      'scope': 'STATUS_MIGRATION_AND_WAITING_ONLY_NO_ECONOMIC_EVALUATION',
                                                                      'source_coverage': 'NOT_VERIFIED',
                                                                      'source_sha256': {'researchlib/__init__.py': '6a52c32055618076a5a44b9dacc39d79711ef3ab7a4de73f9f5ddc9015268741',
                                                                                        'researchlib/common.py': 'a3e7aa7619acee94e05e733c20a4ae4eb30ff7056f9b0fca0b441ecb55d9b683',
                                                                                        'researchlib/contracts.py': '7929f554936294d08407fd7198a2aa0fdfc72ee466c386c34244a711edbc55fd',
                                                                                        'researchlib/funding_review.py': 'e3b5afd7eeea6754e2723bdb5039c17086da8247330f4983c8d80f1bfb83148a',
                                                                                        'researchlib/novelty.py': 'e7390b597cfd2a978fa3e9b9208213b6cbb0f331407bb762a5a62a1b8b1b3d08',
                                                                                        'researchlib/public.py': 'db4eb97c35a312277798605f76ac334dfd57bbc6fe3b1b6d718cd86f00d20dbd',
                                                                                        'researchlib/readiness.py': 'ad57c793f68a53c848048d84e21370811b7470bf71e8770d3f2a76cb2df059c7',
                                                                                        'researchlib/review.py': '771f64a7764f2c957dcce98cc54cdc1bad5fb4381f9b465175cfa153bba4b906',
                                                                                        'researchlib/snapshot.py': 'e5404cf0775ab6b99906a8115a2bb6cf97c05f86fc8bc9b0979d25bf64f22e15',
                                                                                        'researchlib/store.py': '6a9e7bc0ac8ee533fedb94bab0c87b9217436dbf4d8437f99fba9af8a02e06f6',
                                                                                        'scripts/prepare_funding_review.py': '4290cecc2fdf4a86dca7f235501a06b9eb11e0467a4fe9f79689139c1c4caedf'},
                                                                      'state_schema': 'funding-waiting-state-v1'},
 'd21b004a0efe4295f391a3f82ccba05f6a967b9205d370eabd807a8692f91f65': {'availability_basis': 'SOURCE_BYTES_OBSERVED_AT_PREPARATION_NOT_BACKDATED',
                                                                      'dependency_scope': 'Recursive static '
                                                                                          'local import '
                                                                                          'closure including '
                                                                                          'package '
                                                                                          'initializer; '
                                                                                          'standard library '
                                                                                          'bound by Python '
                                                                                          'version',
                                                                      'method_code_sha256': 'd21b004a0efe4295f391a3f82ccba05f6a967b9205d370eabd807a8692f91f65',
                                                                      'method_version': 'funding-review-waiting-v1',
                                                                      'native_identity': 'NOT_ATTESTED',
                                                                      'plan_hashes': {'p-btc-funding-long-control-20260923@1': 'a8dd9a25bd4a5353bc8ed479ec41056bcf07704fccb285f2d014a9615358d02c',
                                                                                      'p-btc-funding-short-20260923@1': '65ff62c3603d257b82b3274785fd1bfe2c5a784d215786be4775fe7fa076bce4'},
                                                                      'runtime': {'implementation': 'CPython',
                                                                                  'python_version': '3.9.6',
                                                                                  'third_party_runtime_dependencies': []},
                                                                      'schema_version': '1.0',
                                                                      'scope': 'STATUS_MIGRATION_AND_WAITING_ONLY_NO_ECONOMIC_EVALUATION',
                                                                      'source_coverage': 'NOT_VERIFIED',
                                                                      'source_sha256': {'researchlib/__init__.py': '6a52c32055618076a5a44b9dacc39d79711ef3ab7a4de73f9f5ddc9015268741',
                                                                                        'researchlib/common.py': 'a3e7aa7619acee94e05e733c20a4ae4eb30ff7056f9b0fca0b441ecb55d9b683',
                                                                                        'researchlib/contracts.py': '60a65556a02328b309f016a602ba142b887d23771556a907ecce2b71144c6041',
                                                                                        'researchlib/funding_review.py': 'e3b5afd7eeea6754e2723bdb5039c17086da8247330f4983c8d80f1bfb83148a',
                                                                                        'researchlib/novelty.py': 'e7390b597cfd2a978fa3e9b9208213b6cbb0f331407bb762a5a62a1b8b1b3d08',
                                                                                        'researchlib/public.py': '514263bb4038d7d1b1548f31ba9d3d00d67c0f0410990456fc9f02e85e9fd063',
                                                                                        'researchlib/readiness.py': 'ad57c793f68a53c848048d84e21370811b7470bf71e8770d3f2a76cb2df059c7',
                                                                                        'researchlib/review.py': '771f64a7764f2c957dcce98cc54cdc1bad5fb4381f9b465175cfa153bba4b906',
                                                                                        'researchlib/snapshot.py': 'e5404cf0775ab6b99906a8115a2bb6cf97c05f86fc8bc9b0979d25bf64f22e15',
                                                                                        'researchlib/store.py': '6a9e7bc0ac8ee533fedb94bab0c87b9217436dbf4d8437f99fba9af8a02e06f6',
                                                                                        'scripts/prepare_funding_review.py': '4290cecc2fdf4a86dca7f235501a06b9eb11e0467a4fe9f79689139c1c4caedf'},
                                                                      'state_schema': 'funding-waiting-state-v1'}}
WAITING_SOURCE_ATTACHMENTS = {
    'funding_review.py': 'researchlib/funding_review.py',
    'review.py': 'researchlib/review.py',
    'contracts.py': 'researchlib/contracts.py',
    'common.py': 'researchlib/common.py',
    'store.py': 'researchlib/store.py',
    'prepare_funding_review.py': 'scripts/prepare_funding_review.py',
}
MAX_SOURCES = 4
MAX_EVENTS = 20_000
MAX_PRIVATE_BYTES = 32_000_000
MAX_HISTORY_REVIEWS = 64
MAX_HISTORY_NODES = 128
MAX_CONTEXT_BYTES = 128_000_000
MAX_VALIDATION_SECONDS = 180
ORIGIN = 'MANUAL_CONDITIONAL_PREPARATION_NOT_NATURAL'
PUBLIC_SCANNER_SOURCE_HASH = 'db4eb97c35a312277798605f76ac334dfd57bbc6fe3b1b6d718cd86f00d20dbd'
PUBLIC_SCANNER_GIT_URL = 'https://github.com/He1met/research-tree-lab/blob/e65bb32e162ddc21b2513ee4edfd4d90829c5b5b/researchlib/public.py'


class Rejected(ContractError):
    """A fixed reason code safe for public summaries; never exception text."""


def fail(code):
    raise Rejected(code)


def sha(value):
    return digest(canonical(value))


def method_material(prepared_at):
    root = Path(__file__).resolve().parents[1]
    pending = ['researchlib/conditional_review.py', 'scripts/prepare_conditional_review.py']
    sources, attachments = {}, {}
    def enqueue(module):
        for relative in ('/'.join(module) + '.py', '/'.join(module) + '/__init__.py'):
            if (root / relative).is_file():
                pending.append(relative)
                return
    while pending:
        relative = pending.pop()
        if relative in sources:
            continue
        content = (root / relative).read_text(encoding='utf-8')
        sources[relative] = digest(content.encode())
        attachments['SOURCE/' + relative] = content
        package = relative.split('/')[:-1]
        if package and package[0] == 'researchlib':
            pending.append('researchlib/__init__.py')
        for node in ast.walk(ast.parse(content)):
            if isinstance(node, ast.ImportFrom):
                module = (package[:len(package)-node.level+1] if node.level else []) + (node.module.split('.') if node.module else [])
                if module and module[0] == 'researchlib':
                    enqueue(module)
                    for alias in node.names:
                        enqueue(module + [alias.name])
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split('.')[0] == 'researchlib':
                        enqueue(alias.name.split('.'))
    runtime = {'implementation': platform.python_implementation(), 'python_version': platform.python_version(),
               'third_party_runtime_dependencies': []}
    identity = sha({'sources': dict(sorted(sources.items())), 'runtime': runtime})
    method = {'schema_version': '1.0', 'method_version': VERSION, 'method_code_sha256': identity,
              'source_sha256': dict(sorted(sources.items())), 'runtime': runtime,
              'available_at': prepared_at, 'created_at': prepared_at,
              'availability_basis': 'SOURCE_BYTES_OBSERVED_AT_PREPARATION_NOT_BACKDATED',
              'scope': 'CONDITIONAL_OBSERVATIONS_ONLY_NO_FINAL_ACTUAL_RETURN_OR_READINESS',
              'plan_hashes': PLAN_HASHES, 'private_schema': PRIVATE_VERSION, 'public_state_schema': STATE_VERSION}
    if sources.get('researchlib/public.py') != PUBLIC_SCANNER_SOURCE_HASH:
        fail('SOURCE_PUBLIC_EXPORT_EXCEPTION_REVIEW_REQUIRED')
    method['public_archive'] = {'self_contained_method_restore': False,
        'excluded_source_attachments': [{'path': 'SOURCE/researchlib/public.py', 'sha256': PUBLIC_SCANNER_SOURCE_HASH,
            'reason': 'SCANNER_SELF_MATCHES_OWN_PRIVATE_PATH_REGEX', 'git_source_locator': PUBLIC_SCANNER_GIT_URL,
            'locator_scope': 'IMMUTABLE_GIT_REF_NOT_NETWORK_AVAILABILITY_ATTESTATION'}],
        'full_source_closure_retained_locally': True}
    attachments['METHOD.json'] = canonical(method).decode()
    return method, attachments


def _bound_attachment_bytes(store, metadata, review, relative, context, maximum=MAX_PRIVATE_BYTES):
    bundle = metadata[review['review_id']]['bundle_id']
    ref = 'bundle:' + bundle + '/attachments/' + relative
    if bundle not in context['bundles']:
        # Store's unchanged full manifest integrity gate, once per exact bundle.
        manifest, _ = store._read_bundle(store.root / 'bundles' / bundle)
        context['bundles'][bundle] = {entry['path']: entry for entry in manifest['files']}
    resolved = context['bundles'][bundle].get('attachments/' + relative, {})
    if resolved.get('kind') != 'attachment' or not 0 < resolved.get('bytes', 0) <= maximum:
        fail('PREVIOUS_ATTACHMENT_INVALID')
    path = under(store.root / 'bundles' / bundle, 'attachments/' + relative)
    raw = path.read_bytes()
    if len(raw) != resolved['bytes'] or digest(raw) != resolved['sha256']:
        fail('PREVIOUS_ATTACHMENT_HASH_MISMATCH')
    return raw, ref


def _attachment(store, metadata, review, relative, context, maximum=MAX_PRIVATE_BYTES):
    raw, ref = _bound_attachment_bytes(store, metadata, review, relative, context, maximum)
    return json.loads(raw), raw, ref


def _visible(ref, records, metadata, at):
    if ref not in records or ref not in metadata:
        fail('REGISTERED_REFERENCE_REQUIRED')
    record = records[ref]
    if utc(record['available_at']) > utc(at) or utc(metadata[ref]['committed_at']) > utc(at):
        fail('REFERENCE_NOT_AVAILABLE_AND_COMMITTED')
    if record.get('synthetic') is not False:
        fail('SYNTHETIC_REGISTERED_INPUT_REJECTED')
    return record


def decode_sources(store, requests, records, metadata, information_as_of, market_cutoff, *, _deadline=None):
    """Decode registered single files; input cannot supply rows, marks or claims."""
    if not isinstance(requests, list) or len(requests) > MAX_SOURCES:
        fail('SOURCE_REQUEST_LIMIT_OR_SCHEMA')
    events, bindings, audits, identities = {}, [], [], set()
    for request in requests:
        if _deadline is not None and time.monotonic() >= _deadline:
            fail('VALIDATION_TIME_LIMIT_EXCEEDED')
        if not isinstance(request, dict) or set(request) != {'dataset_ref', 'adapter', 'filename', 'declared_partition', 'window'}:
            fail('SOURCE_REQUEST_FIELDS_REJECTED')
        fingerprint = sha(request)
        if fingerprint in identities:
            fail('DUPLICATE_SOURCE_REQUEST')
        identities.add(fingerprint)
        dataset = _visible(request['dataset_ref'], records, metadata, information_as_of)
        if dataset.get('record_type') != 'dataset' or dataset.get('instrument_ref') != 'BTC-USDT-SWAP':
            fail('TARGET_DATASET_REQUIRED')
        adapter = request['adapter']
        role = 'TARGET_TRADE_HISTORY' if adapter == TRADE_ADAPTER else 'TARGET_REALIZED_FUNDING'
        if adapter not in {TRADE_ADAPTER, FUNDING_ADAPTER} or dataset.get('data_role') != role:
            fail('DATA_ROLE_OR_ADAPTER_NOT_SUPPORTED')
        identity = dataset.get('sha256')
        if not isinstance(identity, str) or dataset.get('data_ref') != 'sha256:' + identity:
            fail('REGISTERED_RAW_BYTES_REQUIRED')
        if utc(dataset['acquired_at']) > utc(dataset['available_at']):
            fail('DATASET_ACQUISITION_AFTER_AVAILABILITY')
        path = under(store.data_root, 'objects/' + identity)
        fmt = request['filename'].rsplit('.', 1)[-1]
        manifest = {'schema_version': 1, 'format': fmt, 'filename': request['filename'],
                    'sha256': identity, 'size_bytes': dataset['bytes'], 'source_url': dataset['source_url'],
                    'obtained_at': dataset['acquired_at'], 'declared_partition': request['declared_partition']}
        if adapter == TRADE_ADAPTER:
            if request['window'] is None:
                fail('TRADE_WINDOW_REQUIRED_FOR_CONDITIONAL_INPUT')
            result = scan_trade_file(path, manifest, information_as_of=information_as_of, synthetic=False,
                                     window=request['window'], max_selected_events=MAX_EVENTS,
                                     cancel=(lambda: time.monotonic() >= _deadline) if _deadline is not None else None)
        else:
            if request['window'] is not None or path.stat().st_size > 10_000_000:
                fail('FUNDING_WINDOW_OR_SIZE_REJECTED')
            result = normalize_funding_file(path.read_bytes(), manifest, information_as_of=information_as_of, synthetic=False)
        if _deadline is not None and time.monotonic() >= _deadline:
            fail('VALIDATION_TIME_LIMIT_EXCEEDED')
        audit = result['audit']
        bindings.append({'request': deepcopy(request), 'dataset_sha256': sha(dataset),
                         'dataset_available_at': dataset['available_at'],
                         'dataset_committed_at': metadata[request['dataset_ref']]['committed_at'],
                         'acquired_at': dataset['acquired_at'], 'raw_sha256': identity,
                         'raw_bytes': dataset['bytes']})
        audits.append(audit)
        for event in result['kernel_payload']['events']:
            if utc(event['event_at']) > utc(market_cutoff):
                continue  # Full original file already validated before this cutoff selection.
            ident = event['event_id']
            if ident in events and events[ident] != event:
                fail('CROSS_FILE_EVENT_CONFLICT_REQUIRES_SOURCE_SELECTION')
            events[ident] = event
            if len(events) > MAX_EVENTS:
                fail('TOTAL_EVENT_LIMIT_EXCEEDED')
    payload = {'instrument': 'BTC-USDT-SWAP', 'currency': 'USDT', 'synthetic': False,
               'source_coverage': 'UNKNOWN', 'data_complete': False,
               'events': sorted(events.values(), key=lambda e: (e['event_at'], e['kind'], e['event_id']))}
    return payload, bindings, audits


def _formal_stage(plan, kernel):
    if utc(kernel['information_as_of']) >= utc(plan['effective_from']) and kernel['evaluation_stage'] == 'NOT_YET_EFFECTIVE':
        return 'WAITING_DATA'
    return kernel['evaluation_stage']


def _summary(plan, kernel, private_hash):
    before = utc(kernel['information_as_of']) < utc(plan['effective_from'])
    historical = not before and kernel['evaluation_stage'] == 'NOT_YET_EFFECTIVE'
    return {'schema_version': STATE_VERSION, 'plan_hash': kernel['plan_hash'],
            'state': 'HISTORICAL_PRE_EFFECTIVE_INPUTS_ONLY' if historical else kernel['simulation_state'].get('state', 'WAITING_DATA'),
            'inventory': '0' if before else None,
            'inventory_scope': 'BEFORE_EFFECTIVE_ONLY' if before else 'ACTUAL_INVENTORY_UNKNOWN',
            'historical_pre_effective_cutoff': historical,
            'conditional_state_only': True, 'accepted_observation_count': len(kernel['simulation_state']['event_hashes']),
            'private_computation_sha256': private_hash, 'source_coverage': 'UNKNOWN'}


def _context():
    return {'verified': {}, 'visiting': set(), 'decode': {}, 'bundles': {}, 'nodes': set(),
            'encoded_bytes': 0, 'deadline': time.monotonic() + MAX_VALIDATION_SECONDS}


def _reserve(context, value):
    context['encoded_bytes'] += len(canonical(value))
    if context['encoded_bytes'] > MAX_CONTEXT_BYTES:
        fail('VALIDATION_CONTEXT_SIZE_LIMIT_EXCEEDED')


def _check_time(context):
    if time.monotonic() >= context['deadline']:
        fail('VALIDATION_TIME_LIMIT_EXCEEDED')


def _decoded(context, store, requests, records, metadata, at, cutoff):
    _check_time(context)
    key = sha({'requests': requests, 'information_as_of': at, 'market_cutoff': cutoff})
    if key not in context['decode']:
        result = decode_sources(store, requests, records, metadata, at, cutoff, _deadline=context['deadline'])
        _reserve(context, result)
        context['decode'][key] = result
    return context['decode'][key]


def _verify_kernel(plan, result, prior=None):
    # Public opening hashes bind public summaries; this opening hash binds the
    # predecessor's private kernel state. Neither domain may substitute for the other.
    rebuilt = evaluate(plan, result['input_payload'], result['information_as_of'], result['market_event_cutoff'], previous=prior)
    if result != rebuilt:
        fail('PREVIOUS_KERNEL_TRANSITION_NOT_REPRODUCIBLE')


def _correction_summary(correction, parent, prior, payload):
    if prior is None or not isinstance(correction, dict) or set(correction) != {'previous_review_ref', 'old_input_fingerprint', 'new_input_fingerprint', 'event_diff', 'reason'}:
        fail('CORRECTION_CONTRACT_REQUIRED')
    difference = _event_diff(prior['input_payload'], payload)
    if (correction['previous_review_ref'] != parent['review_id']
            or correction['old_input_fingerprint'] != sha(prior['input_payload'])
            or correction['new_input_fingerprint'] != sha(payload) or correction['event_diff'] != difference
            or not any(difference.values()) or not isinstance(correction['reason'], str)
            or not 1 <= len(correction['reason']) <= 1000):
        fail('CORRECTION_NOT_BOUND_TO_EXACT_INPUT_DIFF')
    return {'diff_sha256': sha(difference), 'old_input_fingerprint': correction['old_input_fingerprint'],
            'new_input_fingerprint': sha(payload), 'counts': {k: len(v) for k, v in difference.items()}}


def _verify_transition(plan, review, private, parent, prior, migration):
    result = private['kernel_result']
    if review.get('opening_state_hash') != sha(parent['simulation_state']):
        fail('PUBLIC_OPENING_STATE_HASH_MISMATCH')
    if review.get('provenance', {}).get('state_migration') != migration:
        fail('STATE_MIGRATION_DOMAIN_MISMATCH')
    correction = private['correction']
    if correction is None:
        if review.get('supersedes') or review.get('correction_reason') or review['provenance'].get('correction_summary') is not None:
            fail('ORDINARY_REVIEW_HAS_CORRECTION_CLAIMS')
        _verify_kernel(plan, result, prior)
    else:
        summary = _correction_summary(correction, parent, prior, result['input_payload'])
        if (review.get('supersedes') != parent['review_id']
                or review.get('correction_reason') != 'EXPLICIT_INPUT_REVISION_SEE_PRIVATE_AUDIT'
                or review['provenance'].get('correction_summary') != summary):
            fail('PUBLIC_PRIVATE_CORRECTION_MISMATCH')
        _verify_kernel(plan, result, None)


def _latest_review_ref(records, metadata, plan_ref, information_as_of, exclude=None):
    candidates = [r for ref, r in records.items() if ref != exclude and r.get('record_type') == 'review'
                  and r.get('plan_ref') == plan_ref and utc(r['available_at']) <= utc(information_as_of)
                  and utc(metadata[ref]['committed_at']) <= utc(information_as_of)]
    if not candidates:
        fail('LATEST_FORMAL_PREDECESSOR_MISSING')
    latest_time = max(utc(r['available_at']) for r in candidates)
    tied = [r for r in candidates if utc(r['available_at']) == latest_time]
    if len(tied) != 1:
        fail('LATEST_FORMAL_PREDECESSOR_AMBIGUOUS')
    return tied[0]['review_id']


def _previous(store, previous, plan, records, metadata, current_method, context=None):
    context = context if context is not None else _context()
    _check_time(context)
    if previous is None:
        fail('PREVIOUS_FORMAL_REVIEW_REQUIRED')
    ident = previous['review_id']
    if previous.get('plan_hash') != sha(plan):
        fail('PREVIOUS_PLAN_HASH_MISMATCH')
    if ident in context['visiting']:
        fail('PREVIOUS_REVIEW_CHAIN_CYCLE')
    if ident in context['verified']:
        return context['verified'][ident]
    if len(context['visiting']) >= MAX_HISTORY_REVIEWS:
        fail('PREVIOUS_REVIEW_CHAIN_LIMIT_EXCEEDED')
    context['nodes'].add(ident)
    if len(context['nodes']) > MAX_HISTORY_NODES:
        fail('PREVIOUS_REVIEW_NODE_LIMIT_EXCEEDED')
    context['visiting'].add(ident)
    try:
        result = _previous_node(store, previous, plan, records, metadata, current_method, context)
        _reserve(context, result)
        _check_time(context)
        context['verified'][ident] = result
        return result
    finally:
        context['visiting'].remove(ident)


def _previous_node(store, previous, plan, records, metadata, current_method, context):
    previous_ref = previous['review_id']
    if previous.get('plan_hash') != sha(plan) or previous.get('plan_ref') != plan['plan_id'] + '@' + str(plan['version']):
        fail('PREVIOUS_PLAN_HASH_MISMATCH')
    _visible(previous_ref, records, metadata, current_method['available_at'])
    if previous.get('evaluator_version') == waiting.LEGACY_METHOD:
        if waiting.LEGACY_REVIEW_HASHES.get(previous_ref) != sha(previous):
            fail('LEGACY_REVIEW_NOT_APPROVED_ORIGINAL')
        waiting._validate_previous(previous, plan, sha(plan), 'unused')
        return None, None, 'APPROVED_LEGACY_EMPTY_STATE_TO_CONDITIONAL'
    parent_ref = previous.get('previous_review_ref')
    if parent_ref in context['visiting']:
        fail('PREVIOUS_REVIEW_CHAIN_CYCLE')
    if parent_ref != _latest_review_ref(records, metadata, previous['plan_ref'], previous['available_at'], previous_ref):
        fail('HISTORICAL_LATEST_PREDECESSOR_SKIPPED')
    parent = _visible(parent_ref, records, metadata, previous['available_at'])
    if (parent.get('record_type') != 'review' or parent.get('plan_ref') != previous['plan_ref']
            or previous.get('opening_state_hash') != sha(parent.get('simulation_state'))
            or previous.get('revision') != parent['revision'] + 1
            or utc(parent['available_at']) >= utc(previous['available_at'])
            or utc(parent['data_cutoff']) > utc(previous['data_cutoff'])):
        fail('FORMAL_PREDECESSOR_LINK_INVALID')
    prior, _, migration = _previous(store, parent, plan, records, metadata, current_method, context)
    material, _, method_ref = _attachment(store, metadata, previous, 'METHOD.json', context, 1_000_000)
    if (previous.get('review_method_ref') != method_ref or material.get('available_at') != previous['available_at']
            or utc(material['available_at']) > utc(metadata[previous_ref]['committed_at'])
            or previous.get('provenance', {}).get('method_available_at') != material['available_at']):
        fail('PREVIOUS_METHOD_BINDING_OR_TIME_INVALID')
    if material.get('method_version') == waiting.VERSION:
        identity = material.get('method_code_sha256')
        template = APPROVED_WAITING_PROFILES.get(identity)
        if template is None:
            fail('WAITING_METHOD_NOT_APPROVED_IDENTITY')
        expected = dict(template, available_at=previous['available_at'], created_at=previous['available_at'])
        if (material != expected
                or identity != sha({'sources': material['source_sha256'], 'runtime': material['runtime']})
                or previous.get('provenance', {}).get('method_code_sha256') != identity):
            fail('WAITING_METHOD_NOT_APPROVED_IDENTITY')
        # These six are the actual attachments emitted by the approved helper.
        # Remaining static dependencies were hash-bound, never bundled by it.
        # Do not substitute current source, execute attachments, or fetch Git.
        for attachment, source in WAITING_SOURCE_ATTACHMENTS.items():
            content, _ = _bound_attachment_bytes(store, metadata, previous, attachment, context)
            if digest(content) != template['source_sha256'][source]:
                fail('WAITING_METHOD_SOURCE_BYTES_MISMATCH')
        if prior is not None or previous.get('supersedes') or previous.get('correction_reason'):
            fail('WAITING_METHOD_CANNOT_RESET_CONDITIONAL_HISTORY')
        evaluator = waiting.VERSION + '@sha256:' + identity
        waiting._validate_previous(previous, plan, sha(plan), evaluator)
        return None, None, 'APPROVED_WAITING_STATE_TO_CONDITIONAL_NOT_ZERO_INVENTORY'
    expected = dict(current_method, available_at=previous['available_at'], created_at=previous['available_at'])
    if material != expected or previous.get('evaluator_version') != VERSION + '@sha256:' + current_method['method_code_sha256']:
        fail('PREVIOUS_CONDITIONAL_METHOD_NOT_SUPPORTED')
    private, raw, _ = _attachment(store, metadata, previous, 'PRIVATE/' + previous_ref + '.json', context)
    if (private.get('schema_version') != PRIVATE_VERSION or private.get('plan_hash') != sha(plan)
            or private.get('information_as_of') != previous['available_at']
            or private.get('method_code_sha256') != material['method_code_sha256']):
        fail('PREVIOUS_PRIVATE_BINDING_INVALID')
    result = private['kernel_result']
    if (result['information_as_of'] != previous['available_at'] or result['market_event_cutoff'] != private['market_event_cutoff']
            or previous.get('evaluation_stage') != _formal_stage(plan, result) or previous.get('data_complete') is not False
            or previous.get('metrics') != {key: None for key in waiting.METRICS}
            or previous.get('provenance', {}).get('evaluation_information_as_of') != previous['available_at']):
        fail('PREVIOUS_RESULT_TIME_OR_PUBLIC_STATUS_MISMATCH')
    for relative, expected_sha in material['source_sha256'].items():
        content, _ = _bound_attachment_bytes(store, metadata, previous, 'SOURCE/' + relative, context)
        if digest(content) != expected_sha:
            fail('PREVIOUS_METHOD_SOURCE_BYTES_MISMATCH')
    if previous.get('simulation_state') != _summary(plan, result, digest(raw)):
        fail('PREVIOUS_PUBLIC_PRIVATE_STATE_MISMATCH')
    _verify_transition(plan, previous, private, parent, prior, migration)
    payload, bindings, audits = _decoded(context, store, private['requests'], records, metadata,
                                         result['information_as_of'], result['market_event_cutoff'])
    if payload != result['input_payload'] or bindings != private['source_bindings'] or audits != private['decode_audits']:
        fail('PREVIOUS_DECODE_NOT_REPRODUCIBLE')
    expected_coverage = _coverage(plan, result['market_event_cutoff'], audits, payload['events'])
    expected_coverage.update(information_as_of=result['information_as_of'],
        reason_codes=['CONDITIONAL_OBSERVATIONS_ONLY', 'SOURCE_COVERAGE_UNKNOWN', 'EXACT_MARK_MISSING', 'ACTUAL_COSTS_UNKNOWN'])
    if previous.get('coverage') != expected_coverage:
        fail('PREVIOUS_COVERAGE_PROJECTION_MISMATCH')
    if previous.get('input_fingerprint') != sha(payload) or private['market_event_cutoff'] != previous['data_cutoff']:
        fail('PREVIOUS_INPUT_OR_CUTOFF_BINDING_INVALID')
    return result, private, 'CONDITIONAL_PREFIX_CONTINUATION'


def _event_diff(old, new):
    a = {e['event_id']: sha(e) for e in old['events']}
    b = {e['event_id']: sha(e) for e in new['events']}
    return {'added': sorted(set(b) - set(a)), 'removed': sorted(set(a) - set(b)),
            'changed': sorted(k for k in set(a) & set(b) if a[k] != b[k])}


def _coverage(plan, cutoff, audits, events):
    required = (utc(plan['effective_from']), utc(cutoff))
    def intervals(adapter):
        pairs = sorted((utc(a['partition_utc']['start_inclusive']), utc(a['partition_utc']['end_exclusive']))
                       for a in audits if a['adapter_version'] == adapter)
        cursor = required[0]
        for lo, hi in pairs:
            if lo > cursor:
                break
            cursor = max(cursor, hi)
        return {'files_decoded': len(pairs), 'declared_partition_union_covers_requested_interval': bool(pairs) and required[1] >= required[0] and cursor >= required[1],
                'meaning': 'DECLARED_PARTITIONS_ONLY_NOT_EVENT_COMPLETENESS'}
    return {'requested_market_event_cutoff': cutoff,
            'actually_evaluated_market_cutoff': None,
            'conditional_computation_market_cutoff': cutoff,
            'observed_event_max_at': max((event['event_at'] for event in events), key=utc) if events else None,
            'cutoff_scope': 'CONDITIONAL_COMPUTATION_ONLY_NOT_COMPLETE_EVALUATED_INTERVAL',
            'file_integrity': 'VERIFIED_BYTES_AND_SCHEMA' if audits else 'NO_INPUT_FILES',
            'trade_partitions': intervals(TRADE_ADAPTER), 'funding_partitions': intervals(FUNDING_ADAPTER),
            'source_event_completeness': 'UNKNOWN', 'exchange_chronology': 'UNKNOWN',
            'exact_settlement_mark': 'MISSING', 'full_mark_path': 'MISSING', 'actual_costs': 'UNKNOWN',
            'source_coverage': 'UNKNOWN', 'result_is_evaluable': False}


def correction_proposal(store, plan_ref, sources, market_event_cutoff, reason):
    """Read-only LOCAL_ONLY exact-diff proposal; no automatic correction or write."""
    at = store.clock()
    records, metadata, anomalies = store.load(strict=True)
    if anomalies:
        fail('STORE_ANOMALY_DURING_CORRECTION_PROPOSAL')
    plan = _visible(plan_ref, records, metadata, at)
    if PLAN_HASHES.get(plan_ref) != sha(plan) or not utc(market_event_cutoff) <= min(utc(at), utc(plan['evaluation_end'])):
        fail('CORRECTION_PLAN_OR_CUTOFF_REJECTED')
    batch = freeze_batch(store, 'conditional-correction-proposal', at, ORIGIN, None)
    item = next((item for item in batch['items'] if item['plan_ref'] == plan_ref), None)
    previous = records.get(item['previous_review_ref']) if item else None
    if previous is None or previous['review_id'] != _latest_review_ref(records, metadata, plan_ref, at):
        fail('LATEST_FORMAL_PREDECESSOR_SKIPPED')
    method, _ = method_material(at)
    old, _, _ = _previous(store, previous, plan, records, metadata, method)
    if old is None or utc(previous['available_at']) >= utc(at) or utc(old['market_event_cutoff']) > utc(market_event_cutoff):
        fail('CORRECTION_REQUIRES_CHRONOLOGICAL_CONDITIONAL_PREDECESSOR')
    payload, _, _ = decode_sources(store, sources, records, metadata, at, market_event_cutoff)
    difference = _event_diff(old['input_payload'], payload)
    if not any(difference.values()) or not isinstance(reason, str) or not 1 <= len(reason) <= 1000:
        fail('CORRECTION_REQUIRES_CHANGED_INPUT_AND_PRIVATE_REASON')
    return {'scope': 'LOCAL_ONLY_PROPOSAL_NOT_PREPARED_OR_COMMITTED',
            'correction': {'previous_review_ref': previous['review_id'],
                           'old_input_fingerprint': sha(old['input_payload']),
                           'new_input_fingerprint': sha(payload), 'event_diff': difference, 'reason': reason}}


def prepare_bundle(store, batch_id, input_manifest, market_event_cutoff=None):
    """Pure preparation; only registered datasets, no arbitrary observation input."""
    safe_id(batch_id)
    if len(batch_id) > 90:
        fail('BATCH_ID_TOO_LONG')
    if not isinstance(input_manifest, dict) or set(input_manifest) != {'schema_version', 'plans'} or type(input_manifest['schema_version']) is not int or input_manifest['schema_version'] != 1 or not isinstance(input_manifest['plans'], dict):
        fail('INPUT_MANIFEST_FIELDS_REJECTED')
    at = store.clock()
    now = utc(at)
    if market_event_cutoff and utc(market_event_cutoff) > now:
        fail('FUTURE_MARKET_CUTOFF_REJECTED')
    records, metadata, anomalies = store.load(strict=True)
    if anomalies or batch_id in records:
        fail('STORE_ANOMALY_OR_BATCH_ALREADY_COMMITTED')
    class FrozenStore:
        clock = staticmethod(lambda: at)
        def load(self, strict=True):
            return deepcopy(records), deepcopy(metadata), []
    batch = freeze_batch(FrozenStore(), batch_id, at, ORIGIN, None)
    if set(input_manifest['plans']) - set(batch['plan_refs']):
        fail('INPUT_PLAN_NOT_IN_FROZEN_BATCH')
    method, attachments = method_material(at)
    bundle_id = 'bundle-' + batch_id
    evaluator = VERSION + '@sha256:' + method['method_code_sha256']
    method_ref = 'bundle:' + bundle_id + '/attachments/METHOD.json'
    disclosure = {'visibility': 'PUBLIC', 'license': 'OWN_ANALYSIS',
                  'public_attachments': ['attachments/' + name for name in sorted(attachments) if name != 'SOURCE/researchlib/public.py'],
                  'scope': 'Authored summaries, method identity and explicitly scanned source. public.py remains local because its scanner matches its own regex; archive is not a self-contained method restore. Private computation never exported.'}
    common = {'schema_version': '1.0', 'created_at': at, 'available_at': at, 'synthetic': False, 'disclosure': disclosure}
    output = []
    context = _context()
    for item in batch['items']:
        ref = item['plan_ref']; plan = records[ref]; previous = records.get(item['previous_review_ref'])
        suffix = digest(ref.encode())[:16]
        rid, fid = 'review-' + batch_id + '-' + suffix, 'feedback-' + batch_id + '-' + suffix
        stage, reasons, summary, migration = 'RULES_INCOMPLETE', ['UNSUPPORTED_OR_MODIFIED_PLAN'], None, None
        cutoff = market_event_cutoff or (min(now, utc(plan['evaluation_end'])).isoformat() if PLAN_HASHES.get(ref) == item['plan_hash'] else at)
        coverage = {'source_coverage': 'UNKNOWN', 'result_is_evaluable': False, 'actually_evaluated_market_cutoff': None}
        fingerprint, correction_public = sha(input_manifest['plans'].get(ref, {})), None
        if PLAN_HASHES.get(ref) == item['plan_hash']:
            try:
                if utc(cutoff) > utc(plan['evaluation_end']):
                    fail('MARKET_CUTOFF_AFTER_ORIGINAL_ENDPOINT')
                _visible(ref, records, metadata, at)
                _visible(item['previous_review_ref'], records, metadata, at)
                if item['previous_review_ref'] != _latest_review_ref(records, metadata, ref, at):
                    fail('LATEST_FORMAL_PREDECESSOR_SKIPPED')
                if previous and (utc(previous['available_at']) >= now or utc(previous['data_cutoff']) > utc(cutoff)):
                    fail('PREDECESSOR_OR_MARKET_TIME_NOT_CHRONOLOGICAL')
                config = input_manifest['plans'].get(ref, {'sources': [], 'correction': None})
                if not isinstance(config, dict) or set(config) != {'sources', 'correction'}:
                    fail('PLAN_INPUT_FIELDS_REJECTED')
                old_result, old_private, migration = _previous(store, previous, plan, records, metadata, method, context)
                payload, bindings, audits = _decoded(context, store, config['sources'], records, metadata, at, cutoff)
                fingerprint = sha(payload)
                correction = config['correction']
                if correction is not None:
                    correction_public = _correction_summary(correction, previous, old_result, payload)
                if old_result and correction is None:
                    difference = _event_diff(old_result['input_payload'], payload)
                    late = any(e['event_id'] in difference['added'] and utc(e['event_at']) <= utc(old_result['market_event_cutoff']) for e in payload['events'])
                    if difference['changed'] or difference['removed'] or late:
                        fail('EXPLICIT_CORRECTION_REQUIRED')
                result = evaluate(plan, payload, at, cutoff, previous=None if correction else old_result)
                _verify_kernel(plan, result, None if correction else old_result)
                private = {'schema_version': PRIVATE_VERSION, 'plan_hash': item['plan_hash'],
                           'method_code_sha256': method['method_code_sha256'], 'information_as_of': at,
                           'market_event_cutoff': cutoff, 'requests': deepcopy(config['sources']),
                           'source_bindings': bindings, 'decode_audits': audits, 'kernel_result': result,
                           'correction': deepcopy(correction)}
                private_raw = canonical(private)
                if len(private_raw) > MAX_PRIVATE_BYTES:
                    fail('PRIVATE_COMPUTATION_SIZE_LIMIT')
                attachments['PRIVATE/' + rid + '.json'] = private_raw.decode()
                summary = _summary(plan, result, digest(private_raw))
                stage = _formal_stage(plan, result)
                reasons = ['CONDITIONAL_OBSERVATIONS_ONLY', 'SOURCE_COVERAGE_UNKNOWN', 'EXACT_MARK_MISSING', 'ACTUAL_COSTS_UNKNOWN']
                coverage = _coverage(plan, cutoff, audits, payload['events'])
            except Exception as exc:
                # No repr/exception messages/rows/paths enter any public field.
                stage = 'TECHNICAL_FAILURE'
                reasons = [str(exc) if isinstance(exc, Rejected) else 'CONDITIONAL_INPUT_OR_STATE_REJECTED']
                summary, correction_public = None, None
                cutoff = previous['data_cutoff'] if previous else plan['available_at']
        elif previous and utc(cutoff) < utc(previous['data_cutoff']):
            cutoff = previous['data_cutoff']
        coverage.update(information_as_of=at, reason_codes=reasons)
        provenance = {'trigger_origin': ORIGIN, 'natural_trigger': False, 'native_task_ref': None,
                      'method_available_at': at, 'method_code_sha256': method['method_code_sha256'],
                      'evaluation_information_as_of': at, 'state_migration': migration,
                      'prior_state_preserved_in': item['previous_review_ref'], 'correction_summary': correction_public}
        review = dict(common, record_type='review', review_id=rid, plan_ref=ref, plan_hash=item['plan_hash'],
                      batch_ref=batch_id, revision=previous['revision'] + 1 if previous else 1,
                      previous_review_ref=item['previous_review_ref'], opening_state_hash=item['opening_state_hash'],
                      review_method_ref=method_ref, evaluator_version=evaluator, data_cutoff=cutoff,
                      data_complete=False, evaluation_stage=stage, simulation_state=summary,
                      metrics={key: None for key in waiting.METRICS}, coverage=coverage, provenance=provenance,
                      evidence_refs=[method_ref], feedback_refs=[fid], input_fingerprint=fingerprint,
                      summary='条件输入复算与缺项处置；来源完整性未证，实际收益与交易状态未知。',
                      limitations=['Conditional observations do not prove a first trade or complete funding/mark path.',
                                   'No FINAL, NOT_TRIGGERED, readiness, actual return or natural execution claim.'])
        if correction_public:
            review.update(supersedes=previous['review_id'], correction_reason='EXPLICIT_INPUT_REVISION_SEE_PRIVATE_AUDIT')
        feedback = dict(common, record_type='feedback', feedback_id=fid, review_ref=rid,
                        status='AVAILABLE_FOR_RESEARCH_NOT_YET_ADOPTED', supported_facts=[stage] + reasons,
                        interpretation='仅支持已声明条件与数据缺口；不支持策略盈利、无效或未触发结论。',
                        proposed_question='保留原规则，补充合法来源的排序、覆盖和精确mark证据。',
                        what_changes='输入与复算版本；原计划和真实可得时点不改。',
                        required_data=['Official event completeness, chronology and exact settlement mark evidence'],
                        provenance=provenance)
        item.update(disposition=stage, review_ref=rid, result_is_evaluable=False, reason_codes=reasons)
        output.extend([review, feedback])
    batch.update(common, summary='全部登记方案逐项处置；条件计算不是完整经济评价。')
    batch['coverage'] = verify_batch_coverage(batch, {record_ref(r): r for r in output})
    batch['coverage'].update(evaluable_results=0, final_results=0,
                             technical_failures=sum(i['disposition'] == 'TECHNICAL_FAILURE' for i in batch['items']))
    batch['complete'] = batch['coverage']['coverage_complete']
    output.insert(0, batch)
    for record in output:
        validate_record(record, 'review')
        public_record(record)
    validate_relationships(dict(records, **{record_ref(r): r for r in output}))
    for name in disclosure['public_attachments']:
        scan_bytes(name, attachments[name[len('attachments/'):]].encode())
    request_hash = sha({'batch_id': batch_id, 'input_manifest': input_manifest, 'market_event_cutoff': market_event_cutoff})
    bundle = {'bundle_id': bundle_id, 'role': 'review', 'request_key': VERSION + ':' + batch_id,
              'records': output, 'attachments': attachments,
              'preparation': {'prepared_at': at, 'method_code_sha256': method['method_code_sha256'],
                              'request_fingerprint': request_hash, 'state': 'OUTBOX_PREPARED_NOT_COMMITTED',
                              'formal_economic_evaluation': False, 'natural_trigger': False}}
    bundle['preparation']['content_sha256'] = sha(bundle)
    return bundle


def prepare_outbox(store, batch_id, input_manifest, relative, market_event_cutoff=None):
    """One immutable preparation per batch; retries return its retained original."""
    safe_id(batch_id)
    retained = under(store.code_root, '.local/review-outbox/.prepared-batches/' + digest(batch_id.encode()) + '.json')
    request_hash = sha({'batch_id': batch_id, 'input_manifest': input_manifest, 'market_event_cutoff': market_event_cutoff})
    if retained.exists():
        saved = read_json(retained)
        content_hash = saved['preparation'].pop('content_sha256')
        method, _ = method_material(saved['preparation']['prepared_at'])
        if (sha(saved) != content_hash or saved['preparation']['request_fingerprint'] != request_hash
                or saved['preparation']['method_code_sha256'] != method['method_code_sha256']):
            fail('PREPARED_BATCH_INPUT_METHOD_OR_CONTENT_CHANGED')
        prepared_at = saved['preparation']['prepared_at']
        if utc(prepared_at) > utc(store.clock()) or saved.get('bundle_id') != 'bundle-' + batch_id:
            fail('RECOVERY_TIME_OR_IDENTITY_INVALID')
        records, metadata, anomalies = store.load(strict=True)
        if anomalies:
            fail('STORE_ANOMALY_DURING_PREPARATION_RECOVERY')
        committed_refs = {ref for ref in records if metadata[ref]['bundle_id'] == saved['bundle_id']}
        if committed_refs:
            manifest = read_json(under(store.root / 'bundles' / saved['bundle_id'], 'manifest.json'))
            expected_files = {'records/' + record['record_type'] + '/' + record_ref(record) + '.json': canonical(record)
                              for record in saved['records']}
            expected_files.update({'attachments/' + name: content.encode() for name, content in saved['attachments'].items()})
            actual_files = {entry['path']: (entry['sha256'], entry['bytes']) for entry in manifest['files']}
            if (committed_refs != {record_ref(record) for record in saved['records']}
                    or manifest['producer_role'] != saved['role'] or manifest['request_key'] != saved['request_key']
                    or actual_files != {name: (digest(raw), len(raw)) for name, raw in expected_files.items()}):
                fail('PREPARED_BATCH_DIFFERS_FROM_COMMITTED_ORIGINAL')
        visible = {ref: record for ref, record in records.items()
                   if metadata[ref]['bundle_id'] != saved['bundle_id']
                   and utc(metadata[ref]['committed_at']) <= utc(prepared_at)
                   and utc(record['available_at']) <= utc(prepared_at)}
        class RecoverySnapshot:
            clock = staticmethod(lambda: prepared_at)
            def load(self, strict=True):
                return deepcopy(visible), {ref: deepcopy(metadata[ref]) for ref in visible}, []
            def __getattr__(self, name):
                return getattr(store, name)
        expected = prepare_bundle(RecoverySnapshot(), batch_id, input_manifest, market_event_cutoff)
        saved['preparation']['content_sha256'] = content_hash
        if canonical(saved) != canonical(expected):
            fail('RECOVERED_BUNDLE_SEMANTICS_DIFFER_FROM_FROZEN_REQUEST')
        return retained
    bundle = prepare_bundle(store, batch_id, input_manifest, market_event_cutoff)
    return waiting.write_outbox(store.code_root, relative, bundle)
