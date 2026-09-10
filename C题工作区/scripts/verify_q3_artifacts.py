"""Verify report/figure lineage and preservation after the numerical audits."""
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd
from PIL import Image

WORK=Path(__file__).resolve().parents[1]


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    checks={}
    def test(key,value):checks[key]=bool(value)
    root=WORK/'reports/figures/modelviz_q3_v1_en'
    source_before=json.loads((WORK/'reports/figures/modelviz_v3_en/source_hashes_before.json').read_text())
    for name,value in source_before.items():test('preserved_'+name,digest(WORK/name)==value)
    for group in ['q3','q3_feedback_control']:
        output=WORK/'results'/group
        test(group+'_audit',json.loads((output/'validation.json').read_text())['passed'])
        for name,value in json.loads((output/'input_code_hashes.json').read_text()).items():
            test(group+'_source_'+name,digest(WORK/name)==value)
    test('LP_audit',json.loads((WORK/'results/q3/independent_lp_audit.json').read_text())['passed'])
    test('model_tests',(WORK/'logs/q3/all_model_tests.log').read_text().endswith('OK\n'))
    for name,value in json.loads((WORK/'results/q3/report_sources.json').read_text()).items():test('report_source_'+name,digest(WORK/name)==value)
    for name,value in json.loads((root/'source_hashes.json').read_text()).items():test('figure_source_'+name,digest(WORK/name)==value)
    for name in ['q3_monthly','q3_execution']:
        task=root/name;ws=task/'workspace'
        lineage=json.loads((ws/'data_lineage.json').read_text())
        test(name+'_input_hash',digest(task/'data.csv')==lineage['plot_data_sha256'])
        for source,value in lineage['source_files'].items():test(name+'_source_'+source,digest(WORK/source)==value)
        test(name+'_code_copy',(ws/'adapted_plot.py').read_bytes()==(WORK/'scripts/modelviz'/f'{name}.py').read_bytes())
        test(name+'_English_code',re.search(r'[\u3400-\u9fff]',(ws/'adapted_plot.py').read_text()) is None)
        test(name+'_English_SVG',re.search(r'[\u3400-\u9fff]',(task/'outputs/chart.svg').read_text()) is None)
        quality=json.loads((ws/'final_quality_report.json').read_text())
        test(name+'_quality',quality['passed'])
        visual=json.loads((ws/'assistant_visual_assessment.json').read_text())
        test(name+'_viewed_png',digest(task/'outputs/chart.png')==visual['inspected_png_sha256'])
        test(name+'_viewed_script',digest(ws/'adapted_plot.py')==visual['inspected_script_sha256'])
        with Image.open(task/'outputs/chart.png') as im:
            test(name+'_resolution',im.width>=3000 and im.height>=2000)
            test(name+'_300dpi',all(abs(value-300)<.1 for value in im.info['dpi']))
        data=pd.read_csv(task/'data.csv',float_precision='round_trip')
        if name=='q3_monthly':
            for policy in ['no_update','all_A','all_B']:
                daily=pd.read_csv(WORK/f'results/q3/{policy}/daily.csv',float_precision='round_trip')
                monthly=daily.assign(month=daily.date.str[:7]).groupby('month').total_cost_yuan.sum()
                test(name+'_'+policy+'_values',np.allclose(data[policy+'_total_cost_yuan'],monthly,rtol=0,atol=1e-6))
            facts=json.loads((ws/'plot_facts.json').read_text())
            for policy,cost in facts['annual_costs_yuan'].items():
                expected=json.loads((WORK/f'results/q3/{policy}/summary.json').read_text())['total_cost_yuan']
                test(name+'_'+policy+'_annotation',abs(cost-expected)<=1e-5)
        else:
            ledger=pd.read_csv(WORK/'results/q3/all_A/ledger.csv',float_precision='round_trip')
            expected=ledger.loc[ledger.date.isin(['2025-03-20','2025-06-21','2025-09-23','2025-12-21'])].reset_index(drop=True)
            test(name+'_copy_equal',data.equals(expected))
        provenance=json.loads((ws/'template_provenance.json').read_text())
        test(name+'_template_unchanged',digest(Path(provenance['source_script']))==provenance['source_script_sha256'])
    for file in ['papers/q3_draft.md','reports/q3_model_and_results.md','reports/q3_representative_tables.md']:
        text=(WORK/file).read_text()
        test(file+'_internal_disclosure','内部' in text and '正式' in text)
        for link in re.findall(r'!\[[^\]]*\]\(([^)]+)\)',text):test(file+'_image_'+link,(WORK/file).parent.joinpath(link).is_file())
    comparisons=pd.read_csv(WORK/'results/q3/comparison_with_feedback_control.csv')
    text=(WORK/'papers/q3_draft.md').read_text()
    for row in comparisons.itertuples():test('paper_cost_'+row.policy,f'{row.total_cost_yuan:,.2f}' in text)
    package=WORK/'deliverables/q2/v1_internal_baseline'
    manifest=json.loads((package/'manifest.json').read_text())
    test('Q2_package_manifest',all(digest(package/name)==value for name,value in manifest.items()))
    result={'passed':all(checks.values()),'check_count':len(checks),'checks':checks,
        'preserved_source_file_count':len(source_before),'q2_package_files':len(manifest)}
    (WORK/'results/q3/artifact_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('Artifact verification',result['passed'],len(checks),'checks; preserved',len(source_before),'original sources')
    for name,ok in checks.items():
        if not ok:print('FAIL',name)
    if not result['passed']:sys.exit(1)


if __name__=='__main__':main()
