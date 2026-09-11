# Q2库存终态与有限费用选择：结果包入口

先读[研究报告](research_report.md)，再读[论文补充](../../papers/q2_cost_aware_v2/paper_supplement.md)。这是新增研究版本，保留原Q2、上一轮风险采购成果、旧论文、正式XLSX和ZIP，不是正式提交文件；没有重算Q3/Q4，没有commit/push。

主要发现：简单P_floor总费14022838.60元，比B0/B1/P分别少2310844.79/1355368.75/186671.25元；比已测6000终态仅少12790.19元且描述性区间跨零。S_terminal最低，但只再少1160.79元；预定S_joint没有胜过两个固定终态对照。九条新年度路径和四个旧对照全部报告。

## 文件索引

下列路径以C题工作区为根，相对布局在解包后保持不变。

| 内容 | 路径 |
|---|---|
| 科学结论/论文 | `reports/q2_cost_aware_v2/research_report.md`、`papers/q2_cost_aware_v2/paper_supplement.md` |
| 事前七路径协议 | `reports/q2_cost_aware_v2/protocol.md`、`protocol_freeze.json`；`configs/q2_cost_aware_v2/experiments.json` |
| 事后两路径探索协议 | `reports/q2_cost_aware_v2/extension_protocol.md`、`extension_freeze.json`；`configs/q2_cost_aware_v2/extension.json` |
| BZD方法适配/审查 | `method_fit_and_workflow.md`、`independent_bzd_review.md`；848/487/4207单记录及完整许可 |
| 原输入/预测 | `results/q2_cost_aware_v2/inputs/`、`forecasts/`；两预测器均可独立从过去实际重建 |
| 每条新路径 | `results/q2_cost_aware_v2/runs/<policy>/`：ledger、plans、daily、summary、config、decisions、decision_evidence |
| 旧冻结对照 | `results/q2_cost_aware_v2/references/{B0,B1,P,P_terminal}/`，全部与旧源SHA一致 |
| 所有统计 | `results/q2_cost_aware_v2/comparison_all.csv`、daily/monthly/hourly、selection_counts、ablation、block_bootstrap |
| 简单终态补充统计/指定日表 | `results/q2_cost_aware_v2/followup_diagnostics/`，单独标为结果后描述性分析 |
| 主方案等指定日表 | `results/q2_cost_aware_v2/representative/`，四日期×采购/充放电/紧急表 |
| 因果检查 | `causality_inputs/`、`causality_extension_inputs/`、`causality_original/`、`causality_mutated/`及reports中的对应validation |
| 尾部诊断与理想界 | `results/q2_cost_aware_v2/stress/`、`lower_bound/`，不混作真实可执行收益 |
| 独立证据 | `reports/q2_cost_aware_v2/independent_validation.json`、`independent_validation_followup.json`、`independent_numeric_review.md` |
| 独立验证器版本 | `scripts/q2_cost_aware_v2/independent_verify.py`；主检查时精确源码冻结于`independent_primary_validator_snapshot.json`，新增followup入口不篡改原报告 |
| 图与来源 | `reports/q2_cost_aware_v2/figures/{annual,monthly}/outputs/chart.png`和SVG，workspace含召回/选择/代码/执行/质量/源SHA |
| 环境与溯源 | `environment.json`、`requirements.lock.txt`、`code_and_input_hashes.json`、`preservation_validation.json`、`package_manifest.csv` |
| 失败与调整 | `change_log.md`、原失败日志、绘图修正前文件；不含未披露的成功筛选 |

NPZ按日期、候选、情景、时段记录。`decisions.json`给出精确列名、候选次序、选择索引、历史日来源和有效情景数；部分日期历史短于最大窗口，NPZ末尾NaN仅为矩形填充，必须按有效情景数截取。不能当成数值失败或额外场景。实际账本才是总费用评价来源，评分包含的库存代理不能充作收入。

## 不覆盖交付文件的复现

运行环境为Python3.12.14，NumPy2.3.5、pandas2.2.3、highspy1.14.0、SciPy1.18.1；日MILP单线程、种子0、时限120秒、相对gap1e−9、绝对gap1e−7、原/对偶/整数可行性容差1e−8。LP时限300秒、原/对偶可行性容差1e−9。全部日MILP成功，无超时或回退；不同环境若出现多解或求解差异，应保留差异，不能静默改基线。

在项目根目录`/Users/justingao/Documents/CUMCM`运行：

```sh
C题工作区/.venv/bin/python C题工作区/scripts/q2_cost_aware_v2/verify_package.py
C题工作区/.venv/bin/python C题工作区/scripts/q2_cost_aware_v2/reproduce.py --smoke --target C题工作区/results/q2_cost_aware_v2/new_smoke
C题工作区/.venv/bin/python C题工作区/scripts/q2_cost_aware_v2/reproduce.py --target C题工作区/results/q2_cost_aware_v2/new_full_replay
```

目标必须是本版本results下尚不存在的目录。全流程复制输入、冻结档案和4对照，独立从原始已处理实际前缀重建验证两种预测，然后运行手算测试、一月门槛、因果扰动、LP、9条年度、全量独立验证、结果后终态统计和增量核验。它不会向原结果写入，也不会访问网络或执行Git命令。全量复现会产生约2.4万个年度MILP和所有证据，时间、磁盘占用明显大于smoke。

**实际完成的搬迁复验是smoke完整P_floor路径，不是再次全量重算九条。** 其334天所有账本数值与文本完全一致，最大数值差0、总费差0；独立新目录数学核验通过，结果见`portability_validation.json`。主工作目录中九条年度及全量独立验证已实际执行，不能混淆这两个验证范围。

解包至其他机器时，以新解包目录为C题工作区根，使用本机满足锁定依赖的Python运行其`scripts/q2_cost_aware_v2/reproduce.py`，省略target即可在该版本results下自动创建新目录。数值工作不依赖ModelViz或旧项目目录存在，复现器会从保留副本构造必要源路径。

## 图表复现与独立检查

交付的适配脚本只依赖NumPy/pandas/Matplotlib，可直接以CSV和新的输出目录为参数运行；无需重新调用ModelViz服务：

```sh
MPLCONFIGDIR=C题工作区/results/q2_cost_aware_v2/runtime TMPDIR=C题工作区/results/q2_cost_aware_v2/runtime C题工作区/.venv/bin/python C题工作区/scripts/q2_cost_aware_v2/plots/annual.py C题工作区/reports/q2_cost_aware_v2/figures/annual/data.csv C题工作区/results/q2_cost_aware_v2/new_plot_annual
MPLCONFIGDIR=C题工作区/results/q2_cost_aware_v2/runtime TMPDIR=C题工作区/results/q2_cost_aware_v2/runtime C题工作区/.venv/bin/python C题工作区/scripts/q2_cost_aware_v2/plots/monthly.py C题工作区/reports/q2_cost_aware_v2/figures/monthly/data.csv C题工作区/results/q2_cost_aware_v2/new_plot_monthly
```

上述命令已将MPLCONFIGDIR/TMPDIR设在本版本runtime内；解包后若不存在该缓存目录，请先创建。沿用比赛文件不进入tmp的限制。完整ModelViz服务重放另需本机原skill路径和langchain-core等依赖；交付保留全部服务记录及脚本SHA，未把其本机目录依赖隐藏成跨机器必然可用。图内全部英文；实际查看PNG后才提交视觉通过意见。

独立数值验证可在复现目录使用`independent_verify.py --scope all`；追加统计为`--scope followup`。在已交付原目录运行会改写审计报告时间戳并使清单SHA变化，所以日常只读核验用`verify_package.py`，数学重验在新的复现目录进行。

## 打包口径

ZIP包含本轮5个独立目录的科学代码、配置、输入、计划/回放、统计、独立证据、图和文稿。排除运行缓存、重复搬迁工作区及包自身；搬迁验证JSON和日志另附。清单列文件SHA，ZIP读回逐项核验，并另留整包SHA侧车。3268个旧科学文件的保护检查独立于包内清单；旧成果从不重新打包成“新实验”。

结果不支持未来收益保证、完整随机最优性或对原题歧义的最终解释。更早冷启动不足7个情景日当前会显式停止，不能据本次结果宣称该回退能力已完成。建议在新年度验证少量冻结终态，当前不继续在同一年无边界调参。

年度实际计算规模：23714次MILP，累计求解器耗时628.916秒，最大单次0.073561秒，最大相对MIP gap为5.392e−16，失败/回退均0。LP耗时1.853秒。这些是当前机器实测求解器时间，不包括独立复核、I/O、图表和论文处理。
