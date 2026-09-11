# 变更与失败记录

- 原协议冻结十条分时/情景选择方案，旧主上限661273.6528153808元、普通与总费须下降；旧协议及验收保持不变。
- 用户在原年度结果期间改为紧急费≤1000000元、总费用优先；八条追加profile另冻结extension协议，不能称原先未看结果的主方案。
- 独立审读发现近28天少于7日、但56天足够时风险校准可能默认为零。新增稀疏输入测试先失败（test_sparse_red.log），在近28日检查后显式停止，再五测通过（test_sparse_green.log）；原完整轨迹没有触发此边界。
- 扩展因果检查初次复用prefix变量名与已有浮点前缀误差冲突，两种scope均TypeError（causality_refresh.log与extension_causality.log）。沿堆栈定位，路径名改为path_prefix，复用已落盘轨迹、逐文件确认输入未变后完整两scope通过（*_fixed.log）。失败日志保留；采购策略未改变。
- 原因果报告旧源SHA保存在causality_validation_original_script.json；现报告在修复后重新核对既有轨迹并绑定新脚本。该重验不修改既有实际账本。
- agent-reach的Exa入口DNS解析失败，改用直接网页工具读取原作者/大学来源。具体原始文献与采纳边界见method_fit_and_workflow.md。
- 所有负收益/超限方案均在全表、重采样及结果包中保留；未使用Q3/Q4重算结果，没有新增设备、改结算或日内普通价交易。
