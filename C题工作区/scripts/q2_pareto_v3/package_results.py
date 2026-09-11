"""Build only after numeric, text, figure, relocation and preservation gates pass."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

WORK=Path(__file__).resolve().parents[2];VERSION='q2_pareto_v3';REPORT=WORK/'reports'/VERSION


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda:stream.read(1024*1024),b''):h.update(part)
    return h.hexdigest()


def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def main():
    archive=REPORT/'q2_pareto_v3_review.zip'
    if archive.exists():raise FileExistsError('Archive already exists; preserve it and use a new name/version.')
    science=['base_policy.py','policy.py','run_experiments.py','causality_checks.py','analyze_results.py','analyze_user_cap.py']
    for filename in ['independent_validation.json','independent_validation_extension_all.json']:
        audit=json.loads((REPORT/filename).read_text());assert audit['passed'],filename
        assert digest(WORK/'scripts'/VERSION/'independent_verify.py')==audit['validator_sha256']
        for name in science:assert digest(WORK/'scripts'/VERSION/name)==audit['producer_sha256'][name],name
    summary=json.loads((REPORT/'independent_final_numeric_summary.json').read_text());assert summary['passed']
    for name,value in summary['reports'].items():assert digest(REPORT/name)==value,name
    text_review=json.loads((REPORT/'independent_text_review.json').read_text());assert text_review['passed']
    assert not text_review.get('unresolved_in_scope_findings',[])
    for name,value in text_review['artifact_sha256'].items():assert digest(WORK/name)==value,name
    for name in ['causality_validation.json','extension_causality_validation.json','portability_validation.json','independent_figure_validation.json']:
        assert json.loads((REPORT/name).read_text())['passed'],name
    figure_audit=json.loads((REPORT/'independent_figure_validation.json').read_text())
    for name,record in figure_audit['figures'].items():
        for relative,value in record['artifact_sha256'].items():assert digest(REPORT/'figures'/name/relative)==value,name+relative
    for name in ['savings','monthly']:
        assert json.loads((REPORT/'figures'/name/'workspace/final_quality_report.json').read_text())['passed']
    freeze=json.loads((REPORT/'protocol_freeze.json').read_text())
    assert digest(REPORT/'protocol.md')==freeze['protocol_sha256']
    assert digest(WORK/'configs'/VERSION/'experiments.json')==freeze['config_sha256']
    for name,value in json.loads((REPORT/'extension_freeze.json').read_text())['files'].items():assert digest(WORK/name)==value,name
    before=json.loads((REPORT/'protected_hashes_before.json').read_text())
    changed=[name for name,value in before.items() if not (WORK/name).is_file() or digest(WORK/name)!=value]
    save(REPORT/'preservation_validation.json',dict(passed=not changed,protected_files=len(before),changed=changed,
        scope='All pre-existing scientific artifacts captured before this run; runtime caches excluded; no commit/push by this task.'))
    assert not changed,changed
    sources=list((WORK/'scripts'/VERSION).rglob('*.py'))+list((WORK/'configs'/VERSION).glob('*.json'))+list((WORK/'results'/VERSION/'inputs').glob('*'))
    save(REPORT/'code_and_input_hashes.json',{str(p.relative_to(WORK)):digest(p) for p in sources if p.is_file()})
    (REPORT/'git_status_after.txt').write_text(subprocess.check_output(['git','status','--porcelain=v1'],cwd=WORK.parent,text=True))
    exclude={'runtime','portability_check','reproduction_workspace','__pycache__','independent_cache'}
    omit={'package_manifest.csv','package_validation.json','package_build.log','package_verify.log'}
    files=[]
    for top in ['scripts','configs','results','reports','papers']:
        for p in (WORK/top/VERSION).rglob('*'):
            if not p.is_file() or set(p.relative_to(WORK).parts)&exclude:continue
            if p.name in omit or p.suffix in ['.zip','.sha256']:continue
            files.append(p)
    files.sort();manifest=REPORT/'package_manifest.csv'
    with manifest.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['path','bytes','sha256']);writer.writeheader()
        for p in files:writer.writerow(dict(path=str(p.relative_to(WORK)),bytes=p.stat().st_size,sha256=digest(p)))
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files+[manifest]:z.write(p,str(p.relative_to(WORK)))
    expected={str(p.relative_to(WORK)):digest(p) for p in files+[manifest]}
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist())==set(expected)
        for name,value in expected.items():assert hashlib.sha256(z.read(name)).hexdigest()==value,name
        assert z.testzip() is None
    zip_sha=digest(archive);(REPORT/(archive.name+'.sha256')).write_text(zip_sha+'  '+archive.name+'\n')
    save(REPORT/'package_validation.json',dict(passed=True,manifest_files=len(files),zip_entries=len(files)+1,
        zip_bytes=archive.stat().st_size,zip_sha256=zip_sha,readback_sha256_all_match=True,
        excluded='Runtime caches and duplicate portability workspace; relocation summary and logs included.',
        manifest_self_reference='Manifest and package-validation sidecars excluded from manifest; manifest included in ZIP.'))
    print(json.dumps(dict(passed=True,archive=str(archive),files=len(files),bytes=archive.stat().st_size,sha256=zip_sha),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
