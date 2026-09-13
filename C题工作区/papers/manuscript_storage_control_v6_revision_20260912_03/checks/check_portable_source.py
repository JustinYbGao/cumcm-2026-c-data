"""Extract and compile the packaged LaTeX without executing model programs."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import zipfile

P = Path(__file__).resolve().parents[1]
sha = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()
subprocess.run(['python3', str(P / 'code/package_latex.py')], check=True)
archive = P / 'outputs/latex_source.zip'
folder = P / 'checks/portable_source'
assert not folder.exists(), 'Keep prior extracted compilation records; use a fresh directory.'
folder.mkdir()
package = json.loads((P / 'reports/latex_package.json').read_text())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for name in z.namelist():
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
    z.extractall(folder)
assert all(sha(folder / name) == digest for name, digest in package['files'].items())
env = dict(os.environ, TECTONIC_CACHE_DIR=str(P / 'tools/tex-cache'), SOURCE_DATE_EPOCH='1789171200')
command = [str(P / 'tools/tectonic'), 'main.tex', '--outdir', '.', '--keep-logs', '--only-cached']
run = subprocess.run(command, cwd=folder, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
(P / 'reports/portable_compiler_output.txt').write_text(run.stdout)
run.check_returncode()
assert sha(folder / 'main.pdf') == sha(P / 'outputs/manuscript_review.pdf')
result = {'archive_sha256': sha(archive), 'archive_bytes': archive.stat().st_size, 'extracted_files_checked': len(package['files']), 'extracted_compile_pdf_sha256': sha(folder / 'main.pdf'), 'matches_manuscript_pdf_bytes': True, 'command': command, 'package_downloads_allowed': False, 'model_programs_executed': False, 'portability_limit': 'Actual extracted compile on the current host using the recorded cached TeX runtime; other hosts need compatible fonts and packages.'}
(P / 'reports/portable_compile.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
