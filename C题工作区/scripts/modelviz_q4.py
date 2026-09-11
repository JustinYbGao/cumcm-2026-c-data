"""Q4 ModelViz services using real monthly bills and prescribed-day price forecasts."""
import argparse
import json
import os
import shutil
import pandas as pd
import modelviz_revision as engine

WORK=engine.WORK;ROOT=WORK/'reports/figures/modelviz_q4_v1_en';engine.ROOT=ROOT
os.environ['TMPDIR']=str(WORK/'data/interim/q4')
os.environ['MPLCONFIGDIR']=str(WORK/'data/interim/q4/matplotlib')
NAMES=['q4_monthly','q4_prices']


def prepare():
    assert json.loads((WORK/'results/q4/run_status.json').read_text())['completed']
    ROOT.mkdir(parents=True,exist_ok=True)
    sources=[];monthly=None
    for policy in ['q42_fixed','q42_ols','q43_all_A_fixed','q43_all_A_ols']:
        source=WORK/f'results/q4/{policy}/daily.csv';sources.append(source)
        f=pd.read_csv(source,float_precision='round_trip')
        part=f.assign(month=f.date.str[:7]).groupby('month').total_cost_yuan.sum().rename(policy+'_cost_yuan')
        monthly=part.to_frame() if monthly is None else monthly.join(part)
    monthly=monthly.reset_index()
    monthly['q42_saving_yuan']=monthly.q42_fixed_cost_yuan-monthly.q42_ols_cost_yuan
    monthly['q43_saving_yuan']=monthly.q43_all_A_fixed_cost_yuan-monthly.q43_all_A_ols_cost_yuan
    source=WORK/'results/q4/q43_all_A_ols/ledger.csv'
    f=pd.read_csv(source,float_precision='round_trip')
    f=f.loc[f.date.isin(['2025-03-20','2025-06-21','2025-09-23','2025-12-21'])].copy()
    original=WORK/'results/q4/price_forecasts.csv';p=pd.read_csv(original,float_precision='round_trip')
    p['issue_time']=pd.to_datetime(p.issue_time);p['interval_start']=pd.to_datetime(p.interval_start)
    p=p.loc[p.issue_time.dt.hour==0].set_index('interval_start')
    f['price_midnight_yuan_per_kwh']=p.loc[pd.to_datetime(f.interval_start)].price_forecast_yuan_per_kwh.to_numpy()
    datasets={'q4_monthly':monthly,'q4_prices':f}
    all_sources=sources+[source,original]
    engine.save(ROOT/'source_hashes.json',{str(p.relative_to(WORK)):engine.sha(p) for p in all_sources})
    for name in NAMES:
        task=ROOT/name;ws=task/'workspace';ws.mkdir(parents=True,exist_ok=True);(task/'docs').mkdir(exist_ok=True)
        shutil.copy2(engine.SKILL/'docs/package_name_mapping.yaml',task/'docs/package_name_mapping.yaml')
        datasets[name].to_csv(task/'data.csv',index=False)
        relevant=sources if name=='q4_monthly' else [source,original]
        engine.save(ws/'data_lineage.json',{'source_files':{str(p.relative_to(WORK)):engine.sha(p) for p in relevant},
            'plot_data_sha256':engine.sha(task/'data.csv'),'rows':len(datasets[name]),
            'transformation':'Sum actual bills by original calendar month; derive fixed-policy minus OLS-policy cost' if name=='q4_monthly' else 'Select four prescribed dates; join midnight forecast by original interval-start key',
            'units':'CNY and CNY/kWh; only display-unit conversion','time_assumption':'Internal interval-end mapping, no shifting'})
        requirement={'original_request':'使用modelviz-skill做图；不要中文标注，全部英文。',
            'goal':'比较问题4月度费用时间序列及价格预测收益' if name=='q4_monthly' else '比较四个指定日实际价格与因果价格预测时间序列及误差',
            'functional_keywords':['趋势','比较','复合时间序列','多指标时间序列'],
            'chart_types':[],'style_keywords':['English labels','serif typography'],'use_case':'论文正文',
            'negative_requirements':['No Chinese text in figures'],'explicit_template':False,'is_ambiguous':False,'clarification_question':''}
        engine.parse_and_save_requirement(requirement['original_request'],engine.response(requirement),
            vocabulary_path=engine.SKILL/'docs/requirement_vocabulary.yaml',output_path=ws/'user_requirement.json')
        engine.checked(engine.run_candidate_matching_pipeline(requirement_path=str(ws/'user_requirement.json'),
            catalog_path=str(engine.SKILL/'docs/template_catalog.yaml'),output_path=str(ws/'candidate_templates.json'),top_k=8,min_score=.1))
        engine.save(ws/'response_provenance.json',{'author':'Codex current assistant',
            'method':'Assistant-authored structured outputs via RunnableLambda; no external model API',
            'visual_check':'Actual PNG inspection required before approval'})
        print(name,(ws/'candidate_templates.json').read_text())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','adapt','quality']);args=p.parse_args()
    if args.stage=='prepare':prepare()
    else:
        for name in NAMES:getattr(engine,args.stage)(name)
