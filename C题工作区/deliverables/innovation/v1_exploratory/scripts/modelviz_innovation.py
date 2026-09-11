"""ModelViz provenance and services for the innovation ablations."""
import argparse
import json
import os
import shutil
import pandas as pd
import modelviz_revision as engine
WORK=engine.WORK;ROOT=WORK/'reports/figures/modelviz_innovation_v1_en';engine.ROOT=ROOT
os.environ['TMPDIR']=str(WORK/'data/interim/innovation');os.environ['MPLCONFIGDIR']=str(WORK/'data/interim/innovation/matplotlib')
NAMES=['innovation_monthly','innovation_risk']

def prepare():
    ROOT.mkdir(parents=True,exist_ok=True)
    risk=WORK/'results/innovation/risk_models.json'
    daily_sources=sorted((WORK/'results/innovation/evaluation').glob('*/daily.csv'))
    parts=[]
    for source in daily_sources:
        d=pd.read_csv(source,float_precision='round_trip')
        parts.append(d.assign(month=d.date.str[:7]).groupby('month').total_cost_yuan.sum().rename(source.parent.name))
    m=pd.concat(parts,axis=1).reset_index()
    rs=json.loads(risk.read_text());rs=[r for r in rs if r['issue_time']>='2025-04-01' and r['predicted_s_kwh'] is not None]
    f=pd.DataFrame({'date':[r['issue_time'][:10] for r in rs],'observed_prefix_kwh':[r['realized_s_kwh'] for r in rs],
        'forecast_prefix_kwh':[r['predicted_s_kwh'] for r in rs]})
    engine.save(ROOT/'source_hashes.json',{str(p.relative_to(WORK)):engine.sha(p) for p in daily_sources+[risk]})
    for name,data,source in [('innovation_monthly',m,daily_sources),('innovation_risk',f,[risk])]:
        task=ROOT/name;ws=task/'workspace';ws.mkdir(parents=True,exist_ok=True);(task/'docs').mkdir(exist_ok=True)
        shutil.copy2(engine.SKILL/'docs/package_name_mapping.yaml',task/'docs/package_name_mapping.yaml');data.to_csv(task/'data.csv',index=False)
        engine.save(ws/'data_lineage.json',{'source_files':{str(p.relative_to(WORK)):engine.sha(p) for p in source},'plot_data_sha256':engine.sha(task/'data.csv'),
            'rows':len(data),'transformation':'Monthly exact actual-bill sums' if name.endswith('monthly') else 'Select evaluation dates and two recorded risk quantities; no smoothing or shifting'})
        goal='比较创新实验月度费用及节省时间序列' if name.endswith('monthly') else '比较连续风险目标与分位预测时间序列及缺口'
        requirement=dict(original_request='按计划做创新实验；使用modelviz-skill，全部英文标注。',goal=goal,
            functional_keywords=['趋势','比较','复合时间序列','多指标时间序列'],chart_types=[],style_keywords=['English labels','serif typography'],
            use_case='论文正文',negative_requirements=['No Chinese text in figures'],explicit_template=False,is_ambiguous=False,clarification_question='')
        engine.parse_and_save_requirement(requirement['original_request'],engine.response(requirement),vocabulary_path=engine.SKILL/'docs/requirement_vocabulary.yaml',output_path=ws/'user_requirement.json')
        engine.checked(engine.run_candidate_matching_pipeline(requirement_path=str(ws/'user_requirement.json'),catalog_path=str(engine.SKILL/'docs/template_catalog.yaml'),output_path=str(ws/'candidate_templates.json'),top_k=8,min_score=.1))
        engine.save(ws/'response_provenance.json',{'author':'Codex current assistant','method':'Assistant-authored structured outputs via RunnableLambda; no external model API','visual_check':'Actual PNG inspection required'})
        print(name,(ws/'candidate_templates.json').read_text())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','adapt','quality']);a=p.parse_args()
    if a.stage=='prepare':prepare()
    else:
        for name in NAMES:getattr(engine,a.stage)(name)
