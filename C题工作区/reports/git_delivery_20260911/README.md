# Main branch delivery — 2026-09-11

本次交付包括之前的创新/鲁棒性实验、Q2 紧急购电研究 v1—v4、独立审查、论文补充和修复版输出文件。没有为推送而重新计算模型或修改已有科学结论。

优先阅读（路径相对于 C题工作区）：

| 内容 | 入口 |
|---|---|
| 之前的创新实验 | `reports/innovation/model_and_results.md` |
| 已有鲁棒性实验 | `results/robustness/`、`papers/assembly_v1/` |
| 第一轮紧急购电研究 | `reports/emergency_research_v1/research_note.md` |
| Q2 后续研究过程 | `reports/emergency_improvement_v1/`、`reports/q2_cost_aware_v2/`、`reports/q2_pareto_v3/` |
| 当前 Q2 v4 研究 | `reports/q2_direct_v4/README.md` |
| 当前最终12策略比较表 | `results/q2_direct_v4/analysis_all/comparison_all.csv` |
| 本次独立审查 | `reports/q2_direct_v4_audit_20260911/review.md` |
| v4 论文补充 | `papers/q2_direct_v4/paper_supplement.md` |
| 原修复版论文与输出 | `papers/Problem_Restatement_EN.md`、`outputs/revision_v1/README.md` |

四个大于普通 Git 单文件上限的审阅 ZIP 用 23 个原始字节分卷保存。
在仓库根目录执行以下命令恢复并校验；本地已有的相同 ZIP 不会被覆盖：

```bash
python3 C题工作区/deliverables/git_large_files_v1/restore.py
```

分卷清单、完整 ZIP SHA256 及说明见 `deliverables/git_large_files_v1/`。
原始 ZIP 的哈希保持不变，科学结果清单无需改写。完整展开的数据和报告也保存在常规目录中。

研究版本与正式候选输出仍分开。v4 尚未替换旧 result2.xlsx；历史探索、信息/时间工作假设和未来预算保证的限制继续保留。审查指出的原 `reproduce.py` 回写报告问题尚未修正；复现应在独立副本中操作，详见审查报告。
