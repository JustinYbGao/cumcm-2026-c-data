"""Package the compiled LaTeX sources with flat, portable image paths."""
from pathlib import Path
import hashlib
import json
import re
import zipfile

P = Path(__file__).resolve().parents[1]
files = {'main.tex': (P/'main.tex').read_bytes(),
         'elsarticle.cls': (P/'elsarticle.cls').read_bytes()}
for name in ('title.tex', 'abstract.tex', 'keywords.tex', 'body.tex'):
    files[name] = (P/'build'/name).read_bytes()
conversion = json.loads((P/'build/conversion_report.json').read_text())
figures = conversion['figures']
assert figures and [f['number'] for f in figures] == list(range(1, conversion['counts']['figures'] + 1))
assert hashlib.sha256((P/'build/body.tex').read_bytes()).hexdigest() == conversion['outputs']['body.tex']
for figure in figures:
    f = P/figure['copy']
    assert f.name == f"figure-{figure['number']:02d}.png" and f.parent == P/'build'
    data = f.read_bytes()
    assert hashlib.sha256(data).hexdigest() == figure['copy_sha256']
    files[f.name] = data
referenced = re.findall(rb'\\includegraphics(?:\[[^\]]*\])?\{build/(figure-\d+\.png)\}', files['body.tex'])
assert [name.decode() for name in referenced] == [f"figure-{f['number']:02d}.png" for f in figures]
for name in ('main.tex', 'body.tex'):
    # Rewrite file arguments only; Appendix A intentionally prints build/body.tex.
    files[name] = re.sub(rb'(\\(?:input|includegraphics)(?:\[[^\]]*\])?\{)build/', rb'\1', files[name])
# Complete source listings must compile in the portable typesetting archive.
appendix = P/'appendix_programs.tex'
assert appendix.is_file(), 'Complete program appendix is required, never silently omitted'
files['appendix_programs.tex'] = appendix.read_bytes()
listed = re.findall(rb'\\lstinputlisting(?:\[[^\]]*\])?\{([^}]+)\}', files['appendix_programs.tex'])
for name in listed:
    relative = name.decode()
    assert relative.startswith('support_materials/') and '..' not in Path(relative).parts
    files[relative] = (P/relative).read_bytes()
files['README_compile.txt'] = (
    'Compile main.tex with XeLaTeX or Tectonic. Retain the included support_materials subdirectories.\n'
    'A4 manuscript with margins of at least 25 mm, a separate abstract, continuous centered page numbers, and no contents page.\n'
    'The class is distributed under the LaTeX Project Public License stated in elsarticle.cls.\n'
    'This archive compiles the paper and its complete source listings. The separate scientific support archive supplies execution inputs, configuration, saved outputs and verification instructions.\n'
).encode()
output = P/'outputs/latex_source.zip'
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
    for name, data in files.items():
        z.writestr(name, data)
report = {'archive': str(output), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
          'files': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
          'figure_count': len(figures), 'figure_numbers': [f['number'] for f in figures],
          'only_transform': 'Remove build/ prefix from input and image references; include unchanged program appendix and its listed source files at their relative paths.'}
(P/'reports/latex_package.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'archive': str(output), 'files': len(files)}, indent=2))
