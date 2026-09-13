"""Bind completed visual observations and preservation checks to final delivery files."""
from pathlib import Path
import csv
import difflib
import hashlib
import json
import shutil

P = Path(__file__).resolve().parents[1]
sha = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()
read = lambda n: json.loads((P / n).read_text())
def write(n, value):
    (P / n).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

context = read('reports/revision_context.json')
O = Path(context['predecessor'])
check = read('reports/editorial_verification.json')
portable = read('reports/portable_compile.json')
notes = read('reports/actual_visual_notes.json')
assert set(notes) == {str(i) for i in range(1, 77)}
assert sha(P / 'manuscript_EN.md') == check['source_sha256']
assert sha(P / 'outputs/manuscript_review.pdf') == check['pdf_sha256']
assert portable['extracted_compile_pdf_sha256'] == check['pdf_sha256']
assert sha(P / 'outputs/latex_source.zip') == portable['archive_sha256']
assert all(sha(O / rel) == h for rel, h in read('reports/predecessor_manifest.json').items())

rows = []
for render in check['rendered_pages']:
    page = render['page']
    path = P / render['file']
    assert sha(path) == render['sha256']
    method = 'Full-page final render viewed after final compilation'
    if page <= 22:
        earlier = P / 'build_history/visual_attempt_02/pages' / path.name
        assert sha(earlier) == sha(path)
        method = 'Full-page render viewed in visual attempt 02; final PNG is byte-identical'
    rows.append({'page': page, 'pdf_sha256': check['pdf_sha256'], 'image': render['file'],
                 'image_sha256': render['sha256'], 'pixels': 'x'.join(map(str, render['pixels'])),
                 'method': method, 'observation': notes[str(page)],
                 'status': 'No unresolved visual defect observed at the reviewed render settings'})
with (P / 'page_review.csv').open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)

abstract = (P / 'manuscript_EN.md').read_text().split('## Abstract\n', 1)[1].split('# 1 Problem')[0]
context['predecessor_front_matter_prefix_sha256'] = context.pop('abstract_prefix_sha256', context.get('predecessor_front_matter_prefix_sha256'))
context['abstract_and_keywords_sha256'] = hashlib.sha256(abstract.encode()).hexdigest()
context['scope'] = 'Authorized English title change and selected body-prose refinement; abstract, keywords, scientific content and support files are frozen. Coverage details move to Appendix A. No model or annual experiment is run.'
context['title'] = check['title']
write('reports/revision_context.json', context)

diff = []
for name in ['main.tex', 'code/convert_manuscript.py']:
    diff.extend(difflib.unified_diff((O / name).read_text().splitlines(True), (P / name).read_text().splitlines(True), fromfile='revision_02/' + name, tofile='revision_03/' + name))
(P / 'reports/typesetting_changes.diff').write_text(''.join(diff))

locations = list(csv.DictReader((P / 'reports/edited_locations.csv').open(encoding='utf-8-sig')))
assert next(r for r in locations if r['source_line_before'] == '535')['pdf_pages'] == '21'
issues = [{'issue_id': f'R03-{i:02d}', 'request_or_issue': r['reason'],
           'actual_change': 'See the exact original and revised text in reports/editorial_changes.json',
           'location': 'manuscript_EN.md:' + r['source_line_after'] + '; PDF page ' + r['pdf_pages'],
           'evidence': 'reports/manuscript_changes.diff; reports/editorial_verification.json; page_review.csv',
           'status': 'Closed within editorial scope'} for i, r in enumerate(locations, 1)]
for issue_id, issue, action, page in [
    ('R03-LAYOUT-01', 'Table 9 single-row spill', 'Keep the five-row Table 9 in one table block', '20'),
    ('R03-LAYOUT-02', 'Figure 11 interrupts the resampling paragraph', 'Protect the resampling paragraph against the float boundary', '24')]:
    issues.append({'issue_id': issue_id, 'request_or_issue': issue, 'actual_change': action,
                   'location': 'code/convert_manuscript.py; PDF page ' + page,
                   'evidence': 'reports/typesetting_changes.diff; page_review.csv; build_history/',
                   'status': 'Closed within editorial scope'})
with (P / 'issue_resolution.csv').open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=list(issues[0])); writer.writeheader(); writer.writerows(issues)

quality1 = {'language': 76, 'structure': 84, 'specificity': 94, 'validation': 84, 'sources': 92}
quality2 = {'model_appropriateness': 94, 'complexity_benefit': 64, 'hollow_sophistication': 88, 'three_questions': 80}
total1 = 0.6 * quality1['language'] + 0.4 * sum(quality1[k] for k in ['structure', 'specificity', 'validation', 'sources']) / 4
total2 = sum(quality2.values()) / 4
write('reports/style_score_recheck.json', {
    'method': 'Same corrected two-layer offline rubric as the preceding focused review; higher quality is better and higher risk is worse. Scores are agent editorial judgments, not detector measurements.',
    'scope': 'Edited prose and structure only; no new scientific or reference audit and no credit for the unchanged abstract.',
    'source_sha256': check['source_sha256'], 'pdf_sha256': check['pdf_sha256'],
    'before_risk': 20.05, 'layer1_quality': quality1, 'layer2_quality': quality2,
    'layer1_total': total1, 'layer2_total': total2, 'after_risk': 100 - (total1 + total2) / 2,
    'display_risk': 'Approximately 19/100; a modest subjective change from approximately 20/100',
    'basis': ['Fewer repeated defensive qualifications; adverse evidence remains explicit.', 'Verification counts are concentrated in Appendix A; prose links methods, findings and limitations directly.', 'All scientific assessment dimensions retain their previous values.'],
    'limitations': ['Some main-text word reduction is relocation, not removal from the document.', 'A five-point change in language judgment changes the combined risk by 1.5 points; the apparent improvement is not a calibrated effect.', 'No external AI detector was run; this score cannot identify authorship or guarantee a detector outcome.']})

extra = P / 'checks/pages/page-036-poppler144.png'
write('coverage.json', {
    'scope': 'Fresh editorial, preservation, PDF visual and typesetting-package checks',
    'source_sha256': check['source_sha256'], 'pdf_sha256': check['pdf_sha256'],
    'pages_reviewed': list(range(1, 77)), 'body_pages': list(range(2, 26)),
    'reference_pages': [26], 'appendix_pages': list(range(27, 77)),
    'visual_record': 'page_review.csv', 'extra_page_36_render': {'file': str(extra.relative_to(P)), 'sha256': sha(extra), 'dpi': 144, 'renderer': 'Poppler'},
    'figures_checked': list(range(1, 12)), 'tables_checked': list(range(1, 38)),
    'numbered_equations_checked': list(range(1, 12)), 'math_nodes_identical': 243,
    'workbooks_byte_identical': 5, 'support_files_byte_identical': 169,
    'abstract_and_keywords_byte_identical': True, 'model_or_annual_optimization_executed': False,
    'portable_latex_files_extracted_and_compiled': 39,
    'not_repeated': ['Complete 247-item contest checklist', 'Full reference-source audit', 'Scientific optimization or annual replay', 'Support-program smoke tests', 'Full support anonymity audit'],
    'unresolved_external_matters': ['Submission route and portal-specific filenames', 'Any outstanding evidence of actual team review', 'Unperformed sensitivity or out-of-sample experiments'],
    'limit': 'Preservation of a frozen scientific package is not a new proof of all scientific conclusions or contest compliance.'})

alias = P / 'manuscript.pdf'
if alias.exists():
    assert sha(alias) == check['pdf_sha256']
else:
    shutil.copy2(P / 'outputs/manuscript_review.pdf', alias)
artifacts = {}
for name in ['manuscript.pdf', 'manuscript_EN.md', 'support_materials.zip', 'outputs/latex_source.zip']:
    f = P / name
    artifacts[name] = {'path': str(f), 'sha256': sha(f), 'bytes': f.stat().st_size}
write('reports/final_delivery.json', {'title': check['title'], 'artifacts': artifacts,
      'page_count': 76, 'body_pages': 24, 'abstract_and_keywords_unchanged': True,
      'models_results_and_workbooks_unchanged': True, 'visual_pages_recorded': len(rows),
      'support_zip_byte_identical': sha(P / 'support_materials.zip') == sha(O / 'support_materials.zip'),
      'portable_compile_pdf_byte_identical': True, 'scope': context['scope']})
print(json.dumps(read('reports/final_delivery.json'), indent=2, ensure_ascii=False))
