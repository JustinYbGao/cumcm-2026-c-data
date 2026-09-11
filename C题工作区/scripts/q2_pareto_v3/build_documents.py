"""Generate reviewable Chinese research and paper drafts from actual final tables."""
import json
from pathlib import Path
import pandas as pd
WORK=Path(__file__).resolve().parents[2];VERSION='q2_pareto_v3';ROOT=WORK/'results'/VERSION;REPORT=WORK/'reports'/VERSION;PAPER=WORK/'papers'/VERSION
r=ROOT/'analysis_user_cap';t=pd.read_csv(r/'comparison_all.csv').set_index('policy')
a=json.loads((r/'acceptance_user_cap.json').read_text());name=a['best_observed_policy'];b=t.loc[name]
boot=pd.read_csv(r/'block_bootstrap.csv');counts=pd.read_csv(r/'win_loss_counts.csv');win=counts.loc[(counts.policy==name)&(counts.baseline=='P_floor')].iloc[0]
fmt=lambda x:f'{x:,.2f}'
short=[]
for n in ['B0','B1','P','P_terminal','P_floor','S_terminal','R_guard',name]:
 x=t.loc[n];short.append(f"| {n} | {fmt(x.planned_cost_yuan)} | {fmt(x.emergency_cost_yuan)} | {fmt(x.total_cost_yuan)} | {fmt(x.final_energy_kwh)} |")
short='\n'.join(short)
full=[]
for n,x in t.iterrows():
 full.append(f"| {n} | {x.planned_cost_yuan/10000:.4f} | {x.emergency_cost_yuan/10000:.4f} | {x.total_cost_yuan/10000:.4f} | {'是' if x.meets_user_emergency_cap else '否'} | {'是' if x.passes_user_requirement else '否'} |")
full='\n'.join(full)
ci=[]
for block in [7,14]:
 x=boot.loc[(boot.policy==name)&(boot.block_days==block)&(boot.component=='total_cost_yuan')].iloc[0]
 ci.append(f"{block}日块的95%区间为[{fmt(x.ci95_low_yuan)}, {fmt(x.ci95_high_yuan)}]元")
ci='；'.join(ci)
validation=[]
for f in ['independent_validation.json','independent_validation_extension_all.json']:
 p=REPORT/f;validation.append(f"{f}: "+('PASS' if p.exists() and json.loads(p.read_text())['passed'] else '最终汇总审查中'))
report=f'''# Q2费用继续优化研究：按用户100万元紧急费上限验收

本轮最低的合格历史回放为 **{name}**：普通费{fmt(b.planned_cost_yuan)}元，紧急费{fmt(b.emergency_cost_yuan)}元，总费用{fmt(b.total_cost_yuan)}元。相对上一版P_floor，普通费少{fmt(b.ordinary_saving_vs_P_floor_yuan)}元、紧急费少{fmt(b.emergency_saving_vs_P_floor_yuan)}元，合计少{fmt(b.total_saving_vs_P_floor_yuan)}元（0.20364%）；相对上一轮略优的S_terminal也少{fmt(b.total_saving_vs_S_terminal_yuan)}元。100万元上限余量为{fmt(1000000-b.emergency_cost_yuan)}元，这是已观察年度的余量，不是未来保证。

因此不能说已经降到头，也不能把本轮小幅领先写成稳定优越性。我们实际试了18条新路径，找到有限改进，同时发现继续整体减购常把普通费转成更贵的紧急费。现阶段更合理的结论是：原风险采购已取得大部分可见收益，分时配置还有少量改进，简单降低保守程度不单调降低总费；全球最优与未尝试方法仍未解决。

## 两轮标准与完整比较

最初用户要求紧急费不再上升，原协议用P_floor精确紧急费661273.6528153808元，并要求普通与总费同时减少，主方案预定为R_guard。原十条里只有R_guard满足三条件，省1530.586773元。用户随后明确允许紧急费≤1000000元、以总费用优先；我们保留原协议，再冻结八条追加分时曲线。新表以100万元作为上限，普通费不作为硬条件。观察最优{name}也满足旧P_floor三条件，但没有达到更早P的641845.279394元紧急费；相对P紧急费增加2446.89元，不能隐去。

所有方案使用2025-02-01至12-31共334天、48096段，相同7268.4231640740745kWh初态，随后各自连续。B0是原冻结点预测策略，B1为季节性强基线，P为旧0.8风险校准且计划终态等于日初态，P_terminal为固定6000，P_floor为固定1200。新方案统一计划终态1200，不能将相对B0/B1的全部改善归给本轮分时调整。

| 策略 | 普通费/元 | 紧急费/元 | 实际总费/元 | 实际末态/kWh |
|---|---:|---:|---:|---:|
{short}

本轮最好方案相对B0省{fmt(b.total_saving_vs_B0_yuan)}元（14.3226%），相对B1省{fmt(b.total_saving_vs_B1_yuan)}元（8.9993%）；这些差异包括此前风险校准和终态策略变化。隔离本轮增量应比较P_floor或S_terminal，分别约2.86万元、2.74万元。

以下全表金额为万元，四位小数；精确数值在analysis_user_cap/comparison_all.csv。“达到新要求”指紧急费≤100万元且总费严格低于P_floor。B0/B1、P等对照仍完整报告。

| 策略 | 普通费/万元 | 紧急费/万元 | 总费/万元 | 紧急≤100万元 | 达到新要求 |
|---|---:|---:|---:|---|---|
{full}

## 方法与原因

新固定方案沿用原点预测和原日前MILP，只按小时改变历史净负荷预测误差分位数。最终{name}在09:00—11:00取0.85，11:00—18:00取0.65，18:00—22:00取0.95，其他时段0.80。小时区间为左闭右开，残差来自过去28天当时发布预测，每小时汇总6×可用日样本，线性经验分位插值；不是以全年拟合误差，也不是将负荷/PV边缘分位机械相减。此曲线在追加实验前固定，但设计依据来自已看年度，因此属于事后诊断后的历史探索。

本年相对P_floor，普通合同电量少285054.12kWh，已买未用电量少240784.48kWh，已买未用部分的购电费从768060.46降到614122.14元。与此同时增加了晨间/晚间部分风险覆盖，普通费净降只剩11574.85元。未用电费用下降153938.32元是合同费内部变化，不能再和实际节省相加。紧急电量少6824.80kWh，紧急费少16981.49元。这是时段重分配和连续库存共同作用的结果，不是独立可加的机制贡献率。

调研还落实了有限情景选择：每天重解7个候选，使用过去56日（敏感性28日）整日联合净误差，逐段按原贪心执行模拟各情景。得分为普通费+经验平均紧急费−μ×经验平均库存变化，μ=0.38232元/kWh（午夜电价0.4248×0.9）。主R_guard限制候选普通费、平均紧急费和90%经验CVaR不高于同初态anchor、平均末态不低于anchor。样本内有保护，不保证真实日/月/年上限。R_mean去掉CVaR，R_cost去掉保护，R_w28缩短情景窗，结果都没有超过P_floor，复杂选择器本轮不能写成成功创新。

CVaR借鉴Rockafellar与Uryasev的辅助函数形式，精确处理离散尾部边界权重；微网风险调度与配网概率约束原文只提供方法启发，不引入其需求响应、弃负荷、额外机组、售电等本题没有的权限。原始来源与BZD逐项适配见method_fit_and_workflow.md，两个字典单记录保留BZD数模社制作署名和原许可。28/56日的90%尾部仅约3—6个等效日，不宜将经验风险估计当总体风险真值。

## 消融、敏感性和失败

只在11—18时从0.8降至0.7（T_day_trim），普通费下降185504.19元，但紧急费增加192258.45元，总费反而增加6754.26元。只提高晚间到0.9（T_evening_hedge），紧急费下降129685.46元，但普通费增加120110.57元，总费小降9574.89元。两者合并、soft/strong以及晨间补偿各有连续轨迹；不能把单项差值简单相加。

继续把白天降到0.6（X_day60）总费只省6790.05元，弱于0.65的T_strong；降到0.5（X_day50）总费增加87576.20元且紧急费1012398.77元，违反新上限。整体0.70（X_uniform70）紧急费1227152.59元且总费增加104050.34元；整体0.75虽紧急费在上限内，总费仍高于P_floor。X_evening85_day60紧急费999283.31元，几乎耗尽上限，但总费仍更高。不能因为紧急费额度尚有余额，就把它花满。

原十条和追加八条全部保留，无失败删除、阈值舍入放行、日内正常价补购或期末状态拼接。18条新路径中10条满足新要求、8条不满足；不满足可能是总费未下降、超限或两者兼有。

## 可信范围与验收证据

所有新增年度共14028个候选MILP；原十条11356、追加八条2672，另有一月148候选门槛。所有求解失败和回退为0，候选的最优性只指确定性日前MILP。独立验证器只依赖标准库、NumPy与pandas，不导入生产预测/评分/求解/执行器；从源预测、所有候选与情景，到实际逐段物理和费用重新核算。物理1e−6kWh、汇总1e−5元阈值保持不变。最终状态：{'；'.join(validation)}。

未来扰动测试覆盖全部18个配置：将Jan25 12:00后原始负荷加800kWh、PV减半，重新预测并回放Jan24—26。此前216段实际前缀不变（浮点最大约9.1e−13kWh），前两天00:00全部候选证据和冻结计划相同，次日预测/采购出现阳性响应；另独立验证情景递推前缀。这比只检查时间戳更有意义，但不是所有可能输入的形式化无泄漏证明。

物理口径沿用原模型：充放电效率均0.9；SOC1200—10800；5000kW母线功率等于每十分钟833.333333kWh；互斥充放；应急只补负荷缺口、全额5p；已承诺未用仍计费、无售电收入。日内执行沿用十分钟段内自动平衡、区间末可观测本段负荷/PV的工作假设，不借用未来区间。题面/模板时间映射与效率、功率计量解释尚需正式确认，没有因本轮结果有利而静默改动。

年度辅助库存值用ν=平均普通电价×0.9=0.6895775元/kWh，与每日选择得分μ不同。最好方案末态2441.73kWh，比P_floor多463.18kWh；按事先固定ν调整后，相对P_floor仍省28875.74元，因此本轮增量不是靠耗尽更多末态库存。辅助值只用于比较，不是假设售电或现金收入。

## 稳定性与论文可用结论

最好方案在{int(win.total_winning_days)}天总费较低、{int(win.total_losing_days)}天更高；11个月只有{int(win.positive_total_months)}个月总费较低。紧急费有{int(win.emergency_worse_days)}天、{int(win.emergency_worse_months)}个月高于P_floor，年度下降不代表每期下降。7/14日循环块重采样各2000次，对普通、紧急和总费使用相同配对索引；{ci}，均跨0。它只是固定历史路径的相关性敏感性描述，不计入多次选参偏差，也不是未来100万元上限的达标概率。

可写进论文：原固定点预测忽视非对称紧急费用；风险校准与明确终态条件在本数据下大幅降低旧B0/B1的数值账单；本轮分时调整在相同终态、初态和执行下再节省28556.34元且紧急费644292.17元；更激进统一减购与复杂样本选择均有失败，应一并报告。相对旧基线的金额差异不等于本轮增量具有统计显著性。

不能写：全局最优、已降到头、未来年度稳定省2.86万元、90%风险上限有总体保证、每月都省钱、仅本轮新方法独自带来相对B0/B1的全部收益。仅一个已反复查看的年度，下一步优先用未参与设计的新时间段验证分时曲线，再考虑更充分的预测/场景建模；不应在此年度继续无界调参来包装更好数字。

## 交付入口

研究代码、两份冻结配置、全部逐段账本/候选NPZ、源预测/对照副本、独立验证、日/月/小时与消融统计、18路径块重采样及新论文草稿均在本版本五目录。README.md给出复现命令；package_manifest.csv、ZIP读回SHA和旧文件保护验收用于追溯。绘图为ModelViz适配，所有图内文字英文，300dpi PNG与SVG，保留候选选择、脚本、依赖和视觉质量报告。只完成Q2，没有重算Q3—4、覆盖旧论文/XLSX或执行commit/push。
'''
(REPORT/'research_report.md').write_text(report)
paper=r'''# 问题2论文补充草稿：分时风险校准与费用上限检验

以下为研究补充，未替换正式论文。题面十分钟信息与功率/效率计量口径沿用既有工作假设，需在终稿统一确认。所有方案使用2025年2—12月同334天及同7268.4231640740745kWh初态，随后各自连续。

## 模型调整

设日前时刻d的净负荷预测为 \(\hat N_{d,t}=\hat L_{d,t}-\hat P_{d,t}\)，历史净预测误差为 \(r_{j,t}=L_{j,t}-P_{j,t}-\hat N_{j,t}\)。仅使用在d日00:00之前已完整观测的历史日，按小时h汇集过去28天内各日6个十分钟误差。令 \(Q^{\mathrm{lin}}_\tau\) 为线性插值经验分位数，则

\[
\Delta_{d,h}=Q^{\mathrm{lin}}_{\tau_h}\{r_{j,t}:d-28\le j<d,\ h(t)=h\},\qquad
\widetilde N_{d,t}=\hat N_{d,t}+\Delta_{d,h(t)}.
\]

采购计划仍由既有日前MILP求得，00:00冻结，计划末态固定1200kWh，实际状态不重置。只调节历史误差裕量，不增加设备、不开放日内普通价补购、不使用问题3光伏预报。等价的非负计划负荷/PV拆分保持校准净负荷不变。

对于无储能、固定价、无残值的单时段简化模型，\(C(q)=pq+5p\mathbb E[(N-q)^+]\)。连续分布内点有 \(C'(q)=p-5p[1-F(q)]=0\)，从而 \(F(q)=0.8\)。该结论说明不对称费用下0.8可作为候选依据，不能证明含跨时储能的全时段0.8最优。本文进一步以分时 \(\tau_h\) 进行有限敏感性比较。

## 经验情景选择及消融

对每个候选k，在同一实际日初态下重解采购 \(q^{(k)}\)。场景s由已完成的整日净误差向量与当日净预测相加；同一候选在所有情景中使用同一采购，后续动作按原贪心规则逐段递推，不能自由利用场景未来。若场景紧急费用为 \(H_{k,s}=\sum_t5p_tu_{k,s,t}\)、普通费 \(A_k=\sum_tp_tq^{(k)}_t\)、末态为 \(E_{k,s}^{\rm end}\)，选择得分为

\[
J_k=A_k+\frac1S\sum_s H_{k,s}-\mu\left(\frac1S\sum_s E_{k,s}^{\rm end}-E_d\right),\quad\mu=0.38232.
\]

定义90%经验CVaR [1]
\[
\widehat{\mathrm{CVaR}}_{0.9}(H_k)=\min_\eta\left\{\eta+\frac1{0.1S}\sum_s(H_{k,s}-\eta)^+\right\}.
\]

离散尾部按边界分数权重处理，不将严格超过样本分位数的值简单平均。R_guard相对同初态基准候选0要求 \(A_k\le A_0\)、\(\overline H_k\le\overline H_0\)、\(\overline E_k\ge\overline E_0\) 以及经验CVaR不增加；在可行候选中按J最小选择。去掉尾部约束、去掉全部保护及缩短场景窗分别作为消融。28/56日样本较短，风险量仅为经验代理；相关微网与配网研究[2—3]的方法不能自动保证本题未来年度费用上限。

可复现参数：情景窗口默认56个历史自然日，R_w28改为28日；风险池仍为28日。近28日风险样本或情景池不足7个完整历史日则停止。四条R路径的候选库首个为anchor；费用保护容差1e−7元、库存容差1e−6kWh，得分距最小值1e−8元内按冻结候选顺序选择首个。μ=0.4248×0.9=0.38232元/kWh，用于日前选择时对末态库存的辅助估值。HiGHS 1.14.0、单线程、随机种子0、时限120秒、相对gap 1e−9及绝对gap 1e−7；仅发布Optimal状态，其他状态报错而不回退。两阶段配置分别位于configs/q2_pareto_v3/experiments.json和extension.json。

## 回放结果与新增偏好

原十条方案按“普通费、总费均下降且紧急费不高于P_floor”的协议检验，仅R_guard通过，总费下降1530.59元。用户随后将紧急费硬上限改为100万元、总费优先，我们另冻结八条固定分时方案并全部回放。所有结果均是查看过年度数据后的探索，最优候选的挑选不是独立盲测。

新增最优候选X_strong_morning85在9—11时取0.85、11—18时取0.65、18—22时取0.95，其余小时取0.8。实际普通费13349990.09元、紧急费644292.17元、总费13994282.26元。相对相同计划末态约束的P_floor，分别节省11574.85元、16981.49元和28556.34元，总费下降0.20364%。相对原冻结B0与季节性B1的总费差额分别为2339401.13和1383925.09元，但其中包含此前风险校准和计划终态调整，不能全部归给本轮分时方法。

仅削减白天裕量的T_day_trim导致紧急费增量超过普通费节省，总费反增6754.26元。白天进一步降至0.5的X_day50紧急费1012398.77元，超上限且总费更高；全时段0.7的X_uniform70也超限。R_mean、R_cost、R_w28均未改善P_floor总费。全部18条新方案及六对照列于研究附件，不能只保留胜出策略。

## 独立验证与局限

实际执行采用SOC1200—10800kWh、充放电效率各0.9、5000kW母线功率（每十分钟5000/6kWh）、互斥充放，紧急电只补负荷缺口，已购未用仍付费且无售电。区间内自动平衡按区间末可观测的本段负荷/PV计算，未来区间输入不得进入本段决策。所有路径跨日连续，年度候选MILP合计14028个，失败/回退0。独立验证器从源数据、历史发布预测、冻结采购、候选场景与实际账本重算，物理残差阈值1e−6kWh、费用阈值1e−5元，并用真实未来数据扰动核验此前决策不变。

最优候选期末2441.73kWh，比P_floor多463.18kWh。按固定 \(\nu=\overline p\times0.9=0.6895775\) 的辅助库存价值调整后，仍比P_floor少28875.74元。\(\nu\) 与选优得分中的 \(\mu\) 用途不同，库存调整不是实际售电收入。

该候选214天总费较低、120天较高，11个月仅5个月总费较低。7日块与14日块、各2000次配对循环重采样的总节省95%区间分别为[-42272.41,113910.09]元与[-40824.52,116945.99]元，均跨零。原十条bootstrap种子20260913，追加八条种子20260914，普通/紧急/总费在每次重采样使用同一组日索引。区间仅描述固定历史轨迹，不含候选筛选偏差、不代表未来达标概率。因此本文仅确认本数据中存在小幅可追溯改进，不主张全局最优、每月下降或对未知年份的稳定优势。

## 图表与数据定位

图S1（全部18条新方案的普通/紧急/总费差额）为reports/q2_pareto_v3/figures/savings/outputs/chart.png，图S2（逐月节省，含亏损月份）为reports/q2_pareto_v3/figures/monthly/outputs/chart.png；同目录提供SVG。两图全部英文，费用单位为thousand CNY。

完整24策略表位于results/q2_pareto_v3/analysis_user_cap/comparison_all.csv。2025-03-20、06-21、09-23、12-21四个指定日期的逐段冻结采购、真实执行、六个指定区间购电、四小时充放电及紧急事件表位于results/q2_pareto_v3/analysis_user_cap/representative/X_strong_morning85/（four_days_ledger.csv、table1_intervals.csv、table1_daily.csv、table2_charge_discharge.csv、table3_emergency.csv及terminal.csv）；其他追加方案同级保留，原七策略代表日位于results/q2_pareto_v3/representative/。这些指定日期只是结果展示，未用来挑选有利片段或替代全年评价。

## 参考资料

[1] Rockafellar R T, Uryasev S. Optimization of Conditional Value-at-Risk. 作者大学公开稿：https://sites.math.washington.edu/~rtr/papers/rtr179-CVaR1.pdf 。

[2] Vahedipour-Dahraie M, Anvari-Moghaddam A, Guerrero J M. Evaluation of Reliability in Risk-Constrained Scheduling of Autonomous Microgrids with Demand Response and Renewable Resources. IET Renewable Power Generation, 2018,12(6):657—667. DOI:10.1049/iet-rpg.2017.0720. 作者稿：https://vbn.aau.dk/ws/files/266946440/IET_RPG.20.12.2017_R1.pdf 。

[3] Hashmi M U, et al. Chance constrained day-ahead robust flexibility needs assessment for low voltage distribution network. arXiv:2207.10234,2022. https://arxiv.org/abs/2207.10234 。本轮仅检索摘要用于方法边界比较，不据此导入未验证分布假设。

BZD模型字典仅作为建模流程辅助，记录504（多目标规划）、2984（CVaR）保留BZD数模社制作署名及许可；不作为实际费用或性能数字的证据。AI参与调研、代码实现、独立公式复核和草稿，正式使用应按比赛要求记录使用说明。
'''
(PAPER/'paper_supplement.md').write_text(paper)
print('Generated research_report.md and paper_supplement.md')
