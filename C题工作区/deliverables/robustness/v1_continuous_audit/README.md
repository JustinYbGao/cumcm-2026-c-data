# 连续策略与论文装配结果包（内部假设版）

按archive_index.json下载本目录全部part ZIP，解压到同一目录；各ZIP成员不重叠，不是二进制分卷。解压后形成C题工作区的相对目录结构。先读papers/assembly_v1/00_README_装配顺序.md，再读papers/robustness_draft.md。全部原五份初稿保留。

manifest.json记录所有源文件相对于工作区的路径、字节数和SHA-256。验证脚本以自身位置推导工作区，不依赖原用户绝对目录；论文中的绝对图文链接服务于当前Codex预览，迁移后按相同相对路径调整。

复核命令（在解压根目录配置同依赖Python环境后）：
```
python -B scripts/validate_robustness.py
python -B scripts/audit_robustness_lp.py
python -B scripts/analyze_robustness.py
python -B -m unittest discover -s tests -p 'test_robustness*.py'
```

run_robustness.py会拒绝覆盖已完成结果；从头求解应另建副本，仅准备必要输入和空results/robustness，不删除此冻结包。图形可直接运行各图workspace/adapted_plot.py并提供DATA_PATH、OUTPUT_DIR；完整ModelViz流程依赖本地skill。内部时间/市场/效率口径尚待确认，不包含正式Excel。此前各问大包仍在原deliverables/q1—q4及innovation，本包不重复封装。
