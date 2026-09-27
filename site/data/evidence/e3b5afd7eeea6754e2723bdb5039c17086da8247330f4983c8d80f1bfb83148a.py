"""Prepare immutable waiting-status reviews; never calculate or commit economics.

Only the two exact sealed plans and explicit empty-state schemas are understood.
Method availability is observed at preparation, never backdated to the old plan.
No caller-provided native identity, coverage flag, market rows or metrics enter.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from pathlib import Path
import os
import ast
import platform
import uuid

from .common import ContractError, canonical, digest, now_iso, read_json, safe_id, safe_relative, under, utc
from .contracts import record_ref, validate_record, validate_relationships
from .review import freeze_batch, verify_batch_coverage
from .store import Store

VERSION = 'funding-review-waiting-v1'
STATE_SCHEMA = 'funding-waiting-state-v1'
ORIGIN = 'MANUAL_PREPARATION_NOT_NATURAL'
LEGACY_METHOD = 'independent-forward-status-v1@sha256:0cf401a81d83fc989b84ea70339ddbb6ca68f71882ef79f9f889b64f2dca2455'
PLAN_HASHES = {
    'p-btc-funding-short-20260923@1': '65ff62c3603d257b82b3274785fd1bfe2c5a784d215786be4775fe7fa076bce4',
    'p-btc-funding-long-control-20260923@1': 'a8dd9a25bd4a5353bc8ed479ec41056bcf07704fccb285f2d014a9615358d02c',
}
LEGACY_REVIEW_HASHES = {
    'review-btc-funding-long-control-manual-20260923-v1': 'c39f6f1f92be9e6f2cb12ea3919a4b97d0c107d6f45910a32f8591eced7b32e5',
    'review-btc-funding-short-manual-20260923-v1': 'ab50b6a7d78979d9ae63f65d59d683885564a31a37df6dfcb47d802a32241edd',
}
LEGACY_KEYS = {'continuation', 'currency', 'entry_fee', 'entry_fill', 'exit_fee', 'exit_fill',
               'funding_cashflow', 'inventory', 'last_event_at', 'processed_event_ids', 'slippage_cost', 'state'}
METRICS = ('actual_total_cost', 'equity_path', 'funding_cashflow', 'gross_price_pnl',
           'holding_period', 'net_pnl', 'actual_net', 'observed_path_drawdown',
           'realized_pnl', 'trade_count', 'unrealized_pnl')


def readonly_store(project_root):
    """Use the actual Store reader without its mkdir-on-initialization behavior."""
    root = Path(project_root).resolve()
    installation = root / '.local/installation.json'
    config = read_json(installation) if installation.exists() else {}
    store = Store.__new__(Store)
    store.code_root = root
    store.root = store._stable_root(config.get('store_root') or '.local/store')
    store.data_root = store._stable_root(config.get('data_root') or '.local/data')
    store.clock = now_iso
    if not (store.root / 'bundles').is_dir():
        raise ContractError('Existing stable store required; preparation never creates a store')
    return store


def _local_source_closure():
    """Conservative static closure, including package initializers and CLI imports."""
    root = Path(__file__).resolve().parents[1]
    pending = ['researchlib/funding_review.py', 'scripts/prepare_funding_review.py']
    sources = {}
    def enqueue(module):
        stem = '/'.join(module)
        for relative in (stem + '.py', stem + '/__init__.py'):
            if (root / relative).is_file():
                pending.append(relative)
                return
    while pending:
        relative = pending.pop()
        if relative in sources:
            continue
        text = (root / relative).read_text(encoding='utf-8')
        sources[relative] = digest(text.encode())
        package = relative.split('/')[:-1]
        if package and package[0] == 'researchlib':
            pending.append('researchlib/__init__.py')
        for node in ast.walk(ast.parse(text)):
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
    return dict(sorted(sources.items()))


def method_material(prepared_at):
    base = Path(__file__).resolve().parent
    names = ('funding_review.py', 'review.py', 'contracts.py', 'common.py', 'store.py')
    attachments = {name: (base / name).read_text(encoding='utf-8') for name in names}
    attachments['prepare_funding_review.py'] = (base.parent / 'scripts/prepare_funding_review.py').read_text(encoding='utf-8')
    sources = _local_source_closure()
    runtime = {'implementation': platform.python_implementation(), 'python_version': platform.python_version(),
               'third_party_runtime_dependencies': []}
    code_hash = digest(canonical({'sources': sources, 'runtime': runtime}))
    method = {'schema_version': '1.0', 'method_version': VERSION,
              'method_code_sha256': code_hash, 'source_sha256': sources, 'runtime': runtime,
              'dependency_scope': 'Recursive static local import closure including package initializer; standard library bound by Python version',
              'available_at': prepared_at, 'created_at': prepared_at,
              'availability_basis': 'SOURCE_BYTES_OBSERVED_AT_PREPARATION_NOT_BACKDATED',
              'plan_hashes': PLAN_HASHES, 'state_schema': STATE_SCHEMA,
              'scope': 'STATUS_MIGRATION_AND_WAITING_ONLY_NO_ECONOMIC_EVALUATION',
              'source_coverage': 'NOT_VERIFIED', 'native_identity': 'NOT_ATTESTED'}
    attachments['METHOD.json'] = canonical(method).decode()
    return method, attachments


def _validate_method_evidence(store, previous, metadata, method, records):
    if previous is None:
        return
    if previous.get('evaluator_version') == LEGACY_METHOD:
        if LEGACY_REVIEW_HASHES.get(previous['review_id']) != digest(canonical(previous)):
            raise ContractError('LEGACY_REVIEW_NOT_ONE_OF_TWO_FROZEN_ORIGINALS')
        return  # Exact original bytes bind the existing pre-effective status method.
    ref = previous.get('review_method_ref')
    bundle_id = metadata[previous['review_id']]['bundle_id']
    expected = 'bundle:' + bundle_id + '/attachments/METHOD.json'
    if ref != expected:
        raise ContractError('PREVIOUS_METHOD_NOT_BOUND_TO_COMMITTED_REVIEW_BUNDLE')
    resolved = store.resolve_evidence(ref, records)
    path = under(store.root / 'bundles' / bundle_id, 'attachments/METHOD.json')
    raw = path.read_bytes()
    if resolved.get('kind') != 'attachment' or resolved.get('sha256') != digest(raw):
        raise ContractError('PREVIOUS_METHOD_BYTES_NOT_VERIFIED')
    evidence = read_json(path)
    expected_method = dict(method, available_at=previous['available_at'], created_at=previous['available_at'])
    if evidence != expected_method or previous.get('provenance', {}).get('method_available_at') != previous['available_at']:
        raise ContractError('PREVIOUS_METHOD_IDENTITY_OR_AVAILABILITY_MISMATCH')
    if utc(evidence['available_at']) > utc(metadata[previous['review_id']]['committed_at']):
        raise ContractError('PREVIOUS_METHOD_NOT_AVAILABLE_WHEN_COMMITTED')


def _zero(value):
    if not isinstance(value, str):
        return False
    try:
        number = Decimal(value)
        return number.is_finite() and number == 0
    except InvalidOperation:
        return False


def _waiting_state(plan_hash, before_effective):
    return {'schema_version': STATE_SCHEMA, 'plan_hash': plan_hash,
            'state': 'NOT_STARTED_BEFORE_EFFECTIVE' if before_effective else 'WAITING_DATA_NO_VERIFIED_EVENTS',
            'currency': 'USDT', 'inventory': '0' if before_effective else None,
            'inventory_scope': 'BEFORE_EFFECTIVE_ONLY' if before_effective else 'UNKNOWN_AFTER_EFFECTIVE',
            'entry_fill': None, 'exit_fill': None, 'last_event_at': None,
            'processed_event_ids': [], 'event_hashes': {}, 'initial_notional': None,
            'evaluated_market_cutoff': None,
            'observation_scope': 'NO_ACCEPTED_EVENTS_DOES_NOT_PROVE_NO_MARKET_EVENTS'}


def _validate_previous(previous, plan, plan_hash, evaluator):
    if previous is None:
        raise ContractError('PREVIOUS_FORMAL_REVIEW_REQUIRED')
    if previous.get('plan_hash') != plan_hash:
        raise ContractError('PREVIOUS_PLAN_HASH_MISMATCH')
    state = previous.get('simulation_state')
    if not isinstance(state, dict):
        raise ContractError('UNKNOWN_PREVIOUS_STATE')
    if previous.get('evaluator_version') == LEGACY_METHOD and previous.get('review_method_ref') == LEGACY_METHOD:
        if set(state) != LEGACY_KEYS or state.get('state') != 'NOT_STARTED_BEFORE_EFFECTIVE':
            raise ContractError('UNKNOWN_LEGACY_STATE_SCHEMA')
        if previous.get('evaluation_stage') != 'NOT_YET_EFFECTIVE' or utc(previous['data_cutoff']) >= utc(plan['effective_from']):
            raise ContractError('LEGACY_STATE_NOT_PRE_EFFECTIVE')
        if state.get('currency') != 'USDT' or not _zero(state.get('inventory')):
            raise ContractError('LEGACY_INVENTORY_NOT_PROVEN_ZERO')
        if state.get('processed_event_ids') != [] or any(state.get(k) is not None for k in
                ('entry_fill', 'exit_fill', 'last_event_at', 'entry_fee', 'exit_fee', 'funding_cashflow', 'slippage_cost')):
            raise ContractError('LEGACY_EVENTS_FILLS_OR_COSTS_PRESENT')
        if not isinstance(state.get('continuation'), str):
            raise ContractError('UNKNOWN_LEGACY_CONTINUATION')
        return 'LEGACY_PRE_EFFECTIVE_EMPTY_STATE_TO_VERSIONED_WAITING_STATE'
    if previous.get('evaluator_version') == evaluator:
        before = previous.get('evaluation_stage') == 'NOT_YET_EFFECTIVE'
        if previous.get('evaluation_stage') not in {'NOT_YET_EFFECTIVE', 'WAITING_DATA'}:
            raise ContractError('PREVIOUS_STATUS_NOT_CONTINUABLE')
        if state != _waiting_state(plan_hash, before):
            raise ContractError('WAITING_STATE_CHANGED_OR_CONTAINS_UNPROVEN_POSITION')
        if before and utc(previous['provenance']['evaluation_information_as_of']) >= utc(plan['effective_from']):
            raise ContractError('PREVIOUS_ZERO_INVENTORY_OUTSIDE_PRE_EFFECTIVE_TIME')
        return 'VERSIONED_WAITING_STATE_CONTINUATION_NO_EVENT_REPLAY'
    raise ContractError('UNKNOWN_PREVIOUS_EVALUATOR_OR_STATE')


def prepare_bundle(store, batch_id, market_event_cutoff=None):
    """Freeze all real plan versions at current clock; return an uncommitted bundle.

    Deliberately no information-as-of override: new method availability and this
    batch's information cutoff are the actual current preparation observation.
    Market cutoff may be historical, but cannot exceed now or the frozen endpoint.
    """
    safe_id(batch_id)
    if len(batch_id) > 90:
        raise ContractError('Batch ID too long')
    prepared_at = store.clock()
    now = utc(prepared_at)
    requested = utc(market_event_cutoff) if market_event_cutoff is not None else None
    if requested and requested > now:
        raise ContractError('Future market cutoff rejected')
    records, metadata, anomalies = store.load(strict=True)
    if anomalies:
        raise ContractError('Store anomalies require investigation before freezing batch')
    if batch_id in records:
        raise ContractError('Batch already committed; reuse its original outbox, do not regenerate')
    # freeze_batch uses one already-verified read, avoiding a moving registry.
    class FrozenStore:
        clock = staticmethod(lambda: prepared_at)
        def load(self, strict=True):
            return deepcopy(records), deepcopy(metadata), []
    batch = freeze_batch(FrozenStore(), batch_id, prepared_at, ORIGIN, None)
    bundle_id = 'bundle-' + batch_id
    method, attachments = method_material(prepared_at)
    evaluator = VERSION + '@sha256:' + method['method_code_sha256']
    method_ref = 'bundle:' + bundle_id + '/attachments/METHOD.json'
    disclosure = {'visibility': 'PUBLIC', 'license': 'OWN_ANALYSIS',
                  'public_attachments': ['attachments/' + name for name in attachments],
                  'scope': 'Status-only own analysis and method source; no market source rows'}
    common = {'schema_version': '1.0', 'created_at': prepared_at, 'available_at': prepared_at,
              'synthetic': False, 'disclosure': disclosure}
    provenance = {'trigger_origin': ORIGIN, 'natural_trigger': False, 'native_task_ref': None,
                  'native_identity_evidence': 'NOT_ATTESTED_BY_THIS_HELPER',
                  'evaluation_information_as_of': prepared_at,
                  'method_available_at': prepared_at, 'method_code_sha256': method['method_code_sha256']}
    output = []
    for item in batch['items']:
        ref = item['plan_ref']; plan = records[ref]
        previous = records.get(item['previous_review_ref'])
        suffix = digest(ref.encode())[:16]
        review_id = 'review-' + batch_id + '-' + suffix
        feedback_id = 'feedback-' + batch_id + '-' + suffix
        stage, reasons, migration, state = 'RULES_INCOMPLETE', ['UNSUPPORTED_OR_MODIFIED_PLAN'], None, None
        cutoff = market_event_cutoff or prepared_at
        if PLAN_HASHES.get(ref) == item['plan_hash']:
            cutoff = market_event_cutoff or min(now, utc(plan['evaluation_end'])).isoformat()
            try:
                if utc(cutoff) > utc(plan['evaluation_end']):
                    raise ContractError('MARKET_CUTOFF_AFTER_ORIGINAL_ENDPOINT')
                for used_ref in (ref, item['previous_review_ref']):
                    if used_ref and (utc(metadata[used_ref]['committed_at']) > now or utc(records[used_ref]['available_at']) > now):
                        raise ContractError('INPUT_NOT_COMMITTED_AND_AVAILABLE_BY_BATCH_CUTOFF')
                if previous and (utc(previous['available_at']) >= now or utc(previous['data_cutoff']) > utc(cutoff)):
                    raise ContractError('CONTINUATION_TIME_NOT_CHRONOLOGICAL')
                _validate_method_evidence(store, previous, metadata, method, records)
                migration = _validate_previous(previous, plan, item['plan_hash'], evaluator)
                before = now < utc(plan['effective_from'])
                stage = 'NOT_YET_EFFECTIVE' if before else 'WAITING_DATA'
                state = _waiting_state(item['plan_hash'], before)
                reasons = ['FORMAL_SOURCE_ADAPTER_NOT_BOUND_TO_STATUS_METHOD', 'SOURCE_COVERAGE_NOT_VERIFIED',
                           'ACTUAL_COSTS_UNKNOWN', 'NO_ACCEPTED_MARKET_INPUTS']
                if before:
                    reasons.append('ORIGINAL_ENTRY_EVENTS_NOT_YET_OCCURRED')
                elif now < utc(plan['evaluation_end']):
                    reasons.append('REMAINING_ORIGINAL_WINDOW_EVENTS_NOT_YET_OCCURRED')
                else:
                    reasons.append('ORIGINAL_WINDOW_ELAPSED_REQUIRED_INPUTS_NOT_ACCEPTED')
            except (ContractError, KeyError, TypeError, ValueError) as exc:
                stage, reasons = 'TECHNICAL_FAILURE', [str(exc) if isinstance(exc, ContractError) else 'MALFORMED_PREVIOUS_STATE']
                # No reset/copy of unknown state or raw rows: preserve its immutable reference/hash.
                state = None
                cutoff = previous['data_cutoff'] if previous else plan['available_at']
        elif previous and utc(cutoff) < utc(previous['data_cutoff']):
            cutoff = previous['data_cutoff']
        coverage = {'information_as_of': prepared_at,
                    'market_event_cutoff': cutoff if stage in {'NOT_YET_EFFECTIVE', 'WAITING_DATA'} else None,
                    'requested_market_event_cutoff': market_event_cutoff,
                    'actually_evaluated_market_cutoff': None, 'source_coverage': 'NOT_VERIFIED',
                    'reason_codes': reasons, 'original_hash_verified': PLAN_HASHES.get(ref) == item['plan_hash'],
                    'result_is_evaluable': False}
        review = dict(common, record_type='review', review_id=review_id, plan_ref=ref,
                      plan_hash=item['plan_hash'], batch_ref=batch_id,
                      revision=previous['revision'] + 1 if previous else 1,
                      previous_review_ref=item['previous_review_ref'], opening_state_hash=item['opening_state_hash'],
                      review_method_ref=method_ref, evaluator_version=evaluator,
                      data_cutoff=cutoff, data_complete=False, evaluation_stage=stage,
                      simulation_state=state, metrics={key: None for key in METRICS}, coverage=coverage,
                      provenance=dict(provenance, state_migration=migration,
                                      prior_state_preserved_in=item['previous_review_ref'],
                                      input_committed_at={k: metadata[k]['committed_at'] for k in (ref, item['previous_review_ref']) if k}),
                      evidence_refs=[method_ref], feedback_refs=[feedback_id],
                      input_fingerprint=digest(canonical({'plan_hash': item['plan_hash'],
                          'previous_review_ref': item['previous_review_ref'], 'opening_state_hash': item['opening_state_hash'],
                          'cutoff': cutoff, 'information_as_of': prepared_at, 'evaluator': evaluator})),
                      summary='状态核对与等待处置；未执行经济回放，收益、费用、交易次数均未知。',
                      limitations=['No accepted events does not prove zero trades, zero funding or no entry.',
                                   'Independent hypothetical plans are not an aggregate account result.'])
        feedback = dict(common, record_type='feedback', feedback_id=feedback_id, review_ref=review_id,
                        status='AVAILABLE_FOR_RESEARCH_NOT_YET_ADOPTED', provenance=provenance,
                        supported_facts=[stage] + reasons,
                        interpretation='只支持当前方法、输入及状态边界，不支持策略有效或无效的经济判断。',
                        proposed_question='核验原窗口官方来源、完整覆盖与可得时点，再按原规则版本化复核。',
                        what_changes='补齐证据与方法引用；不改变旧方案信号、数量、窗口或成本情景。',
                        required_data=['Audited official source adapter and per-role coverage evidence',
                                       'Original-window target trades, marks, settlements and verified cost scope'],
                        limitations=['This feedback is newly prepared; no successor adoption is asserted.'])
        item.update(disposition=stage, review_ref=review_id, result_is_evaluable=False, reason_codes=reasons)
        output.extend([review, feedback])
    batch.update(common, provenance=provenance, summary='固定全部正式版本逐项处置；经济评价与最终结果均为0，不是策略通过。')
    batch['coverage'] = verify_batch_coverage(batch, {record_ref(r): r for r in output})
    batch['coverage'].update(evaluable_results=0, final_results=0,
                             technical_failures=sum(i['disposition'] == 'TECHNICAL_FAILURE' for i in batch['items']),
                             rules_incomplete=sum(i['disposition'] == 'RULES_INCOMPLETE' for i in batch['items']))
    batch['complete'] = batch['coverage']['coverage_complete']
    output.insert(0, batch)
    for record in output:
        ref = validate_record(record, 'review')
        if ref in records:
            raise ContractError('Output identity already committed; preparation cannot overwrite')
    validate_relationships(dict(records, **{record_ref(r): r for r in output}))
    return {'bundle_id': bundle_id, 'role': 'review', 'request_key': VERSION + ':' + batch_id,
            'records': output, 'attachments': attachments,
            'preparation': {'schema_version': '1.0', 'prepared_at': prepared_at,
                            'state': 'OUTBOX_PREPARED_NOT_COMMITTED', 'trigger_origin': ORIGIN,
                            'natural_trigger': False, 'formal_economic_evaluation': False}}


def _outbox_directory(parent_fd, parts):
    fd = os.dup(parent_fd)
    try:
        for name in parts:
            try:
                os.mkdir(name, mode=0o700, dir_fd=fd)
            except FileExistsError:
                pass
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _publish_exclusive(directory_fd, filename, payload):
    temporary = '.preparing-' + uuid.uuid4().hex + '.json'
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory_fd)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        # Atomic create-only publication: no half-written file is a prepared identity.
        os.link(temporary, filename, src_dir_fd=directory_fd, dst_dir_fd=directory_fd, follow_symlinks=False)
        os.fsync(directory_fd)
    finally:
        os.unlink(temporary, dir_fd=directory_fd)


def write_outbox(project_root, relative, bundle):
    """Freeze one immutable preparation per batch ID, independently of export name.

    The internal preparation file is a full recoverable original, not a Store
    research claim. A later attempt always refuses that batch identity, including
    after interruption before its requested export; use the retained original.
    """
    payload = canonical(bundle)
    parts = safe_relative(relative).parts
    if not parts or not parts[-1].endswith('.json') or parts[0].casefold() == '.prepared-batches':
        raise ContractError('Outbox requires a new non-reserved relative JSON filename')
    batch = bundle['records'][0]
    batch_id = safe_id(batch['batch_id'])
    if batch.get('record_type') != 'review_batch' or bundle['bundle_id'] != 'bundle-' + batch_id:
        raise ContractError('Outbox batch identity mismatch')
    root = Path(project_root)
    if root.is_symlink() or not root.is_dir():
        raise ContractError('Existing non-symlink project root required')
    descriptors = []
    try:
        fd = os.open(str(root), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW); descriptors.append(fd)
        outbox_fd = _outbox_directory(fd, ('.local', 'review-outbox')); descriptors.append(outbox_fd)
        destination_fd = _outbox_directory(outbox_fd, parts[:-1]); descriptors.append(destination_fd)
        try:
            os.stat(parts[-1], dir_fd=destination_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise FileExistsError('Outbox destination already exists')
        prepared_fd = _outbox_directory(outbox_fd, ('.prepared-batches',)); descriptors.append(prepared_fd)
        identity = digest(batch_id.encode()) + '.json'
        try:
            _publish_exclusive(prepared_fd, identity, payload)
        except FileExistsError as exc:
            raise ContractError('BATCH_ALREADY_PREPARED: reuse immutable .prepared-batches/' + identity) from exc
        _publish_exclusive(destination_fd, parts[-1], payload)
    finally:
        for fd in reversed(descriptors):
            os.close(fd)
    return root / '.local/review-outbox' / relative
