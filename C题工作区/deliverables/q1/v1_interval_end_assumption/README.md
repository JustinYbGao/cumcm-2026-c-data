# 问题1可追溯结果包 v1

状态：区间终点工作假设下的内部验收包，非正式提交版。冻结后不要直接修改；修订使用新版本。首先阅读 papers/q1_draft.md，再阅读 reports/q1_model_and_results.md。此包在问题2开发前冻结，问题1报告中的“问题2未执行”为冻结时状态。

## 从结论追到证据

traceability.csv将费用、表1/表2、储能、效率对照和时间歧义逐一连接到结果文件及重算方法。data/processed/q1_day.csv为实际输入快照，source保留中文题面、原附件1和原始空模板；configs固定工作假设；scripts保留求解和独立验证代码；logs保留实际运行、版本与字典依据。manifest_sha256.json对包内每个交付文件校验，ZIP外另有校验文件。

## 独立检查与数值复现

使用已有项目虚拟环境，执行：

```bash
/Users/justingao/Documents/CUMCM/C题工作区/.venv/bin/python -B scripts/verify_q1_package.py
```

须在本包根目录运行。该入口验证包内哈希、六组保存策略物理约束与汇总，并重新求解两种效率下MILP和LP比较目标；不覆盖冻结结果。求解器环境依赖requirements.txt，实际版本见logs/q1/environment.json。原求解脚本的main面向完整原项目；不要在孤立包里直接调用原main。历史input_hashes是原项目所有受保护文件的运行证据，包内仅附问题1所需输入，其他问题原数据不重复打包。

## 尚未完成与使用边界

正式result1.xlsx尚未导出；source中的同名文件是原始空模板。模板00:10—次日00:10与内部00:00—24:00不同。效率、交流侧功率、平均功率及Q1初值解释仍需团队确认。论文为初稿，未做全文编号和精修，不能据此宣称全题完成或真实全年最优。

AI协助：Codex整理模型、实现与运行代码、生成结果说明及论文初稿、组织独立读回验证和此包。独立指分离的核算代码，不代表独立人员审计。
