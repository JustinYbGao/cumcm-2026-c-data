"""Use the independently assembled Q3 matrix LP with each Q4 forecast price vector."""
import json
import os
from pathlib import Path
import sys
import time

import pandas as pd
from audit_q3_lp import independent_lp

WORK=Path(__file__).resolve().parents[1]
os.environ['TMPDIR']=str(WORK/'data/interim/q4')


def main():
    out=WORK/'results/q4';physical=json.loads((out/'physical_snapshot.json').read_text())
    rows=[];dates=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
    for policy,rule in [('q42_ols','A'),('q43_all_A_ols','A'),('q43_all_B_ols','B')]:
        versions=pd.read_csv(out/policy/'plan_versions.csv',float_precision='round_trip').groupby(['date','issue_hour'])
        for s in json.loads((out/policy/'solvers.json').read_text()):
            if s['date'] not in dates:continue
            f=versions.get_group((s['date'],s['issue_hour']));started=time.perf_counter()
            bound,eq,ub,bounds=independent_lp(f,f.price_forecast_yuan_per_kwh.to_numpy(),s['initial_energy_kwh'],s['terminal_target_kwh'],physical['battery'],physical['interval_minutes'],rule,s['issue_hour'])
            gap=s['solver']['objective_yuan']-bound
            rows.append({'policy':policy,'date':s['date'],'issue_hour':s['issue_hour'],
                'milp_objective_yuan':s['solver']['objective_yuan'],'independent_lp_bound_yuan':bound,
                'milp_minus_lp_yuan':gap,'primal_violation':max(eq,ub,bounds),'runtime_seconds':time.perf_counter()-started,
                'passed':gap>=-1e-5 and max(eq,ub,bounds)<=1e-6})
    f=pd.DataFrame(rows);f.to_csv(out/'independent_lp_audit.csv',index=False)
    result={'passed':bool(f.passed.all() and len(f)==36),'sample_count':len(f),
        'max_milp_minus_lp_yuan':float(f.milp_minus_lp_yuan.max()),'max_primal_violation':float(f.primal_violation.max()),
        'method':'Independent scipy sparse matrix formulation reused from Q3, forecast prices from each Q4 version; same HiGHS algorithm family, not independent vendor'}
    (out/'independent_lp_audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    if not result['passed']:sys.exit(1)


if __name__=='__main__':main()
