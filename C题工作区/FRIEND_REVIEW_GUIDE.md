# 给队友的审阅导航

本次完整内容在分支 **codex/innovation-experiments**。从这份导航开始；下列阅读副本仅把本机绝对链接转换为仓库相对链接，公式、数值与原装配稿相同，适合GitHub预览。原稿与冻结结果包均保留。

## 优先看这四处

1. **[装配顺序与文件归属](papers/friend_review_v1/00_README_装配顺序.md)**：先了解旧五份初稿和新增敏感性稿各放在哪个Part，图表如何取舍。
2. **[合并阅读稿](papers/friend_review_v1/assembled_review_draft.md)**：按Part01—10通读。重点看Part02的假设是否符合题意，Part06的创新是否接在原模型上，Part08的证据能否支撑结论。可暂跳附录的大表。
3. **[Part08 检验、敏感性与收益稳定性](papers/friend_review_v1/part08_validation_sensitivity.md)**：本轮新增连续回放、窗口/效率/终态/价格对照、亏损日月和分块区间都在这里。不能把历史区间写成未来概率保证。
4. **[本轮审查及待解决问题](reports/robustness/bzd_solution_check.md)**：优先核对时间映射、效率与功率侧别、退款/最终一次计费、未来价格是否可知；然后处理符号、图表编号、引用与正式Excel。

## 按分工看

| 负责内容 | 主文件 | 重点 |
|---|---|---|
| 共同模型与题意 | [Part02](papers/friend_review_v1/part02_assumptions_notation.md)、[Part03](papers/friend_review_v1/part03_shared_model.md) | 单位、守恒、计划与实际的区别、附加假设 |
| 问题1 | [Part04](papers/friend_review_v1/part04_q1.md) | 确定性最优、指定表；效率检验在Part08 |
| 问题2 | [Part05](papers/friend_review_v1/part05_q2.md) | 因果预测、1月选型、全年失败对照，不事后换赢家 |
| 问题3与创新 | [Part06](papers/friend_review_v1/part06_q3.md) | 状态反馈和新PV信息分开；校正4月启用、SOC不断开 |
| 问题4 | [Part07](papers/friend_review_v1/part07_q4.md) | 因果价格与实际收费分开；校正仅迁移Q4-3 |
| 写作整合 | [Part09](papers/friend_review_v1/part09_evaluation_limits.md)、[Part10](papers/friend_review_v1/part10_references_reproduction.md) | 保留失败与局限；统一引用、符号和AI使用记录 |
| 指定日期表 | [附录A](papers/friend_review_v1/appendix_A_required_tables.md) | 此处是装配暂存；最终应按题面要求放回对应问题正文 |

## 需要核对数字时

- [paired_summary.csv](results/robustness/paired_summary.csv)：六组原始/校正成对费用，明确275日与334日两个范围。
- [paired_monthly.csv](results/robustness/paired_monthly.csv)：月度正负收益。
- [bootstrap_intervals.csv](results/robustness/bootstrap_intervals.csv)：块长3/7/14日及循环7日对照，不挑选性报告。
- [独立审阅记录](logs/robustness/review.md)：429222项独立检查、160个LP核验及审稿修正。
- [完整结果包](deliverables/robustness/v1_continuous_audit/README.md)：完整代码、配置、逐段账本、图表、验证与哈希；下载两个ZIP并解压到同一目录。

对数字的核心检查：主28天方案2—12月成本13,726,733.57元，比原始PV省46,146.49元；4—12月153天省费、122天增费，7月及12月增费。Q4-3迁移省41,783.10元。不要把0.403%的275日节省率误写成334日节省率。

这是一份可复核的装配初稿。正式模板时间及若干市场/物理口径仍待确认；现有检验通过不等于正式Excel、最终格式、全部学术引用及AI材料已完成。请优先反馈具体公式、数字或假设问题，再精修语言。
