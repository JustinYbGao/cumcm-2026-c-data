"""Prepare real final data and run ModelViz requirement parsing and candidate recall."""
import json
import shutil
import pandas as pd
import modelviz_driver as engine


if __name__=='__main__':
    result=engine.WORK/'results/q2_cost_aware_v2'
    specs=[('annual','comparison_all.csv','比较Q2各策略实际合同费、紧急费组成与理想下界，堆叠柱状图',['比较','组成','堆叠柱状图'],['柱状图']),
           ('monthly','monthly_costs_and_differences.csv','比较每月策略总费用及配对节省，保留负收益月份，复合时间序列',['趋势','比较','复合时间序列','多指标时间序列'],[])]
    for name,source,goal,keywords,types in specs:
        task=engine.ROOT/name;ws=task/'workspace';ws.mkdir(parents=True,exist_ok=True);(task/'docs').mkdir(exist_ok=True)
        f=pd.read_csv(result/source,float_precision='round_trip')
        if name=='annual':
            order=['B0','B1','P','P_terminal','P_floor','S_terminal','S_joint','P_B1','P_B1_floor']
            f=f.set_index('policy').loc[order,['planned_cost_yuan','emergency_cost_yuan','total_cost_yuan']].reset_index()
            f['relaxed_lower_bound_yuan']=json.loads((result/'lower_bound/status.json').read_text())['dual_bound_yuan']
        else:f=f[['month','P','P_floor','S_joint']]
        f.to_csv(task/'data.csv',index=False)
        shutil.copyfile(engine.SKILL/'docs/package_name_mapping.yaml',task/'docs/package_name_mapping.yaml')
        engine.save(ws/'data_lineage.json',{'source':str(result/source),'source_sha256':engine.sha(result/source),
            'plot_data_sha256':engine.sha(task/'data.csv'),'rows':len(f),'transform':'Declared policies, exact monthly dates and paired subtraction; CNY unit conversion only.'})
        req={'original_request':'继续研究Q2整体费用改进，modelviz-skill，图内全部英文，300dpi PNG与SVG，公开负结果',
             'goal':goal,'functional_keywords':keywords,'chart_types':types,'style_keywords':['科研风','English labels','serif typography'],
             'use_case':'论文正文','negative_requirements':['No Chinese text','No smoothing','No 3D'],
             'explicit_template':False,'is_ambiguous':False,'clarification_question':''}
        engine.parse_and_save_requirement(req['original_request'],engine.response(req),vocabulary_path=engine.SKILL/'docs/requirement_vocabulary.yaml',output_path=ws/'user_requirement.json')
        engine.checked(engine.run_candidate_matching_pipeline(requirement_path=str(ws/'user_requirement.json'),catalog_path=str(engine.SKILL/'docs/template_catalog.yaml'),output_path=str(ws/'candidate_templates.json'),top_k=8,min_score=.1))
        engine.save(ws/'response_provenance.json',{'author':'Codex assistant','method':'Assistant-authored structured decisions through RunnableLambda with deterministic schema validation; no external model API call.','visual_check':'Actual image must be inspected before pass.'})
        print(name,(ws/'candidate_templates.json').read_text(),flush=True)
