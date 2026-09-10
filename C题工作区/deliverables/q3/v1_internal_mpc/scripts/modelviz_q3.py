"""Q3 ModelViz service orchestration; reuses the audited service adapter, not old outputs."""
import argparse
import os
from pathlib import Path
import shutil
import json

import modelviz_revision as engine
import pandas as pd

WORK=engine.WORK
ROOT=WORK/'reports/figures/modelviz_q3_v1_en'
engine.ROOT=ROOT
os.environ['TMPDIR']=str(WORK/'data/interim/q3')
os.environ['MPLCONFIGDIR']=str(WORK/'data/interim/q3/matplotlib')
NAMES=['q3_monthly','q3_execution']


def prepare():
    assert json.loads((WORK/'results/q3/run_status.json').read_text())['completed']
    ROOT.mkdir(parents=True,exist_ok=True)
    sources={}
    monthly=None
    for policy in ['no_update','all_A','all_B']:
        source=WORK/f'results/q3/{policy}/daily.csv'
        sources[policy]=source
        f=pd.read_csv(source,float_precision='round_trip')
        group=f.assign(month=f.date.str[:7]).groupby('month')[['total_cost_yuan','contract_cost_yuan','emergency_cost_yuan']].sum().add_prefix(policy+'_')
        monthly=group if monthly is None else monthly.join(group)
    monthly=monthly.reset_index()
    for policy in ['all_A','all_B']:monthly[policy+'_saving_yuan']=monthly.no_update_total_cost_yuan-monthly[policy+'_total_cost_yuan']
    source=WORK/'results/q3/all_A/ledger.csv'
    execution=pd.read_csv(source,float_precision='round_trip')
    execution=execution.loc[execution.date.isin(['2025-03-20','2025-06-21','2025-09-23','2025-12-21'])]
    datasets={'q3_monthly':monthly,'q3_execution':execution}
    all_sources=[*sources.values(),source]
    engine.save(ROOT/'source_hashes.json',{str(p.relative_to(WORK)):engine.sha(p) for p in all_sources})
    for name in NAMES:
        task=ROOT/name;ws=task/'workspace';ws.mkdir(parents=True,exist_ok=True)
        (task/'docs').mkdir(exist_ok=True)
        shutil.copy2(engine.SKILL/'docs/package_name_mapping.yaml',task/'docs/package_name_mapping.yaml')
        datasets[name].to_csv(task/'data.csv',index=False)
        relevant=list(sources.values()) if name=='q3_monthly' else [source]
        engine.save(ws/'data_lineage.json',{'source_files':{str(p.relative_to(WORK)):engine.sha(p) for p in relevant},
            'plot_data_sha256':engine.sha(task/'data.csv'),'rows':len(datasets[name]),
            'transformation':'Sum actual daily bills by original calendar month; derive no-update minus update cost' if name=='q3_monthly' else 'Select the four prescribed dates, keep interval boundaries and values unchanged',
            'units':'CNY to million CNY; kWh to MWh only for display','time_assumption':'Internal interval-end labels, no shift'})
        requirement={'original_request':'使用modelviz-skill做图；不要中文标注，全部英文。',
            'goal':'比较问题3月度费用时间序列与更新节约值' if name=='q3_monthly' else '展示问题3四个指定日购电调整、储能容量功率时间序列与紧急量',
            'functional_keywords':['趋势','比较','复合时间序列','多指标时间序列'] if name=='q3_monthly' else ['趋势','比较','时间序列','容量功率','多面板'],
            'chart_types':[],'style_keywords':['English labels','serif typography'],'use_case':'论文正文',
            'negative_requirements':['No Chinese text in figures'],'explicit_template':False,'is_ambiguous':False,'clarification_question':''}
        engine.parse_and_save_requirement(requirement['original_request'],engine.response(requirement),
            vocabulary_path=engine.SKILL/'docs/requirement_vocabulary.yaml',output_path=ws/'user_requirement.json')
        engine.checked(engine.run_candidate_matching_pipeline(requirement_path=str(ws/'user_requirement.json'),
            catalog_path=str(engine.SKILL/'docs/template_catalog.yaml'),output_path=str(ws/'candidate_templates.json'),top_k=8,min_score=.1))
        engine.save(ws/'response_provenance.json',{'author':'Codex current assistant',
            'method':'Assistant-authored structured responses through RunnableLambda; no external model API',
            'visual_check':'Pending actual PNG inspection; never infer visual quality from execution success'})
        print(name,(ws/'candidate_templates.json').read_text())


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','adapt','quality'])
    args=parser.parse_args()
    if args.stage=='prepare':prepare()
    else:
        for name in NAMES:getattr(engine,args.stage)(name)
