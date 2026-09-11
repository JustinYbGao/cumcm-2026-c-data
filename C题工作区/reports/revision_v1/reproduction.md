# 本轮复现与文件对应

代码基点`538a67e`（当前分支`codex/innovation-experiments`），包含队友`d3b4dfa`和既有实验`3d5c064`。本轮修订尚未提交，因此不能捏造一个“最终提交号”；当前具体文件版本由`revision_manifest.json`记录SHA256。后续提交后可追加Git号，文件哈希仍用于准确对应数值。

## 不重做全年即可核验本轮结果

在仓库根目录执行：

```bash
cd /Users/justingao/Documents/CUMCM
PYTHONDONTWRITEBYTECODE=1 C题工作区/.venv/bin/python C题工作区/scripts/audit_power_boundary.py
PYTHONDONTWRITEBYTECODE=1 C题工作区/.venv/bin/python -m unittest discover -s C题工作区/tests -v
/Users/justingao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 C题工作区/scripts/prepare_result_workbooks.py
TMPDIR=/Users/justingao/Documents/CUMCM/C题工作区/data/interim/revision_v1 /Users/justingao/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node C题工作区/scripts/revision_v1/build_result_workbooks.mjs
/Users/justingao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 C题工作区/scripts/validate_result_workbooks.py
/Users/justingao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 C题工作区/scripts/validate_result_workbooks.py --self-test
```

首次在这台机器配置JS依赖时，`scripts/revision_v1/node_modules`是指向已安装官方运行环境`.../dependencies/node/node_modules`的符号链接；不要复制或提交运行时目录。换机器请用工作区依赖加载器定位新的Node、Python和`@oai/artifact-tool`路径，重新建立该链接。脚本仅覆盖本轮`outputs/revision_v1`的审阅副本、验证报告和侧别情景，不覆盖冻结的Q1—4/创新/鲁棒性包。

`prepare_result_workbooks.py`只读CSV/模板，产出JSON；Excel写入由官方运行时`@oai/artifact-tool`执行。独立验证脚本不读该JSON、不导入导出器，而从CSV和电价重建检查。预览位于`workbook_previews/`，正文所用数值按物理日期—时段核对。没有使用Excel求解器重算优化，Excel只是既有求解结果的输出载体。

现有测试使用标准库unittest，共54项。首次探测pytest时发现未安装，该探测没有运行测试；随后使用仓库实际测试框架执行，日志为`unit_tests.log`。不需要为此安装或改动环境。

工作簿校验器另有3项自测，覆盖首末时段、紧急事件不跨业务日合并、样式编号变化但外观不变。最终样式修订曾触发5个检查误报：原检查把工作簿内部style_id当作跨文件稳定标识；现已改为比较字体、填充、边框、对齐和数值格式等实际属性。失败记录保留为`xlsx_validation_before_style_fix.log`，当前结论以`export_validation.json`中的最终通过结果及校验器哈希为准。

## 数值来源和配置

| 输出 | 账本 | 主要配置 |
|---|---|---|
| result1 | results/q1/baseline/schedule.csv | configs/model_baseline.json |
| result2 | results/q2/selected/ledger.csv | configs/q2_baseline.json |
| result3 | results/robustness/fixed_w28/ledger.csv | configs/robustness.json，继承Q3物理/结算 |
| result4-2 | results/q4/q42_ols/ledger.csv | configs/q4_baseline.json |
| result4-3 | results/robustness/variable_w28/ledger.csv | configs/robustness.json，继承Q4因果价格 |

模型求解运行环境与依赖精确版本见`environment.json`；既有各结果根目录中的config_snapshot、physical_snapshot、selection及求解器状态继续作为原始证据。HiGHS配置主随机种子0、单线程；历史块自助5000次、种子20260910。此次新增四物理情景继承Q1配置，时间上限120s、相对gap1e-9、绝对gap1e-7，检查容差1e-6。

年度原始重算入口为`scripts/run_q2.py`、`run_q3.py`、`run_q4.py`和`run_robustness.py`；完整依赖顺序和各参数详见对应冻结包README。本轮没有改变年度求解器或运行入口，因此没有重复几十万段的年度求解。若最终口径改变，应先复制一份新配置并指定新结果目录，按`issue_resolution.md`的依赖范围重跑，不能在旧冻结包中覆盖运行。

`scripts/revise_paper.py`是从队友基稿进行首次表格装配的迁移脚本，带防重复保护；后续审阅编辑保存在当前Markdown及Git差异中。它不是需要每次重跑的数值求解程序。当前全文是主稿，旧`assembly_v1`和`friend_review_v1`为历史参考，不再用旧稿生成器覆盖修订后的全文。
