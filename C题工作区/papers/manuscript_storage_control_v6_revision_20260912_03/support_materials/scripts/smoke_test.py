"""Compile/import the scientific core and solve two bounded diagnostic problems."""
from pathlib import Path
import importlib.metadata
import json
import sys
import numpy as np
import pandas as pd

WORK=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(WORK/'scripts/storage_control_v6'))
import kernel
from policy import decision
from solve_q1 import solve_model

physical=json.loads((WORK/'configs/model_baseline.json').read_text())
data=pd.read_csv(WORK/'saved/q1/input_day.csv',float_precision='round_trip')
_,status=solve_model(data,physical)
expected=json.loads((WORK/'saved/q1/baseline/summary.json').read_text())['cost_yuan']
assert abs(status['objective_yuan']-expected)<1e-5
# A short synthetic remaining-day problem exercises the real finite q/R search.
load=np.full(6,500.);pv=np.zeros(6);price=np.array([.4,.5,.6,.7,.8,.9])
net=np.vstack([load-100.,load+100.]);residual=np.vstack([np.full(6,-100.),np.full(6,100.)])
result=decision(load,pv,net,residual,price,6000.,138,physical,control='reserve')
i=int(result['selected_index']);q=result['q'][i];reserve=result['reserve'][i]
assert len(result['q'])==12 and np.all(q>=0) and np.all((reserve>=1200)&(reserve<=10800))
assert np.isfinite(result['score']).all()
out={'passed':True,'q1_objective_yuan':status['objective_yuan'],
     'short_diagnostic_intervals':6,'short_diagnostic_candidates':len(result['q']),
     'annual_optimizations_run':0,'selected_diagnostic_candidate':i,
     'packages':{name:importlib.metadata.version(name) for name in ['numpy','pandas','scipy','highspy','openpyxl']}}
(WORK/'smoke_results.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
