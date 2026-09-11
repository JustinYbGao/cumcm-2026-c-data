"""Assemble the handoff report from verified, unrounded experiment outputs."""
import json
from pathlib import Path
import pandas as pd

WORK=Path(__file__).resolve().parents[2]
ROOT=WORK/'results/unified_direct_v5';OUT=WORK/'outputs/unified_direct_v5';REPORT=WORK/'reports/unified_direct_v5'


def money(x):return f'{x:,.6f}'


def main():
    table=pd.read_csv(ROOT/'comparison_all.csv',float_precision='round_trip');lookup=table.set_index('policy')
    pairs=pd.read_csv(ROOT/'paired_summary.csv',float_precision='round_trip')
    chosen=json.loads((ROOT/'selection.json').read_text())['selected']
    checks={key:json.loads((REPORT/filename).read_text()) for key,filename in {
        'independent':'independent_report.json','analysis':'analysis_validation.json','causality':'causality_checks.json',
        'numerical':'numerical_checks.json','reproduction':'reproduction_comparison.json','workbook':'workbook_readback.json','preservation':'preservation_check.json'}.items()}
    assert all(v['passed'] for v in checks.values())
    new=table.loc[table.stage=='new_direct'];coverage=checks['independent']['metrics']['policies'];assert set(new.policy)==set(coverage)
    counts={key:sum(v[key] for v in coverage.values()) for key in ['ledger_rows','decisions','candidate_vectors','candidate_scenario_paths']}
    selected_rows=[]
    for group,old in [('q3','old_q3_w28'),('q42','old_q42_ols'),('q43','old_q43_w28_ols')]:
        name=chosen[group];r=lookup.loc[name];o=lookup.loc[old]
        selected_rows.append({'问题':group,'策略':name,'总费/元':r.total_cost_yuan,'紧急费/元':r.emergency_cost_yuan,
          '最终合同费/元':r.contract_cost_yuan,'旧主策略':old,'较旧主策略节省/元':o.total_cost_yuan-r.total_cost_yuan,
          '100万元余量/元':r.emergency_margin_yuan,'采用建议':'替换为新策略（仅历史支持）' if r.total_cost_yuan<o.total_cost_yuan else '不替换旧策略；新结果保留'})
    def pair(c,r):return pairs.loc[(pairs.candidate==c)&(pairs.reference==r)].iloc[0]
    soc=pair('q3_soc','q3_no_update');pv=pair('q3_raw','q3_soc');correction=pair('q3_w28','q3_raw');price=pair('q42_ols','q42_fixed')
    failures=int(new.optimizer_non_success_count.sum());attempts=int(new.optimizer_count.sum());fallback=int(new.initializer_fallback_count.sum());exceptions=int(new.optimizer_exception_count.sum())
    keep=int(new.keep_current_selected_count.sum());starts=int(new.retained_start_selected_count.sum())
    paragraphs=[
      '# Unified direct v5：方法统一、连续回放与同版结果验收',
      '',
      '本轮已按冻结协议完成十条新策略的334日连续运行、全部候选独立核算、三个最终分支的隔离目录复现，以及五份工作簿和指定日期表的独立读回。旧论文、原附件、旧工作簿及冻结包保留；本轮没有精修论文或执行commit/push。结论来自反复查看过的2025年历史路径，属于探索性选择。',
      '', '## 最终选择与真实费用', '',
      pd.DataFrame(selected_rows).to_markdown(index=False,floatfmt='.6f'),
      '',
      'Q1 baseline：总费35,126.94858928963元、固定单日、初末6000kWh。Q2 D112：正常费13,075,237.028039372元，紧急费838,655.4538288128元，总费13,913,892.481868185元。两者按源价独立回归核对，Q2原路径未改动。五份文件均是已披露工作口径下的内部审阅版。',
      '',
      '选择规则在年度运行前冻结：各分支按未舍入历史总费最小、紧急费最小、矩阵顺序破同差。Q3与Q4-3最终均采用原PV；Q4-2最终采用固定价规划控制，Q4-3采用因果OLS价。后两者仍以同一实际变价计费，区别只在允许的规划价格输入；这种分支选择有历史选择偏差，不能写成普遍优越。',
      '', '## 十条新策略与失败结果', '',
      new[['policy','branch','contract_cost_yuan','emergency_cost_yuan','total_cost_yuan','final_energy_kwh','wall_seconds','optimizer_non_success_count','initializer_fallback_count']].to_markdown(index=False,floatfmt='.6f'),
      '',
      f'共{attempts:,}次L-BFGS-B启动，{failures:,}次非success；求解异常{exceptions}次，初始化回退{fallback}次。选中保留初值{starts}次，日内选中keep_current {keep}次。所有终止状态、最低评估点、返回点和候选目标均在各策略decisions.json与evidence内保留。非success不等于物理不合格，也不证明局部或全局最优。没有通过未来实际费用挑候选。',
      '',
      f'十条新策略均未超过100万元紧急费参考线；最小余量为{money(new.emergency_margin_yuan.min())}元。该线是此前Q2的研究偏好，不是赛题新增硬约束，不构成未来保证。未出现需否决采用的旧主策略迁移，但校正、价格输入及部分日/月对照有失败结果，全部保留。',
      '', '## 信息、校正与价格能够说明什么', '',
      f'Q3无更新→仅SOC反馈节省{money(soc.total_saving_yuan)}元；仅SOC→新PV四时刻更新进一步节省{money(pv.total_saving_yuan)}元。这是共享算法和初态、各自连续SOC路径的匹配政策比较。不能把新旧MILP与直接采购的全部差额归因于信息更新。',
      '',
      f'Q3原PV→28日校正的节省为{money(correction.total_saving_yuan)}元，即总费上升；紧急费节省{money(correction.emergency_saving_yuan)}元，合同费节省{money(correction.contract_saving_yuan)}元。故旧校正在新直接目标下不再支持总费下降。Q4-2使用OLS预测价相对固定价控制的节省为{money(price.total_saving_yuan)}元，保留该负结果。',
      '',
      'Q4-3价格×校正的成对比较如下。没有新增Q4无更新/仅SOC对照，故不单独量化变价下的新PV信息价值。不同问题的绝对费用差含价格与权限变化，不作单因素解释。', '',
      pairs.loc[pairs.purpose.str.startswith('Q43 '),['candidate','reference','total_saving_yuan','contract_saving_yuan','emergency_saving_yuan','winning_days','losing_days','losing_months','block7_lower_yuan','block7_upper_yuan','block14_lower_yuan','block14_upper_yuan']].to_markdown(index=False,floatfmt='.6f'),
      '',
      '全部配对日/月、胜负天数、亏损月及库存代理见paired_daily.csv、paired_monthly.csv、paired_summary.csv。库存代理仅用固定参考价0.6895775元/kWh乘期末净库存，不减真实账单。7/14日循环块重采样使用种子20260915、2000次；区间跨零均明列。这些区间描述固定历史路径，不能替代物理压力测试，不能修正同年选优偏差。',
      '', '## 共同机制与权限边界', '',
      '共同使用W112历史整日残差场景、κ=5、μ=0.38232、当前真实SOC、严格逐段贪心、非负采购、双起点和候选重评；最终采购没有每天固定末态或名义零紧急的等式。初始化MILP的末态1200仅限制搜索起点。Q2与Q4-2午夜冻结144维采购，Q4-2不读取附件3；Q3与Q4-3仅00/06/12/18修订未来段，午夜六候选、日内追加keep_current第七候选。',
      '',
      '日内目标使用相对午夜原量的一次最终A合同费用：p q0+1.5p(q−q0)+−0.5p(q0−q)+；已执行段沉没且不重复收费。真实紧急费恒为5p。Q4规划价按当时可得OLS预测或固定价控制代入，实际费用按附件4目标段价格结算。负荷每日午夜冻结；历史PV误差与当前源发布阶段一致，历史校正使用其自身当时截止，4月启用且不重置SOC。',
      '',
      '详细公式、旧新机制及组合归因边界见[method_changes.md](method_changes.md)，模型字典适配和局限见[model_fit.md](model_fit.md)。本轮未新增参数网格或容量优化，也未制作分析图；完整数表是主交付。',
      '', '## 验收证据', '',
      f"独立NumPy/openpyxl验证器不导入生产核、贪心或计费函数：十策略{counts['ledger_rows']:,}个实际段、{counts['decisions']:,}次决策、{counts['candidate_vectors']:,}条候选向量、{counts['candidate_scenario_paths']:,}条候选—场景路径全部通过。它从原始附件重建52560段实际值、364日B0、1460次原始PV发布和1336次因果OLS发布，并核查历史场景、修订时刻与计费。",
      '',
      f"三条最终策略在独立源/数据目录重新编译核并完整重放；候选、账本、计划和费用差异见[reproduction_comparison.json](reproduction_comparison.json)。有限差分覆盖360个坐标和四种剩余时域，边界6组；未来扰动共{len(checks['causality']['records'])}组，覆盖可用前信息/候选不变、可用后阳性响应、午夜冻结以及Q4-2附件3禁止读取（含拦截器阳性控制）。",
      '',
      '物理阈值1e-6kWh、费用阈值1e-5元。逐项最大误差和单位见[independent_report.json](independent_report.json)、[analysis_validation.json](analysis_validation.json)、[numerical_checks.json](numerical_checks.json)、[causality_checks.json](causality_checks.json)；独立主报告中的工作簿“outside scope”由[workbook_readback.json](workbook_readback.json)单独闭合。最终验收总表见[acceptance_report.md](acceptance_report.md)。',
      '', '## 文件、指定日期表与论文接力', '',
      '| 题目/策略 | 拟更新论文内容 | 数据与指定表 | 最终文件 |',
      '|---|---|---|---|',
      '| Q1 baseline | 问题一确定性基准、表1/2 | outputs/unified_direct_v5/specified_days/result1 | result1.xlsx |',
      '| Q2 D112 | 问题二直接采购目标与真实风险 | D112原账本；specified_days/result2 | result2.xlsx |',
      f"| Q3 {chosen['q3']} | 问题三滚动合同目标、信息消融和校正负结果 | runs/{chosen['q3']}；specified_days/result3 | result3.xlsx |",
      f"| Q4-2 {chosen['q42']} | 变价午夜采购、OLS负对照 | runs/{chosen['q42']}；specified_days/result4-2 | result4-2.xlsx |",
      f"| Q4-3 {chosen['q43']} | 变价滚动采购、价格×校正对照 | runs/{chosen['q43']}；specified_days/result4-3 | result4-3.xlsx |",
      '',
      '工作簿均位于../../outputs/unified_direct_v5/；策略、代码/配置SHA、源账本、初末态及费用在policy_mapping.json。其他四问每份334×144采购，Q3/Q43另有最终调整量；六个4小时充放电块和0/24电量、全年紧急事件均完整。Q1以及3月20日、6月21日、9月23日、12月21日题面表1/2/3以CSV和Markdown交付，含日量与日费。',
      '',
      '紧急事件按>1e-7kWh的相邻段聚合并跨午夜拆开，与旧审阅导出一致；冻结协议原写1e-6的表述已在protocol_amendments.md明确更正。实际全账本计费保留所有尾数，事件阈值遗漏量与显示精度损失由工作簿报告列明。中文模板字段保留，时间映射CSV公开1008项，不静默移数。',
      '',
      '下一位论文agent优先阅读五份：①本README；②method_changes.md；③cost_tables.md；④acceptance_report.md（链接到各独立证据）；⑤workbook_report.md。原outline_20260911仍是写作蓝图，不能覆盖本轮负结果或把固定价规划控制写成OLS预测主方案。',
      '', '## 重现命令', '',
      '在C题工作区运行以下命令；年度生产run.py默认拒绝覆盖已有目录。完整复现会在新的v5子目录重新准备数据、编译并运行三个选定策略。请将rerun_02换成尚不存在的目录名。',
      '', '```sh',
      'PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/unified_direct_v5/reproduce.py --target results/unified_direct_v5/rerun_02',
      'PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/unified_direct_v5/independent_verify.py',
      'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/unified_direct_v5/validate_analysis.py',
      'PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/unified_direct_v5/verify_workbooks.py',
      '```', '',
      '首次完整十策略执行命令及输出保存在results/unified_direct_v5/prepare.log、run.log，方案和参数在configs/unified_direct_v5/experiments.json。工作簿作者运行命令见workbook_report.md。原始运行时间是本机墙钟时间，含不同阶段系统竞争；旧基准缺失的时间/停止计数为空，不填零伪造。所有重验报告都写v5目录，若须保留封包时的验收报告，应先另建新版本再重验。',
      '', '## 剩余问题与结论边界', '',
      '1. A最终一次结算、区间终点/平均功率、小时点值插值、首小时历史锚点、效率含义、母线功率侧别、区间末观测与段内平衡、审阅模板时间映射尚未获正式题意确认。工作簿不能冒充口径已确认的最终比赛提交版。',
      '2. 同年多轮历史选择、重叠残差窗及4月校正切换的非平稳性限制泛化；尚无未见年度/站点验证，不保证未来费差或紧急预算。',
      '3. 直接目标非光滑，非success大量存在；候选选择和物理执行已核验，最优性仍未证明。μ沿用Q2，本轮不将重新调参收益混入迁移。',
      '4. 新旧目标/场景/采购可行集合/终态共同变化，只支持组合迁移解释。Q4更新价值未作无更新/SOC消融，不能独立归因。',
      '5. 三次复现使用同一主机和依赖版本，证明隔离重算一致，不等同于跨平台数值稳定性。未来扰动是有限三日实现测试，不是年度压力风险保证。',
      '',
      '结果包为五个独立v5目录；逐文件清单与SHA在package_manifest.json、SHA256SUMS.txt，读回在package_readback.json。旧文件前后SHA及新增路径检查见preservation_check.json。没有必要为本轮验收再复制为大型ZIP。',
    ]
    (REPORT/'README.md').write_text('\n'.join(paragraphs)+'\n')
    result={'passed':True,'coverage':counts,'selected':chosen,'checks':{k:True for k in checks},'unresolved_external_assumptions':True,'research_not_blind_test':True,'new_policies':10,'workbooks':5}
    (ROOT/'acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    lines=['# 最终验收','',pd.DataFrame([{'验收项':k,'结果':'PASS'} for k in checks]).to_markdown(index=False),'',
           '年度10策略、全部候选、逐段实际执行和源价计费已覆盖；五份实际XLSX独立读回、三选定策略隔离年度复现均通过。各项详细范围与最大误差以链接的原始JSON为准，题意工作假设未视为正式确认。','',
           json.dumps(counts,ensure_ascii=False,indent=2),'','证据入口：', '']
    lines += [f'- [{key}]({filename})' for key,filename in [('独立源/候选/账本','independent_report.json'),('费用统计','analysis_validation.json'),('未来扰动','causality_checks.json'),('导数和边界','numerical_checks.json'),('隔离复现','reproduction_comparison.json'),('工作簿读回','workbook_readback.json'),('旧文件保护','preservation_check.json')]]
    (REPORT/'acceptance_report.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
