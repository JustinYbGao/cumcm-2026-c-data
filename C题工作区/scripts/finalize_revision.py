"""Record final review-artifact lineage and create a compact review handoff ZIP."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

WORK = Path(__file__).resolve().parents[1]
REPORT = WORK / 'reports/revision_v1'


def main():
    validation = json.loads((REPORT/'export_validation.json').read_text())
    if validation['status'] != 'pass' or validation['error_count']:
        raise RuntimeError('Refuse to freeze a revision with failed workbook validation')
    paper = WORK/'papers/Problem_Restatement_EN.md'
    text = paper.read_text()
    substitutions = {
        'while strengthened source-price rebilling validation and assumption approval remain pending.':
            'including independent rebilling from exported purchases and source prices; adoption of the working assumptions remains pending.',
        'strengthened source-price rebilling validation and assumption approval remain pending.':
            'independent rebilling from exported purchases and source prices has also passed, while adoption of the working assumptions remains pending.',
        'then complete strengthened source-price rebilling validation for the five populated review workbooks generated from the versioned ledgers; their independent read-back checks have passed.':
            'then regenerate any affected outputs if the adopted conventions differ. The five populated review workbooks have passed independent read-back and source-price rebilling validation.',
        '- Complete strengthened source-price rebilling validation for the five populated review `.xlsx` exports; generation and independent read-back checks have passed, and the required-date tables and manuscript numbering are complete.':
            '- Retain the completed workbook read-back, source-price rebilling, required-date tables and numbering checks with the exported-file hashes; rerun affected checks after any later change.',
        '2. Complete strengthened source-price rebilling validation for the populated review workbooks and freeze their reconciliation with the completed required-date tables.':
            '2. Preserve the verified workbook and required-date-table reconciliation; regenerate it if a working assumption or result changes.',
        'they remain internal outputs pending strengthened source-price rebilling validation and approval of the timestamp, efficiency, power-boundary, terminal, price-information, and settlement assumptions.':
            'independent source-price rebilling has also passed. They remain internal outputs pending adoption of the timestamp, efficiency, power-boundary, terminal, price-information, and settlement assumptions.',
    }
    for old, new in substitutions.items():
        text = text.replace(old, new)
    # Put bibliographic records after the disclosure, keeping citation identifiers unchanged.
    if '### Verified References\n' in text:
        begin = text.index('### Verified References\n')
        end = text.index('## Items Requiring Confirmation', begin)
        references = text[begin:end].replace('### Verified References', '# 10 References', 1).strip()
        text = text[:begin] + text[end:]
        text += '\n\n# 9 AI Tool Usage Declaration — Working Draft\n\n'
        text += ('This team used AI tools for model implementation and discussion, code generation and debugging, '
                 'verification design and result analysis, figure generation, reference checks, and manuscript drafting. '
                 'The team\'s specific manual-review and verification records remain to be supplied. '
                 'This disclosure is a working draft and must not be submitted with incomplete human-review records. '
                 'The supporting [AI-use working record](revision_v1/AI工具使用详情_工作稿.md) identifies known uses and missing records.\n\n')
        text += references + '\n'
    paper.write_text(text)
    assert 'pending strengthened source-price rebilling' not in text
    assert 'Complete strengthened source-price rebilling' not in text
    report = REPORT/'paper_report.md'
    report_text = report.read_text()
    if '## Final delivery status' not in report_text:
        report.write_text(report_text + '\n## Final delivery status\n\nThe strengthened XLSX audit passed: 1,718,486 checks, 891,622 numeric comparisons, zero errors. Pending rebilling phrases were updated to completed. The five verified bibliographic records were moved after a plainly marked AI declaration working draft; citation identifiers are unchanged. Human-review records and final PDF remain pending. The current Markdown and file hashes, rather than the one-time migration script alone, identify the final edited artifact.\n')
    # Freeze the reviewed artifact set, not environment symlinks/caches or old frozen packages.
    files = [WORK/'FRIEND_REVIEW_GUIDE.md', paper,
             WORK/'papers/论文问题与待确认事项.md', WORK/'papers/Paper_Review_Findings.md']
    for folder in ['outputs/revision_v1','papers/revision_v1','results/revision_v1', 'reports/revision_v1']:
        files += [p for p in (WORK/folder).rglob('*') if p.is_file()
                  and p.name not in ('revision_manifest.json','package_validation.json')
                  and 'workbook_previews' not in p.parts and not p.name.endswith('.diff')]
    files += [WORK/'scripts'/n for n in ['prepare_result_workbooks.py','validate_result_workbooks.py','audit_power_boundary.py','revise_paper.py','finalize_revision.py']]
    files += [WORK/'scripts/revision_v1/build_result_workbooks.mjs']
    files += list((WORK/'configs').glob('*.json'))
    records = {str(p.relative_to(WORK)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
               for p in sorted(set(files))}
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=WORK,text=True).strip()
    manifest = {'status':'internal_review_not_official_submission','base_commit':head,
                'revision_state':'working_tree_uncommitted; file hashes identify this repair',
                'excluded':'Historical full ledgers/data and plotting lineage remain in repository/frozen packages; runtime dependencies and previews omitted. This handoff ZIP is not a standalone formal support submission.',
                'files':records}
    manifest_path = REPORT/'revision_manifest.json'
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    archive = WORK/'deliverables/revision_v1_review.zip'
    archive.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for rel in records:
            z.write(WORK/rel, rel)
        z.write(manifest_path,str(manifest_path.relative_to(WORK)))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(records)+1
        for rel, detail in records.items():
            assert hashlib.sha256(z.read(rel)).hexdigest() == detail['sha256']
    result = {'passed':True,'members':len(records)+1,'bytes':archive.stat().st_size,
              'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
              'under_20_MB':archive.stat().st_size < 20000000,
              'purpose':'Compact internal review handoff; not formal submission and requires existing repository ledgers to regenerate XLSX.'}
    (REPORT/'package_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
