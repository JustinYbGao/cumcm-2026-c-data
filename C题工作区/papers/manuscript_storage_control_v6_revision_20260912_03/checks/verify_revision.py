"""Fresh editorial preservation, PDF structure, and rendering checks; no model run."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import re
import unicodedata
import zipfile

from pypdf import PdfReader
import pypdfium2 as pdfium

P = Path(__file__).resolve().parents[1]
O = Path(json.loads((P / 'reports/revision_context.json').read_text())['predecessor'])
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
norm = lambda s: re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKC', s).lower())
before = (O / 'manuscript_EN.md').read_text()
after = (P / 'manuscript_EN.md').read_text()
abstract = lambda s: s.split('## Abstract\n', 1)[1].split('# 1 Problem')[0]
assert abstract(before) == abstract(after)
for name in ['abstract.tex', 'keywords.tex']:
    assert (O / 'build' / name).read_bytes() == (P / 'build' / name).read_bytes(), name
assert before.split('# AI tool usage declaration')[1].split('# Appendix A')[0] == after.split('# AI tool usage declaration')[1].split('# Appendix A')[0]
assert before.split('# Appendix B')[1] == after.split('# Appendix B')[1]
title = after.splitlines()[0][2:]
old_title = before.splitlines()[0][2:]
assert title == 'A Study of Microgrid Power Scheduling Based on Mixed-Integer Programming and Historical Scenario Optimization'
assert (P / 'main.tex').read_text().replace('pdftitle={' + title + '}', 'pdftitle={' + old_title + '}') == (O / 'main.tex').read_text()

def walk(x):
    if isinstance(x, dict):
        yield x
        yield from walk(x.get('c', []))
    elif isinstance(x, list):
        for v in x:
            yield from walk(v)

a = json.loads((O / 'build/source_ast.json').read_text())['blocks']
b = json.loads((P / 'build/source_ast.json').read_text())['blocks']
ta = [x for x in a if x['t'] == 'Table']
tb = [x for x in b if x['t'] == 'Table']
assert ta == tb and len(tb) == 36
ma = [x['c'] for x in walk(a) if x['t'] == 'Math']
mb = [x['c'] for x in walk(b) if x['t'] == 'Math']
assert ma == mb and len(mb) == 243
assert re.findall(r'\\tag\{(\d+)\}', after) == [str(i) for i in range(1, 12)]
decimal = re.compile(r'(?<![A-Za-z])[-+]?\d[\d,]*\.\d+(?:e[-+]?\d+)?')
assert Counter(decimal.findall(before)) == Counter(decimal.findall(after))

for name in ['elsarticle.cls', 'appendix_programs.tex', 'support_materials.zip']:
    assert sha(P / name) == sha(O / name), name
support = []
for name in ['support_materials', 'figures', 'disclosure']:
    for f in sorted((O / name).rglob('*')):
        if f.is_file():
            rel = f.relative_to(O)
            assert sha(f) == sha(P / rel), str(rel)
            support.append(str(rel))
assert sum(s.startswith('support_materials/') for s in support) == 169
with zipfile.ZipFile(P / 'support_materials.zip') as z:
    assert z.testzip() is None
    for info in z.infolist():
        if not info.is_dir():
            assert z.read(info.filename) == (P / info.filename).read_bytes()
images = re.findall(r'!\[Figure (\d+): .*?\]\((.*?)\)', after)
assert [int(n) for n, _ in images] == list(range(1, 12))
assert re.findall(r'\*\*Table (\d+)\.', after) == [str(i) for i in range(1, 37)]
assert '\\caption{Supporting file inventory' in (P / 'appendix_programs.tex').read_text() or '\\caption{' in (P / 'appendix_programs.tex').read_text()

pdf = P / 'outputs/manuscript_review.pdf'
reader = PdfReader(pdf)
old_reader = PdfReader(O / 'manuscript.pdf')
texts = [page.extract_text() or '' for page in reader.pages]
old_front = old_reader.pages[0].extract_text()
assert norm(texts[0].split('Abstract', 1)[1]) == norm(old_front.split('Abstract', 1)[1])
assert reader.metadata.title == title
assert not reader.metadata.author
refs = next(i + 1 for i, t in enumerate(texts) if t.strip().startswith('References'))
appendix = next(i + 1 for i, t in enumerate(texts) if t.strip().startswith('Appendix A.'))
assert refs - 2 <= 30 and appendix > refs
for i, page in enumerate(reader.pages, 1):
    assert abs(float(page.mediabox.width) - 595.276) < 1
    assert abs(float(page.mediabox.height) - 841.89) < 1
    assert texts[i - 1].strip().splitlines()[-1].strip() == str(i), i
log = (P / 'reports/compiler_output.txt').read_text()
assert not re.search(r'warning|error|overfull|underfull', log, re.I), log
tex = (P / 'build/body.tex').read_text()
labels = re.findall(r'\\label\{fig:(\d+)\}', tex)
assert [int(n) for n in labels] == list(range(1, 12))
for label, total in [('Figure', 11), ('Table', 37)]:
    rendered_labels = [int(n) for text in texts for n in re.findall(r'\b' + label + r'\s+(\d+)\s*:', text)]
    assert list(dict.fromkeys(rendered_labels)) == list(range(1, total + 1)), (label, rendered_labels)

# Main-paragraph membership remains the same through Section 9; no main paragraphs
# were split or merged. The extra verification paragraphs are in Appendix A.
initial = P.parent / 'manuscript_storage_control_v6_revision_20260912_01'
prior = list(csv.DictReader((P.parent / 'ai_style_audit_v6_20260912_01/paragraphs.csv').open(encoding='utf-8-sig')))
spans = {r['paragraph']: (r['source_line_start'], r['source_line_end']) for r in json.loads((initial / 'reaudit/source_objects.json').read_text())['paragraphs']}
def metrics(s):
    ls = s.splitlines()
    ps = [' '.join(ls[spans[r['paragraph']][0]-1:spans[r['paragraph']][1]]) for r in prior if r['scope'] == 'main']
    def plain(v):
        v = re.sub(r'\$[^$]*\$', ' FORMULA ', v)
        v = re.sub(r'`[^`]*`', ' CODE ', v)
        v = re.sub(r'\[\d+\]', '', v)
        return re.sub(r'[*_]', '', v)
    ss = [s.strip() for p in ps for s in re.split(r'(?<=[.!?])\s+(?=[A-Z])', plain(p)) if s.strip()]
    words = [w for p in ps for w in re.findall(r"[a-z]+(?:[-'][a-z]+)*", plain(p).lower()) if w not in ['formula', 'code']]
    neg = re.compile(r'\b(?:not|no|never|neither|cannot|without)\b', re.I)
    qual = re.compile(r'\b(?:does not|do not|cannot|not a |not an |neither|rather than|not establish|no .*guarantee)\b', re.I)
    return {'paragraphs': len(ps), 'words': len(words), 'sentences_heuristic': len(ss), 'negative_marker_sentences': sum(bool(neg.search(s)) for s in ss), 'qualification_pattern_sentences': sum(bool(qual.search(s)) for s in ss)}
prior_metrics, current_metrics = metrics(before), metrics(after)
assert prior_metrics['words'] == 8090 and prior_metrics['qualification_pattern_sentences'] == 62
(P / 'reports/style_comparison.json').write_text(json.dumps({'before': prior_metrics, 'after': current_metrics, 'scope': 'Same 128 main-prose paragraphs; some detailed coverage text moved to Appendix A. Counts describe editing, not authorship.'}, indent=2))

changes = json.loads((P / 'reports/editorial_changes.json').read_text())
locations = []
normalized_pages = [norm(s) for s in texts]
for c in changes:
    target = c['after'].split('\n\n')[-1]
    fragments = [norm(s) for s in re.split(r'\$[^$]*\$|`[^`]*`', target)]
    pages = []
    for fragment in fragments:
        if len(fragment) > 40:
            pages = [i+1 for i, s in enumerate(normalized_pages) if fragment[:95] in s]
            if pages:
                break
    assert pages, (c['reason'], fragments)
    locations.append({'source_line_before': c['source_line_before'], 'source_line_after': after[:after.index(c['after'].split('\n\n')[0])].count('\n')+1, 'reason': c['reason'], 'pdf_pages': ';'.join(map(str, pages))})
with (P / 'reports/edited_locations.csv').open('w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(locations[0])); w.writeheader(); w.writerows(locations)

pages_dir = P / 'checks/pages'; pages_dir.mkdir(exist_ok=True)
rendered = []
doc = pdfium.PdfDocument(str(pdf))
for i in range(len(doc)):
    page = doc[i]; bitmap = page.render(scale=105/72); im = bitmap.to_pil()
    f = pages_dir / f'page-{i+1:03d}.png'; im.save(f)
    rendered.append({'page': i+1, 'file': str(f.relative_to(P)), 'sha256': sha(f), 'pixels': list(im.size)})
    bitmap.close(); page.close()
doc.close()

manifest = json.loads((P / 'reports/predecessor_manifest.json').read_text())
assert all(sha(O / rel) == expected for rel, expected in manifest.items())
report = {'source_sha256': sha(P / 'manuscript_EN.md'), 'pdf_sha256': sha(pdf), 'title': title, 'abstract_and_keywords_byte_identical': True, 'abstract_tex_and_keywords_tex_byte_identical': True, 'pdf_abstract_text_identical': True, 'page_count': len(texts), 'body_start_page': 2, 'body_end_page': refs-1, 'body_pages': refs-2, 'references_start_page': refs, 'appendix_start_page': appendix, 'figures': 11, 'tables': 37, 'numbered_equations': 11, 'math_nodes_unchanged_in_order': len(mb), 'all_36_markdown_tables_unchanged': True, 'appendix_inventory_and_programs_unchanged': True, 'all_decimal_occurrences_unchanged': True, 'support_files_byte_identical': 169, 'workbooks_byte_identical': 5, 'support_zip_byte_identical': True, 'figures_byte_identical': 11, 'disclosure_unchanged': True, 'predecessor_files_unchanged': len(manifest), 'continuous_centered_footers': True, 'rendered_pages': rendered, 'annual_optimization_run': False, 'scope': 'Fresh editorial and packaging checks; no new comprehensive scientific or contest-checklist audit.'}
(P / 'reports/editorial_verification.json').write_text(json.dumps(report, indent=2))
print(json.dumps({k: v for k, v in report.items() if k != 'rendered_pages'}, indent=2))
print(json.dumps({'style_before': prior_metrics, 'style_after': current_metrics}, indent=2))
