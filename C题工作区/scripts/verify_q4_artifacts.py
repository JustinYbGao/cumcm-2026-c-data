"""Check Q4 source/figure/report traceability and preservation of Q1-Q3."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import numpy as np
import pandas as pd
from PIL import Image

WORK=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    checks={}
    def test(key,value):checks[key]=bool(value)
    root=WORK/'reports/figures/modelviz_q4_v1_en';out=WORK/'results/q4'
    for name in ['validation','independent_lp_audit']:
        test(name,json.loads((out/f'{name}.json').read_text())['passed'])
    log=(WORK/'logs/q4/all_model_tests.log').read_text()
    test('25_model_tests','Ran 25 tests' in log and log.endswith('OK\n'))
    for source in [out/'input_code_hashes.json',out/'report_sources.json',root/'source_hashes.json']:
        for name,value in json.loads(source.read_text()).items():test(source.stem+'_'+name,digest(WORK/name)==value)
    prior=json.loads((WORK/'reports/figures/modelviz_v3_en/source_hashes_before.json').read_text())
    for name,value in prior.items():test('prior_source_'+name,digest(WORK/name)==value)
    for group in ['q2/v1_internal_baseline','q3/v1_internal_mpc']:
        folder=WORK/'deliverables'/group;manifest=json.loads((folder/'manifest.json').read_text())
        test('frozen_'+group,all(digest(folder/name)==value for name,value in manifest.items()))
    protected=['data/processed','results/q1','results/q2','results/q3','results/q3_feedback_control',
        'deliverables/q1','deliverables/q2','deliverables/q3','scripts/run_q2.py','scripts/run_q3.py','scripts/solve_q1.py']
    diff=subprocess.run(['git','diff','--name-only','HEAD','--',*protected],cwd=WORK,capture_output=True,text=True,check=True)
    test('prior_tracked_unchanged',not diff.stdout.strip())
    for name in ['q4_monthly','q4_prices']:
        task=root/name;ws=task/'workspace';lineage=json.loads((ws/'data_lineage.json').read_text())
        test(name+'_input_hash',digest(task/'data.csv')==lineage['plot_data_sha256'])
        for source,value in lineage['source_files'].items():test(name+'_source_'+source,digest(WORK/source)==value)
        test(name+'_code_copy',(ws/'adapted_plot.py').read_bytes()==(WORK/'scripts/modelviz'/f'{name}.py').read_bytes())
        for suffix,path in [('code',ws/'adapted_plot.py'),('SVG',task/'outputs/chart.svg')]:
            test(name+'_English_'+suffix,re.search(r'[\u3400-\u9fff]',path.read_text()) is None)
        test(name+'_quality',json.loads((ws/'final_quality_report.json').read_text())['passed'])
        visual=json.loads((ws/'assistant_visual_assessment.json').read_text())
        test(name+'_viewed_png',digest(task/'outputs/chart.png')==visual['inspected_png_sha256'])
        test(name+'_viewed_code',digest(ws/'adapted_plot.py')==visual['inspected_script_sha256'])
        with Image.open(task/'outputs/chart.png') as im:
            test(name+'_resolution',im.width>=3000 and im.height>=2000)
            test(name+'_300dpi',all(abs(v-300)<.1 for v in im.info['dpi']))
        data=pd.read_csv(task/'data.csv',float_precision='round_trip')
        if name=='q4_monthly':
            for policy in ['q42_fixed','q42_ols','q43_all_A_fixed','q43_all_A_ols']:
                daily=pd.read_csv(out/policy/'daily.csv',float_precision='round_trip')
                monthly=daily.assign(month=daily.date.str[:7]).groupby('month').total_cost_yuan.sum()
                test(policy+'_monthly_keys',data.month.tolist()==monthly.index.tolist())
                test(policy+'_monthly_values',np.allclose(data[policy+'_cost_yuan'],monthly,rtol=0,atol=1e-6))
            for branch in ['q42','q43']:
                a=branch+('_all_A' if branch=='q43' else '')
                test(branch+'_savings',np.allclose(data[branch+'_saving_yuan'],data[a+'_fixed_cost_yuan']-data[a+'_ols_cost_yuan'],rtol=0,atol=1e-6))
        else:
            ledger=pd.read_csv(out/'q43_all_A_ols/ledger.csv',float_precision='round_trip')
            expected=ledger.loc[ledger.date.isin(['2025-03-20','2025-06-21','2025-09-23','2025-12-21'])].reset_index(drop=True)
            test('prices_source_copy',data[expected.columns].equals(expected))
            p=pd.read_csv(out/'price_forecasts.csv',float_precision='round_trip')
            p['issue_time']=pd.to_datetime(p.issue_time);p['interval_start']=pd.to_datetime(p.interval_start)
            p=p[p.issue_time.dt.hour==0].set_index('interval_start')
            test('prices_midnight_values',np.allclose(data.price_midnight_yuan_per_kwh,p.loc[pd.to_datetime(data.interval_start)].price_forecast_yuan_per_kwh,rtol=0,atol=1e-12))
        provenance=json.loads((ws/'template_provenance.json').read_text())
        test(name+'_template_preserved',digest(Path(provenance['source_script']))==provenance['source_script_sha256'])
    for file in ['papers/q4_draft.md','reports/q4_model_and_results.md','reports/q4_representative_tables.md']:
        text=(WORK/file).read_text();test(file+'_disclosure','内部' in text and '正式' in text)
        for link in re.findall(r'!\[[^\]]*\]\(([^)]+)\)',text):test(file+'_image_'+link,(WORK/file).parent.joinpath(link).is_file())
    text=(WORK/'papers/q4_draft.md').read_text()
    for row in pd.read_csv(out/'comparison.csv').itertuples():test('paper_cost_'+row.policy,f'{row.total_cost_yuan:,.2f}' in text)
    result={'passed':all(checks.values()),'check_count':len(checks),'checks':checks,'preserved_source_file_count':len(prior)}
    (out/'artifact_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('Q4 artifact verification',result['passed'],len(checks),'checks')
    for key,ok in checks.items():
        if not ok:print('FAIL',key)
    if not result['passed']:sys.exit(1)

if __name__=='__main__':main()
