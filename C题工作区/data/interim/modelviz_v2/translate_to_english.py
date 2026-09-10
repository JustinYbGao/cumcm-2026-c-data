from pathlib import Path
import json,shutil,re
w=Path('/Users/justingao/Documents/CUMCM/C题工作区')
old=w/'reports/figures/modelviz_v2';new=w/'reports/figures/modelviz_v3_en'
new.mkdir(exist_ok=True)
for name in ['battery_states','dispatch','monthly_costs','representative_execution']:
 t=new/name;(t/'workspace').mkdir(parents=True,exist_ok=True)
 shutil.copy2(old/name/'data.csv',t/'data.csv')
 shutil.copytree(old/name/'docs',t/'docs',dirs_exist_ok=True)
 for file in ['user_requirement.json','candidate_templates.json','assistant_decisions.json','data_lineage.json']:
  shutil.copy2(old/name/'workspace'/file,t/'workspace'/file)
 p=t/'workspace/user_requirement.json';d=json.loads(p.read_text());d['original_request']='不要中文标注！！全部要英文的';d['style_keywords']=['English labels','serif typography'];d['negative_requirements']=['No Chinese text in figures'];p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
 p=t/'workspace/assistant_decisions.json';d=json.loads(p.read_text());d['plan']['title_plan']='English-only titles, axes, legends, annotations and footnotes';d['plan']['style_elements_to_preserve']=['Existing layout and colors','Times New Roman with DejaVu Serif fallback'];d['plan']['elements_allowed_to_change']=['Translate every visible label to English; preserve data and time alignment'];d['adaptation']['changes_summary']=['Translate every visible label to English','Remove Chinese font dependency','Preserve data, layout, colors and units'];d['adaptation']['changed_elements']=d['adaptation']['changes_summary'];p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
for file in ['source_hashes_before.json','requirements.generated.txt']:
 shutil.copy2(old/file,new/file)
translations={
'问题1  |  效率口径与日内储能轨迹':'Problem 1 | Efficiency assumptions and stored energy',
'充、放电效率均为90%（主口径）':'90% per direction (baseline)',
'往返效率90%（敏感性）':'90% round-trip (sensitivity)',
'下界 1.2 MWh':'Lower bound: 1.2 MWh','上界 10.8 MWh':'Upper bound: 10.8 MWh',
'储能电量 / MWh':'Stored energy (MWh)','(a) 两种口径的最优解':'(a) Optimal storage trajectories',
'储能差 / MWh':'Energy difference (MWh)','时刻 / h':'Time of day (h)',
'(b) 往返效率90% − 主口径':'(b) 90% round-trip minus baseline',
'内部区间终点假设；145个状态点，均按原时间键绘制。轨迹连线仅连接相邻状态。':'Internal interval-end assumption; 145 original state points; lines connect adjacent states.',
'问题1  |  购电、储能与分时电价':'Problem 1 | Grid purchases, storage and electricity price',
'给定光伏预测':'Given PV forecast','计划购电':'Planned grid purchase','负荷':'Load',
'交流侧功率 / MW':'AC power (MW)',
'(a) 负荷、光伏与计划购电':'(a) Load, PV and planned grid purchases',
'充电（正）':'Charging (+)','放电（负）':'Discharging (-)',
'储能交流侧功率 / MW':'Battery AC power (MW)',
'(b) 充放电功率与储能状态（功率上限 ±5 MW）':'(b) Battery power and stored energy (power limits: ±5 MW)',
'储能状态（右轴）':'Stored energy (right axis)',
'电价 / (元/kWh)':'Price (CNY/kWh)','(c) 已知分时电价':'(c) Known electricity price',
'主口径：充、放电效率均为90%。内部区间终点假设；144个十分钟区间，无平滑或时移。':'Baseline: 90% efficiency per direction. Internal interval-end assumption; 144 ten-minute intervals.',
'问题2  |  月度费用与季节基线比较':'Problem 2 | Monthly costs versus the seasonal baseline',
'选中策略：计划购电费':'Selected: planned cost','选中策略：紧急购电费':'Selected: emergency cost',
'季节基线：总费用':'Seasonal baseline: total cost','购电费用 / 万元':'Cost ($10^4$ CNY)',
'(a) 月度费用组成':'(a) Monthly cost breakdown',
'2—12月合计：选中策略 {total:,.2f} 万元  |  季节基线 {baseline:,.2f} 万元':'Feb-Dec total (million CNY): selected {total/100:.2f}  |  seasonal {baseline/100:.2f}',
'费用差 / 万元':'Cost difference ($10^4$ CNY)','2025年月度':'Month (2025)',
'(b) 选中策略 − 季节基线：累计 +{total-baseline:.2f} 万元（+{(total/baseline-1)*100:.2f}%）':'(b) Selected minus seasonal: total +{(total-baseline)/100:.3f} million CNY (+{(total/baseline-1)*100:.2f}%)',
'选型仅使用1月历史；2—12月为冻结评价期。正差表示选中策略费用更高。内部工作假设，非正式提交版。':'Selected using January only; evaluated February-December. Positive gap = higher cost. Internal results.',
'问题2  |  指定日的储能执行与紧急购电':'Problem 2 | Storage execution and emergency purchases',
'紧急购电 / kWh':'Emergency energy (kWh)',
'紧急购电合计 {f.emergency_kwh.sum():,.2f} kWh':'Emergency total: {f.emergency_kwh.sum():,.2f} kWh',
'实际储能（左轴）':'Actual storage (left axis)','日前计划（左轴）':'Day-ahead plan (left axis)',
'每十分钟紧急购电（右轴）':'Emergency energy per 10 min (right axis)',
'四日使用相同纵轴尺度；灰色水平虚线为1.2与10.8 MWh边界。沿用内部时间假设，实际状态不按日重置。':'Identical scales across days; dotted bounds: 1.2 and 10.8 MWh. Internal assumptions; no daily state reset.'}
for p in (w/'scripts/modelviz').glob('*.py'):
 s=p.read_text().replace('from matplotlib import font_manager\n','').replace("font_manager.fontManager.addfont('/System/Library/Fonts/Supplemental/Songti.ttc')\n",'').replace("['Times New Roman','Songti SC']","['Times New Roman','DejaVu Serif']")
 for a,b in sorted(translations.items(),key=lambda pair:len(pair[0]),reverse=True):s=s.replace(a,b)
 s=s.replace("[f'{i}月' for i in range(2,13)]","['Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']")
 s=s.replace('cumcm-modelviz-v2','cumcm-modelviz-v3-en')
 assert not re.search(r'[\u3400-\u9fff]',s),[v for v in s.splitlines() if re.search(r'[\u3400-\u9fff]',v)]
 p.write_text(s)
for name in ['modelviz_revision.py','plot_results_modelviz.py','verify_modelviz_revision.py','package_modelviz_revision.py','report_q1.py','report_q2.py']:
 p=w/'scripts'/name;p.write_text(p.read_text().replace('modelviz_v2','modelviz_v3_en'))
p=w/'AGENTS.md';s=p.read_text().replace('使用中文标签、明确单位及一致配色','图内全部使用英文（标题、坐标轴、图例、注释、脚注、月份），不得出现中文；保留明确单位及一致配色').replace('modelviz_v2','modelviz_v3_en');p.write_text(s)
