"""Recompile and rerun an annual policy in a new, isolated local workspace."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

WORK=Path(__file__).resolve().parents[2];VERSION='q2_direct_v4';ROOT=WORK/'results'/VERSION


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--target',type=Path,default=ROOT/'reproduction_workspace')
    parser.add_argument('--policy');args=parser.parse_args();target=args.target.resolve()
    assert target.is_relative_to(ROOT.resolve()) and not target.exists(),'Choose a new directory inside this version results.'
    target.mkdir(parents=True)
    for top in ['scripts','configs']:
        shutil.copytree(WORK/top/VERSION,target/top/VERSION,ignore=shutil.ignore_patterns('__pycache__'))
    for name in ['inputs','forecasts']:
        shutil.copytree(ROOT/name,target/'results'/VERSION/name)
    report=target/'reports'/VERSION;report.mkdir(parents=True)
    for name,dest in {'actual_10min.csv':'data/processed/actual_10min.csv','fixed_price.csv':'data/processed/fixed_price.csv',
        'model_baseline.json':'configs/model_baseline.json','q2_baseline.json':'configs/q2_baseline.json','problem_text.txt':'data/interim/problem_text.txt'}.items():
        out=target/dest;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'inputs'/name,out)
    best=args.policy or json.loads((ROOT/'analysis_all/acceptance.json').read_text())['best_observed_policy']
    refinement=best in [c['policy'] for c in json.loads((WORK/'configs'/VERSION/'refinement.json').read_text())['runs']]
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    runtime=target/'results'/VERSION/'runtime';runtime.mkdir()
    for key in ['TMPDIR','TMP','TEMP','MPLCONFIGDIR']:env[key]=str(runtime)
    scripts=target/'scripts'/VERSION
    def run(script,*arguments):
        with (report/(script+'.log')).open('w') as log:
            subprocess.run([sys.executable,str(scripts/script),*arguments],cwd=target,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        print('Completed',script,flush=True)
    run('test_kernel.py');run('independent_verify.py','--scope','sources')
    run('run_experiments.py','runs','--policies',best,*(['--refinement'] if refinement else []))
    # Import only the independent validator from the relocated script folder.
    sys.path.insert(0,str(scripts));import independent_verify as v
    a=v.Audit();folder=target/'results'/VERSION/'runs'/best
    source=v.csv(target/'results'/VERSION/'inputs/actual_10min.csv');archive=v.csv(target/'results'/VERSION/'forecasts/linear_harmonic.csv')
    actual=v.ledger_audit(a,folder,source,7268.4231640740745,best);candidate=v.candidate_audit(a,folder,archive,best)
    assert a.passed
    import numpy as np
    orig=v.csv(ROOT/'runs'/best/'ledger.csv');new=v.csv(folder/'ledger.csv')
    assert orig.shape==new.shape and orig.columns.tolist()==new.columns.tolist()
    numeric=orig.select_dtypes(include='number').columns;textcols=orig.columns.difference(numeric)
    error=float(abs(orig[numeric]-new[numeric]).to_numpy().max());same_text=orig[textcols].equals(new[textcols])
    cost=abs(float(orig.total_cost_yuan.sum()-new.total_cost_yuan.sum()))
    assert error<=1e-6 and cost<=1e-5 and same_text
    oldev=v.npz(ROOT/'runs'/best/'decision_evidence.npz');newev=v.npz(folder/'decision_evidence.npz')
    bitwise=all(np.array_equal(oldev[k],newev[k],equal_nan=True) for k in oldev)
    assert bitwise
    result=dict(passed=True,policy=best,scope='Complete 334-day best-policy relocation, C recompile and independent source/candidate/physical/bill audits.',
        ledger_max_numeric_difference=error,total_cost_difference_yuan=cost,text_identical=same_text,candidate_evidence_bitwise_identical=bitwise,
        independent_check_count=len(a.rows),actual=actual,candidates=candidate,target=str(target))
    (report/'reproduction_comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    shutil.copyfile(report/'reproduction_comparison.json',WORK/'reports'/VERSION/'portability_validation.json')
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
