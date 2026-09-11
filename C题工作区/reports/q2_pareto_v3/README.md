# Q2 分时风险与100万元紧急费上限结果包

用户最终要求：实际总费用更低、2025年2—12月紧急购电费不超过100万元。本轮最低合格历史方案X_strong_morning85：总费13994282.258970976元，普通费13349990.093968334元，紧急费644292.1650026435元。相对P_floor省28556.33952757元，约0.204%。这是探索性历史回放，7/14日块区间跨零，不保证未来节省或上限。

先读research_report.md；论文补充在papers/q2_pareto_v3/paper_supplement.md。原66.13万元三条件协议在protocol.md，用户改变偏好后的追加协议在extension_protocol.md；不得混用两次验收。

## 路径与证据

以下相对路径均以C题工作区为根。解压ZIP后保留scripts/configs/results/reports/papers五级目录结构。

- scripts/q2_pareto_v3：预测/原执行支持副本、新分时与经验风险逻辑、连续回放、独立验证、分析、绘图与复现代码。independent_verify.py不导入生产逻辑。
- configs/q2_pareto_v3：experiments.json原十条；extension.json追加八条。完整24小时分位曲线、日期、初态、参数和随机种子均固定。
- results/q2_pareto_v3/inputs、forecasts、references：输入、历史发布预测及六对照副本。副本与原路径SHA一致。
- results/q2_pareto_v3/runs及extension_runs：18个年度路径，每个有config.json、ledger.csv、plans.csv、daily.csv、summary.json、decisions.json、decision_evidence.npz。NPZ包含所有候选计划/校准/整日情景/费用/末态/得分/CVaR/可行mask/选择索引，不只保留被选候选。填充场景使用NaN，实际数量见逐日scenario_count。
- results/q2_pareto_v3/january与extension_january：一月148候选门槛；causality_inputs及各causality目录：原始未来扰动与36条三日轨迹。
- results/q2_pareto_v3/comparison_all.csv、acceptance.json：原16策略旧标准。analysis_user_cap/中comparison_all.csv、eligible_ranking.csv、acceptance_user_cap.json：24策略新标准；daily/monthly/hourly、108组paired_daily、win_loss_counts和108行block_bootstrap全保留。
- 代表日：原representative/七策略，以及analysis_user_cap/representative/八追加策略，含三张题目表及完整账本，未覆盖旧XLSX。
- reports/q2_pareto_v3/independent_validation.json、independent_validation_extension_all.json、independent_final_numeric_summary.json：最终数值审计，18年度、14028候选、707819候选情景，1e−6kWh/1e−5元阈值。
- independent_text_review.json及对应Markdown：BZD九项正文审读。method_fit_and_workflow.md与两个bzd_*record.json：方法适配、原始来源及BZD署名许可。
- figures/savings和figures/monthly：真实ModelViz服务流程、候选选择/适配/依赖/执行/视觉检查报告、全英文300dpi PNG与SVG。无需在线模型API；人工智能助手提供结构化决策，真实图片已查看。
- portability_validation.json：独立新嵌套目录重放最好方案全334日，全部账本数字0差、文本一致；其他17条未在克隆目录重复跑，但已完整独立逐式审计。
- environment.json、requirements.numerical.txt、requirements.plotting.txt、code_and_input_hashes.json、package_manifest.csv、preservation_validation.json、package_validation.json：环境、最终输入/代码与文件SHA、3668旧科学文件保护、ZIP逐文件读回。

## 复现命令

在本机C题工作区运行。不会覆盖交付结果，目标目录已存在时会拒绝执行。

```bash
cd '/Users/justingao/Documents/CUMCM/C题工作区'
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/q2_pareto_v3/verify_package.py
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/q2_pareto_v3/reproduce.py --smoke --target results/q2_pareto_v3/reproduction_smoke_new
```

完整复现全部18条新路径、一月门槛、未来扰动、两轮分析与独立验证：

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/q2_pareto_v3/reproduce.py --target results/q2_pareto_v3/reproduction_full_new
```

脚本先在目标中重建旧输入/对照所需相对路径，源预测由独立审计器按历史前缀重算，无需外部原工作区或网络。新机器可在解压根建立Python3.12虚拟环境，并安装requirements.numerical.txt所列版本；严格账本复现依赖所列求解器/数值库版本。运行输出、临时缓存都在版本结果目录。完整复制重放可能需数分钟。

已有账本重新核验（原本机有保护清单全部源文件时）：

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/q2_pareto_v3/independent_verify.py --scope all
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/q2_pareto_v3/independent_verify.py --scope extension_all
```

这些审计会更新本版本审计报告；若需保持交付清单哈希，请优先使用隔离复现。图表可直接运行scripts/q2_pareto_v3/plots/savings.py或monthly.py，传入对应figures下data.csv和新输出目录，已适配脚本不依赖ModelViz本地安装；重跑完整ModelViz选模流程则需原skill服务及requirements.plotting.txt。本包保留模板源哈希与决策，不分发外部论文全文。

## 范围

沿用每向效率0.9、母线5000kW、区间末观测/段内自动平衡、5p全额紧急价、00:00合同冻结、已买未用仍付费等公开工作假设。最终最优是本次有限候选中的历史最低，不是全局最优或盲测。用户100万元上限与较早P的约64.18万元紧急费是不同门槛；最好新方案仍比P紧急费多2446.89元。

本轮未重算Q3/Q4，未覆盖旧论文、五份XLSX或旧ZIP，没有commit/push。所有新增科研文件位于本版本独立目录。runtime和重复portability_check/reproduction工作区不放入ZIP，复现结果摘要与日志保留；清单自身与打包验证旁文件为避免循环自引用不纳入清单，清单本身纳入ZIP。
