#!/usr/bin/env python3
"""Conditional accounting only: flat mark/notional and observed settlement rates.
This is not a trade simulation or actual net performance. Original code: MIT.
"""
from decimal import Decimal as D
from pathlib import Path
import json
p=Path(__file__).parent
x=json.loads((p/'derived_facts.json').read_text())
out={'schema_version':'1.0','evidence_stage':'REAL_DATA_CONDITIONAL_ACCOUNTING','actual_trade_result':False,'price_pnl':None,'assumptions':['Constant mark price and fixed notional at all observed settlements','Short continuously present for the three observations only; no assumed subsequent rates','Symmetric entry/exit fee and adverse slippage scenarios, not verified venue or account costs','No future profit, expected return, or comparison of actual fills is implied'],'products':{}}
for product,v in x['products'].items():
    carry=D(v['sum_basis_points_diagnostic'])
    cases=[]
    for fee in (0,2,5,10):
        for slip in (0,1,3):
            cost=D(2*(fee+slip))
            cases.append({'fee_bps_each_side':fee,'slippage_bps_each_side':slip,'roundtrip_cost_bps':str(cost),'short_funding_diagnostic_bps':str(carry),'conditional_flat_price_after_cost_bps':str(carry-cost),'funding_covers_assumed_cost':carry>=cost})
    out['products'][product]={'scenarios':cases,'primary_5bp_fee_1bp_slippage_each_side':next(c for c in cases if c['fee_bps_each_side']==5 and c['slippage_bps_each_side']==1),'interpretation':'Observed rate sum alone does not establish net advantage.'}
print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True))
