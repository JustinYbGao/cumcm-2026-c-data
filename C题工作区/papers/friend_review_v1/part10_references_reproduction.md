# Part10 文献、复现与附件索引

> 内部装配初稿；未确认口径不作正式提交结论。来源：各问复现记录；本轮实际工具/脚本；官方与作者网页

## 10.1 当前真实查用的参考来源
[1] 全国大学生数学建模竞赛组委会. 2026年C题《微网与外部电网电力调控策略》及附件1—5. 本地题面和原附件。
[2] Hyndman R J, Athanasopoulos G. Forecasting: Principles and Practice, 3rd ed. OTexts, 2021. https://otexts.com/fpp3/tscv.html （按时序验证方法）.
[3] Sheppard K. arch: Time-series Bootstraps. https://bashtage.github.io/arch/bootstrap/timeseries-bootstraps.html （分块方法与边缘权重限制）.
[4] 全国大学生数学建模竞赛组委会. 全国大学生数学建模竞赛章程（2023年修订稿）. https://www.mcm.edu.cn/html_cn/block/44e92058f537729c6b6a62a3662ee417.html （本轮测试安排依据，未必作为正文研究文献保留）.

BZD数模社制作的模型字典是选型辅助资料；原版权许可和查询记录在各结果包中保留，不冒充原始研究论文。模型与求解器的最终学术引用、数据附件命名和访问日期需要按正文实际引用统一。本列表只列真实查阅来源，不凑文献数量。

## 10.2 复现与附件
各问冻结包依次在 deliverables/q1、q2、q3、q4、innovation；新增结果为results/robustness，执行计划与方法为reports/robustness，代码为scripts/*robustness*.py，日志为logs/robustness。新增包的manifest给出精确路径及SHA-256。

```bash
cd /Users/justingao/Documents/CUMCM/C题工作区
.venv/bin/python -B scripts/validate_robustness.py
.venv/bin/python -B scripts/audit_robustness_lp.py
.venv/bin/python -B scripts/analyze_robustness.py
.venv/bin/python -B scripts/report_robustness.py
.venv/bin/python -B scripts/assemble_paper.py
```

从头求解命令为 `.venv/bin/python -B scripts/run_robustness.py`；完成目录受保护，独立复算应使用新的工作区副本并保留原结果。不要删除已有结果以重跑。ModelViz运行与视觉质检命令见新图目录，质量通过以与PNG和脚本哈希绑定的实际检查为准。

## 10.3 AI与提交材料
本轮AI辅助涉及模型实现、代码检查、数值验证、图形适配和初稿装配。工具、提示词、生成内容和人工核对情况应按真实日志整理最终AI使用详情，不能把AI检查写成无关第三方认证。当前未完成最终AI使用表、全文格式与匿名检查，未导出正式Excel。
