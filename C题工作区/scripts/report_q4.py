"""Create Q4 result explanation, complete prescribed-day tables and paper draft."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import report_q3 as tables

WORK=Path(__file__).resolve().parents[1];OUT=WORK/'results/q4'
LABELS={'q42_fixed':'4-2 固定价输入','q42_ols':'4-2 因果OLS价格','q42_perfect':'4-2 完美价格（假想）',
    'q43_no_update_ols':'4-3 仅0点/OLS','q43_all_A_ols':'4-3 全更新A/OLS','q43_all_B_ols':'4-3 全更新B/OLS',
    'q43_all_A_hold0':'4-3 全更新A/价格保持0点','q43_all_A_fixed':'4-3 全更新A/固定价输入',
    'q43_all_A_perfect':'4-3 全更新A/完美价格（假想）'}
tables.OUT=OUT;tables.LABELS=LABELS
read=tables.read;num=tables.num;table=tables.table

MODEL=r"""## 1. 信息结构与跨问题继承

问题4要求在实际波动电价下重算问题2、问题3。附件4只有每个目标区间的实际价格，未说明提前公开，也没有每次交易时刻的远期报价。因此本稿主分支采用未来价格未知、区间结束后才观测实际价的解释；另设提前知道全部目标价格的假想对照，不能与可实施策略混称。常规购电和调整量均按目标区间实际价结算，没有提前锁价；这一市场解释仍待人工确认。

评价期2025年2月1日至12月31日，共334天、48,096个十分钟区间。Q4-2继承Q2选中模型的每日0点负荷和历史PV预测；Q4-3使用同一负荷预测及附件3在0/6/12/18点精确发布的PV版本。负荷模型不因已看过全年结果重新选择，Q2负结果保留。Q4-3仅0点对照使日内更新的比较双方具有相同PV来源；不能把Q4-2到Q4-3的全部差额视为更新收益。

所有策略从Q2共同1月预热所得的2月1日7,268.423164 kWh状态出发，再各自连续递推。本轮没有按波动价格重新做各策略的1月初始化，这是继承比较的初态假设。每次计划仍以当天0点实际储能为24点目标，日内只改变规划初态，实际电量从不重置；Q2—Q4的每日循环目标是额外基线限制，不能冒充题面明示约束。

原数据标签按区间终点解释，例如00:10对应[00:00,00:10)，未平移、循环移位或填补未来数据。正式模板时间映射未确认，本稿和所有CSV是内部假设版，未生成正式result4-2.xlsx、result4-3.xlsx。

## 2. 因果价格预测

令$u$为十分钟区间起点，以该点的钟点相位$\phi_u$及星期构造已知日历特征。价格回归沿用统一方案的少参数结构：

$$\widetilde p_{u|k}=\beta_0+\sum_{j=1}^{2}\{a_j\sin(2\pi j\phi_u)+b_j\cos(2\pi j\phi_u)\}+\beta_1p_{u-1\mathrm d}+\beta_7p_{u-7\mathrm d}+\sum_{r=1}^{6}\gamma_r\mathbf1\{\mathrm{weekday}(u)=r\}.$$

共13个特征，星期省略一个基准。每个允许决策时刻$k$，只取最近28天内、且区间结束不晚于$k$的训练目标，要求每个训练行已有7天历史滞后；用最小二乘lstsq拟合，不计算矩阵逆，不把有时间相关性的区间当作独立样本做t检验。预测目标只到当天24点，因此其昨日和上周滞后在当前时刻都已知。日内更新可使用当天已结束区间的实际价格，但禁止当前未结束区间或未来价格进入回归。

规划采用$\widehat p_{u|k}=\max\{10^{-6},\widetilde p_{u|k}\}$，单位元/kWh。下限是计算前固定的严格正价数值规则，不是由全年最低价格估计；所有触发逐版记录。上周同期价格作为无参数误差对照，不凭它在评价期表现重新选型。价格保持0点的消融在日内继续使用0点回归预测向量，只更新PV和实际储能。

## 3. 优化与实际结算分离

重用Q3 MILP。$q_t^0$为0点原承诺，$q_t^k$为允许时刻更新后的承诺，$c_t,b_t,w_t$为交流侧充、放、富余处置电量，$E_t$为内部储电量。十分钟能量约束保持

$$q_t^k+\widehat G_{t|k}+b_t=\widehat L_t+c_t+w_t,\quad E_{t+1}=E_t+0.9c_t-b_t/0.9,$$
$$1200\le E_t\le10800,\quad0\le c_t\le(5000/6)z_t,\quad0\le b_t\le(5000/6)(1-z_t),\quad z_t\in\{0,1\}.$$

购电和无收益处置非负，不向外售电。免费处置包括未使用的已付费合同电量。Q4只继承Q1物理配置中的电池、步长、求解参数，处置规则沿用Q3，不受Q1配置叙述字段“仅弃光”约束。已执行区间冻结，更新规划只到本日24点。

Q4-2在0点最小化$\sum_t\widehat p_{t|0}q_t^0$。Q4-3在允许时刻最小化剩余区间的分段合同费：
$$F_A(q;q^0,p)=pq^0+1.5p(q-q^0)_+-0.5p(q^0-q)_+,$$
$$F_B(q;q^0,p)=pq^0+1.5p(q-q^0)_++0.5p(q^0-q)_+.$$
A为取消原款退还后收50%违约费，B为原款保留再收50%。用Q3的凸分段上图形式线性化；B下$q\ge q^0$由自由处置的支配关系保证不损最优性。预计紧急购电仍被无限额、最多1.5倍边际价的常规增购支配，故规划不额外设置紧急通道。

实际执行沿用同一准静态贪心反馈：合同电加实际PV若有富余，按功率和容量上限充电后处置；不足时按功率和SOC上限放电，剩余缺口$e_t$紧急补购。规划阶段不用未来真实缺口，账单阶段才使用实际价格：

$$J_{4-2}=\sum_t p_t^{\rm actual}(q_t^0+5e_t),$$
$$J_{4-3}=\sum_t\{F(\bar q_t;q_t^0,p_t^{\rm actual})+5p_t^{\rm actual}e_t\}.$$

$\bar q_t$为该区间最终执行的有效承诺。相对0点原量每段只结算一次，不相加6/12/18点的整段目标。未用合同量也付费，预测价绝不直接代替账单实际价。完美价格情景只替换规划价格，仍有负荷/PV误差和同一执行器，因此它不是全信息最优调度，不是实际费用下界。

## 4. 实验组织

固定九组策略：Q4-2固定价输入、因果OLS、完美价格；Q4-3 OLS仅0点、OLS全更新A/B、A下价格保持0点、A固定价输入和A完美价格。所有实际账单均用同一套附件4实际价。“固定价输入”表示仍按附件1制定决策，不表示按附件1付费。

这是在已查看Q2/Q3全年结果之后开展的回顾性计算，没有未触及测试集上的选优声明。对照在本次Q4计算前固定，不把表现较好的事后曲线替换主策略。完整保存各时域价格输入、预测、状态、购电承诺、求解界及实际账本。库存修正采用已知附件1平均价乘放电效率，仅作末态比较代理，不把全年未来平均实际价用于控制。

"""


def main():
    audit=json.loads((OUT/'validation.json').read_text());lp=json.loads((OUT/'independent_lp_audit.json').read_text())
    assert audit['passed'] and lp['passed']
    comp=read(OUT/'comparison.csv');r=comp.set_index('policy')
    actual=read(WORK/'data/processed/actual_10min.csv');actual.index=pd.to_datetime(actual.interval_start)
    forecasts=read(OUT/'price_forecasts.csv');forecasts['issue_time']=pd.to_datetime(forecasts.issue_time)
    truth=actual.loc[pd.to_datetime(forecasts.interval_start)].actual_price_yuan_per_kwh.to_numpy()
    forecasts['actual_price_yuan_per_kwh']=truth
    errors=[]
    for hour,f in forecasts.groupby(forecasts.issue_time.dt.hour):
        for label,col in [('OLS','price_forecast_yuan_per_kwh'),('lag7','lag7_forecast_yuan_per_kwh')]:
            err=f[col]-f.actual_price_yuan_per_kwh
            errors.append({'issue_hour':hour,'model':label,'interval_count':len(f),'mae_yuan_per_kwh':float(err.abs().mean()),'rmse_yuan_per_kwh':float(np.sqrt((err**2).mean()))})
    error=pd.DataFrame(errors);error.to_csv(OUT/'price_error_summary.csv',index=False)
    cost_table=table(['策略','实际总费/元','合同费/元','紧急费/元','紧急量/kWh','较同分支固定输入节省/%','期末储电/kWh'],
        [[LABELS[x.policy],num(x.total_cost_yuan),num(x.contract_cost_yuan),num(x.emergency_cost_yuan),num(x.emergency_kwh),f'{x.saving_percent_vs_branch_fixed:.3f}',num(x.final_energy_kwh)] for x in comp.itertuples()])
    error_table=table(['发布时刻','模型','同一剩余时域段数','MAE/元每kWh','RMSE/元每kWh'],
        [[f'{x.issue_hour:02d}:00',x.model,x.interval_count,f'{x.mae_yuan_per_kwh:.6f}',f'{x.rmse_yuan_per_kwh:.6f}'] for x in error.itertuples()])
    q42=r.loc['q42_ols'];q43=r.loc['q43_all_A_ols'];q43b=r.loc['q43_all_B_ols'];hold=r.loc['q43_all_A_hold0']
    no_update=r.loc['q43_no_update_ols'];fixed42=r.loc['q42_fixed'];fixed43=r.loc['q43_all_A_fixed']
    price_models=json.loads((OUT/'price_models.json').read_text())
    floor=sum(m['floor_activations'] for m in price_models)
    daily={policy:read(OUT/policy/'daily.csv').set_index('date') for policy in comp.policy}
    perfect_worse=int((daily['q42_perfect'].total_cost_yuan-daily['q42_ols'].total_cost_yuan>1e-6).sum())
    old=read(WORK/'results/q2/selected/ledger.csv');p=actual.loc[pd.to_datetime(old.interval_start)].actual_price_yuan_per_kwh.to_numpy()
    old_repriced=float(((old.grid_plan_kwh+5*old.emergency_kwh)*p).sum())
    month=[]
    for policy,f in daily.items():
        m=f.groupby(pd.to_datetime(f.index).strftime('%Y-%m'))[['total_cost_yuan','contract_cost_yuan','emergency_cost_yuan']].sum().reset_index()
        m=m.rename(columns={m.columns[0]:'month'});m['policy']=policy;month.append(m)
    pd.concat(month,ignore_index=True).to_csv(OUT/'monthly_comparison.csv',index=False)
    max_balance=max(max(v for k,v in a['max_residuals'].items() if k.endswith('_balance')) for a in audit['policies'].values())
    runtime=[]
    for x in comp.itertuples():
        meta=json.loads((OUT/x.policy/'solvers.json').read_text());duration=[m['solver']['runtime_seconds'] for m in meta]
        runtime.append([LABELS[x.policy],x.solves,f'{sum(duration):.3f}',f'{max(duration):.4f}',f'{x.max_mip_gap:.3e}'])
    runtime_table=table(['策略','求解次数','累计求解器秒','单次最大秒','最大gap'],runtime)
    analysis=f"""## 5. 实际结果与解释

{cost_table}

表中Q4-2统一以q42_fixed为参照，Q4-3统一以全更新A/固定价输入为参照。B行还改变退款规则，仅0点行还改变更新机制，因此这些行的百分比不是单独的价格预测贡献；正文只用规则和机制匹配的对照解释价格收益。

Q4-2因果OLS价格的实际费用为{num(q42.total_cost_yuan)}元，比同核固定价输入对照减少{num(fixed42.total_cost_yuan-q42.total_cost_yuan)}元（{q42.saving_percent_vs_branch_fixed:.3f}%）。Q4-3全更新A为{num(q43.total_cost_yuan)}元，比其固定价输入对照{'减少' if fixed43.total_cost_yuan>=q43.total_cost_yuan else '增加'}{num(abs(fixed43.total_cost_yuan-q43.total_cost_yuan))}元（节省率{q43.saving_percent_vs_branch_fixed:.3f}%）。这才是在相同实际收费条件下价格适配的效果；不能将Q4与原固定价Q2/Q3账单的全部差额解释成策略变化。

Q4-3全更新A相对同为附件3光伏来源的仅0点OLS基线，节省{num(no_update.total_cost_yuan-q43.total_cost_yuan)}元，比例{100*(no_update.total_cost_yuan-q43.total_cost_yuan)/no_update.total_cost_yuan:.3f}%。其中同时包含PV版本更新、实际SOC反馈和价格再拟合，不等于纯价格或纯PV信息收益。Q3已证明SOC反馈是重要来源，本题没有将这些作用全部归给价格模型。

每次重估价格的A策略相对保持0点价格预测的A策略，实际费用差为{num(q43.total_cost_yuan-hold.total_cost_yuan)}元（正值为更贵）。这项小差额不支持“价格越频繁更新越省钱”；两组都使用最新PV及实际SOC，并按同一收费机制结算。保留此负结果，不在报告阶段调参使其转正。

B口径费用为{num(q43b.total_cost_yuan)}元；B减购不能获得原款退款，模型不会主动把承诺降到0点原量以下。A/B的总账单差还受各自连续状态和紧急电量影响，不能把不同轨迹的总费比较误当作同一交易量下收费函数的大小比较。

完美价格Q4-2费用{num(r.loc['q42_perfect','total_cost_yuan'])}元，比OLS全年差{num(r.loc['q42_perfect','total_cost_yuan']-q42.total_cost_yuan)}元，但有{perfect_worse}天的实际费用反而更高。即使规划价格准确，净负荷预测误差和贪心补救仍可能造成不利轨迹；本稿不把完美价格对照称为真实费用下界。

本轮固定价输入对照统一使用Q3求解核。旧Q2已冻结动作按实际价重计为{num(old_repriced)}元，与本轮q42_fixed相差{num(fixed42.total_cost_yuan-old_repriced)}元。物理模型在严格正价下的最优费用可一致而轨迹未必唯一，求解表示及后续状态反馈可能使重算轨迹不同；因此不把旧动作重计价与本轮同核对照混用。旧账本本身未修改。

## 6. 价格误差与数值验证

{error_table}

同一行时域中的OLS/上周对照可以比较；不同发布时刻的剩余时域和重复目标不同，不能把所有行当独立样本。共1,336次价格拟合，正价数值下限实际触发{floor}次；不存在由截断制造的本轮收益。所有回归矩阵和系数由不导入预测模块的验证器独立重建，每次训练截止、未来目标的可用滞后、版本数和价格序列均核对。

独立审计{audit['check_count']:,}项通过，包括全部价格模型及九组账本：实际与计划守恒、SOC递推、充放互斥、每日初态/固定日终目标、实际价计费、最新版本、0点原承诺、表1/2/3和相邻紧急事件展开。最大能量平衡残差{max_balance:.3e} kWh，检查阈值1e-6；费用汇总阈值1e-5元。全部输入和核心代码SHA-256前后保持一致。

36个指定日时域以独立稀疏矩阵LP核验，MILP减LP下界最大{lp['max_milp_minus_lp_yuan']:.3e}元，LP约束误差最大{lp['max_primal_violation']:.3e}。底层同属HiGHS，不是不同厂商算法验证，结论只限这些预测时域。新5项单测覆盖拒绝未来数据、常价预测、当前已完成价格影响、时域长度及实际价结算；全套Q1—Q4单测共25项。

{runtime_table}

全年共{int(comp.solves.sum()):,}次MILP、{int(comp.intervals.sum()):,}个实际执行段。Python3.12.14、highspy1.14.0、单线程、seed0、每次限时120秒、相对gap1e-9；所有状态Optimal。上述耗时是求解器内部时间，未包含回归、CSV读写和仿真，不代表端到端墙钟时间。扩展环境沿用requirements-q3.txt，实际版本日志另留在logs/q4。

## 7. 范围与剩余问题

已完成价格信息情景、固定价决策对照、A/B规则及保持0点价格消融；没有Q4终态、效率、寿命费、预测误差扰动或通信延迟敏感性，不声称全面鲁棒。物理执行器是电量级准静态贪心补救，MILP最优不等于全年真实费用最优。库存残值代理与原账单分别保存，不能把代理费当电网账单。

未来价格是否可知、目标实际价或提前锁价、改购是否逐次收费、A/B退款、90%效率和功率侧别、额外日循环约束及正式时间模板仍需确认。下一步可先解决这些解释，再整合Q1—Q4论文、文献和AI使用清单；当前不做文章精修或虚构正式提交文件。

"""
    figures="""## 8. 英文图形

图4-1在相同实际收费口径下比较固定价输入和OLS输入，主图曲线接近时用差值柱显示小额收益。图4-2展示四个指定日实际价、0点价预测和按允许时刻更新的预测；实际价仅用于事后评价。

![Q4 monthly costs](figures/modelviz_q4_v1_en/q4_monthly/outputs/chart.png)

![Q4 causal price forecasts](figures/modelviz_q4_v1_en/q4_prices/outputs/chart.png)

两图按ModelViz模板候选、字段适配、执行和实际视觉复核生成，全部英文，300 dpi PNG和SVG，来源与质检在各图workspace。

"""
    commands="""## 运行与文件索引

在 `/Users/justingao/Documents/CUMCM` 运行；完成标记禁止覆盖现有求解。若完整重算，复制所需输入到新的版本工作区，不把旧results/q4放入新目录。

```bash
PYTHONDONTWRITEBYTECODE=1 C题工作区/.venv/bin/python C题工作区/scripts/run_q4.py
PYTHONDONTWRITEBYTECODE=1 C题工作区/.venv/bin/python C题工作区/scripts/validate_q4.py
PYTHONDONTWRITEBYTECODE=1 C题工作区/.venv/bin/python C题工作区/scripts/audit_q4_lp.py
PYTHONDONTWRITEBYTECODE=1 C题工作区/.venv/bin/python -m unittest discover -s C题工作区/tests -p 'test_q*.py'
PYTHONDONTWRITEBYTECODE=1 C题工作区/.venv/bin/python C题工作区/scripts/report_q4.py
PYTHONDONTWRITEBYTECODE=1 C题工作区/.venv/bin/python C题工作区/scripts/modelviz_q4.py quality
```

每个策略目录有ledger、plan_versions、solvers、daily、summary和指定表；price_forecasts.csv和price_models.json记录逐发布版本价格模型，price_error_summary.csv只作事后评估。完整指定日表包括Q4-2 OLS及Q4-3 A/B OLS，见reports/q4_representative_tables.md。原Q1—Q3及其冻结包保留。
"""
    all_tables='\n'.join(tables.representative(p) for p in ['q42_ols','q43_all_A_ols','q43_all_B_ols'])
    (WORK/'reports/q4_representative_tables.md').write_text('# 问题4指定日期完整表\n\n内部时间假设，不是正式Excel。\n\n'+all_tables)
    title='# 问题4：波动价格下的日前计划与日内调整\n\n可追溯内部结果和论文初稿；尚未精修，不是正式提交版。\n\n'
    (WORK/'reports/q4_model_and_results.md').write_text(title+MODEL+analysis+figures+'## 9. 指定日期完整结果\n\n'+all_tables+commands)
    (WORK/'papers/q4_draft.md').write_text(title+MODEL+analysis+figures.replace('(figures/','(../reports/figures/')+
        '## 9. 指定日期结果\n\n正文列Q4-2和Q4-3 A；B完整表在q4_representative_tables.md。\n\n'+tables.representative('q42_ols')+'\n'+tables.representative('q43_all_A_ols')+commands)
    metrics={'check_count':audit['check_count'],'solves':int(comp.solves.sum()),'execution_intervals':int(comp.intervals.sum()),
        'price_floor_activations':floor,'q42_ols_saving_yuan':float(fixed42.total_cost_yuan-q42.total_cost_yuan),
        'q43_ols_saving_yuan':float(fixed43.total_cost_yuan-q43.total_cost_yuan),
        'q43_updates_saving_yuan':float(no_update.total_cost_yuan-q43.total_cost_yuan),
        'q43_price_updates_extra_cost_yuan':float(q43.total_cost_yuan-hold.total_cost_yuan),
        'old_Q2_actions_repriced_yuan':old_repriced,'max_balance_kwh':max_balance,'perfect_price_worse_days_q42':perfect_worse}
    (OUT/'report_metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
    files=[OUT/'comparison.csv',OUT/'validation.json',OUT/'independent_lp_audit.json',OUT/'price_forecasts.csv',OUT/'price_models.json',WORK/'scripts/report_q4.py']
    (OUT/'report_sources.json').write_text(json.dumps({str(p.relative_to(WORK)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2)+'\n')
    print(json.dumps(metrics,indent=2))


if __name__=='__main__':main()
