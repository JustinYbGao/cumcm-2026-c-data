# C题数据工作区

本目录独立于朋友的 `111`，数据脚本直接读取 `../CUMCM2026Problems/C题/附件/`，不覆盖原附件或其他成员代码。问题1—4已有内部模型、实际求解、独立核验及论文初稿；问题2和问题4负结果继续保留。尚未填写正式附件5。当前进度见 `reports/workflow_progress.md`，较早报告中的后续状态属于当时快照。

## 最新交付：创新实验完成

- [论文实验增补](papers/innovation_draft.md)、[完整模型与结果](reports/innovation/model_and_results.md)、[冻结执行计划](reports/innovation/execution_plan.md)、[BZD检查](reports/innovation/bzd_solution_check.md)。
- 按统一方案顺序完成PV校正、连续风险余量、更新门槛，共11组；2月启动，3月校准，4—12月275天评价。明确属于探索性顺序回测。
- PV校正省46,146.49元；风险余量只有2—5元差额，不列为实质改进；α0.5/0.75门槛分别增费2,279.99/135,578.73元。3月冻结选择保留校正、固定余量和不加门槛，失败候选未删。
- 308,491项独立检查、36个独立LP、34项新旧单测通过；LP有真实松弛差，未声称完全等价。两张[全英文ModelViz图](reports/figures/modelviz_innovation_v1_en/)已实际检查。
- [冻结结果包入口](deliverables/innovation/v1_exploratory/README.md)，运输ZIP分卷与校验值见[archive_index.json](deliverables/innovation/archive_index.json)。所有分卷解压至同一目录，无需拼接字节。

```bash
.venv/bin/python -B scripts/validate_innovation.py
.venv/bin/python -B scripts/audit_innovation_lp.py
.venv/bin/python -B scripts/verify_innovation_artifacts.py
```

当前不生成正式Excel，不把单模块结果外推为组合策略或Q4提升。问题1—4原结果和冻结包保留。

## 问题4内部验收

- [问题4论文初稿](papers/q4_draft.md)、[模型与实际结果](reports/q4_model_and_results.md)、[四日完整表](reports/q4_representative_tables.md)、[BZD检查](reports/q4_bzd_solution_check.md)。
- 九组策略均以附件4实际价结算：日前OLS 17,030,881.70元，比同核固定价输入省42,860.98元（0.251%）；日内全更新A/OLS 14,534,062.64元，反而比固定价输入多6,183.03元。B/OLS为14,537,309.28元。
- 全更新A比同PV来源的仅0点OLS省2,108,394.56元；单独再估价格比保持0点价格多85.45元。不能把整体更新收益全归于价格预测。
- 211,834项独立检查、1,336次价格模型重建、36个独立矩阵LP、25项Q1—Q4单测通过。两张[ModelViz英文图](reports/figures/modelviz_q4_v1_en/)均有300 dpi PNG/SVG及实际视觉检查记录。
- [冻结包](deliverables/q4/v1_internal_variable_price.zip)包含来源、版本、完整账本、初稿及复制包数值重验日志；使用副本复验，不覆盖冻结版本。
- 正式时间、未来价格可用性、结算、效率及每日终态解释仍待确认，当前不是正式提交版。

在本工作区复核：

```bash
.venv/bin/python -B scripts/validate_q4.py
.venv/bin/python -B scripts/audit_q4_lp.py
.venv/bin/python -B scripts/verify_q4_artifacts.py
.venv/bin/python -B -m unittest discover -s tests -p 'test_q*.py'
```

首次安装使用requirements-q3.txt。完整重算必须另开版本且不复制完成结果目录；详见问题4报告。以下保留前阶段交付索引。

## 问题2冻结、问题3内部验收

- 问题2补齐[论文初稿](papers/q2_draft.md)与[138文件冻结包](deliverables/q2/v1_internal_baseline.zip)，已在复制包内重新独立验证。
- 问题3[论文初稿](papers/q3_draft.md)、[模型与数值说明](reports/q3_model_and_results.md)、[A/B四日完整表](reports/q3_representative_tables.md)、[BZD局部检查](reports/q3_bzd_solution_check.md)。
- 问题3主六组策略：只用0点预报15,842,067.99元；全更新A 13,772,880.06元、B 13,765,041.25元。补充仅状态反馈13,934,357.97元，新PV相对该控制再省161,477.91元；不能把总更新节省全归于新PV信息。
- 新图位于[modelviz_q3_v1_en](reports/figures/modelviz_q3_v1_en/)，全部英文、300 dpi PNG和SVG，保留模板决策、输入、修复与最终质检记录。
- 主实验110,401检查、补充30,048检查、36个独立LP时域、20项Q1—Q3单测通过；来源/图文201项检查通过，118份原数据及旧结果保持原哈希。
- 问题3冻结包入口：[deliverables/q3/v1_internal_mpc.zip](deliverables/q3/v1_internal_mpc.zip)。内部工作假设；正式模板时间映射、A/B结算及效率等仍待确认。

Q3数值在 `results/q3/`，补充控制在 `results/q3_feedback_control/`。复核命令（在本工作区运行）：

```bash
.venv/bin/python -B scripts/validate_q3.py
.venv/bin/python -B scripts/validate_q3.py --results results/q3_feedback_control
.venv/bin/python -B scripts/audit_q3_lp.py
.venv/bin/python -B scripts/verify_q3_artifacts.py
```

首次新环境安装扩展依赖：`.venv/bin/python -m pip install -r requirements-q3.txt`。求解、报告及绘图命令见问题3结果说明；完成标记禁止覆盖既有求解，另开版本才能重算。本轮先使用了BZD workflow、dictionary、solution-checker以及ModelViz，另以边界单测和完成前验证流程核验代码。

## 最新交付与问题2基础版

- 图表已按 **modelviz-skill** 重做：[新图总览与复现说明](reports/modelviz_v3_en_revision.md)。四张图的标题、坐标、图例、注释及脚注全部使用英文，均提供300 dpi PNG和SVG，当前论文/报告已引用新图；旧图及Q1冻结包保留。以后绘图的约定见 [AGENTS.md](AGENTS.md)。
- 问题1论文初稿：[papers/q1_draft.md](papers/q1_draft.md)。
- 问题1冻结结果包：[deliverables/q1/v1_interval_end_assumption.zip](deliverables/q1/v1_interval_end_assumption.zip)，附SHA-256清单、来源快照和包内数值复现入口；保留原始结果，不在此包内改版。
- 问题2模型与结果：[reports/q2_model_and_results.md](reports/q2_model_and_results.md)；四日结果表：[reports/q2_representative_tables.md](reports/q2_representative_tables.md)。

问题2结果保存于 `results/q2/`。selected是只依据1月校准选中的模型，全年实际费用反而高于seasonal，不代表最终优选；失败对照完整保留。原计划与实际轨迹、紧急量及账单分列；各策略共享2月1日真实初态，之后各自连续运行。正式result2.xlsx仍待模板时间映射确认。

```bash
cd /Users/justingao/Documents/CUMCM/C题工作区
export PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$PWD/data/interim/q2"
.venv/bin/python scripts/run_q2.py > logs/q2/run.log 2>&1 &&
.venv/bin/python scripts/validate_q2.py > logs/q2/validate.log 2>&1 &&
.venv/bin/python -m unittest discover -s tests -p test_q2.py > logs/q2/tests.log 2>&1 &&
.venv/bin/python scripts/report_q2.py > logs/q2/report.log 2>&1
```

Q1冻结包校验：`.venv/bin/python -B deliverables/q1/v1_interval_end_assumption/scripts/verify_q1_package.py`。新版本打包前使用不同版本目录，不能覆盖v1。包内原始输入仅复制Q1所需三份文件作为来源证据，不改动它们。

## 问题1内部求解与验收

结果说明见 [reports/q1_model_and_results.md](reports/q1_model_and_results.md)，BZD模型适配和局部检查分别见 `reports/q1_model_fit.md`、`reports/q1_bzd_solution_check.md`。基准参数在 `configs/model_baseline.json`，逐区间结果、状态、指定表格、配置快照、模型和验证证据在 `results/q1/`，新图在 `reports/figures/modelviz_v3_en/`，旧图在 `reports/figures/q1/`，运行日志在 `logs/q1/`。

本轮仍采用原始时间为区间终点、十分钟平均功率、交流侧功率限额、固定初末6000 kWh、充放效率各0.9的工作假设；另求解往返0.9情景。原模板时间偏移未确认，未导出正式result1.xlsx。完整内部策略在 `results/q1/baseline/schedule.csv`。

```bash
cd /Users/justingao/Documents/CUMCM
export PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$PWD/C题工作区/data/interim/q1"
C题工作区/.venv/bin/python C题工作区/scripts/solve_q1.py > C题工作区/logs/q1/solve.log 2>&1
C题工作区/.venv/bin/python C题工作区/scripts/validate_q1_solution.py > C题工作区/logs/q1/validate.log 2>&1
C题工作区/.venv/bin/python -m unittest discover -s C题工作区/tests -p test_q1_solution.py > C题工作区/logs/q1/tests.log 2>&1
C题工作区/.venv/bin/python C题工作区/scripts/report_q1.py > C题工作区/logs/q1/report.log 2>&1
```

每条命令退出码须为0。新增依赖仅为 `highspy==1.14.0`，使用下文原有安装命令即可。Q1运行不重建数据，缓存和临时文件定向项目内 `data/interim/q1/`。数据清洗重建命令和用途如下，保持独立。

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

Q1—Q3内部结果与论文初稿已完成；Q2候选退化证据保留，Q3费用/时刻及信息反馈对照已完成。Q4具备实际价格归档，尚未计算。所有正式模板填写仍待时间映射确认。当前状态以workflow_progress.md为准。

`data/interim`保存题面抽取、源文件清单、日期变换日志、预报覆盖、111运行副本。`reports/figures`存放三张描述性图；绘图源代码为 `scripts/report_data.py`。本轮没有单独创建空模块。

## 论文装配与新增敏感性（2026-09-10）

先读 [装配顺序与逐文件归属](papers/assembly_v1/00_README_装配顺序.md)，或直接读[合并装配初稿](papers/assembly_v1/assembled_review_draft.md)。原五份初稿保留，新的[连续策略与稳健性初稿](papers/robustness_draft.md)已放入Part08，PV校正及迁移分别衔接Part06/07。

10条334日回放、429222独立检查、160 LP及11新增单测通过；图全部英文。主28天部署省46146.49元，有限对照方向稳定，但存在增费日/月，不作跨年保证。可追溯包入口：[README](deliverables/robustness/v1_continuous_audit/README.md)。当前仍为内部假设版，正式时间与交易等口径未确认。
