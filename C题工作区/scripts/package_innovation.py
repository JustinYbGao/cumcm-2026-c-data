"""Freeze innovation evidence and verify portable numerical audits in the copy."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

WORK=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    target=WORK/'deliverables/innovation/v1_exploratory'
    if target.exists():raise FileExistsError('Use a new version; frozen package already exists')
    assert json.loads((WORK/'results/innovation/artifact_validation.json').read_text())['passed']
    files=set()
    for directory in ['results/innovation','logs/innovation','reports/innovation','reports/figures/modelviz_innovation_v1_en']:
        for p in (WORK/directory).rglob('*'):
            if p.is_file() and p.name!='package.log' and 'smoke' not in p.relative_to(WORK/directory).parts:files.add(p)
    files.update(WORK/n for n in json.loads((WORK/'results/innovation/input_code_hashes.json').read_text()))
    files.update(WORK/n for n in ['requirements.txt','requirements-q3.txt','scripts/validate_innovation.py','scripts/audit_innovation_lp.py',
        'scripts/report_innovation.py','scripts/verify_innovation_artifacts.py','scripts/modelviz_innovation.py','scripts/modelviz_revision.py',
        'scripts/modelviz/innovation_monthly.py','scripts/modelviz/innovation_risk.py','scripts/package_innovation.py',
        'tests/test_innovation_core.py','papers/innovation_draft.md'])
    for source in sorted(files):
        dest=target/source.relative_to(WORK);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
    (target/'data/interim/innovation').mkdir(parents=True,exist_ok=True)
    (target/'README.md').write_text('''# Frozen innovation experiment package

Read papers/innovation_draft.md and reports/innovation/model_and_results.md.
Eleven policies have February-March calibration and April-December evaluation.
March selects PV bias correction, fixed reserve, and paid updates without a gate.
Later PV savings are positive; risk-reserve effects are only a few yuan and both
gates increase actual cost. All candidate results, including failures, remain.

This is exploratory retrospective evaluation, NOT a formal submission or a claim
of original algorithms. Time mapping, settlement, efficiency and terminal-state
assumptions remain explicit. No full Q4 transfer or combined innovation policy is
claimed. Proxy penalties are separate from actual bills.

Use Python 3.12, install requirements-q3.txt, then run inside a COPY:

    python -B scripts/validate_innovation.py
    python -B scripts/audit_innovation_lp.py
    python -B -m unittest discover -s tests -p test_innovation_core.py

All three commands ran in this copied package before its manifest was created.
Audits can rewrite runtime diagnostics, so keep this frozen directory unchanged.
Inputs include the cleaned actual/PV/price files and inherited frozen Q2 forecasts
and Q3 common-state source. Full recomputation uses scripts/run_innovation.py in
a new work copy without completed results/innovation. Source hashes are relative.
The 25 previous-model tests are evidenced in logs/innovation/base_tests.log; the
nine innovation tests are included. No unrelated member workspace is copied.

Figures contain English labels only, PNG at 300 dpi and SVG. The standalone
workspace/adapted_plot.py accepts data.csv and an output directory. Full ModelViz
services need the installed skill; historical template paths are provenance.
verify_innovation_artifacts.py also checks earlier packages in the parent workspace,
so it is not a portable numerical command. Initial render/repair evidence is retained.

manifest.json hashes all package files except itself. Sibling partNN.zip archives
are independent ZIPs containing disjoint paths: extract ALL parts into ONE folder.
Their .sha256 files and archive_index.json provide transport checks. Splitting keeps
individual transport files manageable; no byte concatenation is needed. BZD query
logs preserve full attribution and licensing.
''')
    env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(target/'data/interim/innovation'),TMP=str(target/'data/interim/innovation'),TEMP=str(target/'data/interim/innovation'))
    commands=[['scripts/validate_innovation.py'],['scripts/audit_innovation_lp.py'],['-m','unittest','discover','-s','tests','-p','test_innovation_core.py']]
    passed=[]
    for i,args in enumerate(commands,1):
        result=subprocess.run([sys.executable,'-B',*args],cwd=target,env=env,capture_output=True,text=True)
        (target/f'package_validation_{i}.log').write_text(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        passed.append({'command':['python','-B',*args],'exit_code':0});print('Copied innovation audit',i,'passed',flush=True)
    (target/'package_validation.json').write_text(json.dumps({'passed':True,'commands':passed},indent=2)+'\n')
    for name,value in json.loads((target/'results/innovation/report_sources.json').read_text()).items():assert sha(target/name)==value,name
    manifest={str(p.relative_to(target)):sha(p) for p in sorted(target.rglob('*')) if p.is_file()}
    (target/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    archives=[];z=None
    for p in sorted(target.rglob('*')):
        if not p.is_file():continue
        if z is None or z.fp.tell()>70_000_000:
            if z:z.close()
            archive=target.parent/f'{target.name}.part{len(archives)+1:02d}.zip';archives.append(archive);z=zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED)
        z.write(p,str(p.relative_to(target)))
    if z:z.close()
    index=[];seen=set()
    for archive in archives:
        digest=sha(archive);archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n')
        with zipfile.ZipFile(archive) as bundle:
            assert bundle.testzip() is None
            for name in bundle.namelist():
                assert name not in seen;seen.add(name)
                if name!='manifest.json':assert hashlib.sha256(bundle.read(name)).hexdigest()==manifest[name]
        index.append({'file':archive.name,'bytes':archive.stat().st_size,'sha256':digest})
    assert seen==set(manifest)|{'manifest.json'}
    (target.parent/'archive_index.json').write_text(json.dumps({'package':target.name,'file_count':len(manifest),'extract_all_parts_into_one_directory':True,'archives':index},indent=2)+'\n')
    print('Innovation package:',len(manifest),'files;',len(archives),'ZIP parts;',sum(a.stat().st_size for a in archives),'bytes',flush=True)

if __name__=='__main__':main()
