"""Relocate and replay in a new nested workspace; never overwrite delivered results."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

WORK=Path(__file__).resolve().parents[2]
VERSION='q2_pareto_v3';ROOT=WORK/'results'/VERSION


def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--target',type=Path,default=ROOT/'reproduction_workspace')
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--smoke',action='store_true',help='Relocate sources, rerun and independently verify the best observed eligible new policy.')
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
    for folder in (ROOT/'references').iterdir():
        old='results/emergency_improvement_v1/runs' if folder.name in ['B0','B1','P','P_terminal'] else 'results/q2_cost_aware_v2/runs'
        for source in folder.iterdir():
            if not source.is_file():continue
            dest=target/old/folder.name/source.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
            protected[str(dest.relative_to(target))]=hashlib.sha256(dest.read_bytes()).hexdigest()
    save(report/'protected_hashes_before.json',protected)
    (report/'reproduction_scope.md').write_text('Relocated supplied source snapshots, both forecast archives and six references. The independent auditor reconstructs forecasts from raw processed prefixes. Clone preservation covers copied snapshots; original 3668-file preservation is separately audited. No original workspace dependency is required for numerical replay. ModelViz plotting additionally needs the local skill.\n')
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
    run('test_policy.py');run('independent_verify.py','--scope','sources')
    original_names=[c['policy'] for c in json.loads((target/'configs'/VERSION/'experiments.json').read_text())['runs']]
    extension_names=[c['policy'] for c in json.loads((target/'configs'/VERSION/'extension.json').read_text())['runs']]
    if args.smoke:
        best=json.loads((ROOT/'analysis_user_cap/acceptance_user_cap.json').read_text())['best_observed_policy']
        assert best in original_names+extension_names
        extra=['--extension'] if best in extension_names else []
        run('run_experiments.py','runs','--policies',best,*extra)
        sys.path.insert(0,str(scripts));import independent_verify as v
        actual,price,archive,sources=v.source_audit()
        stage='extension_runs' if best in extension_names else 'runs'
        audit=v.run_audit(target/'results'/VERSION/stage/best,actual,price,archive)
        save(report/'independent_smoke.json',dict(passed=sources['passed'] and audit['passed'],audit=audit))
        assert sources['passed'] and audit['passed'];names=[best]
    else:
        for extra in [[],['--extension']]:
            run('run_experiments.py','january',*extra)
            run('independent_verify.py','--scope','extension_january' if extra else 'january')
        run('causality_checks.py');run('causality_checks.py','--extension')
        run('run_experiments.py','runs');run('run_experiments.py','runs','--extension')
        run('analyze_results.py');run('analyze_user_cap.py')
        run('independent_verify.py','--scope','all');run('independent_verify.py','--scope','extension_all')
        names=original_names+extension_names
    import pandas as pd
    differences={}
    for name in names:
        stage='extension_runs' if name in extension_names else 'runs'
        original=pd.read_csv(ROOT/stage/name/'ledger.csv',float_precision='round_trip',dtype={'selected_terminal':str})
        replay=pd.read_csv(target/'results'/VERSION/stage/name/'ledger.csv',float_precision='round_trip',dtype={'selected_terminal':str})
        assert original.shape==replay.shape and original.columns.tolist()==replay.columns.tolist()
        numeric=original.select_dtypes(include='number').columns
        max_value=float((original[numeric]-replay[numeric]).abs().to_numpy().max())
        text_cols=original.columns.difference(numeric);same_text=original[text_cols].equals(replay[text_cols])
        cost_error=abs(float(original.total_cost_yuan.sum()-replay.total_cost_yuan.sum()))
        differences[name]=dict(max_numeric_difference=max_value,text_columns_match=same_text,total_cost_difference_yuan=cost_error)
        assert max_value<=1e-6 and cost_error<=1e-5 and same_text,name
    save(report/'reproduction_comparison.json',dict(passed=True,scope='One selected annual policy relocation smoke' if args.smoke else 'All 18 new numerical paths',by_policy=differences))
    print('Numerical reproduction passed:',target,flush=True)


if __name__=='__main__':main()
