"""Freeze a traceable Q1 package and an unpolished paper chapter, without altering results."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

WORK = Path(__file__).resolve().parents[1]


def main():
    report = (WORK/'reports/q1_model_and_results.md').read_text()
    result = WORK/'results/q1'
    audit = json.loads((result/'validation.json').read_text())
    if not audit['passed']:
        raise RuntimeError('Q1 must pass its saved-file audit before packaging')
    papers = WORK/'papers'
    papers.mkdir(exist_ok=True)
    def section(number):
        part = report.split(f'## {number}. ',1)[1]
        return part.split('\n## ',1)[0].split('\n',1)[1].strip()
    model = section(3)
    results = section(4)
    results = results.replace('本次基准MILP求解器计时 0.0268秒','本次基准MILP求解器计时约0.03秒')
    validation = '''为检验所求策略的可行性，将完整策略保存为CSV后，由独立脚本重新读取源数据与决策结果，逐区间计算供需平衡残差和储能递推残差。进一步检查容量、功率、非负性、弃光上限、充放电互斥、状态连续性和首末状态，并独立重算全天费用、表1和表2。电量验收容差取10⁻⁶ kWh，费用容差取10⁻⁶元。

基准供需平衡最大绝对残差为1.14×10⁻¹³ kWh，储能递推最大绝对残差为8.81×10⁻¹³ kWh，均低于验收阈值；电池状态始终处于1200—10800 kWh，日初、日末均为6000 kWh，未发生同一十分钟区间同时充放电。由原始价格与保存的购电量重新计算的总费用，与求解器目标及汇总结果一致。

为核对实现，使用一个可手算的两区间套利例子，以及故意引入功率超限、状态递推错误、汇总错误和时间错移的反例进行测试。8项程序测试通过；六组保存结果及跨文件一致性检查共240项通过。“独立”指读取与计算逻辑独立于求解器输出过程，并不表示不同研究人员的审计。

MILP目标值与LP松弛下界一致，说明在给定输入、工作假设及数值容差内已求得全局最优目标。该最优性结论仅针对确定性调度模型，不包含对光伏预测误差、真实运行波动或未确认题意口径的保证。'''
    draft = '# 问题1：基于混合整数线性规划的微网日前购电策略（论文初稿）\n\n'
    draft += '> 可继续编辑的章节初稿，尚未作全文编号、版式和语言精修。时间按区间终点标签解释；效率按单向各90%解释。上述口径及正式模板映射待确认。本稿只涵盖问题1，不是完整竞赛论文或正式提交版。\n\n'
    draft += '''## 1 问题分析与建模思路

问题1给出了某天的负荷、光伏发电预测和分时电价，要求在满足小区负荷和储能设备约束的条件下确定当天购电策略，并使日初与日末储电量相等。储能设备能够将低价时段或光伏富余时段的电量转移到高价时段使用，但充放电损耗、功率和容量限制共同约束这种转移。因此，不能仅对各时段分别选择最低费用，而需联合优化全天144个十分钟区间。

将购电、交流侧充放电和弃光作为决策量，以电池内部储能连接相邻区间。固定效率下，目标函数和物理约束均为线性；为禁止同一区间同时充放电，引入一个二元状态变量，构成混合整数线性规划。另求解其线性规划松弛，提供目标下界，并以无储能策略作为可行费用对照。

## 2 数据口径与模型假设

附件1的价格单位为元/kWh，负荷和光伏预测功率单位为kW。本文把00:10标签解释为00:00—00:10区间的终点，并将每条功率视为该十分钟区间平均值，从而以功率除以6得到区间电量。保留144个原始数值顺序和源行信息，不移动或循环重排数据。全天负荷为111024.808100 kWh，给定光伏电量为55482.835667 kWh。

储能额定容量为12000 kWh，运行范围为1200—10800 kWh；5000 kW充放电上限解释在交流母线侧，每区间上限为833.333333… kWh。基准采用充电效率和放电效率均为0.9，并以双向均取sqrt(0.9)作口径敏感性比较。中文附录明确给出2025年1月1日初值6000 kWh，英文称运行初始6000 kWh；对无日期的问题1，本文显式固定初值6000 kWh，同时约束日末相同，不将初始电量交由优化器自由选择。

仅允许处置未利用的光伏电量，无售电收入、未供负荷及任意购入电量处置。电池损耗在状态方程中计算，不计入弃光。假设十分钟内采用准静态平均功率描述，不额外引入题面未提供参数的自放电、退化和爬坡成本。

## 3 符号与数学模型

'''+model+'\n\n## 4 数值求解与指定结果\n\n'+results
    draft += '\n\n## 5 策略解释与无储能对照\n\n'+section(5)
    draft += '\n\n## 6 模型检验\n\n'+validation
    draft += '\n\n## 7 效率敏感性与方案非唯一性\n\n'+section(6)
    draft += '''

## 8 适用范围与向问题2的衔接

本模型的优点是物理边界明确、费用可复算，并能够通过上下界与逐区间验证提供数值可信度。局限在于将给定光伏预测视为确定输入，尚未处理预测偏差及实际执行误差；两种效率解释也会引起实质性费用变化。原模板首行00:10—00:20、末行次日00:00—00:10与本模型00:00—24:00范围不同，正式填表前需确认映射。完整内部策略已经保存，本文未把未经确认的模板结果视为正式提交文件。

进入问题2后，沿用本节的电量单位、交流侧功率和储能状态定义。日前预测只能使用当天0:00以前已完成的观测；优化得到的计划储能轨迹与真实供需下的实际轨迹必须分别保存。实际缺口以交易电价的5倍补购，原计划未使用的电量仍按原计划收费。实际日末状态应连续传到次日，不能强行改成计划末态或每天重置6000 kWh。

## 本章证据与引用待整合说明

题意与参数来源为2026年C题题面、附录1及附件1。模型选型核对使用BZD数模社制作的#913确定性混合整数线性规划、#797线性规划；完整适配和许可保留在结果包中。未在本章虚构外部文献。全文整合时再统一参考文献、公式、表格和图号；AI协助范围及执行证据见结果包README和来源说明。
'''
    draft = draft.replace('(figures/q1/', '(../reports/figures/q1/')
    (papers/'q1_draft.md').write_text(draft)
    package = WORK/'deliverables/q1/v1_interval_end_assumption'
    if package.exists():
        raise FileExistsError('Frozen package already exists; create a new version rather than overwrite it')
    def copy(src,relative):
        dst=package/relative
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)
    for folder in ['results/q1','reports/figures/q1']:
        for src in (WORK/folder).rglob('*'):
            if src.is_file(): copy(src,src.relative_to(WORK))
    for rel in ['papers/q1_draft.md','configs/model_baseline.json','data/processed/q1_day.csv',
                'scripts/solve_q1.py','scripts/validate_q1_solution.py','scripts/report_q1.py',
                'scripts/verify_q1_package.py','scripts/package_q1.py','tests/test_q1_solution.py','requirements.txt',
                'reports/q1_model_and_results.md','reports/q1_model_fit.md','reports/q1_bzd_solution_check.md',
                'reports/data_dictionary.md','reports/processing_notes.md','reports/template_review.md']:
        copy(WORK/rel,rel)
    for src in (WORK/'logs/q1').glob('*'):
        if src.is_file(): copy(src,src.relative_to(WORK))
    base=WORK.parent/'CUMCM2026Problems/C题'
    for src in [base/'C题.pdf',base/'附件/附件1.xlsx',base/'附件/附件5/result1.xlsx']:
        copy(src,Path('source')/src.relative_to(base))
    trace='''claim_id,claim,source,verification,assumption
Q1-COST,基准购电费,results/q1/baseline/summary.json:cost_yuan,原价格乘schedule.grid_kwh;MILP与LP界,单向各0.9及区间终点
Q1-GRID,全天购电量,results/q1/baseline/summary.json:grid_kwh,schedule.grid_kwh求和,无售电
Q1-T1,表1六区间,results/q1/baseline/table1_intervals.csv,按start_minute/end_minute选取,非模板行号映射
Q1-T2,表2六区段,results/q1/baseline/table2_blocks.csv,逐区间交流侧充放电累计,AC侧5000kW
Q1-STATE,首末及全部储能,results/q1/baseline/states.csv,145状态点递推及边界,固定6000初值
Q1-SAVING,无储能节费,results/q1/comparison.csv,无储能费用减基准费用,相同输入初末状态
Q1-EFF,效率比较,results/q1/efficiency_sensitivity.json,roundtrip_90与baseline独立求解,两种90%解释
Q1-VALID,可行性验收,results/q1/validation.json,scripts/validate_q1_solution.py,数值容差见配置
Q1-MAP,时间映射未决,results/q1/time_mapping_evidence.json,source/附件/附件5/result1.xlsx,不生成正式提交版
'''
    (package/'traceability.csv').write_text(trace)
    (package/'README.md').write_text('''# 问题1可追溯结果包 v1

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
''')
    manifest={str(p.relative_to(package)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(package.rglob('*')) if p.is_file()}
    (package/'manifest_sha256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    archive=package.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for src in sorted(package.rglob('*')):
            if src.is_file(): z.write(src,Path(package.name)/src.relative_to(package))
    archive.with_suffix('.zip.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
    print(f'Frozen {len(manifest)} files; paper: {papers/"q1_draft.md"}; package: {archive}')


if __name__=='__main__': main()
