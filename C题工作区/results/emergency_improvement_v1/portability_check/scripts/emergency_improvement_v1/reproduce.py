"""Reproduce in a NEW nested workspace; never overwrite delivered runs or old project outputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

WORK=Path(__file__).resolve().parents[2]
VERSION='emergency_improvement_v1'
ROOT=WORK/'results'/VERSION


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--target',type=Path,default=ROOT/'reproduction_workspace')
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args();target=args.target.resolve()
    if target.exists():raise SystemExit('Target already exists; choose a new directory to preserve results.')
    target.mkdir(parents=True)
    for top in ['scripts','configs']:
        shutil.copytree(WORK/top/VERSION,target/top/VERSION)
    shutil.copytree(ROOT/'inputs',target/'results'/VERSION/'inputs')
    report=target/'reports'/VERSION;report.mkdir(parents=True)
    for name in ['protocol.md','protocol_freeze.json']:
        shutil.copyfile(WORK/'reports'/VERSION/name,report/name)
    mapping={'actual_10min.csv':'data/processed/actual_10min.csv','fixed_price.csv':'data/processed/fixed_price.csv',
             'model_baseline.json':'configs/model_baseline.json','q2_baseline.json':'configs/q2_baseline.json',
             'original_run_q2.py':'scripts/run_q2.py','original_solve_q1.py':'scripts/solve_q1.py',
             'problem_text.txt':'data/interim/problem_text.txt','selection.json':'results/q2/selection.json',
             'bzd_quantile_record.json':'reports/emergency_research_v1/bzd_quantile_record.json',
             'baseline_B0.csv':'results/q2/selected/ledger.csv','baseline_B1.csv':'results/q2/seasonal/ledger.csv',
             'baseline_no_storage.csv':'results/q2/no_storage/ledger.csv'}
    protected={}
    for src,dst in mapping.items():
        path=target/dst;path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/'inputs'/src,path)
        protected[dst]=hashlib.sha256(path.read_bytes()).hexdigest()
    (report/'protected_hashes_before.json').write_text(json.dumps(protected,ensure_ascii=False,indent=2)+'\n')
    (report/'reproduction_scope.md').write_text('Independent cloned numerical workspace. Its protection manifest covers the supplied source snapshots only; the original 2837-file preservation proof remains in the delivered report.\n')
    if args.prepare_only:
        print(target);return
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    runtime=target/'results'/VERSION/'runtime';runtime.mkdir(exist_ok=True)
    for key in ['TMPDIR','TMP','TEMP','MPLCONFIGDIR']:env[key]=str(runtime)
    commands=[('run_experiments.py',['forecasts']),('run_experiments.py',['baselines']),
              ('run_experiments.py',['january']),('independent_verify.py',['--scope','january']),
              ('run_experiments.py',['january_pe']),('run_experiments.py',['main']),
              ('run_experiments.py',['sensitivity']),('causality_checks.py',[]),
              ('analyze_results.py',[]),('independent_verify.py',[])]
    for i,(script,options) in enumerate(commands):
        command=[sys.executable,str(target/'scripts'/VERSION/script),*options]
        with (report/f'reproduce_{i:02}_{script}.log').open('w') as log:
            subprocess.run(command,cwd=target,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        print('Completed',script,*options,flush=True)
    import pandas as pd
    got=pd.read_csv(target/'results'/VERSION/'comparison_all.csv',float_precision='round_trip').set_index('policy')
    expected=pd.read_csv(ROOT/'comparison_all.csv',float_precision='round_trip').set_index('policy')
    difference=(got.total_cost_yuan-expected.total_cost_yuan).abs()
    passed=bool((difference<=1e-5).all())
    (report/'reproduction_comparison.json').write_text(json.dumps({'passed':passed,'max_total_cost_difference_yuan':float(difference.max()),'by_policy':difference.to_dict()},indent=2)+'\n')
    assert passed,'Inspect solver/runtime changes; no result is silently replaced.'
    print('All 18 numerical results reproduced:',target)


if __name__=='__main__':main()
