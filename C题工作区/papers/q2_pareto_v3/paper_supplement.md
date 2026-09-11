# 问题2论文补充草稿：分时风险校准与费用上限检验

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
