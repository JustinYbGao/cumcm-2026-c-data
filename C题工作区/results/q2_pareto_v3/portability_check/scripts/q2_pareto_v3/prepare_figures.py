"""Recall ModelViz candidates, then prepare real finalized tables for adaptation."""
import argparse
import json
import shutil
import pandas as pd
import modelviz_driver as engine


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--recall-only',action='store_true');args=parser.parse_args()
    result=engine.WORK/'results/q2_pareto_v3/analysis_user_cap'
    specs=[('savings','比较全部新方案的普通、紧急和总费用节省，分组柱状图，多指标正负值比较',['比较','分组柱状图','多指标'],[]),
           ('monthly','每月总费用节省的时间变化，保留负收益月份，多指标复合时间序列',['趋势','比较','复合时间序列','多指标时间序列'],[])]
    for name,goal,keywords,types in specs:
        task=engine.ROOT/name;ws=task/'workspace';ws.mkdir(parents=True,exist_ok=True);(task/'docs').mkdir(exist_ok=True)
        shutil.copyfile(engine.SKILL/'docs/package_name_mapping.yaml',task/'docs/package_name_mapping.yaml')
        req={'original_request':'研究Q2总费用改进，紧急购电费不超过100万元；按modelviz-skill绘图，图内全部英文，300dpi PNG与SVG，公开负结果。',
             'goal':goal,'functional_keywords':keywords,'chart_types':types,'style_keywords':['科研风','English labels','serif typography'],
             'use_case':'论文正文','negative_requirements':['No Chinese text','No smoothing','No 3D'],
             'explicit_template':False,'is_ambiguous':False,'clarification_question':''}
        engine.parse_and_save_requirement(req['original_request'],engine.response(req),vocabulary_path=engine.SKILL/'docs/requirement_vocabulary.yaml',output_path=ws/'user_requirement.json')
        engine.checked(engine.run_candidate_matching_pipeline(requirement_path=str(ws/'user_requirement.json'),catalog_path=str(engine.SKILL/'docs/template_catalog.yaml'),output_path=str(ws/'candidate_templates.json'),top_k=8,min_score=.1))
        engine.save(ws/'response_provenance.json',{'author':'Codex assistant','method':'Assistant-authored structured decisions through RunnableLambda and deterministic schema validation; no external model API call.','visual_check':'Actual image must be inspected before pass.'})
        print(name,(ws/'candidate_templates.json').read_text(),flush=True)
        if args.recall_only:continue
        source=result/('comparison_all.csv' if name=='savings' else 'monthly.csv')
        raw=pd.read_csv(source,float_precision='round_trip')
        if name=='savings':
            f=raw.loc[raw.study_stage!='reference',['policy','ordinary_saving_vs_P_floor_yuan','emergency_saving_vs_P_floor_yuan','total_saving_vs_P_floor_yuan','emergency_cost_yuan','passes_user_requirement']]
        else:
            best=json.loads((result/'acceptance_user_cap.json').read_text())['best_observed_policy']
            wide=raw.pivot(index='month',columns='policy',values='total_cost_yuan')
            f=pd.DataFrame({'month':wide.index})
            for policy in list(dict.fromkeys([best,'T_strong','R_guard','R_cost'])):f[policy]=(wide.P_floor-wide[policy]).to_numpy()
        f.to_csv(task/'data.csv',index=False)
        engine.save(ws/'data_lineage.json',{'source':str(source),'source_sha256':engine.sha(source),'plot_data_sha256':engine.sha(task/'data.csv'),'rows':len(f),'transform':'All 18 new paths, or declared monthly paired comparisons with P_floor; exact subtraction and display unit conversion only.'})


if __name__=='__main__':main()
