# CUMCM 2026 C题建模工作区

## Current English paper: revision 03, 12 September 2026

- [Reviewed paper PDF](C题工作区/papers/manuscript_storage_control_v6_revision_20260912_03/manuscript.pdf)
- [English manuscript source](C题工作区/papers/manuscript_storage_control_v6_revision_20260912_03/manuscript_EN.md)
- [Scientific support ZIP](C题工作区/papers/manuscript_storage_control_v6_revision_20260912_03/support_materials.zip)
- [Portable LaTeX source ZIP](C题工作区/papers/manuscript_storage_control_v6_revision_20260912_03/outputs/latex_source.zip)
- [Revision records and repository build instructions](C题工作区/papers/manuscript_storage_control_v6_revision_20260912_03/GIT_DELIVERY.md)

The paper now uses the requested English title. Its abstract and keywords are unchanged by revision 03. The PDF has 76 pages, including 24 body pages and complete program appendices. The scientific support archive contains the five English result workbooks and corresponding model programs. Historical entries below describe earlier development stages.

本仓库保存C题原题、复核数据及问题1—4内部模型、实际求解、独立验证、英文图表、论文初稿和冻结结果包。包含朋友在`111`中的原始工作及核验报告。问题2和问题4的负结果保留；正式模板时间与部分结算解释尚未确认，未填写正式提交Excel。

- [创新实验初稿](C题工作区/papers/innovation_draft.md)
- [当前建模进度](C题工作区/reports/workflow_progress.md)
- [问题4论文初稿](C题工作区/papers/q4_draft.md)
- [工作区说明与运行方法](C题工作区/README.md)
- [数据阶段交付清单](C题工作区/reports/data_completion.md)
- [数据字典](C题工作区/reports/data_dictionary.md)
- [数据质量报告](C题工作区/reports/quality_report.md)
- [处理假设与未决口径](C题工作区/reports/processing_notes.md)
- [111审计](C题工作区/reports/111_audit.md)

## 从原附件重建

在克隆后的仓库根目录执行，推荐Python 3.12：

```bash
python3 -m venv C题工作区/.venv
TMPDIR="$PWD/C题工作区/data/interim" C题工作区/.venv/bin/python -m pip install -r C题工作区/requirements.txt
C题工作区/.venv/bin/python C题工作区/scripts/run_pipeline.py
```

脚本按自身文件位置定位仓库，不依赖本机绝对路径；历史日志中的绝对路径保留用于追溯。原附件只读，不需要另行复制。缺失端点、跨年实际值缺口和模板时段歧义均有明确说明，不以填零掩盖。

报名信息、其他赛题、虚拟环境、缓存和Excel锁文件不纳入版本管理。运行环境版本见工作区`logs/runtime_versions.json`。

### 论文装配及补充实验

最新入口：[Part顺序和旧初稿归属](C题工作区/papers/assembly_v1/00_README_装配顺序.md)。已补连续334日策略、窗口/效率/终态/变价对照、日月收益与分块稳定性，保留所有旧稿和冻结包。结果仍受已披露的内部题意口径约束。

### 队友审阅入口

请先读[给队友的审阅导航](C题工作区/FRIEND_REVIEW_GUIDE.md)。最新完整工作在`codex/innovation-experiments`分支；导航链接的阅读副本支持GitHub内图表跳转，原稿及冻结包保留。
