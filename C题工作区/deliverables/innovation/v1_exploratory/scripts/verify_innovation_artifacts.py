"""Verify innovation tables, paper/figure lineage, and prior frozen packages."""
import hashlib
import json
from pathlib import Path
import re
import sys
import numpy as np
import pandas as pd
from PIL import Image

WORK=Path(__file__).resolve().parents[1];OUT=WORK/'results/innovation'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def read(p):return pd.read_csv(p,float_precision='round_trip')
def main():
    checks={}
    def test(k,v):checks[k]=bool(v)
    def close(k,a,b):test(k,np.allclose(a,b,rtol=0,atol=1e-6))
    for name in ['validation','independent_lp_audit']:test(name,load(OUT/f'{name}.json')['passed'])
    for log,count in [('base_tests',25),('innovation_tests',9)]:
        text=(WORK/f'logs/innovation/{log}.log').read_text();test(log,f'Ran {count} tests' in text and text.endswith('OK\n'))
    for source in [OUT/'input_code_hashes.json',OUT/'report_sources.json']:
        for name,value in load(source).items():test(source.stem+'_'+name,sha(WORK/name)==value)
    for phase in ['calibration','evaluation']:
        for folder in sorted((OUT/phase).iterdir()):
            if not folder.is_dir():continue
            key=phase+'_'+folder.name;f=read(folder/'ledger.csv');dates=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
            rep=f[f.date.isin(dates)];t1=read(folder/'table1_representative.csv');wanted=rep[rep.slot_id.isin([61,73,85,97,109,121])]
            test(key+'_table1_keys',t1.date.tolist()==wanted.date.tolist() and pd.to_datetime(t1.interval_start).tolist()==pd.to_datetime(wanted.interval_start).tolist())
            for col in ['grid_original_kwh','grid_effective_kwh']:close(key+'_table1_'+col,t1[col],wanted[col])
            t2=read(folder/'table2_representative.csv');block=rep.assign(block_start_minute=(rep.slot_id-1)//24*240).groupby(['date','block_start_minute'])[['charge_actual_kwh','discharge_actual_kwh']].sum().reset_index()
            test(key+'_table2_keys',t2.date.tolist()==block.date.tolist() and t2.block_start_minute.tolist()==block.block_start_minute.tolist())
            for col in ['charge_actual_kwh','discharge_actual_kwh']:close(key+'_table2_'+col,t2[col],block[col])
            events=read(folder/'emergency_events.csv');t3=read(folder/'table3_representative.csv');test(key+'_table3_subset',t3.equals(events[events.date.isin(dates)].reset_index(drop=True)))
            expanded=[];index=f.set_index('interval_start');index.index=pd.to_datetime(index.index)
            for r in events.itertuples():
                times=pd.date_range(r.interval_start,r.interval_end,freq='10min',inclusive='left');expanded+=times.tolist()
                test(key+'_event_count_'+str(r.Index),len(times)==r.intervals)
                close(key+'_event_energy_'+str(r.Index),index.loc[times].emergency_kwh.sum(),r.emergency_kwh)
            test(key+'_events_exact',expanded==pd.to_datetime(f.loc[f.emergency_kwh>1e-6,'interval_start']).tolist())
    root=WORK/'reports/figures/modelviz_innovation_v1_en'
    for name,value in load(root/'source_hashes.json').items():test('plot_source_'+name,sha(WORK/name)==value)
    for name in ['innovation_monthly','innovation_risk']:
        task=root/name;ws=task/'workspace';data=read(task/'data.csv');lineage=load(ws/'data_lineage.json')
        test(name+'_data_hash',sha(task/'data.csv')==lineage['plot_data_sha256'])
        for source,value in lineage['source_files'].items():test(name+'_'+source,sha(WORK/source)==value)
        test(name+'_code',(ws/'adapted_plot.py').read_bytes()==(WORK/f'scripts/modelviz/{name}.py').read_bytes())
        for label,p in [('SVG',task/'outputs/chart.svg'),('code',ws/'adapted_plot.py')]:test(name+'_English_'+label,re.search(r'[\u3400-\u9fff]',p.read_text()) is None)
        visual=load(ws/'assistant_visual_assessment.json');test(name+'_viewed_png',sha(task/'outputs/chart.png')==visual['inspected_png_sha256']);test(name+'_viewed_code',sha(ws/'adapted_plot.py')==visual['inspected_script_sha256'])
        test(name+'_quality',load(ws/'final_quality_report.json')['passed'])
        with Image.open(task/'outputs/chart.png') as im:test(name+'_300dpi',all(abs(v-300)<.1 for v in im.info['dpi']) and im.width>=3000 and im.height>=1800)
        provenance=load(ws/'template_provenance.json');test(name+'_template_preserved',sha(Path(provenance['source_script']))==provenance['source_script_sha256'])
        if name.endswith('monthly'):
            for policy in data.columns[1:]:
                daily=read(OUT/'evaluation'/policy/'daily.csv');monthly=daily.assign(month=daily.date.str[:7]).groupby('month').total_cost_yuan.sum()
                close(name+'_'+policy,data[policy],monthly);test(name+'_months_'+policy,data.month.tolist()==monthly.index.tolist())
        else:
            r=[m for m in load(OUT/'risk_models.json') if m['issue_time']>='2025-04-01' and m['predicted_s_kwh'] is not None]
            test(name+'_dates',data.date.tolist()==[m['issue_time'][:10] for m in r]);close(name+'_actual',data.observed_prefix_kwh,[m['realized_s_kwh'] for m in r]);close(name+'_forecast',data.forecast_prefix_kwh,[m['predicted_s_kwh'] for m in r])
    for file in ['papers/innovation_draft.md','reports/innovation/model_and_results.md']:
        p=WORK/file;text=p.read_text();test(file+'_internal','内部' in text and '正式' in text and '探索性' in text)
        for link in re.findall(r'!\[[^\]]*\]\(([^)]+)\)',text):test(file+'_image_'+link,p.parent.joinpath(link).is_file())
        for row in read(OUT/'comparison.csv').itertuples():test(file+'_cost_'+row.policy,f'{row.total_cost_yuan:,.2f}' in text)
    for name,value in load(WORK/'reports/figures/modelviz_v3_en/source_hashes_before.json').items():test('preserved_'+name,sha(WORK/name)==value)
    for group in ['q2/v1_internal_baseline','q3/v1_internal_mpc','q4/v1_internal_variable_price']:
        p=WORK/'deliverables'/group;test('frozen_'+group,all(sha(p/name)==value for name,value in load(p/'manifest.json').items()))
    result={'passed':all(checks.values()),'check_count':len(checks),'failed':[k for k,v in checks.items() if not v],'checks':checks}
    (OUT/'artifact_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('Innovation artifact check',result['passed'],len(checks),result['failed'][:20])
    if not result['passed']:sys.exit(1)
if __name__=='__main__':main()
