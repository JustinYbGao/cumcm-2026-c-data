# 验证及报告工具修复记录

年度生产10文件与冻结参数未修改，没有删除或重算年度失败候选。

1. 首次analyze.py已写出比较、选择和配对CSV，在Markdown输出阶段因运行环境没有可选tabulate包终止。改用v5内简短Markdown表格渲染器，不安装或改变旧环境；选择规则、数字和随机种子不变。首次analysis.log为空（错误在标准错误流中），完整原因在本记录保留。重试为analysis_v2.log。
2. 首次validate_analysis.py的“所有数值列有限”断言失败，原日志analysis_validation.log保留。逐列定位发现：旧Q2_B0/Q2_B1的risk_history_start/end各48096行为空，旧Q3_raw/Q43_raw的pv_window_days各48096行为空，均是历史策略未启用风险窗口或校正时的诊断字段。十条新策略全部数值列均有限。修复仅对旧策略这三个不适用诊断列作显式、带计数的例外；实际物理/费用列及全部新策略仍严格要求有限。未填充、修改任何旧账本。重试为analysis_validation_v2.log。

修复不改变数据、方法、历史选择或实际账单。因果审阅补充是在首次完整未来扰动运行前完成，见independent_code_review.md与extra_checks.py。

3. 首次旧文件保护检查发现results/.DS_Store变化，其余4218项和冻结生产10项、原始附件1—4均未变。此为macOS目录元数据，未归因具体进程；任务代码没有有意写入该文件，且仅保存了原SHA，没有原始字节可恢复。保护报告现明确区分研究产物保护PASS与全部原文件字节一致false，保留该例外及前后SHA，不隐藏或改写原保护快照。
