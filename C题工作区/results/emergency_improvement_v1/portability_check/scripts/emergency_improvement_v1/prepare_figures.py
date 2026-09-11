"""Prepare real result copies and invoke ModelViz deterministic candidate recall."""
import json
import shutil
import pandas as pd
import modelviz_driver as engine


def main():
    result=engine.WORK/'results/emergency_improvement_v1'
    specs=[('annual',result/'comparison_all.csv','比较五个问题2策略总费用及合同费、紧急费组成，堆叠柱状图', ['比较','组成','堆叠柱状图'],['柱状图']),
           ('monthly',result/'monthly_costs_and_differences.csv','比较月度总费用时间序列和各策略配对节省金额，复合时间序列', ['趋势','比较','复合时间序列','多指标时间序列'],[])]
    for name,source,goal,keywords,types in specs:
        task=engine.ROOT/name;ws=task/'workspace';ws.mkdir(parents=True,exist_ok=True);(task/'docs').mkdir(exist_ok=True)
        f=pd.read_csv(source,float_precision='round_trip')
        if name=='annual':f=f.loc[f.policy.isin(['B0','B1','P','E','PE']),['policy','planned_cost_yuan','emergency_cost_yuan','total_cost_yuan']]
        else:f=f[['month','B0','B1','P','E','PE']]
        f.to_csv(task/'data.csv',index=False)
        shutil.copyfile(engine.SKILL/'docs/package_name_mapping.yaml',task/'docs/package_name_mapping.yaml')
        engine.save(ws/'data_lineage.json',{'source':str(source),'source_sha256':engine.sha(source),'plot_data_sha256':engine.sha(task/'data.csv'),
                                          'rows':len(f),'transform':'Select declared policies/columns; preserve exact data and dates. CNY to million CNY for display.'})
        req={'original_request':'Q2紧急购电改进研究；modelviz-skill；图内全部英文；PNG300dpi及SVG','goal':goal,
             'functional_keywords':keywords,'chart_types':types,'style_keywords':['科研风','English labels','serif typography'],'use_case':'论文正文',
             'negative_requirements':['No Chinese text','No smoothing','No 3D'],'explicit_template':False,'is_ambiguous':False,'clarification_question':''}
        engine.parse_and_save_requirement(req['original_request'],engine.response(req),vocabulary_path=engine.SKILL/'docs/requirement_vocabulary.yaml',output_path=ws/'user_requirement.json')
        engine.checked(engine.run_candidate_matching_pipeline(requirement_path=str(ws/'user_requirement.json'),catalog_path=str(engine.SKILL/'docs/template_catalog.yaml'),output_path=str(ws/'candidate_templates.json'),top_k=8,min_score=.1))
        engine.save(ws/'response_provenance.json',{'author':'Codex assistant','method':'Assistant-authored structured outputs passed through RunnableLambda; deterministic validators; no external model call','visual_check':'Must inspect actual PNG before pass'})
        print(name,(ws/'candidate_templates.json').read_text(),flush=True)


if __name__=='__main__':main()
