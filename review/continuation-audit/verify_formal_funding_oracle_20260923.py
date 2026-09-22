#!/usr/bin/env python3
"""SYNTHETIC independent oracle: repeat the original 63 arithmetic checks.

Standard library only. Does not import an evaluator, read production records,
write files, or produce a formal review. Reads only this source and its frozen
Markdown oracle for byte identities. JSON receipt is printed to stdout.

Run from the repository root:
  PYTHONDONTWRITEBYTECODE=1 python3 review/continuation-audit/verify_formal_funding_oracle_20260923.py

This standalone audit helper is outside the installed evaluator source closure.
It retains the original mathematical scope; it does not add market samples.
"""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import hashlib
import json
from pathlib import Path
import platform
import sys

D = Decimal
ORACLE_NAME = 'FORMAL_FUNDING_ORACLE_20260923.md'
ORACLE_SHA256 = 'ff3f06795fdf3158f25018f5e179b5ae617d95b699faf1eee84b0e69d8bcce00'

# Expected values were fixed in the independent handwritten oracle, before
# inspecting the formal-review candidate. Columns: fee, slip, total fee,
# total slippage, long net, short net. Every price/rate is SYNTHETIC.
EXPECTED_SCENARIOS = (
    ('0', '0', '0', '0', '.096', '-.096'),
    ('0', '1', '0', '.00021', '.09579', '-.09621'),
    ('0', '3', '0', '.00063', '.09537', '-.09663'),
    ('2', '0', '.00042', '0', '.09558', '-.09642'),
    ('2', '1', '.00042', '.00021', '.09537', '-.09663'),
    ('2', '3', '.00042', '.00063', '.09495', '-.09705'),
    ('5', '0', '.00105', '0', '.09495', '-.09705'),
    ('5', '1', '.00105', '.00021', '.09474', '-.09726'),
    ('5', '3', '.00105', '.00063', '.09432', '-.09768'),
    ('10', '0', '.00210', '0', '.09390', '-.09810'),
    ('10', '1', '.00210', '.00021', '.09369', '-.09831'),
    ('10', '3', '.00210', '.00063', '.09327', '-.09873'),
)

EXPECTED_DRAWDOWNS = (
    ('long', ('1', '.9994', '.9894', '1.1954', '.8954', '1.09474'),
     '.3', '.25096202108080977078802074619374268027438514304835'),
    ('short', ('1', '.9994', '1.0094', '.8034', '1.1034', '.90274'),
     '.206', '.20408163265306122448979591836734693877551020408163'),
    ('separate_extrema', ('1', '.1', '20', '10'), '10', '.9'),
)


def check(condition, label, passed):
    # An explicit exception keeps checks effective with Python optimization.
    if not condition:
        raise AssertionError('SYNTHETIC oracle mismatch: ' + label)
    passed.append(label)


def arithmetic_checks():
    passed = []
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_HALF_EVEN
        for fee, slip, fees, slippage, long_net, short_net in EXPECTED_SCENARIOS:
            f, s = D(fee), D(slip)
            prefix = 'scenario_fee_' + fee + '_slip_' + slip + ':'
            check(D(fees) == D('2.1') * f / 10000, prefix + 'fee', passed)
            check(D(slippage) == D('2.1') * s / 10000, prefix + 'slippage', passed)
            check(D(long_net) == D('.1') - D('.004') - D('2.1') * (f + s) / 10000,
                  prefix + 'long_net', passed)
            check(D(short_net) == -D('.1') + D('.004') - D('2.1') * (f + s) / 10000,
                  prefix + 'short_net', passed)

        settlements = ((D('100'), D('.01')), (D('120'), D('-.005')))
        unsigned_funding = sum((D('.01') * mark * rate for mark, rate in settlements), D(0))
        check(unsigned_funding == D('.004'), 'included_funding_sum', passed)

        for direction, expected in ((D(1), D('-.1046')), (D(-1), D('.1034'))):
            observed = direction * D('.01') * (D(90) - D(100))
            observed -= direction * unsigned_funding + D(1) * D(6) / 10000
            check(observed == expected, 'open_net_direction_' + str(direction), passed)

        for label, path, expected_absolute, expected_fraction in EXPECTED_DRAWDOWNS:
            peak, absolute, fraction = D(path[0]), D(0), D(0)
            for equity in map(D, path):
                peak = max(peak, equity)
                absolute = max(absolute, peak - equity)
                fraction = max(fraction, (peak - equity) / peak)
            check(absolute == D(expected_absolute), label + ':absolute_drawdown', passed)
            check(fraction == D(expected_fraction), label + ':fraction_drawdown', passed)

        # SYNTHETIC asymmetric-cost evidence assumption; never actual production
        # fees. These are the same three checks already run for the Markdown.
        total_cost = D(1) * (D(3) + D(2)) / 10000 + D('1.1') * (D(7) + D(3)) / 10000
        check(total_cost == D('.00160'), 'asymmetric_cost_total', passed)
        check(D('.096') - total_cost == D('.09440'), 'asymmetric_cost_long_net', passed)
        check(D('-.096') - total_cost == D('-.09760'), 'asymmetric_cost_short_net', passed)

        entry = datetime.fromisoformat('2026-09-23T00:05:10+00:00')
        exit_at = datetime.fromisoformat('2026-09-24T00:05:20+00:00')
        cutoff = datetime.fromisoformat('2026-09-23T16:00:00+00:00')
        check((exit_at - entry).total_seconds() == 86410, 'closed_holding_seconds', passed)
        check((cutoff - entry).total_seconds() == 57290, 'open_holding_seconds', passed)
        settlements_at = tuple(datetime.fromisoformat(t) for t in (
            '2026-09-23T00:05:09.999+00:00', '2026-09-23T00:05:10+00:00',
            '2026-09-23T08:00:00+00:00', '2026-09-24T00:05:20+00:00'))
        check([entry <= t < exit_at for t in settlements_at] == [False, True, True, False],
              'entry_inclusive_exit_exclusive', passed)
    if len(passed) != 63:
        raise RuntimeError('The frozen arithmetic scope must remain 63 checks')
    return passed


def main():
    source_path = Path(__file__)
    oracle_path = source_path.with_name(ORACLE_NAME)
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    oracle_hash = hashlib.sha256(oracle_path.read_bytes()).hexdigest()
    if oracle_hash != ORACLE_SHA256:
        raise RuntimeError('Frozen Markdown oracle identity changed; no success receipt')
    passed = arithmetic_checks()
    receipt = {
        'schema_version': '1.0',
        'state': 'PASS_SYNTHETIC_ARITHMETIC_ONLY',
        'synthetic': True,
        'executed_at': datetime.now(timezone.utc).isoformat(),
        'script': 'review/continuation-audit/' + source_path.name,
        'script_sha256': source_hash,
        'oracle': 'review/continuation-audit/' + ORACLE_NAME,
        'oracle_sha256': oracle_hash,
        'runtime': {
            'implementation': platform.python_implementation(),
            'python_version': platform.python_version(),
            'python_build': sys.version,
            'third_party_dependencies': [],
            'decimal_precision': 50,
            'decimal_rounding': ROUND_HALF_EVEN,
        },
        'arithmetic_assertions': len(passed),
        'arithmetic_assertions_passed': len(passed),
        'groups': {'scenario_cost_and_direction_net': 48, 'funding_sum': 1,
                   'open_position_net': 2, 'observed_drawdown': 6,
                   'asymmetric_costs': 3, 'holding_periods': 2, 'funding_boundaries': 1},
        'passed_checks': passed,
        'production_data_read': False,
        'candidate_or_funding_forward_called': False,
        'installed_source_closure_member': False,
        'economic_acceptance': False,
        'boundary': 'Repeat of the original independent SYNTHETIC mathematical scope; '
                    'not candidate validation, source coverage, actual results, or natural operation.',
    }
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
