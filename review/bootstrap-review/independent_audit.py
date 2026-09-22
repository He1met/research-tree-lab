"""Independent read-only audit of bootstrap evidence. No network or store writes.

Reads source bytes independently of the research audit implementation. Outputs
only aggregate diagnostics and hashes into this review's own directory.
"""
import csv
import io
import json
import sys
import zipfile
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from researchlib.common import canonical, digest, now_iso, utc
from researchlib.contracts import validate_relationships
from researchlib.store import Store

HERE = Path(__file__).parent


def main():
    install = json.loads((ROOT / '.local/installation.json').read_text())
    data = Path(install['data_root']) / 'okx/research-bootstrap-20260923-v1'
    copy = json.loads((data / 'STABLE_COPY_RECEIPT.json').read_text())
    checks = {}
    for entry in copy['files']:
        raw = (data / entry['path']).read_bytes()
        checks['source_integrity:' + entry['path']] = len(raw) == entry['bytes'] and digest(raw) == entry['sha256']
    raw = (data / 'allswap-fundingrates-2026-09-21.zip').read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        checks['zip_crc'] = z.testzip() is None
        assert len(z.namelist()) == 1
        payload = z.read(z.namelist()[0])
    rows = list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))
    report = json.loads((ROOT / 'research/bootstrap-v1/results.json').read_text())
    costs = json.loads((ROOT / 'research/bootstrap-v1/cost_stress.json').read_text())
    protocol = json.loads((ROOT / 'research/bootstrap-v1/frozen_protocol.json').read_text())
    sources = json.loads((ROOT / 'research/bootstrap-v1/sources.json').read_text())
    checks['rows_and_instruments'] = len(rows) == report['total_rows'] == 2103 and len({r['instrument_name'] for r in rows}) == report['unique_instruments'] == 482
    checks['local_freeze_before_retrieval'] = utc(protocol['frozen_at']) < utc(sources['archive']['downloaded_at'])
    checks['unknown_source_publication_not_backdated'] = sources['archive']['upstream_publication_time'] is None
    checks['source_is_exact_zip'] = digest(raw) == report['source_sha256'] == sources['archive']['sha256']
    products = {}
    start = utc(protocol['sample_window']['start'])
    end = utc(protocol['sample_window']['end_exclusive'])
    for product, symbol in {'aapl': 'AAPL-USDT-SWAP', 'qqq': 'QQQ-USDT-SWAP', 'btc': 'BTC-USDT-SWAP', 'eth': 'ETH-USDT-SWAP'}.items():
        pairs = sorted((datetime.fromtimestamp(int(r['funding_time']) / 1000, timezone.utc), D(r['funding_rate'])) for r in rows if r['instrument_name'] == symbol)
        points = sum((r * 10000 for _, r in pairs), D(0))
        inside = [(t, r) for t, r in pairs if start <= t < end]
        x = report['products'][product]
        checks[product + ':sum_and_window'] = points == D(x['sum_basis_points_diagnostic']) and len(inside) == x['within_requested_utc_window_count'] == 2 and len(pairs) == x['row_count'] == 3
        checks[product + ':sign_counts'] = [sum(r > 0 for _, r in pairs), sum(r < 0 for _, r in pairs), sum(r == 0 for _, r in pairs)] == [x['positive_count'], x['negative_count'], x['zero_count']]
        checks[product + ':duplicate_and_time'] = len({t for t, _ in pairs}) == len(pairs) and all((b[0] - a[0]).total_seconds() == 28800 for a, b in zip(pairs, pairs[1:]))
        cases = costs['products'][product]['scenarios']
        checks[product + ':all_cost_scenarios'] = len(cases) == 12 and all(D(c['conditional_flat_price_after_cost_bps']) == points - 2 * (D(c['fee_bps_each_side']) + D(c['slippage_bps_each_side'])) for c in cases)
        checks[product + ':incomplete_day_kept'] = x['requested_utc_day_complete'] is False and x['cost_to_real_position'] is None
        products[product] = {'instrument_ref': symbol, 'observed_rate_sum_bps': str(points), 'primary_conditional_accounting_bps': str(points - 12), 'rows': len(pairs), 'requested_window_rows': len(inside)}
    s = Store(ROOT)
    records, metadata, anomalies = s.load(strict=True)
    validate_relationships(records)
    frozen = json.loads((HERE / 'frozen_registry.json').read_text())
    checks['frozen_originals_unchanged'] = all(digest(canonical(records[k])) == v for k, v in frozen['original_record_hashes'].items())
    checks['no_store_anomalies'] = not anomalies
    plans = {}
    for ref, p in sorted(records.items()):
        if p['record_type'] != 'plan' or ref not in frozen['record_refs']:
            continue
        age = (utc(p['rules']['entry']['scheduled_at']) - utc(p['rules']['signal']['event_at'])).total_seconds() / 3600
        checks[ref + ':seal_and_effective_order'] = utc(p['sealed_at']) <= utc(p['effective_from']) <= utc(p['entry_valid_until']) <= utc(p['evaluation_end'])
        checks[ref + ':explicit_rules_and_units'] = all(p['rules'].get(k) for k in ('signal','entry','exit','quantity_or_inventory','reentry','termination')) and D(p['rules']['quantity_or_inventory']['contracts']) * D(p['rules']['quantity_or_inventory']['face_value']) * D(p['rules']['quantity_or_inventory']['multiplier']) == D('0.01')
        checks[ref + ':sample_signal_age'] = age <= 72 and p['rules']['signal']['reevaluate_after_seal'] is False and p['rules']['signal']['use_future_funding_as_signal'] is False
        checks[ref + ':fee_and_visibility_unknown'] = p['cost_model']['actual_entry_fee_rate'] is None and p['cost_model']['actual_exit_fee_rate'] is None and p['public_visibility_ref'] is None
        checks[ref + ':no_account_or_trade_authority'] = p['account_input_required'] is False and p['automatic_trade_authorized'] is False and p['account_eligibility'] == 'NOT_ASSESSED'
        plans[ref] = {'plan_hash': digest(canonical(p)), 'effective_from': p['effective_from'], 'evaluation_end': p['evaluation_end'], 'signal_age_at_entry_hours': str(age), 'direction': p['rules']['quantity_or_inventory']['direction'], 'public_forecast_proof': 'NONE_LOCAL_SEAL_ONLY'}
    assert len(plans) == 2
    checks['opposite_direction_matched_quantity_not_account_sum'] = {p['direction'] for p in plans.values()} == {-1, 1}
    result = {'schema_version': '1.0', 'completed_at': now_iso(), 'reviewer': 'independent_review_official_app_subagent', 'trigger_origin': 'OFFICIAL_APP_SUBAGENT_MANUAL_SAFE_TRIAL', 'native_task_ref': None, 'natural_trigger': False, 'source_sha256': digest(raw), 'test_count': len(checks), 'checks': checks, 'all_checked_assertions_pass': all(checks.values()), 'products': products, 'plans': plans, 'economic_result': 'NOT_EVALUABLE_BEFORE_EFFECTIVE_TIME', 'source_backup': 'LOCAL_ONLY_REMOTE_RAW_BACKUP_NOT_VERIFIED', 'limitations': ['Local timestamps and receipt order are not independent third-party public prediction proof.', 'Aggregate arithmetic agreement is not a simulated or live return.', 'Future target trade path, exact settlement mark path, realized funding and actual fee schedule are absent.']}
    (HERE / 'independent_arithmetic.json').write_bytes(canonical(result))
    print(json.dumps({'checks': len(checks), 'passed': all(checks.values()), 'plans': len(plans)}, indent=2))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
