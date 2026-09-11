"""Render supplemental evidence from saved results; no optimization or selection."""
import hashlib
import json
from pathlib import Path
import pandas as pd
WORK=Path(__file__).resolve().parents[1];R=WORK/'results/robustness';REPORT=WORK/'reports/robustness'
LABELS={'fixed_w14_vs_raw':'固定价：14天','fixed_w28_vs_raw':'固定价：28天（主方案）','fixed_w56_vs_raw':'固定价：56天','efficiency_w28_vs_raw':'各sqrt(0.9)：28天','soft_w28_vs_raw':'软终态：28天','variable_w28_vs_raw':'波动价：28天'}

def read(p):return pd.read_csv(p,float_precision='round_trip')
def load(p):return json.loads(p.read_text())
def fmt(x):return f'{x:,.2f}'
def table(headers,rows):return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+''.join('| '+' | '.join(map(str,row))+' |\n' for row in rows)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    validation=load(R/'validation.json');lp=load(R/'lp_audit.json');analysis=load(R/'analysis_validation.json');status=load(R/'run_status.json')
    assert validation['passed'] and lp['passed'] and analysis['passed'] and status['completed']
    s=read(R/'paired_summary.csv');s=s.loc[s.scope=='april_december'].set_index('comparison_id')
    all_s=read(R/'paired_summary.csv');full=all_s.loc[all_s.scope=='february_december'].set_index('comparison_id')
    m=read(R/'paired_monthly.csv');b=read(R/'bootstrap_intervals.csv');daily=read(R/'paired_daily.csv')
    main_s=s.loc['fixed_w28_vs_raw'];main_full=full.loc['fixed_w28_vs_raw'];main_m=m.loc[(m.scope=='april_december')&(m.comparison_id=='fixed_w28_vs_raw')]
    neg=main_m.loc[main_m.cash_gain_yuan<0];pos=int((main_m.cash_gain_yuan>0).sum())
    comparisons=table(['对照设置','原始PV费用/元','校正PV费用/元','节省/元','节省率/%','库存修正后节省/元'],[
        [LABELS[k],fmt(row.raw_total_cost_yuan),fmt(row.corrected_total_cost_yuan),fmt(row.cash_gain_yuan),f'{100*row.cash_gain_yuan/row.raw_total_cost_yuan:.4f}',fmt(row.inventory_adjusted_gain_yuan)] for k,row in s.iterrows()])
    stability=table(['设置','省费日','增费日','持平日','最差日','最差日省费/元'],[
        [LABELS[k],int(row.winning_days),int(row.losing_days),int(row.tie_days),row.worst_day,fmt(row.worst_daily_gain_yuan)] for k,row in s.iterrows()])
    intervals=table(['设置','方法','块长/日','累计省费/元','2.5%分位/元','97.5%分位/元'],[
        [LABELS[row.comparison_id],'月内移动块' if row.method=='moving_block' else '月内循环块（追加对照）',row.block_days,fmt(row.point_estimate_yuan),fmt(row.lower_95_yuan),fmt(row.upper_95_yuan)] for row in b.itertuples()])
    monthly=table(['月份','原始PV费用/元','校正费用/元','节省/元','累计节省/元'],[
        [row.month,fmt(row.raw_total_cost_yuan),fmt(row.corrected_total_cost_yuan),fmt(row.cash_gain_yuan),fmt(row.cumulative_cash_gain_yuan)] for row in main_m.itertuples()])
    f7=b.loc[(b.comparison_id=='fixed_w28_vs_raw')&(b.method=='moving_block')&(b.block_days==7)].iloc[0]
    positive=int((s.cash_gain_yuan>0).sum());n=len(s)
    cash_direction='均为正' if positive==n else f'{positive}/{n}组为正，不能概括为所有情景均有效'
    lines=[f'''# 连续策略、敏感性与收益稳定性：论文增补初稿

> 内部、回顾性结果，已实际计算并独立复核；不是未经确认即可提交的正式版。原五份初稿保持不变。本文的“全年”如使用，仅指题面要求的2—12月334日，绝非365日。

## 1. 把分阶段创新变成一条连续策略

最终部署规则明确为：2025年2—3月使用原始PV，按既有3月校准选择于4月1日启用28天、按发布小时分组的因果均值偏差校正；0/6/12/18点正常更新，不加风险余量或更新门槛。每一步沿用真实执行后的SOC，跨月和4月切换处均不重置。以同一2月1日初值7268.4231640740745 kWh重新运行10条完整334日政策，保留每版计划、实际账本和四个指定日表。

固定价格A规则下，原始策略2—12月实际成本为 **{fmt(main_full.raw_total_cost_yuan)}元**，28天部署策略为 **{fmt(main_full.corrected_total_cost_yuan)}元**，减少 **{fmt(main_full.cash_gain_yuan)}元（{100*main_full.cash_gain_yuan/main_full.raw_total_cost_yuan:.4f}%）**。2—3月两者轨迹相同；4月1日共同SOC为{main_s.raw_initial_energy_kwh:.9f} kWh。4—12月原始/校正费用分别为{fmt(main_s.raw_total_cost_yuan)}和{fmt(main_s.corrected_total_cost_yuan)}元，该段节省率{100*main_s.cash_gain_yuan/main_s.raw_total_cost_yuan:.4f}%。这是完整新回放的差额，不是将不同初态的历史分段账单相减。

原始/校正年末SOC分别为{main_s.raw_end_energy_kwh:.6f}和{main_s.corrected_end_energy_kwh:.6f} kWh。统一以已知固定价均值×0.9={main_s.inventory_value_yuan_per_kwh:.9f}元/kWh作库存代理，4—12月修正后节省{fmt(main_s.inventory_adjusted_gain_yuan)}元，仍与现金账单分开列示。

## 2. 参数与假设敏感性

14/28/56天是基准28天窗口的减半/加倍对照，不因后续结果重选窗口。效率两种解释对应各0.9与各sqrt(0.9)；后者固定同一2月初态、未重新做另一套1月预热。软终态用同一λ惩罚计划末态偏离，替代额外硬日循环；双方均改变同一约束，以便识别校正的增量。变价对照只用于Q4-3，规划读取既有因果OLS价，实际收费读取附件4目标区间价格，Q4-2不引入附件3PV。

各组均报告4—12月成对费用，不能跨不同效率/终态/价格直接比较校正贡献：

{comparisons}

本次6组校正增量{cash_direction}。这是已计算设置上的方向检查，不是所有参数组合、所有年份或任意预测扰动下的保证；没有把最佳窗口替换为主方案。软/硬终态之间的总费用变化也不能算成PV校正贡献。

## 3. 收益不是每天都出现

{stability}

主28天方案9个月中{pos}个月省费；增费月份为{'; '.join(row.month+'：省费'+fmt(row.cash_gain_yuan)+'元' for row in neg.itertuples()) if len(neg) else '无'}。最差日为{main_s.worst_day}，当日校正多付{-main_s.worst_daily_gain_yuan:,.2f}元；最好日为{main_s.best_day}，省{fmt(main_s.best_daily_gain_yuan)}元。因此应写“累计费用降低、日月表现有波动”，不能写“每日稳定降低成本”。

{monthly}

费用机制可直接重算：主方案常规合同费相对原始方案变化为{-main_s.contract_cost_gain_yuan:,.2f}元，紧急费变化为{-main_s.emergency_cost_gain_yuan:,.2f}元，紧急购电减少{main_s.emergency_energy_reduction_kwh:,.2f} kWh。两项费用变化之和等于总账单变化，收益不等同于所有发布时刻的预测误差均改善。

## 4. 按连续日期分块的不确定性分析

设日级配对省费Δ_d=J_raw,d−J_corr,d。按月份分层，每月抽取连续日期块，有放回拼接并截断到该月原天数；保持9个月样本构成，不独立重抽十分钟点。主设计块长3/7/14日，各5000次，固定种子20260910，累计省费的2.5%和97.5%分位构成95%重抽样区间。3、7、14日覆盖短期、周及双周依赖尺度；报告全部结果，未按是否跨零选方法。

官方arch文档指出非循环移动块降低边缘观测的抽中概率；因此在本轮最终运算前另加7日月内循环块对照，详见design_addendum.md。循环块人为连接月末和月初，并非更真实的日历路径。两者都切断跨月相关，只有9个月历史，不能假定对任意季节结构都有效。

{intervals}

主28天方案7日移动块区间为 **[{fmt(f7.lower_95_yuan)}, {fmt(f7.upper_95_yuan)}]元**。表中区间是给定历史轨迹与重抽方法下的波动描述，不能称为未来收益95%保证、未触及测试集结论或分布无关鲁棒性证明。这里抽的是已实现的日费用，没有在每条重抽样序列上重新训练和执行电池，不是新增物理压力场景。正省费重抽比例只作描述，不解释成p值。

## 5. 独立验证与复现边界

新验证器不导入规划、校正或实际执行模块，独立检查全部实际/计划守恒、SOC递推、功率/容量/互斥、连续初态、费用分解、校正源与截止、价格来源、更新版本、表1/2/3和紧急事件。**{validation['check_count']:,}项检查通过**，最大记录核对残差为{validation['max_residual']:.3e}（不同量纲汇总，仅作日志上界；各项阈值见验证器）。原始PV轨迹与既有Q3基线吻合，全部10条政策的4月前成对路径一致，输入及代码前后哈希一致。

对10策略×4个代表日期（4月1日、6月21日、9月23日、12月21日）×4时刻构造**{lp['sample_count']}个独立稀疏LP下界**，全部通过；MILP−LP最大差{lp['maximum_relaxation_gap_yuan']:.6f}元，LP最大原始可行误差{lp['maximum_lp_primal_violation']:.3e}。不将LP下界贴合或不贴合混称为全年真实费用最优；两个接口底层仍同属HiGHS。

分析脚本核验6组配对、334/275日期范围、合同/紧急费差额分解、日胜负计数及24条Bootstrap输出。随机性只来自明确种子下的重抽样；MILP参数沿用既有配置。

## 6. 写入论文的位置与表达

- Part06.5放PV校正公式、信息截止、3月选择与4月启用，以及连续部署成本。它是原预测—MILP—反馈链条中的小幅改进。
- Part07.5放Q4-3迁移成对结果；不要将不同价格下的总账单差额当作预测或创新收益。
- Part08放本增补的连续验证、参数对照、日月收益与分块区间。每一问提供相关验证，共用物理检验集中写；不要求每一問重复完整敏感性/Bootstrap。
- Part09保留Q2选型失败、风险余量仅2—5元、门槛增费及回顾性局限。原完整创新表放附录B。

建议表述：“在当前A结算、交流侧功率及因果信息假设下，按发布时刻作滚动PV偏差校正，使连续回放的累计实际费用下降；窗口、效率、终态和价格对照用于界定该结果的稳定范围。月度及日级效果存在反例，历史分块区间不作跨年保证。”

## 7. 英文图形

图S-1并列显示六组现金省费、库存代理及7日分块区间；3/14日与循环块数值完整保留上表。图S-2显示28天主策略每月成本及正负省费，未平滑、移位或隐藏亏损月份。

![Sensitivity comparisons]({WORK}/reports/figures/modelviz_robustness_v1_en/robustness_effects/outputs/chart.png)

![Monthly stability]({WORK}/reports/figures/modelviz_robustness_v1_en/robustness_monthly/outputs/chart.png)

## 8. 命令与结果入口

在 /Users/justingao/Documents/CUMCM/C题工作区 运行：

```bash
.venv/bin/python -B scripts/validate_robustness.py
.venv/bin/python -B scripts/audit_robustness_lp.py
.venv/bin/python -B scripts/analyze_robustness.py
.venv/bin/python -B scripts/report_robustness.py
.venv/bin/python -B scripts/assemble_paper.py
```

从空的新版本副本求解使用scripts/run_robustness.py；完成结果受覆盖保护。配置configs/robustness.json；10组逐段文件results/robustness/<policy>/；汇总paired_summary.csv、paired_monthly.csv、paired_daily.csv；bootstrap_intervals.csv；验证validation.json和lp_audit.json。精确运行日志、单测报告、设计补充与图形实际质检一并保留。

正式模板时间映射及市场/效率口径尚待确认，仍无正式Excel。已有证据可进入终稿的结果和检验章节，但应使用本稿限定语，并完成全文符号、引用、AI使用材料及最终格式检查。
''']
    text='\n'.join(lines);(WORK/'papers/robustness_draft.md').write_text(text);(REPORT/'model_and_results.md').write_text(text)
    report_inputs=[R/'paired_summary.csv',R/'paired_monthly.csv',R/'paired_daily.csv',R/'bootstrap_intervals.csv',R/'validation.json',R/'lp_audit.json',R/'analysis_validation.json',WORK/'scripts/report_robustness.py']
    (REPORT/'report_lineage.json').write_text(json.dumps({str(p.relative_to(WORK)):sha(p) for p in report_inputs},indent=2)+'\n')
    print('Supplement draft created from passed saved results',fmt(main_full.corrected_total_cost_yuan))

if __name__=='__main__':main()
