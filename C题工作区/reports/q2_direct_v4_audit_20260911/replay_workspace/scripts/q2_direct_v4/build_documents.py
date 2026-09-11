"""Build this version's research narrative directly from finalized result tables."""
import json
import platform
from pathlib import Path
import sys
import importlib.metadata
import pandas as pd

WORK=Path(__file__).resolve().parents[2];VERSION='q2_direct_v4';ROOT=WORK/'results'/VERSION
REPORT=WORK/'reports'/VERSION;PAPER=WORK/'papers'/VERSION
table=pd.read_csv(ROOT/'analysis_all/comparison_all.csv',float_precision='round_trip').set_index('policy')
best=table.loc['D112'];old=table.loc['X_strong_morning85'];safe=table.loc['D56_risk625']
names=['B0','B1','P_floor','X_strong_morning85','D56','D28','D112','D56_risk625','D56_mu069','D56_mu0','D112_refined','D56_risk625_refined']
rows=['| 策略 | 普通费用/万元 | 紧急费用/万元 | 总费用/万元 | 比v3节省/元 | 紧急≤100万元 |',
      '|---|---:|---:|---:|---:|:---:|']
for name in names:
    s=table.loc[name];rows.append(f"| {name} | {s.planned_cost_yuan/1e4:.4f} | {s.emergency_cost_yuan/1e4:.4f} | {s.total_cost_yuan/1e4:.4f} | {s.total_saving_vs_X_strong_morning85_yuan:.2f} | {'是' if s.passes_emergency_cap else '否'} |")
fulltable='\n'.join(rows)
boot=pd.read_csv(ROOT/'analysis_all/block_bootstrap.csv');counts=pd.read_csv(ROOT/'analysis_all/win_loss_counts.csv')
ci=boot.loc[(boot.policy=='D112')&(boot.component=='total_cost_yuan')]
ciwords='；'.join(f"{int(r.block_days)}日块区间[{r.ci95_low_yuan/1e4:.2f}, {r.ci95_high_yuan/1e4:.2f}]万元" for r in ci.itertuples())
totalopt=sum(table.loc[n,'optimizer_count'] for n in names[4:]);success=sum(table.loc[n,'optimizer_success_count'] for n in names[4:])
models=[json.loads((ROOT/'runs'/n/'decisions.json').read_text())['days'] for n in names[4:]]
metrics={'annual_policies':8,'annual_days':2672,'actual_intervals':2672*144,'saved_candidates':2672*6,
         'optimizer_calls':int(totalopt),'optimizer_success':int(success),'optimizer_non_success':int(totalopt-success),
         'optimizer_evaluations':int(sum(table.loc[n,'optimizer_nfev'] for n in names[4:])),
         'candidate_rescore_evaluations':2672*6,
         'total_objective_calls_including_rescore':int(sum(table.loc[n,'optimizer_nfev'] for n in names[4:]))+2672*6,
         'saved_candidate_scenario_pairs':sum(6*d['scenario_count'] for m in models for d in m),
         'optimizer_total_seconds':sum(table.loc[n,'optimizer_total_wall_seconds'] for n in names[4:]),
         'optimizer_max_seconds':max(table.loc[n,'optimizer_max_wall_seconds'] for n in names[4:]),
         'milp_total_seconds':sum(table.loc[n,'milp_total_runtime_seconds'] for n in names[4:]),
         'milp_max_seconds':max(table.loc[n,'milp_max_runtime_seconds'] for n in names[4:])}
(REPORT/'computation_scale.json').write_text(json.dumps(metrics,indent=2)+'\n')
env={'python':sys.version,'executable':sys.executable,'platform':platform.platform(),
     'packages':{n:importlib.metadata.version(n) for n in ['numpy','pandas','scipy','highspy','matplotlib','pillow','langchain-core','pydantic','PyYAML']},
     'threads':{'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'},'compiler_record':'results/q2_direct_v4/runtime/<source SHA>/build.json; exported compiler_build.json',
     'note':'C source compiled without fast-math; caches only inside this version. Runtime binary is rebuilt on relocation.'}
(REPORT/'environment.json').write_text(json.dumps(env,ensure_ascii=False,indent=2)+'\n')
(REPORT/'requirements.txt').write_text('\n'.join(n+'=='+v for n,v in env['packages'].items())+'\n')
builds=list((ROOT/'runtime').glob('*/build.json'));assert len(builds)==1
(REPORT/'compiler_build.json').write_bytes(builds[0].read_bytes())

research=f'''# Q2继续降费研究：直接采购与更充分搜索

本轮最低历史总费用为 **{best.total_cost_yuan:,.2f}元**，紧急费用 **{best.emergency_cost_yuan:,.2f}元**，低于用户100万元上限，余量 **{1e6-best.emergency_cost_yuan:,.2f}元**。比上轮v3最佳再省 **{best.total_saving_vs_X_strong_morning85_yuan:,.2f}元（{100*best.total_saving_vs_X_strong_morning85_yuan/old.total_cost_yuan:.4f}%）**。不能称“已经降到极限”：这是八条明确研究路径中的历史最低值，非所有因果策略的最优解。

## 1. 省在哪里，为什么普通费用仍高

D112比v3少付普通费用{best.ordinary_saving_vs_X_strong_morning85_yuan:,.2f}元，同时多付紧急费{-best.emergency_saving_vs_X_strong_morning85_yuan:,.2f}元，净省{best.total_saving_vs_X_strong_morning85_yuan:,.2f}元。因此最低总费方案确实增加了紧急费用；它符合后续明确的100万元上限，但不符合较早的“紧急费完全不能再升”。这项取舍公开列示。

若仍希望紧急费也下降，D56_risk625总费{safe.total_cost_yuan:,.2f}元、紧急费{safe.emergency_cost_yuan:,.2f}元；比v3总费少{safe.total_saving_vs_X_strong_morning85_yuan:,.2f}元，紧急少{safe.emergency_saving_vs_X_strong_morning85_yuan:,.2f}元。它比最低总费D112多花{safe.total_cost_yuan-best.total_cost_yuan:,.2f}元，紧急费少{best.emergency_cost_yuan-safe.emergency_cost_yuan:,.2f}元。

334天源负荷约3700.81万kWh，D112仍须采购2099.94万kWh正常电，普通费1307.52万元，平均总费约4.17万元/天。因此“大额”本身不能证明模型出错。更有意义的是已付却未用普通电费：从v3的{old.unused_grid_cost_yuan:,.2f}元降至{best.unused_grid_cost_yuan:,.2f}元，减少{old.unused_grid_cost_yuan-best.unused_grid_cost_yuan:,.2f}元。这是账目分解，不是独立可相加的因果贡献：减少采购会同时影响后续库存、紧急和弃电；剩余未用电也不能事后精准删除再称因果节省。

## 2. 做了什么，哪些约束没有改变

之前把每小时净误差分位数加入点预测，再解确定性采购。现在直接选择144维非负合同q：用过去完整日的净误差情景，逐段运行原严格贪心电池，最小化普通费、加权情景紧急费与末态价值代理的和。每个情景共享同一q，没有自由前视调度。预测器仍是B0；每日00:00冻结，.9/.9效率、SOC1200—10800kWh、833.333333kWh/段功率限制、紧急全额5p且只补负荷缺口均保持。

本轮公开移除了旧附加的“名义预测全天无紧急缺口”和“规划末态固定1200”限制，仅旧MILP起点保留它们；这些不是题面硬条件。最终名义回放缺口列forecast_emergency_kwh用于诊断，不是额外实际交易。直接法同时改变目标与候选空间，不能把全部收益单独归因于“去掉一个终态条件”。段内自动平衡、区间末观测与原时间映射仍为工作假设。

## 3. 全部结果与敏感性

同2025-02-01—12-31、48096段、相同期初7268.4231640740745kWh，各策略之后用自己的真实状态连续运行。B0/B1是原冻结策略和季节性强基线；四个基准副本已独立从源数据核验。

{fulltable}

D56是事先主候选，W=56、κ=5、μ=.38232；D28/D112只改变情景历史窗；D56_risk625只增大规划紧急权重至6.25；mu069/mu0只改变末态价值。.6895775与0均没有改善v3，mu0虽然少买普通电但真实紧急费更高，总费反而增加，否定“越不保守越好”的简单说法。W=112在这些离散点中最低，不表示连续窗口都优于其他值或未来季节仍最优。

看到初轮结果后，另冻结refinement_protocol.md，仅给D112和D56_risk625更多搜索预算（180→1200次迭代、1600→10000次评估上限）。二者真实费用分别比原配置增加{table.loc['D112_refined','total_cost_yuan']-best.total_cost_yuan:,.2f}元和{table.loc['D56_risk625_refined','total_cost_yuan']-safe.total_cost_yuan:,.2f}元。初轮与追加协议、结果、失败、停止原因均保留。更多搜索不是继续省费的充分条件。

## 4. 为什么账目可信，结论可信到哪里

新策略8×334天，2672次MILP起点，{int(totalopt)}次双起点局部搜索，{metrics['saved_candidates']}个保存候选、{metrics['saved_candidate_scenario_pairs']}个候选—日情景配对。优化器内部{metrics['optimizer_evaluations']}次目标评估，另有{metrics['candidate_rescore_evaluations']}次候选重评，合计{metrics['total_objective_calls_including_rescore']}次目标核调用；优化器success {int(success)}次、非success {int(totalopt-success)}次。最大一次搜索{metrics['optimizer_max_seconds']:.4f}秒、累计{metrics['optimizer_total_seconds']:.2f}秒；初始化MILP最大{metrics['milp_max_seconds']:.4f}秒、累计{metrics['milp_total_seconds']:.2f}秒。耗时依赖本机/并行负载，不是通用性能保证。success不是非光滑问题的最优性证书；非success保留当前最好已评估点，不伪装收敛，也不凭它证明效果。

独立验证器不导入生产预测器、执行器、场景费用核或梯度代码，重建发布预测、情景来源、六候选费用、完整MILP起点、实际贪心、冻结合同和账单。物理阈值1e-6kWh，账单核对1e-5元；业务100万元上限使用未舍入值严格比较。C反向导数与独立前向导数差约1.78e-15，离折点中心差分最大误差3.60e-7；不把折点的分支导数称唯一梯度。

将Jan25 12:00以后原负荷加800kWh、光伏乘.5，并从原始前缀重建预测/候选/执行。8种配置的更早216段差约9.09e-13，前两日采购和全部候选证据不变，次日有阳性响应。这是有意义的未来扰动测试，不能替代对所有输入的形式化无泄漏证明。另在全新目录重新编译C核、重跑最佳D112完整334天并独立核验，结果见portability_validation.json。

## 5. 没有隐藏的坏月份与库存效应

D112相对v3：250天总费更低、84天更高；8个月获益、3个月亏损；紧急费有68天、7个月更高。7/14日循环块各2000次（seed20260915）的总节省95%描述区间分别为{ciwords}，均跨零。不得写成统计显著、未来必胜或未来紧急费必不超过100万元。整年已被多轮查看，连新八配置的最终选择也受历史结果影响；这不是盲测，重采样没有消除方法选择偏差。

D112期末{best.final_energy_kwh:.6f}kWh，高于v3的{old.final_energy_kwh:.6f}kWh。按事先固定ν=.6895775元/kWh辅助计价后，节省为{best.inventory_adjusted_saving_vs_X_strong_morning85_yuan:,.2f}元，故本轮最低值并非靠多耗尽期末库存。库存价值只是统一比较口径，不是售电收入；真实账单不减该项。

图1把普通、紧急、总费分开，负值表示更贵；图2保留每月亏损。图内均英文，数据直接来自analysis_all；完整modelviz模板召回、选择、适配与技术/视觉核验记录随包保存。

![Figure 1](figures/savings/outputs/chart.png)

![Figure 2](figures/monthly/outputs/chart.png)

## 6. “极限”目前能回答什么

全知LP证书对应同一2025-02-01至12-31的334天（不是365天），相同期初7268.4231640740745kWh，无每天日末等式，周期期末自由但须在1200—10800kWh范围。其原始值和对偶下界均为12,227,565.30317241元；独立检查同一采购量在原严格贪心执行下也达到该费用，数值误差内无紧急，因此可确认该具体334天全知问题的最优值。LP原SOC与贪心SOC最多相差9600kWh，不能将LP原调度冒充贪心轨迹。

对任一真实可行轨迹，将正常+紧急电映射为LP同价购电、复制原充放电和库存，则LP费用不高于原正常+5p紧急账单，故该放松是下界；再有同成本的严格贪心可行解，得到该全知问题的上下界闭合。它依赖本轮固定物理/结算/全年末态可在范围内的口径。

当前D112距它还差{best.total_cost_yuan-12227565.30317241:,.2f}元。这不是保证还能省的金额，也不是已经计算出EVPI：因果策略族的最优值未知，全年未来先知不能投入日前决策。继续寻找更好的预测、条件情景、跨日库存价值可能有空间，但本轮证据不能支持继续承诺具体金额。真正检验下一轮方法，需要新增未参与研究的时间段或数据，而不是反复挑这一年的最低数字。

## 7. 可入论文与保留意见

可以写：在明确工作假设和同周期实测回放下，D112相对B0省{best.total_saving_vs_B0_yuan:,.2f}元（{100*best.total_saving_vs_B0_yuan/table.loc['B0','total_cost_yuan']:.2f}%）、相对B1省{best.total_saving_vs_B1_yuan:,.2f}元（{100*best.total_saving_vs_B1_yuan/table.loc['B1','total_cost_yuan']:.2f}%），相对v3进一步节省{best.total_saving_vs_X_strong_morning85_yuan:,.2f}元；真实紧急费83.87万元满足本次年度上限。可以写双初值历史场景直接采购、完整独立核验、负结果与期末库存比较。

不能写：Q2全局最优、降到极限、未来年保证、显著改善、完全不增加紧急费、剩余168.63万元可全部实现、SOC触底比例是容量不足的因果贡献率。Q3/Q4没有重算；这些文件是研究补充，不是正式提交或旧XLSX的替代品。来源与适配边界详见method_fit_and_sources.md；论文补充见papers/q2_direct_v4/paper_supplement.md。
'''
(REPORT/'research_report.md').write_text(research)

paper=rf'''# 问题2补充草稿：历史情景驱动的直接采购

本稿为原Q2章节的研究补充，不替换原正式论文。输入源、时间映射、效率/功率和区间末信息假设沿用既定口径；Q3和Q4未重算。2025全年已经用于多轮研究，结果仅为历史探索回放。

## 1. 目标与模型

对日d的第t段（t=1,…,144），正常采购q_dt≥0，单位kWh，在当日00:00一次确定；p_t为元/kWh。由当时可得的B0预测得到净负荷预测n̂_dt。令H_d为过去W日内已完整结束且误差可用的历史日期，历史净误差r_st=(L_st−PV_st)−(L̂_st−PV̂_st)，使用当时发布预测计算。整日场景n_dt^(s)=n̂_dt+r_st保留日内误差结构，所有场景共享同一q；日初库存E_d0为各策略自己的真实上一日期末。

设η_c=η_d=.9、P=5000/6kWh、E_min=1200kWh、E_max=10800kWh，v_t^(s)=q_dt−n_dt^(s)。每段严格采用

$$c_t^s=\min\{{(v_t^s)^+,P,((E_{{\max}}-E_{{t-1}}^s)/\eta_c)^+\}},$$
$$d_t^s=\min\{{(-v_t^s)^+,P,(\eta_d(E_{{t-1}}^s-E_{{\min}}))^+\}},\quad u_t^s=(-v_t^s-d_t^s)^+,$$
$$w_t^s=(v_t^s-c_t^s)^+,\quad E_t^s=E_{{t-1}}^s+\eta_c c_t^s-d_t^s/\eta_d.$$

其中x⁺=max(x,0)，c,d,u,w分别为充电、放电、紧急补电与弃余电量，初始条件E_0^s=E_d0。v的符号保证充放互斥；u仅补该情景负荷缺口，不能用于充电。每个场景的状态只使用该场景当前前缀，无自由未来补救。

采用有限历史目标

$$J_d(q)=\sum_t p_t q_{{dt}}+\frac1{{|H_d|}}\sum_{{s\in H_d}}\left[\kappa\sum_t p_t u_t^s-\mu(E_{{144}}^s-E_{{d0}})\right],\qquad q_{{dt}}\ge0.$$

κ为无量纲规划风险权重，μ为日末库存价值代理，单位元/kWh。实际总账单始终为Σ_t[p_tq_dt+5p_tu_dt^actual]，不减库存价值，不假定售电，已购未用仍付费。该直接模型不强制名义点预测零缺口或日末固定1200；这些是原方法的附加规划限制。本次仅取消其在最终q上的约束，设备、冻结合同和结算规则不变。不能将直接法的整体改善解释为单项终态改变的独立贡献。

## 2. 参数、求解与适用条件

预定主方案D56取W56、κ5、μ.38232；W28/W112用于历史窗敏感性，κ6.25用于额外25%规划风险权重，μ0/.6895775用于库存价值消融。较大μ不等于真实跨日价值函数；历史场景也未被证明iid或平稳。因此样本平均只定义经验目标，不提供真实期望的最优性保证。[1,2]

每日两起点：从自己日初SOC解v3小时风险曲线MILP（9—11时τ=.85，11—18时.65，18—22时.95，其余.8，残差池28日、规划终态1200）；另一点q=(n̂_d)⁺。采用L-BFGS-B，在q/1000与J/10000尺度下传入0.1倍原梯度，非负边界，maxiter180、maxfun1600、maxls30、maxcor10、ftol1e-10、gtol1e-5。[3] 每起点保存初值、最低已评估点与最终返回点，共六候选；重新计算J并以1e-8元同差规则按固定顺序选择。情景与28日风险池均至少需要7个完整日，否则停止。

容量/功率切换使目标不光滑。解析分支导数仅在非折点具有通常梯度意义；L-BFGS-B在此是局部搜索启发式，不是理论适配的精确全局算法。字典指出的平滑前提在本题不满足，故不能用软件success替代最优性证明。C99双精度核仅加速原递推，不改变费用。完整环境和编译命令见environment.json与compiler_build.json。

## 3. 实际回放、消融与失败结果

2025-02-01至12-31共334天48096段，各策略共用期初7268.4231640740745kWh、之后独立连续。实际账单如下，所有新增方案均显示。

{fulltable}

主方案D56通过本次总费与紧急上限验收。初轮六方案中的D112观察总费最低{best.total_cost_yuan:,.2f}元，紧急费{best.emergency_cost_yuan:,.2f}元；相对原冻结B0和季节性B1分别节省{best.total_saving_vs_B0_yuan:,.2f}元和{best.total_saving_vs_B1_yuan:,.2f}元，相对v3省{best.total_saving_vs_X_strong_morning85_yuan:,.2f}元。其中普通费少{best.ordinary_saving_vs_X_strong_morning85_yuan:,.2f}元、紧急费多{-best.emergency_saving_vs_X_strong_morning85_yuan:,.2f}元，不能称两项同时改善。若要求紧急也下降，可用D56_risk625，其两项分别少{safe.ordinary_saving_vs_X_strong_morning85_yuan:,.2f}元和{safe.emergency_saving_vs_X_strong_morning85_yuan:,.2f}元。

去除末态价值μ0与增至.6895775均不优于v3；敏感性呈非单调关系，不能外推连续稳定区间。看完初轮后另冻结两条预算敏感性，将D112及D56_risk625的maxiter/maxfun增至1200/10000，真实成本分别多1174.90元和4665.01元。它们是结果驱动的有限追加，不能称未看结果的预注册设计。更多搜索不保证未知实际场景收益。

图1展示各新策略三种费用差额，图2展示月度正负收益；两图数据均可追溯至analysis_all汇总表。

![图1：各策略费用差额，图内英文](../../reports/q2_direct_v4/figures/savings/outputs/chart.png)

![图2：月度总费节省，图内英文](../../reports/q2_direct_v4/figures/monthly/outputs/chart.png)

## 4. 独立检验与不确定性

独立验证从源数据、已冻结q及最终附件重建发布日期、历史OLS/谐波预测、情景集合、候选目标、实际贪心与费用，不导入生产求解/执行/梯度核。物理阈值1e-6kWh，累计账单1e-5元，100万元业务上限严格以未舍入总额判断。双精度梯度与独立前向灵敏度误差1.78e-15，非折点有限差分误差3.60e-7；折点不强求唯一通常梯度。全年5344次搜索有2533次success、2811次非success，保留全部停止记录。数值有效性与搜索最优性是不同结论。

未来扰动把Jan25中午后负荷+800kWh、PV×.5，原始前缀重新生成预测与决策。8配置更早216段最大差9.09e-13，前两日全部候选证据不变，次日有响应；这是针对实现的因果检验，不是未来所有输入的证明。最佳D112另外进行换目录完整全年复现，C核重新编译，来源与结果独立审计。

D112相对v3获益250天、亏损84天，获益8个月、亏损3个月；紧急费有68天、7个月更高。{ciwords}，均跨零。循环块保留部分时间依赖，但只描述固定观察路径，未纠正反复选模型的偏差，不能据此声称显著或未来保障。

期末D112为{best.final_energy_kwh:.6f}kWh，v3为{old.final_energy_kwh:.6f}kWh；按ν=.6895775元/kWh计算C_adj=C_actual−ν(E_T−E_0)，相对节省{best.inventory_adjusted_saving_vs_X_strong_morning85_yuan:,.2f}元，收益不是靠多消耗期末库存。该价值项仅辅助比较，不是实际售电。

## 5. 下界、结论与边界

全知证书对应相同2025-02-01至12-31的334天、期初7268.4231640740745kWh、设备与结算口径，无每天日末等式，周期期末自由但限制在1200—10800kWh。给全知优化提供该周期所有未来信息，并允许LP放松，以常规价购买正常加紧急电，则其费用不高于任一真实可行方案。独立原始/对偶证书给出下界12,227,565.30317241元；其采购量在原严格贪心执行下也可达到同费用，误差内零紧急，从而闭合该特定全知问题的上下界。LP原状态轨迹与贪心状态轨迹不同，不能混为一个执行方案。

D112距此全知值尚差{best.total_cost_yuan-12227565.30317241:,.2f}元，但不可宣称这笔钱可在Q2信息约束下实现，也不能称其为已测EVPI。结论仅是：在本次已观察历史年与工作假设下，直接情景采购比两个原始基准及此前最好方案总费更低，并满足本次年度紧急费100万元门槛；尚无因果全局最优性、新年度泛化或未来硬上限保证。

## 参考与附件

[1] Linderoth J, Shapiro A, Wright S. The Empirical Behavior of Sampling Methods for Stochastic Programming. Optimization Online, 2002. https://optimization-online.org/2002/01/424/ （本轮核对研究页面与摘要）。

[2] Wang Y, Pan B, Tu W, et al. Sample Average Approximation for Stochastic Optimization with Dependent Data: Performance Guarantees and Tractability. 2021. https://arxiv.org/abs/2112.05368 （本轮核对摘要；未证明本数据满足其理论条件）。

[3] SciPy. minimize(method='L-BFGS-B'). https://docs.scipy.org/doc/scipy/reference/optimize.minimize-lbfgsb.html （官方参数与停止条件）。

BZD数模社制作的SAA与L-BFGS-B字典记录完整许可在reports/q2_direct_v4/bzd_*_record.json。代码、两轮冻结配置、完整账本/情景/轨迹、独立JSON与图表见本版本结果包；README给出换目录复现命令。未替换旧论文/XLSX，未进行commit/push。
'''
(PAPER/'paper_supplement.md').write_text(paper)
print('Research report and paper supplement generated.')
