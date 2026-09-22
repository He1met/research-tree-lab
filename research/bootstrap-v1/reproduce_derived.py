#!/usr/bin/env python3
"""Reproduce PUBLIC derived diagnostics. Does not verify restricted source rows."""
import json
from pathlib import Path
from decimal import Decimal as D
p=Path(__file__).parent
facts=json.loads((p/'derived_facts.json').read_text())
result={'source_integrity_verified':False,'scope':'DERIVED_DIAGNOSTICS_ONLY','products':{},'limitations':['Raw source excluded: redistribution permission not established','This is not market-data restoration or a trading backtest']}
for product,f in facts['products'].items():
    assert f['positive_count']+f['negative_count']+f['zero_count']==f['row_count']
    assert f['within_requested_utc_window_count']+f['outside_requested_utc_window_count']==f['row_count']
    assert D(f['sum_rates_diagnostic'])*D(10000)==D(f['sum_basis_points_diagnostic'])
    result['products'][product]={'count_conservation':True,'bps_conversion':str(D(f['sum_rates_diagnostic'])*D(10000)),'outside_requested_window':f['outside_requested_utc_window_count']>0,'nonzero_rate_observed':f['positive_count']+f['negative_count']>0}
result['zero_interest_implies_zero_funding_refuted']=any(result['products'][s]['nonzero_rate_observed'] for s in ('aapl','qqq'))
result['filename_is_utc_day_refuted']=any(x['outside_requested_window'] for x in result['products'].values())
print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2))
