"""Package the plot revision as a supplement; never overwrite the frozen Q1 package."""
import hashlib
import json
from pathlib import Path
import zipfile

from verify_modelviz_revision import main as verify

WORK=Path(__file__).resolve().parents[1]
ROOT=WORK/'reports/figures/modelviz_v3_en'


def main():
    verify()
    output=WORK/'deliverables/figures/modelviz_v3_en.zip'
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():raise FileExistsError('Preserve existing bundle; use a new version directory')
    files=[p for p in ROOT.rglob('*') if p.is_file() and p.name!='bundle_manifest.json']
    files+=list((WORK/'scripts/modelviz').glob('*.py'))
    files += [WORK/p for p in ['scripts/modelviz_revision.py','scripts/plot_results_modelviz.py',
        'scripts/verify_modelviz_revision.py','scripts/package_modelviz_revision.py',
        'scripts/report_q1.py','scripts/report_q2.py','papers/q1_draft.md',
        'reports/q1_model_and_results.md','reports/q2_model_and_results.md','reports/modelviz_v3_en_revision.md',
        'README.md','AGENTS.md']]
    manifest={str(p.relative_to(WORK)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}
    (ROOT/'bundle_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    files.append(ROOT/'bundle_manifest.json')
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(set(files)):z.write(path,str(path.relative_to(WORK)))
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(digest+'  '+output.name+'\n')
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        for name,expected in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==expected
    print(f'Packaged and checked {len(manifest)} files: {output}')


if __name__=='__main__':main()
