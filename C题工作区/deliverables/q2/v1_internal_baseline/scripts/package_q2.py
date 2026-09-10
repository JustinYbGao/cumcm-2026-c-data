"""Freeze Q2 results and paper, then independently validate the copied package."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

WORK=Path(__file__).resolve().parents[1]


def main():
    target=WORK/'deliverables/q2/v1_internal_baseline'
    if target.exists():raise FileExistsError('Preserve existing Q2 package')
    files=[]
    for directory in ['results/q2','logs/q2']:
        files += [p for p in (WORK/directory).rglob('*') if p.is_file()]
    files += [WORK/p for p in ['data/processed/actual_10min.csv','data/processed/fixed_price.csv',
        'configs/model_baseline.json','configs/q2_baseline.json','requirements.txt','scripts/run_q2.py',
        'scripts/solve_q1.py','scripts/validate_q2.py','tests/test_q2.py','papers/q2_draft.md',
        'reports/q2_model_and_results.md','reports/q2_model_fit.md','reports/q2_bzd_solution_check.md',
        'reports/q2_representative_tables.md','scripts/package_q2.py']]
    for name in ['monthly_costs','representative_execution']:
        files += [p for p in (WORK/'reports/figures/modelviz_v3_en'/name).rglob('*') if p.is_file()]
    for source in files:
        dest=target/source.relative_to(WORK);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
    (target/'README.md').write_text('# Q2 frozen internal baseline\n\nEntry: papers/q2_draft.md. Full numerical ledgers and selection evidence: results/q2.\n\nRun `python -B scripts/validate_q2.py` after installing requirements. The validator recomputes physics, billing, forecasts and output tables from the saved results; no original worktree is needed for this audit. Plot provenance retains original machine paths as historical evidence.\n\nNo formal Excel submission: template time mapping is unresolved. The January-selected model underperformed the seasonal baseline; this negative result is preserved.\n')
    env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(WORK/'data/interim/q3'))
    result=subprocess.run([sys.executable,'-B',str(target/'scripts/validate_q2.py')],cwd=target,env=env,capture_output=True,text=True)
    (target/'package_validation.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    manifest={str(p.relative_to(target)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.rglob('*')) if p.is_file()}
    (target/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    archive=target.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in target.rglob('*'):
            if p.is_file():z.write(p,str(p.relative_to(target)))
    archive.with_suffix('.zip.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(name)).hexdigest()==digest for name,digest in manifest.items())
    print(f'Q2 package: {len(manifest)} files; copied-package independent validation passed; ZIP hashes passed')


if __name__=='__main__':main()
