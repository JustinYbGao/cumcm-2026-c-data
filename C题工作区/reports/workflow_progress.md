# C题当前进度与交接索引

当前阶段：问题1内部结果与初稿保留；问题2已补齐论文初稿和138文件冻结包，候选泛化退化证据不改。之后完成问题3六个主策略和一个仅状态反馈控制的内部求解、验证、英文图及初稿。随后完成问题4九组波动价格策略、因果价格预测、独立验证、英文图、论文初稿及冻结包。再完成11组创新实验及独立验收，详见reports/innovation/progress.md。未做全文精修或正式Excel。

| 阶段 | 材料/Skill | 状态 | 产物 | 阻塞或限制 | 下一步 |
|---|---|---|---|---|---|
| 题意与统一方案 | 既有BZD成果 | 已完成 | 选题分析目录 | 保持原工作假设 | 不重新选题 |
| 数据复核 | 既有processed与验证 | 已完成 | 数据字典、复核报告 | 时间语义待确认 | 保持只读 |
| Q1模型及求解 | dictionary #913/#797 | 已完成 | results/q1 | 内部假设版 | 保留数值 |
| Q1独立验收 | 独立验证器、solution-checker | 已完成 | 240检查、8测试 | 非第三方审计 | 口径变更重验 |
| Q1结果包 | 输入—代码—结果—证据链 | 已完成 | deliverables/q1/v1_interval_end_assumption.zip | 正式模板未导出 | 改版用新版本 |
| Q1论文初稿 | 已验证模型与数值 | 已完成 | papers/q1_draft.md | 尚未全文编号/精修 | 后续整合 |
| Q2候选适配 | dictionary #1788/#2703及已有调度记录 | 已完成 | q2_model_fit.md | 校准仅1月17天 | 保留对照 |
| Q2因果基础闭环 | 预测→MILP→实际执行→费用 | 已完成 | results/q2 | 不支持复杂候选改进有效 | 下一阶段研究风险或滚动适配 |
| Q2读回与局部审查 | 独立验证、solution-checker | 已完成 | 6975检查、5测试、事件核验、q2_bzd_solution_check.md | 非随机成本最优证明 | 不夸大结论 |
| Q2论文与冻结包 | 可追溯结果包 | 已完成 | papers/q2_draft.md、deliverables/q2/v1_internal_baseline.zip | 保留失败模型及当时图 | 不覆盖v1 |
| Q3模型与求解 | dictionary #782/#913/#797 | 内部完成 | results/q3、results/q3_feedback_control | A/B及最终量一次结算假设 | 正式规则确认后另开版本 |
| Q3独立验收 | solution-checker、独立约束账本、LP | 已完成 | 主110401检查、补充30048检查、36个LP、Q1—Q3共20单测 | 非全年随机最优证明 | 保留全部证据 |
| Q3图表与初稿 | ModelViz、真实结果写作 | 已完成 | 两张英文PNG/SVG、四日A/B表、papers/q3_draft.md | 未全文精修；额外终态约束 | 后续整合 |
| Q3结果包 | 文件与来源清单 | 已完成 | deliverables/q3/v1_internal_mpc.zip | 内部假设、便携数值核验 | 不覆盖v1 |
| Q1—Q4正式Excel | 模板映射 | 未开始 | 无正式文件 | 首末时间偏移待确认 | 确认后导出再验 |
| Q4 | dictionary #1788/#782/#913/#797、solution-checker、ModelViz | 内部完成 | 九组结果、211834检查、36 LP、25总单测、初稿及冻结包 | 价格信息/结算/终态与正式时间假设 | 确认口径后新版本，保留负结果 |
| 创新实验 | 统一方案6.3/11/12/14、BZD、ModelViz | 内部完成 | PV校正/风险余量/门槛11组，308491检查、36 LP、34总单测 | 回顾性评价；仅PV有实质增量，风险/门槛负结果保留 | 整合论文，口径确认后新版本 |
| 全文/终稿审查 | 完整论文 | 未开始 | 无评分 | 待整合与补全文献 | 最后执行 |

结果索引：Q1论文初稿`papers/q1_draft.md`、冻结包`deliverables/q1/`；Q2初稿`papers/q2_draft.md`、冻结包`deliverables/q2/`、说明`reports/q2_model_and_results.md`；Q3初稿`papers/q3_draft.md`、冻结包`deliverables/q3/`、说明`reports/q3_model_and_results.md`、完整四日表`reports/q3_representative_tables.md`。运行命令见各结果报告及README。

Q3主结论：全更新A/B为13,772,880.06/13,765,041.25元，只用0点为15,842,067.99元。仅反馈储能13,934,357.97元，新PV再省161,477.91元；不得把SOC反馈带来的节省全部当成新预报价值。B比A总费略低源于不同路径下紧急费降低，不代表不退款收费函数更便宜。

合并剩余问题：正式模板时间映射；A/B退原款及是否逐次计费；效率和功率口径确认；Q2固定1月选型全年退化；贪心执行的经济性；Q2—Q4额外日循环终态、初始化与库存价值假设；问题4未来价可用性/锁价解释、全文引用/AI使用与最终输出。已记录的数值、代码版本、失败实验及早期图形修复证据不应为后续更优结果而覆盖或删除。

Q4索引：`papers/q4_draft.md`、`reports/q4_model_and_results.md`、`reports/q4_representative_tables.md`、`reports/q4_bzd_solution_check.md`、`deliverables/q4/v1_internal_variable_price.zip`。

Q4主结论：日前OLS为17,030,881.70元，较同核固定价输入省42,860.98元；日内全更新A为14,534,062.64元，比固定价输入多6,183.03元。全更新A相对同PV来源仅0点策略省2,108,394.56元，而单独再估价格比保持0点价格多85.45元。价格预测误差改善不等于实际费用改善；完美价格只是信息情景，不是全年实际费用下界。全套25单测通过，Q4独立211,834检查及36个LP通过，1,336次价格模型全部独立重建。

创新入口：`papers/innovation_draft.md`、`reports/innovation/model_and_results.md`、`reports/innovation/progress.md`、`deliverables/innovation/v1_exploratory/`。4—12月PV校正省46,146.49元，风险仅2—5元，两个门槛增费2,279.99/135,578.73元；不以完成实验等同证明创新有效。

## 补充验收与论文装配（2026-09-10）

已补10条334日连续策略、14/28/56窗口、效率/终态/变价情景、日月收益、3/7/14日分块及循环7对照。429222独立检查、160 LP、11新增单测通过；两张ModelViz英文图经实际视觉修复。主28天策略成本13726733.574967869元，较原始PV省46146.486255184元；Q4-3迁移省41783.095967833元。未改选56天；保留122个增费日、7/12月负结果和跨年限制。

论文主入口：`papers/assembly_v1/00_README_装配顺序.md`，12份Part/附录、6份初稿精确归属和合并阅读稿；原五稿均保持不变。详细状态：`reports/robustness/progress.md`；结果包验证见`deliverables/robustness/v1_continuous_audit/package_validation.json`。历史各问的“尚未执行”是原快照状态，以本节补充为准。正式模板/题意确认、Excel导出和最终格式仍未完成。
