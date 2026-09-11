"""Freeze Q4 inputs, decisions, results and evidence; independently audit the copy."""
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
    target=WORK/'deliverables/q4/v1_internal_variable_price'
    if target.exists():raise FileExistsError('Preserve the frozen Q4 package; use a new version')
    assert json.loads((WORK/'results/q4/artifact_validation.json').read_text())['passed']
    files=set()
    for directory in ['results/q4','reports/figures/modelviz_q4_v1_en','logs/q4']:
        files.update(p for p in (WORK/directory).rglob('*') if p.is_file() and p.name!='package.log')
    files.update(WORK/name for name in json.loads((WORK/'results/q4/input_code_hashes.json').read_text()))
    files.update(WORK/name for name in ['requirements.txt','requirements-q3.txt','scripts/validate_q4.py',
        'scripts/audit_q4_lp.py','scripts/audit_q3_lp.py','scripts/report_q4.py','scripts/report_q3.py',
        'scripts/modelviz_q4.py','scripts/modelviz_revision.py','scripts/modelviz/q4_monthly.py',
        'scripts/modelviz/q4_prices.py','scripts/package_q4.py','scripts/verify_q4_artifacts.py',
        'tests/test_q4.py','papers/q4_draft.md','reports/q4_model_and_results.md',
        'reports/q4_model_fit.md','reports/q4_bzd_solution_check.md','reports/q4_representative_tables.md'])
    for source in sorted(files):
        dest=target/source.relative_to(WORK);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
    (target/'data/interim/q4').mkdir(parents=True,exist_ok=True)
    (target/'README.md').write_text('''# Q4 frozen internal variable-price results

Entry: papers/q4_draft.md. Full prescribed-day tables for Q4-2 and Q4-3 A/B:
reports/q4_representative_tables.md. Nine predefined retrospective policies are in
results/q4. Actual prices settle all policies; future actual prices are available
only to the explicitly hypothetical perfect-price controls.

This is NOT a formal submission. Future-price availability, target-price versus
locked-price settlement, A/B refunds, final-volume versus per-revision billing,
efficiency, terminal-state assumptions and template time mapping remain open.
All policies inherit the same Q2 fixed-price January warm-up state. Negative
intraday OLS-price results are preserved. Q1-Q3 source outputs are unchanged.

Use Python 3.12 and install requirements-q3.txt, then run inside a COPY:

    python -B scripts/validate_q4.py
    python -B scripts/audit_q4_lp.py
    python -B -m unittest discover -s tests -p test_q4.py

These commands were executed in this copied package before creating its manifest.
Audit outputs can change diagnostic metadata; preserve this frozen directory.
The 25-test full-workspace evidence is in logs/q4/all_model_tests.log; the five
Q4 tests and all numerical audit dependencies are included here. Full recomputation
requires a fresh work copy without completed results/q4; run scripts/run_q4.py.
All cleaned inputs and inherited forecasts required by that script are included.

Both figures have English labels, 300-dpi PNG and SVG. Each standalone
workspace/adapted_plot.py takes data.csv and an output directory. The full
ModelViz service pipeline requires the installed skill. Its historical absolute
paths are preserved as provenance. verify_q4_artifacts.py is a parent-workspace
preservation check and requires the previous packages and installed template;
it is not one of the portable numerical audit commands above.

The manifest hashes all packaged files except itself. Sibling ZIP/SHA256 files
provide transport integrity. BZD dictionary query logs retain full attribution
and licensing. No unrelated member workspace or previous frozen package is copied.
''')
    env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(target/'data/interim/q4'),TMP=str(target/'data/interim/q4'),TEMP=str(target/'data/interim/q4'))
    commands=[['scripts/validate_q4.py'],['scripts/audit_q4_lp.py'],['-m','unittest','discover','-s','tests','-p','test_q4.py']]
    summaries=[]
    for i,args in enumerate(commands,1):
        result=subprocess.run([sys.executable,'-B',*args],cwd=target,env=env,capture_output=True,text=True)
        (target/f'package_validation_{i}.log').write_text(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        summaries.append({'command':['python','-B',*args],'exit_code':result.returncode})
        print('Copied Q4 audit',i,'passed',flush=True)
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
    print('Q4 package:',len(manifest),'files; ZIP',archive.stat().st_size,'bytes; SHA256',digest,flush=True)

if __name__=='__main__':main()
