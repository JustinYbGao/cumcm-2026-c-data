"""ModelViz services and lineage for the supplemental comparisons."""
import argparse
import json
import os
import shutil
import pandas as pd
import modelviz_revision as engine
WORK=engine.WORK;ROOT=WORK/'reports/figures/modelviz_robustness_v1_en';engine.ROOT=ROOT
for key in ['TMPDIR','TMP','TEMP']:os.environ[key]=str(WORK/'data/interim/robustness')
os.environ['MPLCONFIGDIR']=str(WORK/'data/interim/robustness/matplotlib')
NAMES=['robustness_effects','robustness_monthly']

def prepare():
    ROOT.mkdir(parents=True,exist_ok=True)
    source=WORK/'results/robustness';summary=pd.read_csv(source/'paired_summary.csv',float_precision='round_trip')
    boot=pd.read_csv(source/'bootstrap_intervals.csv',float_precision='round_trip')
    s=summary.loc[summary.scope=='april_december'].copy()
    b=boot.loc[(boot.method=='moving_block')&(boot.block_days==7),['comparison_id','lower_95_yuan','upper_95_yuan']]
    effects=s.merge(b,on='comparison_id',validate='one_to_one')[['comparison_id','comparison_label','cash_gain_yuan','inventory_adjusted_gain_yuan','lower_95_yuan','upper_95_yuan']]
    monthly=pd.read_csv(source/'paired_monthly.csv',float_precision='round_trip')
    monthly=monthly.loc[(monthly.scope=='april_december')&(monthly.comparison_id=='fixed_w28_vs_raw'),['month','raw_total_cost_yuan','corrected_total_cost_yuan','cash_gain_yuan','cumulative_cash_gain_yuan']]
    for name,data,sources in [('robustness_effects',effects,[source/'paired_summary.csv',source/'bootstrap_intervals.csv']),('robustness_monthly',monthly,[source/'paired_monthly.csv'])]:
        task=ROOT/name;ws=task/'workspace';ws.mkdir(parents=True,exist_ok=True);(task/'docs').mkdir(exist_ok=True)
        shutil.copy2(engine.SKILL/'docs/package_name_mapping.yaml',task/'docs/package_name_mapping.yaml');data.to_csv(task/'data.csv',index=False)
        engine.save(ws/'data_lineage.json',{'source_files':{str(p.relative_to(WORK)):engine.sha(p) for p in sources},'plot_data_sha256':engine.sha(task/'data.csv'),'rows':len(data),'transformation':'April-Dec exact paired cash savings; seven-day within-month moving-block percentile interval; inventory value diagnostic' if name.endswith('effects') else 'Main 28-day policy monthly actual costs and signed savings, no shift or smoothing'})
        req=dict(original_request='新的敏感性鲁棒性测试也要；modelviz-skill；全部英文标注。',goal='比较六种校正情景的累计省费及不确定区间' if name.endswith('effects') else '主方案每月实际成本及正负省费时间序列',functional_keywords=['比较','排序','条形图','不确定性'] if name.endswith('effects') else ['趋势','比较','复合时间序列','多指标时间序列'],chart_types=[],style_keywords=['English labels','serif typography'],use_case='论文正文',negative_requirements=['No Chinese text in figures','No significance stars','No three-dimensional view'],explicit_template=False,is_ambiguous=False,clarification_question='')
        engine.parse_and_save_requirement(req['original_request'],engine.response(req),vocabulary_path=engine.SKILL/'docs/requirement_vocabulary.yaml',output_path=ws/'user_requirement.json')
        engine.checked(engine.run_candidate_matching_pipeline(requirement_path=str(ws/'user_requirement.json'),catalog_path=str(engine.SKILL/'docs/template_catalog.yaml'),output_path=str(ws/'candidate_templates.json'),top_k=8,min_score=.1))
        engine.save(ws/'response_provenance.json',{'author':'Codex current assistant','method':'Assistant-authored structured outputs via RunnableLambda; no external model API','visual_check':'Actual PNG inspection required'})
        print(name,(ws/'candidate_templates.json').read_text())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','adapt','quality']);a=p.parse_args()
    if a.stage=='prepare':prepare()
    else:
        for name in NAMES:getattr(engine,a.stage)(name)
