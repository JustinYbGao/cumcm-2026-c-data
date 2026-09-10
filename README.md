# CUMCM 2026 C题数据处理

本仓库保存C题数据阶段的可复现交付：原题与附件、处理脚本、处理后数据、质量检查、预报误差诊断、探索图和运行日志。包含朋友在`111`中的原始工作及核验报告。未训练最终预测模型、未求解购电优化、未填写虚构策略结果。

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
