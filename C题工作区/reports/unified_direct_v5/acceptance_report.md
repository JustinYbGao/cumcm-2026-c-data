# 最终验收

| 验收项 | 结果 |
| --- | --- |
| independent | PASS |
| analysis | PASS |
| causality | PASS |
| numerical | PASS |
| reproduction | PASS |
| workbook | PASS |
| preservation | PASS |

年度10策略、全部候选、逐段实际执行和源价计费已覆盖；五份实际XLSX独立读回、三选定策略隔离年度复现均通过。各项详细范围与最大误差以链接的原始JSON为准，题意工作假设未视为正式确认。旧研究产物保护通过，但results/.DS_Store目录元数据有公开例外；all_prior_files_byte_identical=false。

{
  "ledger_rows": 480960,
  "decisions": 10354,
  "candidate_vectors": 69138,
  "candidate_scenario_paths": 7039035
}

证据入口：

- [独立源/候选/账本](independent_report.json)
- [费用统计](analysis_validation.json)
- [未来扰动](causality_checks.json)
- [导数和边界](numerical_checks.json)
- [隔离复现](reproduction_comparison.json)
- [工作簿读回](workbook_readback.json)
- [旧文件保护](preservation_check.json)

## 最大误差与范围

| 项目 | 最大绝对误差 | 单位 | 阈值 |
| --- | --- | --- | --- |
| 年度物理/初始化最大误差 | 6.68114807922e-09 | kWh | 1e-06 |
| 年度费用最大误差 | 1.86264514923e-09 | 元 | 1e-05 |
| 实际XLSX读回 | 7.27595761418e-11 | kWh | 1e-06 |
| 实际XLSX读回 | 1.30385160446e-07 | 元 | 1e-05 |
| 非折点360坐标梯度 | 1.98827504461e-08 | 元/kWh | 1e-5 |

五工作簿检查4,107,481项，数值比较2,143,182项，错误0；覆盖50份CSV与50份Markdown指定日表、1008项时间映射、288720个采购单元格。三策略隔离复现的所有采购/候选/费用差为0。未来扰动16组的可用前输入及候选差为0。原始实际数据的单位和价格列在相应JSON单独列示。

## 研究边界

验收确认已执行的有限数据与实现，不确认正式题意、全局最优或未来年度表现。最终独立审阅见final_independent_review.md，九项模型评审见model_review.md，封包全部文件的双次SHA读回见package_readback.json。
