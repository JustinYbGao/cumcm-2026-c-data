"""Package only reviewed, preserved results; read back every archived SHA-256."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

WORK=Path(__file__).resolve().parents[2];VERSION='q2_direct_v4';REPORT=WORK/'reports'/VERSION


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for piece in iter(lambda:stream.read(1024*1024),b''):h.update(piece)
    return h.hexdigest()


def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def main():
    archive=REPORT/(VERSION+'_review.zip');assert not archive.exists(),'Preserve existing archive; use a new version.'
    scopes=['sources','references','oracle','gradient','january','annual','causality','analysis',
            'refinement_january','refinement_annual','refinement_causality','analysis_all','figure_validation']
    reports={}
    for scope in scopes:
        p=REPORT/('independent_'+scope+'.json');r=json.loads(p.read_text());assert r['passed'],scope
        assert all(c['passed'] for c in r['checks']),scope
        reports[p.name]=digest(p)
    for name in ['independent_text_review.json','independent_final_summary.json','portability_validation.json','preservation_validation.json']:
        p=REPORT/name;assert json.loads(p.read_text())['passed'],name;reports[name]=digest(p)
    seal=json.loads((REPORT/'independent_final_summary.json').read_text())
    assert not seal['unresolved_in_scope_findings']
    for row in seal['audit_reports']:
        assert row['passed'] and digest(WORK/row['path'])==row['sha256'],row['path']
    for key in ['source_sha256','review_narratives_sha256','final_text_sha256']:
        for name,value in seal[key].items():assert digest(WORK/name)==value,name
    analysis=WORK/'results'/VERSION/'analysis_all'
    assert digest(analysis/'comparison_all.csv')==seal['comparison_csv_sha256']
    assert digest(analysis/'acceptance.json')==seal['acceptance_sha256']
    assert digest(WORK/seal['portability_report']['path'])==seal['portability_report']['sha256']
    for name in ['savings','monthly']:
        ws=REPORT/'figures'/name/'workspace';assert json.loads((ws/'final_quality_report.json').read_text())['passed']
        assessed=json.loads((ws/'assistant_visual_assessment.json').read_text())
        assert digest(REPORT/'figures'/name/'outputs/chart.png')==assessed['inspected_png_sha256']
        assert digest(ws/'adapted_plot.py')==assessed['inspected_script_sha256']
    for name,value in json.loads((REPORT/'protocol_freeze.json').read_text())['files'].items():assert digest(WORK/name)==value
    for name,value in json.loads((REPORT/'refinement_freeze.json').read_text())['sha256'].items():
        p=Path(name);p=p if p.is_absolute() else WORK.parent/p
        assert digest(p)==value
    before=json.loads((REPORT/'protected_hashes_before.json').read_text())
    changed=[name for name,value in before.items() if not (WORK/name).is_file() or digest(WORK/name)!=value]
    assert not changed,changed
    inputs=[p for p in (WORK/'results'/VERSION/'inputs').iterdir() if p.is_file()]
    code=[p for p in (WORK/'scripts'/VERSION).rglob('*') if p.is_file()]
    configs=list((WORK/'configs'/VERSION).glob('*.json'))
    save(REPORT/'code_and_input_hashes.json',{str(p.relative_to(WORK)):digest(p) for p in inputs+code+configs})
    save(REPORT/'package_gate_validation.json',dict(passed=True,reports_sha256=reports,protected_files=len(before)))
    (REPORT/'git_status_after.txt').write_text(subprocess.check_output(['git','status','--porcelain=v1'],cwd=WORK.parent,text=True))
    excluded={'runtime','reproduction_workspace','reproduction_completed','__pycache__','independent_cache'}
    omit={'package_manifest.csv','package_validation.json','package_build.log','package_verify.log'}
    files=[]
    for top in ['scripts','configs','results','reports','papers']:
        for p in (WORK/top/VERSION).rglob('*'):
            if not p.is_file() or set(p.relative_to(WORK).parts)&excluded or p.name in omit or p.suffix in ['.zip','.sha256']:continue
            files.append(p)
    files.sort();manifest=REPORT/'package_manifest.csv'
    with manifest.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['path','bytes','sha256']);writer.writeheader()
        for p in files:writer.writerow(dict(path=str(p.relative_to(WORK)),bytes=p.stat().st_size,sha256=digest(p)))
    print('Manifest complete',len(files),'files',flush=True)
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files+[manifest]:z.write(p,str(p.relative_to(WORK)))
    expected={str(p.relative_to(WORK)):digest(p) for p in files+[manifest]}
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist())==set(expected)
        for name,value in expected.items():assert hashlib.sha256(z.read(name)).hexdigest()==value,name
        assert z.testzip() is None
    sha=digest(archive);(REPORT/(archive.name+'.sha256')).write_text(sha+'  '+archive.name+'\n')
    save(REPORT/'package_validation.json',dict(passed=True,manifest_files=len(files),zip_entries=len(files)+1,
        zip_bytes=archive.stat().st_size,zip_sha256=sha,readback_sha256_all_match=True,
        exclusions='Runtime and duplicate relocation workspaces; logs and relocation report included.',
        self_reference='Manifest excludes itself and package-validation sidecars. Manifest is included in ZIP.'))
    print('Package verified',archive,archive.stat().st_size,sha,flush=True)


if __name__=='__main__':main()
