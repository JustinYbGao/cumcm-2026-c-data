"""Compile the retained manuscript locally; never runs modeling experiments."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

P = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--allow-package-downloads', action='store_true')
args = parser.parse_args()
# Retain each already-built source/PDF before compiling an edited manuscript.
immutable=P/'build/source_manuscript.md'
if immutable.exists() and immutable.read_bytes()!=(P/'manuscript_EN.md').read_bytes():
    history=P/'build_history'
    history.mkdir(exist_ok=True)
    index=1
    while (history/f'attempt_{index:02d}').exists():
        index+=1
    archived=history/f'attempt_{index:02d}'
    archived.mkdir()
    shutil.move(str(P/'build'),str(archived/'build'))
    (P/'build').mkdir()
    for relative in ['outputs/manuscript_review.pdf','reports/compilation.json','reports/page_previews.json']:
        source=P/relative
        if source.exists():
            target=archived/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
subprocess.run([sys.executable, '-B', str(P/'code/convert_manuscript.py')], check=True)
env = dict(os.environ, TECTONIC_CACHE_DIR=str(P/'tools/tex-cache'),
           SOURCE_DATE_EPOCH='1789171200')
command = [str(P/'tools/tectonic'), 'main.tex', '--outdir', 'outputs',
           '--keep-logs', '--keep-intermediates', '--synctex']
if not args.allow_package_downloads:
    command.append('--only-cached')
result = subprocess.run(command, cwd=P, env=env, text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
(P/'reports/compiler_output.txt').write_text(result.stdout)
print(result.stdout)
result.check_returncode()
target = P/'outputs/manuscript_review.pdf'
(P/'outputs/main.pdf').replace(target)
record = {'pdf': str(target), 'pdf_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
          'engine': subprocess.check_output([str(P/'tools/tectonic'), '--version'], text=True).strip(),
          'class_sha256': hashlib.sha256((P/'elsarticle.cls').read_bytes()).hexdigest(),
          'package_downloads_allowed': args.allow_package_downloads,
          'command': command, 'source_date_epoch': env['SOURCE_DATE_EPOCH']}
(P/'reports/compilation.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record, indent=2))
