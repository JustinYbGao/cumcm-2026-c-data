# 数据阶段交付范围与验收索引

本清单记录C题工作区当前交付，不改变111原目录的历史进度。运行结果以最新logs/run_summary.json、validation_all.md和validation_forecast_diagnostics.json为准；任何脚本非零退出不能视为验收通过。

| 数据任务 | 实现与证据 |
|---|---|
| 原附件、工作表、字段、日期和数值探查 | inspect_data.py；source_inventory.json、source_manifest.json |
| Q1与固定价格先行交付 | q1_day.csv、fixed_price.csv；validation_q1.md |
| 全年供需与价格长表连接 | actual_10min.csv；完整52560区间，逐原单元格数值核对 |
| 原始小时预报全版本 | pv_forecast_hourly.csv；35040条、1460次发布、日期填充日志 |
| 小时预报转十分钟电量 | pv_forecast_10min.csv；旧版端点、210234条；逐段独立积分复算 |
| 原值追溯、零值、负净负载和跳变 | 原行列字段、transformation_log.csv、numeric_summary.csv、largest_jumps.csv；未改功率 |
| 历史实际与预报信息隔离 | history_at、forecasts_at；边界测试与23个决策时间检查 |
| 统一口径的预报误差 | pv_forecast_hourly_evaluation.csv；同小时6段电量求和，缺失保留 |
| 相同目标集合的版本比较 | pv_forecast_common_targets.csv、pv_forecast_error_summary.csv；8742个共同小时 |
| 误差校准前的历史访问接口 | errors_at；369个时点及小时结束边界验证，本轮不拟合校准参数 |
| 日总量、月份、星期和代表日诊断 | daily_energy.csv、actual_calendar_summary.csv及3张探索图 |
| 模板结构与输出要求 | template_review.md、template_cells.csv；原模板未改、未填策略值 |
| 111代码与已有输出核验 | audit_111.py、111_audit.md；环境适配副本重跑、原文件不动 |
| 复现与读回验证 | run_pipeline.py、运行日志、输出哈希；测试不改交付数据 |

数据层可继续完成的项目已纳入脚本。以下是事实缺口或建模决定，不能通过清洗编造解决：

- 2025-01-01第一份预报的首小时没有已发布旧端点，留缺6个区间。
- 跨年目标缺实际值，保留空值和状态；不要求把全部预报强行变成可评估样本。
- 原功率平均值/点值、时段结束标签、旧版首小时端点、实际记录可用性属于显式假设，仍需队伍确认。
- 附件5首末时段偏移与跨日标签不一致，最终提交映射需要确认；原模板不改。
- Q4未来价格可知条件、储能效率、SOC、终端条件、调整结算等不属于数据清洗，留给建模阶段。

下游接口要求：决策变量用kWh；供给≥需求，或引入非负富余量后的等价等式；常规购电费按计划/承诺量而非实际用掉的量结算。这些要求已在建模方案中表达，数据阶段没有声称实现优化或费用审计程序。

Q1可接调度求解，Q2可接因果预测与回放，Q3可接原始版本/派生电量滚动输入，Q4可接历史价格及实际结算数据。最终模型、策略效果和正式结果仍未生成。
