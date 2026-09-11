"""Independent sparse LP lower bounds for all ten supplemental settings."""
import copy
import json
import os
from pathlib import Path
import sys
import time
import numpy as np
import pandas as pd
from audit_innovation_lp import independent_lp

WORK = Path(__file__).resolve().parents[1]
OUT = WORK/'results/robustness'
for name in ('TMPDIR','TMP','TEMP'):
    os.environ[name] = str(WORK/'data/interim/robustness')
POLICIES = ['fixed_raw','fixed_w28','fixed_w14','fixed_w56','efficiency_raw',
            'efficiency_w28','soft_raw','soft_w28','variable_raw','variable_w28']
DATES = ['2025-04-01','2025-06-21','2025-09-23','2025-12-21']


def main():
    physical=json.loads((WORK/'configs/model_baseline.json').read_text())
    price=pd.read_csv(WORK/'data/processed/fixed_price.csv',float_precision='round_trip').price_yuan_per_kwh
    penalty=float(.9*price.mean())
    rows=[]
    for policy in POLICIES:
        folder=OUT/policy
        versions=pd.read_csv(folder/'plan_versions.csv',float_precision='round_trip')
        versions=versions.loc[versions.date.isin(DATES)]
        groups=versions.groupby(['date','issue_hour'])
        statuses=json.loads((folder/'solvers.json').read_text())
        statuses={(s['date'],int(s['issue_hour'])):s for s in statuses}
        battery=copy.deepcopy(physical['battery'])
        eta=float(np.sqrt(.9)) if policy.startswith('efficiency_') else .9
        battery.update(eta_charge=eta,eta_discharge=eta)
        soft=policy.startswith('soft_')
        for date in DATES:
            for hour in [0,6,12,18]:
                part=groups.get_group((date,hour)).copy().reset_index(drop=True)
                part['price_yuan_per_kwh']=part.planning_price_yuan_per_kwh
                st=statuses[(date,hour)]
                original=None if hour==0 else part.grid_original_kwh.to_numpy()
                started=time.perf_counter()
                lp=independent_lp(part,st['initial_energy_kwh'],st['terminal_target_kwh'],battery,
                                  physical['interval_minutes'],original=original,soft_terminal=soft,
                                  terminal_penalty=penalty if soft else None)
                gap=float(st['solver']['objective_yuan']-lp['objective_yuan'])
                primal=max(lp['equality_residual'],lp['inequality_violation'],lp['bound_violation'])
                rows.append({'policy':policy,'date':date,'issue_hour':hour,'horizon_intervals':len(part),
                             'milp_objective_yuan':st['solver']['objective_yuan'],
                             'lp_lower_bound_yuan':lp['objective_yuan'],'milp_minus_lp_yuan':gap,
                             'lp_max_primal_violation':primal,'runtime_seconds':time.perf_counter()-started,
                             'passed':bool(gap>=-1e-5 and primal<=1e-6)})
        print(policy,'16 LP horizons',flush=True)
    frame=pd.DataFrame(rows)
    frame.to_csv(OUT/'lp_audit.csv',index=False)
    report={'passed':len(frame)==160 and bool(frame.passed.all()),'sample_count':len(frame),
            'case_counts':frame.groupby('policy').size().to_dict(),
            'maximum_relaxation_gap_yuan':float(frame.milp_minus_lp_yuan.max()),
            'minimum_milp_minus_lp_yuan':float(frame.milp_minus_lp_yuan.min()),
            'maximum_lp_primal_violation':float(frame.lp_max_primal_violation.max()),
            'failed':frame.loc[~frame.passed,['policy','date','issue_hour']].to_dict('records'),
            'method':'Independent SciPy sparse-matrix continuous relaxation; no planner imports. Lower bounds, not equality or annual optimality.',
            'scope':{'policies':POLICIES,'dates':DATES,'hours':[0,6,12,18]}}
    (OUT/'lp_audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)
    if not report['passed']:sys.exit(1)


if __name__=='__main__':
    main()
