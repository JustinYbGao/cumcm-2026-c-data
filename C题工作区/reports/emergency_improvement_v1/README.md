# Q2 风险采购研究结果包

先读 `research_report.md`（人话结论），再读 `independent_review.md`（独立+BZD审查）；论文补充位于 `papers/emergency_improvement_v1/paper_supplement.md`。以下路径除特别说明外均相对于 `C题工作区` 或解压后的对应工作区根目录。

主结论：预定P（τ0.8、残差28日）实际费用14209509.85元，相对B0节省2124173.55元、相对季节性B1节省1168697.51元。E/PE失败保留。本包不是正式提交版，不包含对旧XLSX/旧论文的替换。

## 内容索引

| 路径 | 用途 |
|---|---|
| `reports/emergency_improvement_v1/protocol.md`、`protocol_freeze.json` | 新候选运行前冻结的研究设计及哈希 |
| `configs/emergency_improvement_v1/experiments.json` | 全18条预定年度路径及随机种子 |
| `scripts/emergency_improvement_v1/policy.py` | 净负荷风险校准、原函数无副作用加载、条件E与口径变体 |
| `scripts/emergency_improvement_v1/run_experiments.py` | 发布预测、计划、连续执行及导出 |
| `scripts/emergency_improvement_v1/independent_verify.py` | 不导入生产预测/规划/执行器的独立复算 |
| `scripts/emergency_improvement_v1/causality_checks.py` | 修改未来源数据后整条决策链重跑 |
| `scripts/emergency_improvement_v1/analyze_results.py` | 全比较、消融、覆盖、块自助、压力与四指定日CSV |
| `results/emergency_improvement_v1/inputs/` | 已处理原始输入副本、旧函数/配置、冻结B0/B1/无储能账本、题面、BZD单记录 |
| `results/emergency_improvement_v1/forecasts/` | 1月2日—12月31日，两种滚动发布预测与模型参数 |
| `results/emergency_improvement_v1/runs/<policy>/` | 每条年度路径的`config.json`、`plans.csv`、`ledger.csv`、`daily.csv`、`summary.json`、`models_and_solvers.json` |
| `results/emergency_improvement_v1/january/` | 五种策略的一月17天软件门槛检查，不改主实验预热策略 |
| `results/emergency_improvement_v1/causality/` | 五种策略原输入/未来扰动后的完整测试轨迹 |
| `results/emergency_improvement_v1/comparison_all.csv` | 18种方案及同设定B0/B1引用；`reference_B0_policy`与`reference_B1_policy`指明配对对象 |
| `results/emergency_improvement_v1/paired_assumption_sensitivity.csv` | 终态/效率/功率成对比较及期末库存 |
| `results/emergency_improvement_v1/daily_costs_and_differences.csv`、`monthly_costs_and_differences.csv`、`hourly.csv` | 每日、月、时费用差与紧急交易统计 |
| `results/emergency_improvement_v1/forecast_coverage.csv`、`forecast_lead_time.csv` | 月/小时/预测跨度覆盖、误差及分位损失；不同τ的损失不能直接当同一尺度选优 |
| `results/emergency_improvement_v1/block_bootstrap.csv`、`ablation.json` | 7/14日块自助结果及四格消融 |
| `results/emergency_improvement_v1/stress/` | 22个历史联合误差情景、66条状态条件路径、来源与裁切记录 |
| `results/emergency_improvement_v1/representative/` | 3月20、6月21、9月23、12月21表1区间/全天/终态、表2分块充放电、表3逐段紧急购电 |
| `reports/emergency_improvement_v1/independent_validation.json` | 最终72754385次独立比较通过；中间未完成目录FAIL另存，不覆盖历史 |
| `reports/emergency_improvement_v1/figures/{annual,monthly}/` | 真数据副本、模板召回/选择、依赖、适配脚本、技术/视觉质检、300dpi PNG及SVG |
| `reports/emergency_improvement_v1/{environment.json,requirements.lock.txt}` | 本次软件环境和依赖版本 |
| `reports/emergency_improvement_v1/{protected_hashes_before.json,preservation_validation.json}` | 2837个旧文件完整性证明 |
| `reports/emergency_improvement_v1/{code_and_input_hashes.json,package_manifest.csv}` | 本轮输入/代码和包内文件SHA-256 |

账本单位为kWh和元；显示表可能转为万元或百万CNY，CSV保留原精度。`dispatch_time`及`decision_input_cutoff`为当前区间结束时刻，表示继承的区间即时平衡假设，不是提前知晓未来实现值。风险历史起止记录实际入池日期，`risk_sample_count`为每小时池样本数（天数×6）。

## 不覆盖原件的复现

在项目根目录运行下列命令，将在本研究结果目录内创建全新的`reproduction_workspace`。若已有该目录，命令主动报错；可用`--target`指定另一个尚不存在、位于C题工作区的独立目录。

```bash
cd /Users/justingao/Documents/CUMCM
PYTHONDONTWRITEBYTECODE=1 C题工作区/.venv/bin/python C题工作区/scripts/emergency_improvement_v1/reproduce.py
```

该命令从包内输入快照创建独立工作区，按顺序执行发布预测→B0/B1复现→一月B0/B1/P/E→未来扰动软件检查→独立一月门槛→PE一月→主年度→敏感性→分析/压力→独立全量验收，最后将18种总费用与本包对照，阈值1e-5元。未来扰动检查包括PE软件集成，不作为其正式经济回放；PE经济回放仍在独立门槛之后。终止时若求解器未达到最优或任何检查失败，不出版替代结果。不会读取附件3/Q3预报，也不重算Q3/Q4。

在其他机器解压后，使用Python3.12及`requirements.lock.txt`中相同数值包版本，从解压根目录执行：

```bash
PYTHONDONTWRITEBYTECODE=1 python scripts/emergency_improvement_v1/reproduce.py
```

独立复制工作区的保护清单只覆盖包内提供的源快照。原工作区2837个文件不变的证明仍是随包保存的原验收证据，不声称其他机器也存在全部旧成果。

本轮已实际完成移植P的334天复现，账本SHA-256完全相同；没有为了包装再次重复全部18条年度优化。原主实验18条路径和它们的全量独立验收均已实际运行。总复现入口的因果检查依赖顺序修复后，又在隔离工作区实际重跑四条一月路径及全部因果测试，一月独立门槛通过；原始门槛报告保存在 `reproduction_january_gate.json`，修复和负对照见 `reproduction_dependency_validation.json`。

## 单阶段命令说明

以下在新复制工作区根目录运行，用同一Python环境；`run_experiments.py`拒绝覆盖已存在策略目录。常规用户优先使用上面的总复现命令。

```bash
python scripts/emergency_improvement_v1/test_policy.py
python scripts/emergency_improvement_v1/run_experiments.py forecasts
python scripts/emergency_improvement_v1/run_experiments.py baselines
python scripts/emergency_improvement_v1/run_experiments.py january
python scripts/emergency_improvement_v1/causality_checks.py
python scripts/emergency_improvement_v1/independent_verify.py --scope january
python scripts/emergency_improvement_v1/run_experiments.py january_pe
python scripts/emergency_improvement_v1/run_experiments.py main
python scripts/emergency_improvement_v1/run_experiments.py sensitivity
python scripts/emergency_improvement_v1/analyze_results.py
python scripts/emergency_improvement_v1/independent_verify.py
```

使用`PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1`保持本次环境设置；程序将求解/绘图缓存放入该复制工作区自己的研究目录。没有将比赛产物写入tmp。

## 图表复现与检验

modelviz-skill流程的模板召回、结构化模型决策、原模板哈希和真实视觉审查均已保留。数值结果重跑不需要重新调用模型。只复现已验收图时，从包内真实绘图CSV运行适配脚本即可；输出位置使用新目录。

```bash
python scripts/emergency_improvement_v1/plots/annual.py reports/emergency_improvement_v1/figures/annual/data.csv reports/emergency_improvement_v1/figures/annual/reproduced_outputs
python scripts/emergency_improvement_v1/plots/monthly.py reports/emergency_improvement_v1/figures/monthly/data.csv reports/emergency_improvement_v1/figures/monthly/reproduced_outputs
```

图像像素或SVG元数据可能随字体、Matplotlib环境和生成时间改变；数值数据校验与图片版式检查分别进行。图内全部英文，PNG为300dpi，SVG文字可编辑。修复记录保留月度图脚注对共同尺度含义的澄清。

## 包完整性与保留范围

执行`verify_package.py`只读核对清单及文件SHA-256，不重算模型，不修改账本：

```bash
python scripts/emergency_improvement_v1/verify_package.py
```

ZIP保存全部本轮科学输入、代码、配置、预测/计划/执行、分析、检查、报告与图。为避免重复和环境污染，仅排除运行缓存及移植检查的重复工作区；移植检查日志和验证结果保留。包清单不包含它自身、ZIP本身及ZIP校验旁文件，避免自引用哈希。若重跑或编辑文件，应生成新版本清单，不把旧哈希继续用于已变化的文件。

本轮AI辅助研究/代码/审查均为实际工作记录，未编造人工审核签名。BZD单条资料的完整署名和非商业许可原样保留；正式比赛AI使用声明仍应按团队真实记录补齐。
