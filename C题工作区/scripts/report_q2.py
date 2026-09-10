"""Build Q2 interpretation, required representative tables and plots from audited ledgers."""
import hashlib
import json
import os
from pathlib import Path
import sys

WORK=Path(__file__).resolve().parents[1]
os.environ['TMPDIR']=str(WORK/'data/interim/q2')
os.environ['MPLCONFIGDIR']=str(WORK/'data/interim/q2/matplotlib')
sys.dont_write_bytecode=True
import numpy as np
import pandas as pd


def table(frame):
    rows=['| '+' | '.join(str(c) for c in frame.columns)+' |','| '+' | '.join(['---']*len(frame.columns))+' |']
    for _,row in frame.iterrows():
        rows.append('| '+' | '.join(f'{v:.6f}' if isinstance(v,(float,np.floating)) else str(v) for v in row)+' |')
    return '\n'.join(rows)


def main():
    out=WORK/'results/q2'
    validation=json.loads((out/'validation.json').read_text())
    if not validation['passed']: raise RuntimeError('Validation must pass before reporting')
    comparison=pd.read_csv(out/'comparison.csv').set_index('policy')
    selection=json.loads((out/'selection.json').read_text())
    selected=comparison.loc['selected']
    seasonal=comparison.loc['seasonal']
    none=comparison.loc['no_storage']
    p=pd.read_csv(out/'selected/ledger.csv')
    daily=pd.read_csv(out/'selected/daily.csv')
    simple=pd.read_csv(out/'seasonal/daily.csv')
    cal=pd.read_csv(out/'calibration/comparison.csv')
    figures=WORK/'reports/figures/modelviz_v3_en'
    figures.mkdir(parents=True,exist_ok=True)
    months=daily.assign(month=daily.date.str[:7]).groupby('month')[['planned_cost_yuan','emergency_cost_yuan','total_cost_yuan','emergency_kwh']].sum()
    months['seasonal_total_cost_yuan']=simple.assign(month=simple.date.str[:7]).groupby('month').total_cost_yuan.sum()
    months['excess_cost_yuan']=months.total_cost_yuan-months.seasonal_total_cost_yuan
    months.to_csv(out/'monthly_comparison.csv')
    from plot_results_modelviz import render
    render('q2')
    dates=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
    # Merge only adjacent emergency intervals within the same business day.
    events=[]
    for date,f in p.groupby('date',sort=False):
        selected_rows=f.loc[f.emergency_kwh>1e-6].copy()
        if selected_rows.empty: continue
        groups=selected_rows.slot_id.diff().ne(1).cumsum()
        for _,block in selected_rows.groupby(groups):
            events.append({'date':date,'interval_start':block.interval_start.iloc[0],
                           'interval_end':block.interval_end.iloc[-1],'emergency_kwh':block.emergency_kwh.sum(),
                           'ten_minute_intervals':len(block)})
    event_frame=pd.DataFrame(events)
    event_frame.to_csv(out/'selected/emergency_events_merged.csv',index=False)
    representative=event_frame.loc[event_frame.date.isin(dates)]
    representative.to_csv(out/'selected/table3_merged_representative.csv',index=False)
    # Independently expand each merged event against the saved raw interval export.
    checks=[]
    expanded=[]
    raw=pd.read_csv(out/'selected/emergency_intervals.csv')
    for _,event in event_frame.iterrows():
        block=raw.loc[(raw.date==event.date)&(raw.interval_start>=event.interval_start)&(raw.interval_end<=event.interval_end)]
        checks.append(len(block)==event.ten_minute_intervals and abs(block.emergency_kwh.sum()-event.emergency_kwh)<1e-6)
        expanded.extend(block.index.tolist())
    assert all(checks) and expanded==raw.index.tolist()
    (out/'report_validation.json').write_text(json.dumps({'passed':True,'merged_events':len(events),
                  'covered_original_intervals':len(expanded),'checks':'Every merged event expands exactly to the original ordered emergency interval rows'},indent=2)+'\n')
    def display_time(series): return series.str.slice(11,16)
    parts=[]
    for date in dates:
        d=daily.loc[daily.date==date].iloc[0]
        t1=pd.read_csv(out/'selected/table1_representative.csv')
        t1=t1.loc[t1.date==date].copy()
        t1['时间段']=display_time(t1.interval_start)+'–'+display_time(t1.interval_end)
        t2=pd.read_csv(out/'selected/table2_representative.csv')
        t2=t2.loc[t2.date==date].copy()
        t2['时间段']=t2.block_start_minute.map(lambda v:f'{v//60:02d}:00')+'–'+t2.block_end_minute.map(lambda v:f'{v//60:02d}:00')
        e=representative.loc[representative.date==date].copy()
        e['时间段']=display_time(e.interval_start)+'–'+display_time(e.interval_end)
        parts.append(f'### {date}\n\n全天计划购电{d.grid_plan_kwh:.6f} kWh，计划费{d.planned_cost_yuan:.6f}元；紧急购电{d.emergency_kwh:.6f} kWh，紧急费{d.emergency_cost_yuan:.6f}元；总费{d.total_cost_yuan:.6f}元。实际0:00储能{d.energy_start_actual_kwh:.6f} kWh，24:00储能{d.energy_end_actual_kwh:.6f} kWh。\n\n表1指定区间计划购电：\n\n'+table(t1[['时间段','grid_plan_kwh']].rename(columns={'grid_plan_kwh':'计划购电/kWh'}))+'\n\n表2实际充放电：\n\n'+table(t2[['时间段','charge_actual_kwh','discharge_actual_kwh']].rename(columns={'charge_actual_kwh':'充电/kWh','discharge_actual_kwh':'放电/kWh'}))+'\n\n表3连续紧急购电：\n\n'+table(e[['时间段','emergency_kwh']].rename(columns={'emergency_kwh':'紧急购电/kWh'})))
    (WORK/'reports/q2_representative_tables.md').write_text('# 问题2基础版：四个指定日期结果表\n\n> 内部区间终点假设。对应1月冻结选型的selected策略；充放电和首末储能为实际执行值。不是正式模板导出。\n\n'+'\n\n'.join(parts)+'\n')
    metrics=comparison.reset_index()[['policy','forecast_model','planned_cost_yuan','emergency_cost_yuan','total_cost_yuan','emergency_kwh','final_energy_kwh']]
    metric_table=table(metrics.rename(columns={'policy':'策略','forecast_model':'预测器','planned_cost_yuan':'计划费/元','emergency_cost_yuan':'紧急费/元','total_cost_yuan':'总费/元','emergency_kwh':'紧急量/kWh','final_energy_kwh':'期末储能/kWh'}))
    gap=selected.total_cost_yuan-seasonal.total_cost_yuan
    count=sum(len(r['checks']) for r in validation['runs'].values())+len(validation['cross_checks'])
    residual=validation['runs']['selected']['max_residuals']
    report=fr'''# 问题2基础闭环：模型、实际回放与结果解释

> 状态：已完成1月初始化/校准和2—12月334天内部基础版回放；已独立验证。**技术闭环成立，但1月选中的预测组合在全年评价中劣于简单季节基线，不认定为有效改进。** 沿用问题1的时间与物理假设，正式result2.xlsx未导出。问题3—4未执行。

## 1. 本轮先完成的问题1交付

问题1已先冻结为 `deliverables/q1/v1_interval_end_assumption.zip`，配套SHA-256文件；102个文件包含源输入、完整解、配置、代码、日志、结论追溯表及论文初稿。包内哈希及六组策略验证通过，两种效率下MILP/LP目标已重新计算复现。论文初稿在 `papers/q1_draft.md`，是章节初稿，未进行全文编号和语言精修。冻结包中的“Q2未执行”是冻结时状态，本报告记录其后的进展。

## 2. 问题2输入、因果边界与初始化

Q2使用附件2负荷/PV实际值的历史，以及附件1全天固定价格。程序只加载对应字段，不读取附件3预报或附件4价格。各实际十分钟区间仅在结束后成为历史；当天0:00预测函数只能接收此前完整天的数据，拒绝任何结束时间晚于决策时刻的行。价格为已知固定日型。所有电量仍为kWh、价格为元/kWh，5000 kW限额乘以1/6小时。

1月1日0:00储能6000 kWh。该时刻没有历史观测，采用明确的冷启动政策：不承诺日前购电，预测字段留空；当日按实际供需运行并紧急补购，真实递推电池状态。该政策未声称具备冷启动预测能力，也不是把附件3缺失预报填零。1月2日起以季节基线连续运行到1月底，得到共同2月1日初态 **{selection['common_evaluation_initial_energy_kwh']:.9f} kWh**。这个共同启动政策是工作假设，1月费用保存但不计入2—12月评价。

三条评价策略从同一2月1日真实初态出发，此后各自连续运行。每日日前计划末态约束等于该日真实初态，是保守基础版假设；实际末态由观测供需和执行器生成，既不补写成计划值，也不每天重置。因而Q1“实际日初日末相同”的确定性结果不能直接套用到Q2。

## 3. 预测与选型方法

沿用BZD模型字典#1788负荷回归与#2703动态谐波光伏候选，适配和原记录见 `q2_model_fit.md` 与 `logs/q2/dictionary_*.json`。三个候选在评价前写入配置：

- seasonal：负荷取前一周同刻，不足7天用昨日；PV取昨日同刻。
- linear_persistence：负荷回归，PV仍用昨日同刻。
- linear_harmonic：同一负荷回归，加PV动态谐波回归。

负荷回归取最近28个可训练日，特征为截距、两阶日谐波、昨日及上周同刻负荷和6个星期指示变量，共13列；滞后负荷除以1000仅作数值缩放。最少需要7个训练目标日及其滞后历史，之前回退季节基线。以最小二乘求系数并将负预测截为0，逐日记录系数、矩阵秩和条件数；不对相关高频观测做独立样本显著性或因果解释。

PV候选用最近7天、3阶日谐波拟合周期项，残差采用AR(1)：

$$G_u=alpha_0+sum_{{m=1}}^3[a_msin(2pi mu/144)+b_mcos(2pi mu/144)]+v_u,quad v_u=phi v_{{u-1}}+epsilon_u.$$

估计φ后限制在[−0.99,0.99]，未来h步残差预测为φʰv_last；周期项加动态项后截断非负。没有利用当天实际零值设夜间遮罩。7日窗口和谐波阶数为低复杂度基础设定，并非用全年最优结果调参。

1月15—31日，三个候选从共同当日储能出发进行连续影子回放，每日训练只使用当时过去信息。比较分数为

$$S=J_{{actual}}-lambda(E_{{end}}-E_{{start}}),qquadlambda=operatorname{{mean}}(p_t)eta_d.$$

λ={selection['inventory_value_yuan_per_kwh']:.9f}元/kWh，是以已知固定价均值给库存估值的比较代理，不是电网实际账单。原始费用和期末库存同时保留。校准结果为：

{table(cal[['candidate','total_cost_yuan','final_energy_kwh','inventory_adjusted_score_yuan']])}

2月1日0:00冻结选型 **{selection['selected']}**，以后只滚动更新该模型参数，不以2—12月真实结果回头改候选选择。这个短校准窗口的泛化局限由后续结果检验。

## 4. 日前调度、实际执行与费用

沿用问题1的MILP函数，输入为当天预测负荷与PV、固定价和该日实际初态。目标为预测条件下计划购电费最小，满足预测供需平衡、储能递推、容量、交流侧功率、PV弃光边界和充放电互斥。每次求解保存目标、下界、gap、状态和时间。它是确定性日前基线，**不声称最小化含预测误差的期望实际费用**。

执行时保持整日原计划购电gₜ不变。以本区间实际平均供需形成准静态反馈，记aₜ=gₜ+PVₜ−Lₜ。当aₜ≥0时，优先充电：

$$c_t=min(a_t,5000/6,(10800-E_t)/eta_c),quad d_t=e_t=0,quad w_t=a_t-c_t.$$

当aₜ<0时，优先放电，不足部分紧急购买：

$$d_t=min(-a_t,5000/6,eta_d(E_t-1200)),quad c_t=w_t=0,quad e_t=-a_t-d_t.$$

随后按Eₜ₊₁=Eₜ+ηc cₜ−dₜ/ηd更新。该规则只利用本区间供需，不回传给更早的日前决策，不用紧急购电充电；但贪心执行本身不保证经济最优。实际w是富余处置，不全部称为弃光。采用“优先利用PV”的账目约定，未用购电=min(g,w)，弃光=w−未用购电；这只是来源归属约定，不是对电子来源的物理辨识。

按题目结算：

$$J_{{actual}}=sum_t p_tg_t+5sum_t p_te_t.$$

未使用的计划购电仍在第一项全部收费，没有退款、售电或免费未服务负荷。no_storage对照使用与selected相同预测，日前购买max(预测负荷−预测PV,0)，禁用电池，缺口仍以5倍价补购；因此它与Q1的已知供需无储能基线不同。

## 5. 334天实际结果与不支持的改进结论

三条策略均有48096个十分钟执行区间，输入信息、价格、评价日期和初始SOC一致。

{metric_table}

selected比seasonal的实际总费**增加{gap:.6f}元（{gap/seasonal.total_cost_yuan*100:.4f}%）**。其计划费减少{seasonal.planned_cost_yuan-selected.planned_cost_yuan:.6f}元，但紧急费增加{selected.emergency_cost_yuan-seasonal.emergency_cost_yuan:.6f}元，后者超过前者。紧急电量增加{selected.emergency_kwh-seasonal.emergency_kwh:.6f} kWh。不能只报告日前计划费下降，或把1月表现误写为全年收益。

selected相对同预测无储能对照的实际费用减少{none.total_cost_yuan-selected.total_cost_yuan:.6f}元（{(none.total_cost_yuan-selected.total_cost_yuan)/none.total_cost_yuan*100:.4f}%），但期末库存不同。分别报告原始账单和库存调整比较：selected为{selected.inventory_adjusted_cost_yuan:.6f}元，seasonal为{seasonal.inventory_adjusted_cost_yuan:.6f}元，no_storage为{none.inventory_adjusted_cost_yuan:.6f}元。该代理调整不改变两条储能策略的优劣方向，也不能宣称是真实发生的补充交易。

预测层面，selected负荷MAE为{selected.load_mae_kwh:.6f} kWh/区间，seasonal为{seasonal.load_mae_kwh:.6f}；selected光伏MAE为{selected.pv_mae_kwh:.6f}，seasonal为{seasonal.pv_mae_kwh:.6f}。selected光伏RMSE较低但MAE较高，误差指标与经济收益不一致。实际PV>0时段的分组仅用于事后诊断，未进入预测决策。

图1展示各月计划费、紧急费及季节基线，正的差额表示selected更贵。这是事后诊断，不用于修改已冻结选型。

![图1：月度实际费用与基线](figures/modelviz_v3_en/monthly_costs/outputs/chart.png)

最高紧急费用日及费用分解另可从daily.csv追溯；例如6月1日、6月2日、7月6日存在较大紧急购电。当前证据说明1月样本不足以支持全年固定候选组合优越性，并提示需要研究净负荷偏差风险与执行阶段储能分配。尚未通过对照证明是哪一个改进能解决问题，因此不虚构原因的因果贡献。

## 6. 四个指定日期、完整结果与验证

完整表1、表2及合并连续区间的表3见 [q2_representative_tables.md](q2_representative_tables.md)。表1为0点计划购电，表2和首末储能为实际执行，全天计划费、紧急费、总费分列。原始十分钟紧急量、合并事件与四个指定日期都有独立CSV，合并仅连接同一天连续十分钟区间并逐组读回核对。

![图2：指定日期计划/实际SOC与紧急购电](figures/modelviz_v3_en/representative_execution/outputs/chart.png)

`validate_q2.py`不导入调度或回放脚本，从保存文件独立核算了**{count}项检查，全部通过**。selected实际供需最大残差{residual['actual_balance']:.3g} kWh，计划供需残差{residual['plan_balance']:.3g} kWh，实际状态递推和跨日连续性残差均为0（当前浮点读回精度）。核验包括真实源数据、固定价、供需/储能、功率/容量/互斥、完整承诺计费、紧急5倍费、弃光/未用购电拆分、逐日计划首末、所有指定日期表、元数据可用时间、每个保存预测的重构以及固定审计日期的独立参数重估。5项单元测试覆盖功率和紧急量、满电时富余拆分、禁用电池和容量下限、拒绝未来历史及季节滞后。

全年缺失预测只允许冷启动1月1日；2—12月均有完整预测。输入、配置和运行代码SHA-256与运行开始一致。模型系数和状态在models_and_solvers.json，逐时计划/实际双轨迹在ledger.csv；daily.csv、summary.json给出独立核对过的日及全期汇总。数值可行不代表预测误差风险已处理妥当。

## 7. BZD局部模型求解检查与剩余工作

| 板块 | 结论 | 证据与限制 |
|---|---|---|
| 目标—数据—模型—执行—评价 | 基础闭环已完成 | 334天，计划和真实执行分离，费用逐项结算 |
| 任务输出 | 内部数据完成，正式模板未完成 | 四日表、全期策略/紧急量/SOC齐备；时间映射未决 |
| 算法适配与复现 | 合理 | Q1 MILP复用，历史OLS/谐波参数可追溯，完整运行状态 |
| 模型检验 | 通过 | 独立读回、历史边界、固定日期独立重估、反例测试 |
| 收益/泛化 | **不支持改进有效** | selected比seasonal贵约95.55万元；不得据此事后换模型冒充原决策 |
| 灵敏度/风险 | 本轮证据不足 | Q1效率对照已有；Q2未扩展效率、窗口或分位风险实验，不声称鲁棒 |
| 跨问传递 | 已落实Q1物理接口 | 实际SOC连续；Q3/Q4未实现，不套用调整费 |

最高优先级是保留这份失败对照，下一阶段可用严格过去窗口进行逐月/滚动候选选择，或引入既定方案中的净负荷风险校准；两者都须预先定义规则并与当前基础版比较。不要根据全年结果直接把某模型写成2月1日的已知最佳。初始化、日循环计划和库存代理的假设应继续保留，正式Excel仍待映射确认。全文、格式和AI声明未进入终稿审查，不评分。

## 8. 运行与产物索引

```bash
cd /Users/justingao/Documents/CUMCM/C题工作区
export PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$PWD/data/interim/q2"
.venv/bin/python scripts/run_q2.py > logs/q2/run.log 2>&1 &&
.venv/bin/python scripts/validate_q2.py > logs/q2/validate.log 2>&1 &&
.venv/bin/python -m unittest discover -s tests -p test_q2.py > logs/q2/tests.log 2>&1 &&
.venv/bin/python scripts/report_q2.py > logs/q2/report.log 2>&1
```

配置：configs/q2_baseline.json及物理配置快照；模型适配：reports/q2_model_fit.md；初始化：results/q2/warmup；校准：results/q2/calibration及selection.json；334天结果：selected、seasonal、no_storage子目录；独立验证：validation.json；合并事件核验：report_validation.json。没有覆盖问题1冻结包、已处理数据或其他成员代码，也没有正式result2.xlsx或问题3—4结果。

AI协助范围：整理Q1可追溯包和论文初稿；实现Q2预测、调度调用、回放、测试、独立验证、绘图与本报告；所有数值由本地实际执行生成。独立验证仍是同一AI协助编写的单独实现，不冒充第三方审计。尚未作真实微网试验、外部文献核查或期望成本最优性证明。
'''
    (WORK/'reports/q2_model_and_results.md').write_text(report)
    artifacts=[p for p in out.rglob('*') if p.is_file()]
    artifacts+=list((WORK/'reports').glob('q2_*.md'))+[p for name in ['monthly_costs', 'representative_execution'] for p in (figures/name).rglob('*') if p.is_file()]
    artifacts+=[WORK/p for p in ['scripts/run_q2.py','scripts/validate_q2.py','scripts/report_q2.py',
                               'tests/test_q2.py','configs/q2_baseline.json','reports/workflow_progress.md']]
    manifest={str(p.relative_to(WORK)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(artifacts)}
    (WORK/'logs/q2/artifact_hashes.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print('Q2 report, representative tables, two figures and merged emergency event audit generated.')


if __name__=='__main__': main()
