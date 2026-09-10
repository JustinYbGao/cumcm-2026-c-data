"""Freeze the internal Q3 package and audit its copied numerical results."""
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
    target=WORK/'deliverables/q3/v1_internal_mpc'
    if target.exists():raise FileExistsError('Preserve the frozen Q3 package; use a new version')
    assert json.loads((WORK/'results/q3/artifact_validation.json').read_text())['passed']
    files=set()
    for directory in ['results/q3','results/q3_feedback_control','reports/figures/modelviz_q3_v1_en','logs/q3']:
        files.update(p for p in (WORK/directory).rglob('*') if p.is_file() and p.name!='package.log')
    for directory in ['results/q3','results/q3_feedback_control']:
        files.update(WORK/name for name in json.loads((WORK/directory/'input_code_hashes.json').read_text()))
    files.update(WORK/name for name in ['requirements.txt','requirements-q3.txt','scripts/validate_q3.py',
        'scripts/audit_q3_lp.py','scripts/report_q3.py','scripts/modelviz_q3.py','scripts/modelviz_revision.py',
        'scripts/modelviz/q3_monthly.py','scripts/modelviz/q3_execution.py','scripts/package_q3.py',
        'tests/test_q3.py','results/q1/baseline/schedule.csv','papers/q3_draft.md',
        'reports/q3_model_and_results.md','reports/q3_model_fit.md','reports/q3_execution_plan.md',
        'reports/q3_bzd_solution_check.md','reports/q3_representative_tables.md'])
    for source in sorted(files):
        dest=target/source.relative_to(WORK);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
    (target/'data/interim/q3').mkdir(parents=True,exist_ok=True)
    (target/'README.md').write_text('''# Q3 frozen internal MPC results

Entry: papers/q3_draft.md; full A/B tables: reports/q3_representative_tables.md.
Primary six policies: results/q3. Retrospective state-feedback-only control:
results/q3_feedback_control. The control isolates feedback from PV refresh.

This is NOT a formal submission. Template time mapping, refund versus no-refund,
final-volume versus per-revision billing, efficiency and terminal-state assumptions
remain explicit unresolved interpretations. Q4 has not been run.

Numerical audits are portable: create a Python 3.12 environment, install
requirements-q3.txt, then run from this directory:

    python -B scripts/validate_q3.py
    python -B scripts/validate_q3.py --results results/q3_feedback_control
    python -B scripts/audit_q3_lp.py
    python -B -m unittest discover -s tests -p test_q3.py

Audit outputs were regenerated here before the manifest was created. Later audit
runs can change diagnostic runtime metadata, so preserve this frozen directory
and work on a copy. Core planners refuse to overwrite completed result folders.
Full recomputation requires a fresh result directory in a copied work area; the
needed cleaned inputs, inherited Q2 load predictions and core code are included.

Both figures contain English labels only and include 300-dpi PNG and SVG. Their
standalone workspace/adapted_plot.py accepts data.csv and an output directory,
without the ModelViz skill. Re-running the full ModelViz service pipeline requires
the locally installed skill; original absolute paths in provenance are historical.
Initial failed visual/schema records are retained as repair evidence; the final
quality reports and inspected image hashes identify the accepted renderings.

manifest.json contains SHA-256 values for all packaged files except itself.
The sibling ZIP and .zip.sha256 provide transport integrity. No unrelated member
workspace, original raw attachment, previous frozen package or external credential
is included. BZD dictionary attribution and complete licensing remain in query logs.
''')
    env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(target/'data/interim/q3'))
    commands=[['scripts/validate_q3.py'],['scripts/validate_q3.py','--results','results/q3_feedback_control'],
        ['scripts/audit_q3_lp.py'],['-m','unittest','discover','-s','tests','-p','test_q3.py']]
    summaries=[]
    for i,args in enumerate(commands,1):
        result=subprocess.run([sys.executable,'-B',*args],cwd=target,env=env,capture_output=True,text=True)
        (target/f'package_validation_{i}.log').write_text(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        summaries.append({'command':['python','-B',*args],'exit_code':result.returncode})
        print('Copied package audit',i,'passed',flush=True)
    (target/'package_validation.json').write_text(json.dumps({'passed':True,'commands':summaries},indent=2)+'\n')
    manifest={str(p.relative_to(target)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.rglob('*')) if p.is_file()}
    (target/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    archive=target.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(target.rglob('*')):
            if p.is_file():z.write(p,str(p.relative_to(target)))
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(name)).hexdigest()==value for name,value in manifest.items())
    print('Q3 package:',len(manifest),'files; ZIP',archive.stat().st_size,'bytes; SHA256',digest,flush=True)


if __name__=='__main__':main()
