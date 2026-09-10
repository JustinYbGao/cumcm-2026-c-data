# C题数据工作区

本目录独立于朋友的 `111`，所有脚本直接读取 `../CUMCM2026Problems/C题/附件/`，不复制、不覆盖原附件或其他成员代码。只做数据与验证，不训练预测模型、不求解优化、不填写附件5。

## 一键重建

已配置环境下，在项目根目录执行：

```bash
cd /Users/justingao/Documents/CUMCM
C题工作区/.venv/bin/python C题工作区/scripts/run_pipeline.py
```

迁移到其他电脑（Python 3.11或3.12）时：

```bash
cd /path/to/CUMCM
python3 -m venv C题工作区/.venv
TMPDIR="$PWD/C题工作区/data/interim" C题工作区/.venv/bin/python -m pip install -r C题工作区/requirements.txt
C题工作区/.venv/bin/python C题工作区/scripts/run_pipeline.py
```

本机环境使用Codex提供的Python 3.12与现有pandas/openpyxl等依赖，项目内虚拟环境补充matplotlib/IPython。实际版本见 `logs/runtime_versions.json`。运行不依赖电脑时区，不联网获取竞赛数据。安装依赖才需要网络。

脚本顺序为原文件探查 → Q1生成与读回验证 → 全年供需及价格 → 小时预报 → 十分钟预报 → 基础数据读回验证 → 小时电量预报诊断及独立验证 → 111审计重跑 → 文档和图。每步失败立即退出，退出码与日志真实保留。`logs/run_summary.json`还检查验证不修改输出，并比较重建前后的全部processed CSV哈希。

仅重新生成Q1：

```bash
C题工作区/.venv/bin/python C题工作区/scripts/prepare_data.py --stage q1
C题工作区/.venv/bin/python C题工作区/scripts/validate_data.py --stage q1
```

首次在新目录单独运行验证前，请先执行 `inspect_data.py` 建立只读源文件清单。`prepare_data.py --stage hourly`生成至小时预报原表，不生成派生十分钟数据。

## 数据入口

| 文件（data/processed/） | 用途 |
|---|---|
| fixed_price.csv | 144时段固定价格，slot_id键 |
| q1_day.csv | Q1给定负载和PV预测，功率、电量及有符号净负载 |
| actual_10min.csv | 全年供需、固定价及实际波动价，共52560区间 |
| pv_forecast_hourly.csv | 35040条原始整点预报，保留每个发布版本 |
| pv_forecast_10min.csv | 分段线性积分电量，210234行，第一份缺首小时 |
| pv_forecast_hourly_evaluation.csv | 35040条事后小时电量比较记录，含实际值；只作评估或经errors_at筛选后使用 |

数据字典见 `reports/data_dictionary.md`，口径见 `reports/processing_notes.md`，质量结论见 `reports/quality_report.md`。模板存在十分钟偏移问题，见 `reports/template_review.md`。朋友的具体进度与逐值审计见 `reports/111_audit.md`。

新增数据诊断见 `reports/pv_forecast_diagnostics.md`，分组误差汇总见 `reports/pv_forecast_error_summary.csv`，月度/星期观测汇总见 `reports/actual_calendar_summary.csv`。完整数据阶段验收清单见 `reports/data_completion.md`。这些统计不训练模型，不得用全年统计构造早期预测特征。

## 决策时可用数据接口

`scripts/prepare_data.py` 提供 `history_at(actual, decision_time)` 与 `forecasts_at(forecasts, decision_time)`，接收已读DataFrame和无时区完整时间字符串，返回副本。CSV时间字符串也会解析。可从任何下游脚本将本目录scripts加入模块路径后导入；使用示例保存在 `scripts/example_access.py`，运行示例同样不会产生模型或策略数值。

- 实际区间只有在 `interval_end <= decision_time` 才返回；实际价格同样只返回历史。
- 小时预报要求 `issue_time <= decision_time` 且 `target_time > decision_time`。
- 十分钟预报要求 `issue_time <= decision_time` 且 `interval_start >= decision_time`，因此不会将已经开始的区间冒充完整未来区间。
- 返回所有合法版本，不自动去重。选最新版本时，应在筛选之后按目标区间挑选；完整归档表仍保留。
- 固定价格从fixed_price独立读取，可作为已知日内价格；实际全年表不是随时可见的预测输入。没有生成预测价格或全年训练特征。

`scripts/diagnose_forecasts.py`另提供 `errors_at(evaluation, decision_time)`，仅返回该时刻已经完整结束、有实际值且预测完整的小时误差。读取evaluation CSV时建议指定 `dtype={'actual_positive_pv':'boolean'}`，明确区分零PV与缺失实际值。`error_available_time`为目标小时末；该表绝不能直接作为当时已知的全部特征。

## 本轮范围与后续

Q1可以进入优化输入环节；Q2可开始因果预测与实际回放；Q3具备版本预报与2—12月完整十分钟输入；Q4具备实际价格结算与历史价格输入。最终优化、负载/PV/价格预测、SOC衔接和正式结果填写由后续阶段完成。先确认时间、功率、端点和价格可知条件等假设。

`data/interim`保存题面抽取、源文件清单、日期变换日志、预报覆盖、111运行副本。`reports/figures`存放三张描述性图；绘图源代码为 `scripts/report_data.py`。本轮没有单独创建空模块。
