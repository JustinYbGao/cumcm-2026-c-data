# Q2直接采购研究结果包 v4

本轮继续研究得到：**D112总费13,913,892.48元，紧急费838,655.45元**，满足本次334天历史回放的100万元紧急费上限；比v3最佳再省80,389.78元。普通费减少274,753.07元，紧急费增加194,363.29元。若希望紧急费也下降，D56_risk625总费13,944,430.74元、紧急费638,539.01元，比v3分别少49,851.51元和5,753.16元。

这是历史探索中的最低已验证结果，不能称极限或未来保证。D112相对v3有84天、3个月总费更高；7/14日块区间跨零。增加搜索预算的两条追加方案均更贵。全知未来的334天下界12,227,565.30元需要预知未来，差额不是承诺还能省的钱。

## 阅读顺序

1. `research_report.md`：人话结论、成本分解、八条方案及四个基准、失败与限制。
2. `../../papers/q2_direct_v4/paper_supplement.md`：可接入Q2章节的公式、算法、结果与验证草稿。
3. `../../results/q2_direct_v4/analysis_all/comparison_all.csv`、`acceptance.json`：最终12策略全表。版本结果根目录同名表是初轮6新+4基准，原件保留，不与最终表混用。
4. `independent_*.json/md`：独立源数据、实际账本、历史场景、择优、导数、因果、全知证书、统计、论文与图表审核。
5. `protocol.md`/`protocol_freeze.json`：初轮六方案；`refinement_protocol.md`/`refinement_freeze.json`：看到初轮后追加的两条预算敏感性。`cap_clarification.md`区分数值核对容差与业务硬上限。

## 目录与证据

- `scripts/q2_direct_v4/`：C99双精度核、Python策略、运行、因果扰动、分析、独立验证、图表、文稿与复现脚本。
- `configs/q2_direct_v4/`：初轮及追加配置。每日计划不读未来真实数据；最终选择和追加研究受已观察历史年影响，不称盲测。
- `results/q2_direct_v4/inputs/`：原始处理后数据、价格、原代码/配置/题面、原基线账本副本；`forecasts/`为当时发布预测档案。独立验证从源前缀重建预测。
- `references/`：B0、B1、P_floor、v3最佳原冻结账本及说明。此次重算其实际物理/费用，没有悄悄改解旧基线。
- `january/<policy>/`：先行小样本门槛；`runs/<policy>/`：各自独立连续334天账本；`causality_original/`和`causality_mutated/`：全部八配置的三日源数据扰动。
- 每条路径含`config.json`、`ledger.csv`、`plans.csv`、`daily.csv`、`summary.json`、`decisions.json`、`decision_evidence.npz`。六候选顺序固定：profile_start/profile_incumbent/profile_final/point_start/point_incumbent/point_final；NPZ包含q、场景净负荷、实际5p情景紧急费、末态、经验目标、选择序号和完整MILP起点。NaN仅填充不同日期的场景数。
- 初轮一月原产物缺少完整MILP起点数组，另存`initializer_certificate.npz`补充证书；重跑后全部原候选q和score逐位相同，原文件未覆盖。
- `oracle_source/`：全知LP原始/对偶证书；独立检查同q的严格贪心实际可行性与相同费用。LP与贪心SOC不同，不是同一个调度轨迹。
- `analysis_all/`：全表、配对日/月/小时、胜负统计、时间块重采样、优化器记录与验收；`figures/`在报告目录，包含modelviz真实模板召回/适配、英文PNG/SVG与技术/视觉核验。
- `environment.json`、`requirements.txt`、`compiler_build.json`、`computation_scale.json`记录版本、编译和规模；`code_and_input_hashes.json`、`package_manifest.csv`用于追溯。

## 复现

在本工作区执行（本机虚拟环境已具备依赖）：

```sh
cd '/Users/justingao/Documents/CUMCM/C题工作区'
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/q2_direct_v4/reproduce.py --target results/q2_direct_v4/reproduction_user_01
```

目标必须尚不存在。脚本将输入与代码复制到该版本下的新工作目录，重新编译C核，独立重建预测来源，重跑最佳D112完整334天并独立核验实际账本和六候选证据，最后对比原附件。已经完成一次此项复现，见`portability_validation.json`与`portability_completed.log`，账本数字差0，全部候选证据逐位相同。`reproduction_completed`重复工作区不打入ZIP，汇总证据和日志保留。

在另一台机器解压包后，使用具有`requirements.txt`所列库的Python和可用C99编译器（本机为Clang）；将上述解释器改为相应Python、工作目录改为解压根。数值路径不依赖本机modelviz目录，图表重制额外需要已安装modelviz-skill。默认复现目录位于解压后的`results/q2_direct_v4`，不会覆盖交付的`runs`。

若要重跑全部八条，在一个**新的结果包副本**内保留`inputs/forecasts/references/oracle_source`，将已有`january/runs/causality_original/causality_mutated`目录另存后运行：

```sh
python scripts/q2_direct_v4/run_experiments.py january
python scripts/q2_direct_v4/independent_verify.py --scope january
python scripts/q2_direct_v4/run_experiments.py runs
python scripts/q2_direct_v4/causality_checks.py
python scripts/q2_direct_v4/run_experiments.py january --refinement
python scripts/q2_direct_v4/independent_verify.py --scope refinement_january
python scripts/q2_direct_v4/run_experiments.py runs --refinement
python scripts/q2_direct_v4/causality_checks.py --refinement
python scripts/q2_direct_v4/analyze_results.py --all
python scripts/q2_direct_v4/independent_verify.py --scope annual
python scripts/q2_direct_v4/independent_verify.py --scope refinement_annual
python scripts/q2_direct_v4/independent_verify.py --scope causality
python scripts/q2_direct_v4/independent_verify.py --scope refinement_causality
python scripts/q2_direct_v4/independent_verify.py --scope analysis_all
```

这些命令沿用`PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`环境；Python入口将运行缓存设在本版本results/runtime中。首次单策略复现会创建独立源验证所需的`data/processed`与旧配置镜像。不要在交付原件上删除或覆盖已有目录。

## 验收口径与限制

实际结算始终普通p、紧急全额5p；00:00采购冻结，紧急只能补缺口；SOC1200—10800kWh、充放效率各.9，功率5000kW对应每10分钟5000/6kWh。物理检查1e-6kWh，账单核对1e-5元，业务紧急费严格≤1000000元。期末库存按预先固定ν=.6895775元/kWh辅助比较，真实账单不减该项。

本轮公开取消原附加的名义点预测零缺口/规划日末固定1200限制；它们仅用于MILP起点，实际设备和执行规则未改变。场景均值的统计前提未证实，L-BFGS-B不光滑局部搜索没有全局保证，区间末可用信息等仍是原工作假设。BZD完整署名和许可在字典JSON，原始外部资料和适配范围见`method_fit_and_sources.md`。

初次最终聚合因局部变量重名失败，文稿曾出现LaTeX字符串转义问题，首版费用图底注重叠；均已局部修复并重验，失败日志保留。它们未改变任何回放账本、参数或结果选择。原4305个受保护科学文件另以SHA核验；没有覆盖旧论文或XLSX，没有重算Q3/Q4，没有commit/push。

压缩包为`q2_direct_v4_review.zip`；旁附`.sha256`、`package_manifest.csv`与`package_validation.json`。清单不自包含其自身哈希，验证旁文件不进入包内自引用；ZIP内容逐文件SHA读回核对。运行缓存与两份重复复现工作区排除，全部新科学证据、完整失败结果、代码和输入保留。
