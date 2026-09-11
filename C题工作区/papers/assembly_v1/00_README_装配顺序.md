# 论文装配顺序与文件归属

**从本文件开始。** 原五份初稿全部保留，以下是新装配副本，已拆分重复内容和更新过时状态。先按Part01—10写正文，附录A中题面指定表应排回对应问题正文；附录B保存完整创新实验供裁剪。摘要在结论核对后写，当前不进行文字精修。

## 阅读/写作顺序

| 顺序 | 文件 | 放什么 |
|---|---|---|
| 01 | [part01_problem_analysis.md](/Users/justingao/Documents/CUMCM/C题工作区/papers/assembly_v1/part01_problem_analysis.md) | Part01 问题重述与分析 |
| 02 | [part02_assumptions_notation.md](/Users/justingao/Documents/CUMCM/C题工作区/papers/assembly_v1/part02_assumptions_notation.md) | Part02 数据口径、模型假设与符号 |
| 03 | [part03_shared_model.md](/Users/justingao/Documents/CUMCM/C题工作区/papers/assembly_v1/part03_shared_model.md) | Part03 共同物理模型与实际执行 |
| 04 | [part04_q1.md](/Users/justingao/Documents/CUMCM/C题工作区/papers/assembly_v1/part04_q1.md) | Part04 问题1：确定性日前优化 |
| 05 | [part05_q2.md](/Users/justingao/Documents/CUMCM/C题工作区/papers/assembly_v1/part05_q2.md) | Part05 问题2：历史预测与日前承诺 |
| 06 | [part06_q3.md](/Users/justingao/Documents/CUMCM/C题工作区/papers/assembly_v1/part06_q3.md) | Part06 问题3：日内更新与PV偏差校正 |
| 07 | [part07_q4.md](/Users/justingao/Documents/CUMCM/C题工作区/papers/assembly_v1/part07_q4.md) | Part07 问题4：波动价格及改进迁移 |
| 08 | [part08_validation_sensitivity.md](/Users/justingao/Documents/CUMCM/C题工作区/papers/assembly_v1/part08_validation_sensitivity.md) | Part08 模型检验、敏感性与收益稳定性 |
| 09 | [part09_evaluation_limits.md](/Users/justingao/Documents/CUMCM/C题工作区/papers/assembly_v1/part09_evaluation_limits.md) | Part09 模型评价、失败实验与适用范围 |
| 10 | [part10_references_reproduction.md](/Users/justingao/Documents/CUMCM/C题工作区/papers/assembly_v1/part10_references_reproduction.md) | Part10 文献、复现与附件索引 |
| 11 | [appendix_A_required_tables.md](/Users/justingao/Documents/CUMCM/C题工作区/papers/assembly_v1/appendix_A_required_tables.md) | 附录A 指定日期表格与完整策略入口 |
| 12 | [appendix_B_innovation_archive.md](/Users/justingao/Documents/CUMCM/C题工作区/papers/assembly_v1/appendix_B_innovation_archive.md) | 附录B 原创新实验完整记录 |

## 旧文件逐个放哪里

| 原文件 | 精确归属 | 处理方式 |
|---|---|---|
| [q1_draft.md](/Users/justingao/Documents/CUMCM/C题工作区/papers/q1_draft.md) | 1→Part04.1；2→Part02；3→Part03；4—5→Part04；6—7→Part08.2；8→Part09/问题2衔接；证据说明→Part10 | 正文主材料，移出重复假设；指定表保留Part04 |
| [q2_draft.md](/Users/justingao/Documents/CUMCM/C题工作区/papers/q2_draft.md) | 1—4→Part05；5→Part08.3与Part09 | 保留1月选型失败；不换全年胜出策略；指定表由附录A排回Part05 |
| [q3_draft.md](/Users/justingao/Documents/CUMCM/C题工作区/papers/q3_draft.md) | 1→Part06.1与Part02；2→Part03/06.2；3—4→Part06.3—4；5→Part08.3；6→Part09；7→Part06.6；8及运行→附录A/Part10 | 删掉历史“尚未做Q4”等过时状态；新增校正放Part06.5，不整篇创新另挂正文 |
| [q4_draft.md](/Users/justingao/Documents/CUMCM/C题工作区/papers/q4_draft.md) | 1—5→Part07.1—4；6→Part08.3；7→Part09；8→Part07.6；9及运行→附录A/Part10 | 新增迁移放Part07.5；旧结果保留同核基线；验证集中 |
| [innovation_draft.md](/Users/justingao/Documents/CUMCM/C题工作区/papers/innovation_draft.md) | 1→Part06.5/08.4实验边界；2的PV公式→Part06.5，风险/门槛公式→附录B；3—4的主PV结论→Part06/08，失败结论→Part05.5/09.2；5→Part08/09；6—7→附录B/Part10；全文历史快照→附录B | 成功改进、无效消融分别说明；旧分阶段结果不冒充连续334日 |
| [robustness_draft.md](/Users/justingao/Documents/CUMCM/C题工作区/papers/robustness_draft.md) | 全文→Part08.4；其中固定28天最终策略→Part06.5；变价迁移→Part07.5；限界→Part09 | 本轮新增连续回放/敏感性/分块稳定性；主方案仍28天，不事后选窗口 |

## 图表取舍

| 图或表源 | 正文位置 | 用法 |
|---|---|---|
| [modelviz_v3_en/dispatch](/Users/justingao/Documents/CUMCM/C题工作区/reports/figures/modelviz_v3_en/dispatch) | Part04.3 | 保留供需、购电、SOC与电价关系 |
| [modelviz_v3_en/battery_states](/Users/justingao/Documents/CUMCM/C题工作区/reports/figures/modelviz_v3_en/battery_states) | Part08.2 | 效率口径对照，Part04只交叉引用避免重复 |
| [modelviz_v3_en/monthly_costs](/Users/justingao/Documents/CUMCM/C题工作区/reports/figures/modelviz_v3_en/monthly_costs) | Part05.4 | 保留选型失败 |
| [modelviz_v3_en/representative_execution](/Users/justingao/Documents/CUMCM/C题工作区/reports/figures/modelviz_v3_en/representative_execution) | Part05.4 | 计划/实际SOC及紧急量 |
| [modelviz_q3_v1_en/q3_monthly](/Users/justingao/Documents/CUMCM/C题工作区/reports/figures/modelviz_q3_v1_en/q3_monthly) | Part06.4 | 更新收益 |
| [modelviz_q3_v1_en/q3_execution](/Users/justingao/Documents/CUMCM/C题工作区/reports/figures/modelviz_q3_v1_en/q3_execution) | Part06.6 | 允许时刻与实际轨迹 |
| [modelviz_q4_v1_en/q4_monthly](/Users/justingao/Documents/CUMCM/C题工作区/reports/figures/modelviz_q4_v1_en/q4_monthly) | Part07.4 | 同实际收费下的价格输入对照 |
| [modelviz_q4_v1_en/q4_prices](/Users/justingao/Documents/CUMCM/C题工作区/reports/figures/modelviz_q4_v1_en/q4_prices) | Part07.6 | 因果价格与实际价格 |
| [modelviz_innovation_v1_en/innovation_monthly](/Users/justingao/Documents/CUMCM/C题工作区/reports/figures/modelviz_innovation_v1_en/innovation_monthly) | 附录B | 旧PV/门槛多组结果，正文用新稳健性图替代 |
| [modelviz_innovation_v1_en/innovation_risk](/Users/justingao/Documents/CUMCM/C题工作区/reports/figures/modelviz_innovation_v1_en/innovation_risk) | 附录B | 风险模型诊断，正文只写无显著实际收益 |
| [modelviz_robustness_v1_en/robustness_effects](/Users/justingao/Documents/CUMCM/C题工作区/reports/figures/modelviz_robustness_v1_en/robustness_effects) | Part08.4 | 窗口和假设下的配对省费及重抽样区间 |
| [modelviz_robustness_v1_en/robustness_monthly](/Users/justingao/Documents/CUMCM/C题工作区/reports/figures/modelviz_robustness_v1_en/robustness_monthly) | Part08.4 | 28天主方案月度成本和正负省费 |

题面指定表是必须回答的结果，附录A只是装配暂存，不可最终仅以“见附件”替代正文要求。所有可见图内标注为英文。Part编号是写作文件顺序，最终章节/图表/公式编号还需统一。各小节保留部分原局部符号，Part02列出同义对应；本轮不声称已完成终稿格式检查。
