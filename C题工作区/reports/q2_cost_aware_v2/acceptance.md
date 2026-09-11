# Q2 v2研究验收表

本轮验收的是研究实现、因果实际回放和证据交付，不预设主方案费用最低。预定S_joint未超过两个固定终态对照；这项负结果已保留。研究候选P_floor较P更便宜，但对P_terminal的新增优势小，描述性区间跨零。

| 要求 | 已交付证据 | 验收范围 |
|---|---|---|
| 独立目录与保留旧成果 | 五个q2_cost_aware_v2目录；protected_hashes_before/preservation_validation | 3268个既有科学文件，最终以保护JSON为准；不覆盖正式XLSX/论文/ZIP |
| BZD技能与原始方法 | method_fit_and_workflow、字典单记录、independent_bzd_review | 完整适配、署名许可、九项审读；外部资料获取限制披露 |
| 先协议后主结果 | protocol/config冻结SHA及年度日志 | 七条预定策略，主S_joint不事后更名 |
| 有限追加探索 | extension协议/冻结SHA | 季节性自身误差两条，明确结果后探索 |
| 已授权实现与实际回放 | scripts、runs、january、NPZ、decisions | 9条334天，23714年度候选；6条四日门槛，104候选 |
| 两强制基线与简单终态 | references、comparison_all | B0/B1/P/P_terminal全部来自冻结旧文件并独立核对 |
| 不泄漏与连续状态 | 两套原始未来扰动＋独立causality验证 | 18条三日原/扰动轨迹，冻结采购与前缀不变，次日阳性；不借用其他策略SOC |
| 独立数学复算 | independent_validation及精确验证器快照 | 全候选/情景、计划/实际物理、5p、源预测、费用、求解界证据；未独立重解全部MILP |
| 消融与敏感性 | ablation、comparison_all、selection、block_bootstrap | 仅分位/仅终态/联合，14/28/56日、μ=0；全部负收益保留 |
| 推荐对象补充诊断 | followup_diagnostics、independent_validation_followup | 9组日/月比较、18组描述性区间，六策略指定四日表合计均已核 |
| 压力与乐观界 | stress、lower_bound、独立证书 | 压力不冒充独立样本；下界不冒充可执行政策或EVPI |
| 模型与求解测试 | final_policy_tests、final_bound_tests | 8＋2项通过；原错误日志与修复证据保留 |
| 英文科研图 | figures及独立figure review | ModelViz真实服务、300dpi PNG/SVG、实际看图后核验，负结果可见 |
| 论文与人话结论 | research_report、paper_supplement | 费用组成、终态库存调整、小收益边界与下一步范围明确 |
| 搬迁复现 | reproduce.py、portability_validation | 新目录P_floor完整334天，独立核验及逐段零差；不宣称又全跑九条 |
| 包完整性 | package_manifest、package_validation、ZIP SHA | 封包后逐项读回校验；包自身不自引用 |

仍然未满足且未冒称满足：新年份泛化、完整随机规划全局最优、所有正式题面歧义澄清、少于7个情景日的自动回退、真实设备亚区间验证。它们限制结论适用范围，不使已执行的当前范围数值结果无效。

问题3—4未重算；本轮没有commit/push。后续优先用新年份验证冻结候选，不能把本年的反复试验改名为新测试集。
