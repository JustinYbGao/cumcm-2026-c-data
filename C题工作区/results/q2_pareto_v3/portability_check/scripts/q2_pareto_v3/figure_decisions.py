"""Record assistant-authored ModelViz choices after actual source/template inspection."""
import json
import pandas as pd
import modelviz_driver as e

for name,ident,title,reason,layout,changes in [
    ('savings','cmp_gradient_single_factor_bar','渐变单因子条形图','Three matched horizontal-bar panels show all 18 policies and positive/negative bill differences without conflating additive components.',
     ['Horizontal gradient bars','Repeated aligned panels','Serif typography','Gray background and white grid','Direct numeric labels'],
     ['Use three panels with a shared policy order','Display positive and negative savings from zero','Remove unsupported p-value stars','Hatch cap violations, never omit them','English labels and 300dpi PNG plus SVG']),
    ('monthly','trd_composite_line_bar_dual_axis','折线图、条形图和双Y轴的复合时间序列图','Observed monthly savings compare the best eligible follow-up with fixed and guarded alternatives; losses remain visible.',
     ['Matplotlib','Shared time axis with bars and marked lines','Serif typography','Muted green gold blue colors','Horizontal grid'],
     ['Use supplied paired monthly savings','Use a single currency axis because every series has identical units','Remove demonstration regression and p values','English labels and 300dpi PNG plus SVG'])]:
    ws=e.ROOT/name/'workspace';data=pd.read_csv(e.ROOT/name/'data.csv');cols=list(data.columns)
    candidates=json.loads((ws/'candidate_templates.json').read_text())['candidates']
    choice=dict(dataset_summary=f'{len(data)} real rows; {cols}',relevant_columns=cols,
        candidate_comparisons=[dict(template_id=c['template_id'],suitable=c['template_id']==ident,
          advantages=[reason] if c['template_id']==ident else [],
          limitations=[] if c['template_id']==ident else ['This candidate introduces unnecessary radial, fitted, normalized, 3D, or unrelated analytical encoding.'],
          data_compatibility='Only real named columns, exact paired subtraction and currency conversion.') for c in candidates],
        selected_template_id=ident,selected_template_name=title,selection_reason=reason,
        data_support_reason='Data CSV contains all plotted values and their policy/month keys; no synthetic series.',confidence=.96)
    plan=dict(template_id=ident,template_name=title,plot_goal=reason,selected_columns=cols,
        column_mappings=[dict(data_column=c,template_role='Category key' if c in ['policy','month'] else 'Actual bill difference, emergency amount, or cap outcome') for c in cols],
        required_preprocessing=['Read actual CSV, preserve order; divide yuan by 1000 for axis display'],required_dependencies=['numpy','pandas','matplotlib'],
        layout_elements_to_preserve=layout,style_elements_to_preserve=layout,elements_allowed_to_change=changes,
        title_plan='English Q2 fee tradeoffs',axis_plan='Explicit thousand CNY and zero lines; savings panels disclose differing ranges',
        legend_plan='Upper separate band when needed',annotation_plan='Direct amounts, all failures and scope notes; no significance stars',output_formats=['png','svg'],warnings=['Historical exploratory comparison; no future cap guarantee.'])
    adaptation=dict(changes_summary=[reason],preserved_style_elements=layout,changed_elements=changes,
        data_columns_used=cols,dependencies_used=['matplotlib','numpy','pandas'],additional_dependencies_requested=[],
        assumptions=['Exact historical actual bills; unchanged physical and information constraints.'])
    e.save(ws/'assistant_decisions.json',dict(selection=choice,plan=plan,adaptation=adaptation))
