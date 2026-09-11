"""Freeze manifests and create a separate Q2 research ZIP with read-back validation."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

WORK=Path(__file__).resolve().parents[2]
VERSION='q2_cost_aware_v2'
REPORT=WORK/'reports'/VERSION


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def main():
    validation=json.loads((REPORT/'independent_validation.json').read_text())
    assert validation['passed']
    text_review=json.loads((REPORT/'independent_text_review.json').read_text())
    assert text_review['passed'] and not text_review['unresolved_in_scope_findings']
    for name,expected in text_review['artifact_sha256'].items():
        assert digest(WORK/name)==expected, name
    assert json.loads((REPORT/'independent_validation_followup.json').read_text())['passed']
    assert json.loads((REPORT/'causality_extension_validation.json').read_text())['passed']
    for name in ['annual','monthly']:
        assert json.loads((REPORT/'figures'/name/'workspace/final_quality_report.json').read_text())['passed']
    assert json.loads((REPORT/'causality_validation.json').read_text())['passed']
    assert json.loads((REPORT/'portability_validation.json').read_text())['passed']
    before=json.loads((REPORT/'protected_hashes_before.json').read_text())
    changed=[p for p,h in before.items() if not (WORK/p).is_file() or digest(WORK/p)!=h]
    save(REPORT/'preservation_validation.json',{'passed':not changed,'protected_files':len(before),'changed':changed,
                                            'scope':'All pre-existing scientific artifacts captured before this run; no commit/push by this task.'})
    assert not changed,changed
    freeze=json.loads((REPORT/'protocol_freeze.json').read_text())
    assert digest(REPORT/'protocol.md')==freeze['protocol_sha256']
    assert digest(WORK/'configs'/VERSION/'experiments.json')==freeze['config_sha256']
    extension=json.loads((REPORT/'extension_freeze.json').read_text())
    assert digest(REPORT/'extension_protocol.md')==extension['protocol_sha256']
    assert digest(WORK/'configs'/VERSION/'extension.json')==extension['config_sha256']
    source_files=list((WORK/'scripts'/VERSION).rglob('*.py'))+list((WORK/'configs'/VERSION).glob('*.json'))
    source_files+=list((WORK/'results'/VERSION/'inputs').glob('*'))
    save(REPORT/'code_and_input_hashes.json',{str(p.relative_to(WORK)):digest(p) for p in source_files if p.is_file()})
    env=json.loads((REPORT/'environment.json').read_text())
    (REPORT/'requirements.lock.txt').write_text('\n'.join(f'{name}=={version}' for name,version in sorted(env['packages'].items()))+'\n')
    (REPORT/'git_status_after.txt').write_text(subprocess.check_output(['git','status','--porcelain=v1'],cwd=WORK.parent,text=True))
    exclude={'runtime','portability_check','reproduction_workspace','__pycache__','independent_cache'}
    omit={'package_manifest.csv','package_validation.json','package_build.log','package_verify.log'}
    files=[]
    for top in ['scripts','configs','results','reports','papers']:
        for p in (WORK/top/VERSION).rglob('*'):
            if not p.is_file() or set(p.relative_to(WORK).parts)&exclude:continue
            if p.name in omit or p.suffix in ['.zip','.sha256']:continue
            files.append(p)
    files.sort()
    manifest=REPORT/'package_manifest.csv'
    with manifest.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['path','bytes','sha256']);writer.writeheader()
        for p in files:writer.writerow({'path':str(p.relative_to(WORK)),'bytes':p.stat().st_size,'sha256':digest(p)})
    archive=REPORT/'q2_cost_aware_v2_review.zip'
    if archive.exists():raise FileExistsError('Archive already exists; preserve it and use a new version.')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files+[manifest]:z.write(p,str(p.relative_to(WORK)))
    expected={str(p.relative_to(WORK)):digest(p) for p in files+[manifest]}
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist())==set(expected)
        for name,h in expected.items():
            assert hashlib.sha256(z.read(name)).hexdigest()==h,name
        assert z.testzip() is None
    zip_sha=digest(archive)
    (REPORT/(archive.name+'.sha256')).write_text(zip_sha+'  '+archive.name+'\n')
    save(REPORT/'package_validation.json',{'passed':True,'manifest_files':len(files),'zip_entries':len(files)+1,
                                         'zip_bytes':archive.stat().st_size,'zip_sha256':zip_sha,'readback_sha256_all_match':True,
                                         'excluded':'runtime caches and duplicate portability workspace; its logs/validation are included',
                                         'manifest_self_reference':'Manifest and archive validation sidecars excluded from manifest; manifest included in ZIP.'})
    print(json.dumps({'passed':True,'archive':str(archive),'files':len(files),'bytes':archive.stat().st_size,'sha256':zip_sha},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
