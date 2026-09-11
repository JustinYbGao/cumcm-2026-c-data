"""Full selected-policy reruns from a separate source/data/compiled-kernel workspace."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import numpy as np
import pandas as pd

WORK=Path(__file__).resolve().parents[2]
ROOT=WORK/'results/unified_direct_v5'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--target',type=Path,default=ROOT/'reproduction_workspace');args=parser.parse_args()
    selection=json.loads((ROOT/'selection.json').read_text())['selected']
    policies=[selection[b] for b in ['q3','q42','q43']]
    target=args.target.resolve()
    if ROOT.resolve() not in target.parents:raise ValueError('Reproduction target must be an unused directory inside the v5 results root')
    target.mkdir(exist_ok=False)
    files=[p.relative_to(WORK) for p in (WORK/'scripts/unified_direct_v5').glob('*') if p.suffix in ['.py','.c']]
    files += [Path(p) for p in ['data/processed/actual_10min.csv','data/processed/fixed_price.csv','data/processed/pv_forecast_10min.csv',
        'configs/model_baseline.json','configs/q4_baseline.json','configs/q2_baseline.json','configs/unified_direct_v5/experiments.json',
        'results/q2_direct_v4/forecasts/linear_harmonic.csv','reports/unified_direct_v5/protocol.md','reports/unified_direct_v5/protocol_freeze.json']]
    hashes={}
    for rel in files:
        dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(WORK/rel,dest)
        hashes[str(rel)]=hashlib.sha256(dest.read_bytes()).hexdigest()
        assert hashes[str(rel)]==hashlib.sha256((WORK/rel).read_bytes()).hexdigest()
    runtime=target/'results/unified_direct_v5/runtime';runtime.mkdir(parents=True)
    env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TMPDIR=str(runtime),TMP=str(runtime),TEMP=str(runtime))
    with (target/'run.log').open('w') as log:
        subprocess.run([sys.executable,str(target/'scripts/unified_direct_v5/inputs.py')],cwd=target,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        subprocess.run([sys.executable,str(target/'scripts/unified_direct_v5/run.py'),'--policies',*policies],cwd=target,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    results=[]
    for name in policies:
        left=ROOT/'runs'/name;right=target/'results/unified_direct_v5/runs'/name;metrics={}
        for filename in ['ledger.csv','plan_versions.csv','daily.csv']:
            a=pd.read_csv(left/filename,float_precision='round_trip');b=pd.read_csv(right/filename,float_precision='round_trip')
            assert a.columns.equals(b.columns) and a.shape==b.shape
            nums=a.select_dtypes(include='number').columns;texts=a.columns.difference(nums)
            diff=float(np.max(np.abs(a[nums].to_numpy()-b[nums].to_numpy())))
            equal=a[texts].equals(b[texts]);assert diff<=1e-6 and equal
            metrics[filename]={'max_numeric_error':diff,'text_identical':equal,'numerically_identical':bool(np.array_equal(a[nums],b[nums]))}
        maxerr=0.;exact=True;count=0
        for file in sorted((left/'evidence').glob('*.npz')):
            a=np.load(file);b=np.load(right/'evidence'/file.name);assert set(a.files)==set(b.files)
            for key in a.files:
                if a[key].size:
                    err=float(np.max(np.abs(a[key]-b[key])));maxerr=max(maxerr,err);exact &= np.array_equal(a[key],b[key])
                    assert err<=(1e-5 if key in ['score','ordinary','emergency_fee'] else 1e-6)
                count+=1
        sa=json.loads((left/'summary.json').read_text());sb=json.loads((right/'summary.json').read_text())
        fees={k:sb[k]-sa[k] for k in ['contract_cost_yuan','emergency_cost_yuan','total_cost_yuan']}
        assert max(abs(v) for v in fees.values())<1e-5
        results.append({'policy':name,'files':metrics,'candidate_arrays_checked':count,'all_candidate_arrays_identical':bool(exact),'max_candidate_error':maxerr,'fee_differences_yuan':fees})
    report={'passed':True,'target':str(target),'source_hashes':hashes,'policies':results,'scope':'same host and dependencies, isolated source/data workspace and freshly compiled C kernel; no legacy writes'}
    text=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    (target/'reproduction_comparison.json').write_text(text)
    report_path=WORK/'reports/unified_direct_v5/reproduction_comparison.json'
    if not report_path.exists():report_path.write_text(text)
    print(json.dumps(results,indent=2))


if __name__=='__main__':main()
