"""Reproduce in a new nested workspace, preserving every delivered artifact."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

WORK=Path(__file__).resolve().parents[2]
VERSION='q2_cost_aware_v2'
ROOT=WORK/'results'/VERSION


def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--target',type=Path,default=ROOT/'reproduction_workspace')
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--smoke',action='store_true',help='Relocate, audit all sources, rerun and independently verify P_floor only.')
    args=parser.parse_args();target=args.target.resolve()
    if not target.is_relative_to(ROOT.resolve()):raise SystemExit('Use a new directory under this version results directory.')
    if target.exists():raise SystemExit('Target exists; choose a new directory to preserve results.')
    target.mkdir(parents=True)
    for top in ['scripts','configs']:
        shutil.copytree(WORK/top/VERSION,target/top/VERSION,ignore=shutil.ignore_patterns('__pycache__'))
    for name in ['inputs','forecasts','references']:
        shutil.copytree(ROOT/name,target/'results'/VERSION/name)
    report=target/'reports'/VERSION;report.mkdir(parents=True)
    for name in ['protocol.md','protocol_freeze.json','extension_protocol.md','extension_freeze.json']:
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
        p=target/dst;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'inputs'/src,p)
        protected[dst]=hashlib.sha256(p.read_bytes()).hexdigest()
    for source in (ROOT/'references').rglob('*'):
        if not source.is_file():continue
        dest=target/'results/emergency_improvement_v1/runs'/source.relative_to(ROOT/'references')
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
        protected[str(dest.relative_to(target))]=hashlib.sha256(dest.read_bytes()).hexdigest()
    save(report/'protected_hashes_before.json',protected)
    (report/'reproduction_scope.md').write_text('Cloned sources and verified forecast archives. The independent source audit reconstructs both forecast methods from original actual prefixes. The clone preservation manifest covers supplied snapshots only; the delivered 3268-file preservation audit remains separate.\n')
    if args.prepare_only:print(target);return
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    runtime=target/'results'/VERSION/'runtime';runtime.mkdir(exist_ok=True)
    for key in ['TMPDIR','TMP','TEMP','MPLCONFIGDIR']:env[key]=str(runtime)
    scripts=target/'scripts'/VERSION

    def run(script,*options):
        label=script.replace('.py','')+'_'+'_'.join(options).replace('--','')
        with (report/(label+'.log')).open('w') as log:
            subprocess.run([sys.executable,str(scripts/script),*options],cwd=target,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        print('Completed',script,*options,flush=True)

    run('independent_verify.py','--scope','sources')
    if args.smoke:
        run('run_experiments.py','runs','--policies','P_floor')
        sys.path.insert(0,str(scripts))
        import independent_verify as v
        actual,price,archive,sources=v.source_audit()
        audit=v.run_audit(target/'results'/VERSION/'runs/P_floor',actual,price,archive)
        save(report/'independent_smoke.json',dict(passed=sources['passed'] and audit['passed'],audit=audit))
        assert sources['passed'] and audit['passed']
        names=['P_floor']
    else:
        for script in ['test_policy.py','test_lower_bound.py']:run(script)
        run('run_experiments.py','january');run('run_experiments.py','january','--extension')
        run('independent_verify.py','--scope','january');run('independent_verify.py','--scope','january','--extension')
        run('causality_checks.py');run('causality_checks.py','--extension')
        run('lower_bound.py');run('independent_verify.py','--scope','causality');run('independent_verify.py','--scope','causality','--extension')
        run('independent_verify.py','--scope','lower_bound')
        run('run_experiments.py','runs');run('run_experiments.py','runs','--extension')
        run('analyze_results.py');run('independent_verify.py')
        source=(scripts/'independent_verify.py').read_text()
        save(report/'independent_primary_validator_snapshot.json',dict(source=source,sha256=hashlib.sha256(source.encode()).hexdigest()))
        run('followup_diagnostics.py');run('independent_verify.py','--scope','followup')
        names=[c['policy'] for file in ['experiments.json','extension.json'] for c in json.loads((target/'configs'/VERSION/file).read_text())['runs']]
    import pandas as pd
    differences={}
    for name in names:
        original=pd.read_csv(ROOT/'runs'/name/'ledger.csv',float_precision='round_trip',dtype={'selected_terminal':str})
        replay=pd.read_csv(target/'results'/VERSION/'runs'/name/'ledger.csv',float_precision='round_trip',dtype={'selected_terminal':str})
        assert original.shape==replay.shape and original.columns.tolist()==replay.columns.tolist()
        numeric=original.select_dtypes(include='number').columns
        max_value=float((original[numeric]-replay[numeric]).abs().to_numpy().max())
        text_cols=original.columns.difference(numeric)
        same_text=original[text_cols].equals(replay[text_cols])
        cost_error=abs(float(original.total_cost_yuan.sum()-replay.total_cost_yuan.sum()))
        differences[name]=dict(max_numeric_difference=max_value,text_columns_match=same_text,total_cost_difference_yuan=cost_error)
        assert max_value<=1e-6 and cost_error<=1e-5 and same_text,name
    save(report/'reproduction_comparison.json',dict(passed=True,scope='P_floor relocation smoke' if args.smoke else 'All nine new numerical paths',by_policy=differences))
    print('Numerical reproduction passed:',target,flush=True)


if __name__=='__main__':main()
