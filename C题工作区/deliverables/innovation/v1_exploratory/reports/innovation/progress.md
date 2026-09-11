# 创新实验执行进度与验收

源计划execution_plan.md保留计算前快照，其中“待执行”是冻结时状态；当前进度以本文件为准。

| 阶段 | 状态 | 证据 |
|---|---|---|
| 统一方案与字典适配 | 完成 | execution_plan.md、model_fit.md、dictionary日志 |
| 数值核、边界单测、独立代理审查 | 完成 | 9项新测试、25旧测试，review.md与修复记录 |
| 2月启动、3月选型 | 完成 | calibration、calibration_scores.csv、selection.json |
| 4—12月275天、11组评价 | 完成 | evaluation、comparison.csv、run_status.json |
| 独立数值审计 | 通过 | 308491检查、36 LP；松弛最大差226.8456元 |
| 图表与论文增补 | 完成 | 两张ModelViz英文PNG/SVG，实际检查和修复证据，innovation_draft.md |
| 表格/图文/旧包保护 | 通过 | 16154检查，artifact_validation.json |
| 冻结包 | 生成并复制包复验 | deliverables/innovation/v1_exploratory；以package_validation.json为最终执行证据 |
| 正式导出/组合/Q4迁移 | 未执行 | 需先确认口径并另开版本 |

3月选择：PV校正、固定余量、不加门槛。后续PV省46146.49元（约0.403%）；风险只省2—5元，不足作实质创新证据；门槛α0.5/0.75分别增2279.99/135578.73元。保留所有失败与冻结选择，不因评价期结果修改选型。

风险参考只作用于规划，实际贪心控制未必跟随计划SOC，实际参考未达不是物理硬约束违反。下一步优先整合全文及确认终态/时间/结算；如研究执行器升级，必须给所有对照同一执行器，以新版本检验，不归为原风险模块的已实现收益。
