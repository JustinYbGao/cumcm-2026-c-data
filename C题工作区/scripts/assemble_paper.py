"""Build ordered review drafts without modifying original chapter snapshots."""
import hashlib
import json
import re
from pathlib import Path

WORK = Path(__file__).resolve().parents[1]
OUT = WORK / 'papers/assembly_v1'
ORIGINALS = ['q1_draft.md', 'q2_draft.md', 'q3_draft.md', 'q4_draft.md', 'innovation_draft.md']

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def sections(name):
    text = (WORK / 'papers' / name).read_text()
    chunks = re.split(r'(?m)^## ', text)[1:]
    return {int(m.group(1)): chunk.split('\n', 1)[1].strip()
            for chunk in chunks if (m := re.match(r'(\d+)[. ]', chunk))}

def links(text):
    # Original drafts resolve ../reports from papers; ordered copies are one level deeper.
    return re.sub(r'\]\(\.\./(reports/[^)]+)\)',
                  lambda m: '](' + str(WORK / m.group(1)) + ')', text)

def save(name, title, body, provenance):
    text = f'# {title}\n\n> 内部装配初稿；未确认口径不作正式提交结论。来源：{provenance}\n\n' + body.strip() + '\n'
    (OUT / name).write_text(links(text))

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    before = {n: sha(WORK / 'papers' / n) for n in ORIGINALS}
    q1, q2, q3, q4, inn = [sections(n) for n in ORIGINALS]
    q1[5] = re.sub(r'图1展示.*?(?=图2将)', '效率与SOC对照图移至Part08.2。\n\n', q1[5], flags=re.S)
    q1[7] += '\n\n![Efficiency and battery state](' + str(WORK/'reports/figures/modelviz_v3_en/battery_states/outputs/chart.png') + ')'
    final_fixed = json.loads((WORK/'results/robustness/fixed_w28/summary.json').read_text())
    final_variable = json.loads((WORK/'results/robustness/variable_w28/summary.json').read_text())
    # Generated supplement is required so a half-filled assembly is never marked complete.
    supplement = WORK / 'papers/robustness_draft.md'
    if not supplement.exists():
        raise FileNotFoundError('Generate verified robustness_draft.md before assembling')
    robust = supplement.read_text()
    save('part01_problem_analysis.md', 'Part01 问题重述与分析', r'''
## 1.1 问题重述
微网以光伏和储能满足小区用电需求，并向外网购入不足的电量。储能容量和充放电功率有限，电量转换还存在损耗，因此购电时间、承诺电量和储能状态需要联合安排。

问题1给定一日负荷、光伏预测与固定电价，要求每天0点给出成本最低的购电策略，且0点和24点储电量相同。问题2根据此前实际负荷和光伏数据形成日前计划，计划外缺口按交易价5倍购入，未使用的计划电量仍收费。问题3增加0、6、12、18点发布的光伏预报，允许在发布时刻调整尚未执行的购电量，并计入调整费用；需要分析额外预报是否值得采用。问题4进一步引入波动电价，分别重算问题2与问题3。

## 1.2 问题之间的关系
共同物理模型描述储能与供需平衡。问题1检验确定性优化和储能经济性；问题2把因果预测与实际执行连接起来；问题3以同源基线、更新时刻和状态反馈对照分解更新效果；问题4保持信息边界，区分预测价格与实际收费价格。补充实验检验PV校正是否依赖窗口、效率、日末约束和固定电价。

指定输出为六个十分钟购电量、六个四小时充放电量、首末储能以及四个指定日的紧急购电记录。正文逐问保留题面要求的表格，完整逐段账本作为附件；当前仅形成内部CSV，正式Excel时间映射另待确认。
''', '原题 C-题面提取.txt；q1—q4_draft 各节任务描述，重新合并')
    save('part02_assumptions_notation.md', 'Part02 数据口径、模型假设与符号', r'''
## 2.1 数据与时间
附件1为单日固定价格与供需；附件2为2025年实际负荷、光伏；附件3为每日四版未来24小时整点PV预报；附件4为目标区间实际价格。沿用已清洗复核数据，十分钟平均功率除以6得到kWh。原00:10标签解释为[00:00,00:10)，不移动、循环重排数值。整点PV按既有版本内线性积分转换，首小时只使用当时可得端点。

## 2.2 必须区分的假设
- 电池容量12000 kWh，允许1200—10800 kWh，交流侧5000 kW，基准充放效率各0.9；各sqrt(0.9)为效率含义对照。
- 问题1初末6000 kWh，日循环由题目明示。问题2—4规划末态等于当天实际初态是额外基线假设；实际SOC跨日连续且从不重置。新增软终态仅是对照。
- 问题1只允许弃光；问题2—4允许未用合同电与PV无收益处置，合同电仍计费，不允许售电获利。
- 问题3—4内部A规则为取消部分退原款并收50%违约费，B为不退原款再收50%；每区间按相对0点计划的最终量计一次费。两种解释都报告，待题意确认。
- 问题4主分支未来价格未知，规划用因果预测、按目标区间实际价结算；提前知道价格仅为假想情景，不作为实际费用下界。
- 问题2—4共享原1月预热产生的2月1日7268.4231640740745 kWh初态，评价期334天；效率/价格对照也固定该初态以隔离后续变化，不声称重新模拟了另一套1月启动。
- 不引入无数据支持的退化、秒级动态或通信成本。贪心实际执行是电量级仿真，不保证全年真实费用最优。

## 2.3 核心符号
| 符号 | 含义 | 单位 |
|---|---|---|
| $t,k$ | 十分钟目标区间、允许决策时刻 | — |
| $L_t,G_t$ | 实际负荷、光伏电量；帽号为预测 | kWh |
| $q_t^0,q_t^k$ | 0点承诺与当前有效承诺 | kWh |
| $c_t,b_t$ | 交流侧充电输入、放电输出 | kWh |
| $E_t$ | 电池内部储能；实际/计划分别记录 | kWh |
| $w_t,e_t$ | 无收益富余处置、紧急购电 | kWh |
| $p_t,\widehat p_{t|k}$ | 实际交易价、规划预测价 | 元/kWh |
| $\eta_c,\eta_d,z_t$ | 两向效率、充放互斥二元变量 | — |
| $W,\bar r_{h,W}$ | PV偏差训练窗口天数、按发布小时分组偏差 | 日、kWh |
| $\lambda$ | 日末库存/终态偏离价值代理，非电网账单 | 元/kWh |

以下历史章节摘录中的 $g,PV,d,\ell$ 是局部同义记号，各节有定义；最终排版前统一为上表，不能把PV符号与购电符号跨章混用。
''', 'q1第2—3节，q2第1—3节，q3第1—3节，q4第1—3节，本轮config')
    save('part03_shared_model.md', 'Part03 共同物理模型与实际执行', r'''
## 3.1 预测规划的物理约束
令当前剩余时域为 $\mathcal H_k$。所有电量以kWh计，充、放电均在交流母线侧定义：
$$q_t^k+\widehat G_{t|k}+b_t=\widehat L_t+c_t+w_t,$$
$$E_{t+1}=E_t+\eta_c c_t-b_t/\eta_d,$$
$$1200\le E_t\le10800,\quad0\le c_t\le(5000/6)z_t,\quad0\le b_t\le(5000/6)(1-z_t),\quad z_t\in\{0,1\}.$$
购电与处置非负。问题1有 $w_t\le\widehat G_t$，其余各问的 $w_t$ 可含未使用的已付费合同电。初态是决策当时已知实际储能；各问目标函数、可见信息和终态约束分别在后文给出。0点为正价线性购电目标，更新时为分段线性合同费，故使用MILP并以连续松弛提供下界。

## 3.2 实际供需反馈
令 $a_t=q_t+G_t-L_t$。若 $a_t\ge0$，则 $c_t^{act}=\min\{a_t,5000/6,(10800-E_t)/\eta_c\}$、放电和紧急量为零，其余处置。若 $a_t<0$，则 $b_t^{act}=\min\{-a_t,5000/6,\eta_d(E_t-1200)\}$、$e_t=-a_t-b_t^{act}$，充电和处置为零。实际SOC按同一状态方程连续递推。

规划只读取截至决策时刻可用的历史和预报，当前实际供需仅用于该十分钟区间的执行与事后账单，未来实际值不进入计划。优化器返回的是给定预测的最优计划；实际执行采用上述反馈，不能把二者的SOC曲线或目标值混为一谈。

## 3.3 求解与独立复核
采用Python与HiGHS，单线程、种子0、时域时间限120秒，相对gap容差1e-9。保存每版承诺、预测、SOC、求解状态和界；验证器重新读文件，按物理式及收费式重算。先核验可行性和费用，再解释策略收益。独立LP矩阵通过SciPy构造，底层同为HiGHS，故是独立建模交叉验证而不是不同厂商算法验证。
''', 'q1第3节、q2第3节、q3第2—3节、q4第3节；去掉跨章重复')
    save('part04_q1.md', 'Part04 问题1：确定性日前优化',
         '## 4.1 建模目标\n\n'+q1[1]+'\n\n在Part03约束上增加 $E_0=E_{144}=6000$，最小化 $\\sum_t p_tq_t$。\n\n## 4.2 数值求解与题面指定表格\n\n'+q1[4]+
         '\n\n## 4.3 储能经济性与策略解释\n\n'+q1[5]+ '\n\n模型检验、效率含义与方案非唯一性统一见Part08。', 'q1_draft.md 第1、4、5节；第2、3节已移到Part02—03；第6、7节移到Part08')
    q2model = q2[3].split('全年实际账单为', 1)[1].split('##')[0]
    save('part05_q2.md', 'Part05 问题2：历史预测与日前承诺',
         '## 5.1 任务与可用信息\n\n'+q2[1]+'\n\n## 5.2 因果预测与1月选型\n\n'+q2[2]+
         '\n\n## 5.3 实际计费\n\n物理约束和实际执行沿用Part03，规划日末目标等于当日实际初态。全年实际账单为'+q2model+
         '\n\n## 5.4 实际结果与失败对照\n\n'+q2[4]+
         '\n\n## 5.5 风险余量的补充结论\n\n预先列出的固定2400 kWh及风险分位余量在4—12月仅减少约2—5元费用，相对千万元账单没有实质改进。计划SOC参考未被贪心执行器直接跟踪，因此计划满足参考不等于实际保持参考。该结果保留为适用边界，不能包装成有效创新。模型、覆盖率、执行机制与全部失败候选见Part09及附录B。\n\n指定日完整表格见附录A，定稿时按题面要求排入本节之后；独立验证见Part08。', 'q2_draft.md第1—4节；innovation_draft风险余量内容；q2第5节移到Part08/09')
    q3intro = q3[1].split('当前内部时间假设')[0]
    contract = q3[2].split('对最终执行量', 1)[1]
    control = q3[3].split('主实验包括',1)[1]
    save('part06_q3.md', 'Part06 问题3：日内更新与PV偏差校正',
         '## 6.1 信息更新与承诺规则\n\n'+q3intro+'\n\n## 6.2 改购费用模型\n\n对最终执行量'+contract+
         '\n\n## 6.3 更新机制对照\n\n主实验包括'+control+'\n\n## 6.4 更新收益与来源\n\n'+q3[4]+
         '\n\n## 6.5 将PV校正写入原模型\n\n'+r'''在原有MILP前增加可追溯的预报偏差校正，不改变合同目标或实际执行器。对发布小时 $h\in\{0,6,12,18\}$，以当天0点前已完成、最近 $W=28$ 日且原始PV预报为正的目标区间估计实际减预报的平均偏差 $\bar r_{h,W}$，并令
$$\widehat G^{corr}_{t|k}=\begin{cases}\max(0,\widehat G^{raw}_{t|k}+\bar r_{h,W}),&\widehat G^{raw}_{t|k}>0,\\0,&\widehat G^{raw}_{t|k}=0.\end{cases}$$
历史不足时只用可得样本，无样本偏差取零；日内仍以当天0点为训练截止。保留夜间原始零值，不借用未来真实昼夜状态。

2—3月实际运行原始PV策略；3月校准比较选择了28天PV校正，于4月1日起启用。此次补充从2月1日起重新连续运行，3月31日至4月1日不重置SOC；最终334日账单、四个指定日表格和9个月配对效果见Part08。原创新包的分阶段账单作为历史实验记录保留，不能无说明拼接成正式全年策略。

写作贡献可表述为“针对分发布时刻的系统偏差，在因果信息约束下增加简洁预报校正，并用真实账单与连续储能回放检验改进”。不能称为全新优化算法，也不能声称四个发布时刻的预测误差都降低；既有结果仅12/18点误差明显改善，0/6点部分误差指标反而增大。

付费更新门槛在同一软终态条件下增费，故主策略保留正常更新，不以门槛作为成功改进。其公式和反例保留在附录B。
'''+f'\n\n连续部署2—12月的实际成本为{final_fixed["total_cost_yuan"]:,.2f}元，原始PV基线13,772,880.06元；校正于4月启用后累计节省46,146.49元。9个月中7个月省费，同时存在122个增费日，收益的稳定范围见Part08。\n\n## 6.6 图形与指定表格\n\n'+q3[7]+'\n\n四个指定日原始A策略表见附录A；校正后最终策略表对应 results/robustness/fixed_w28/table*.csv，属于独立完整策略，不混用两者。', 'q3_draft第1—4、7节；innovation_draft第1—4节PV与门槛；新增连续回放')
    pricebill = q4[3].split('Q4-2在0点',1)[1]
    save('part07_q4.md', 'Part07 问题4：波动价格及改进迁移',
         '## 7.1 价格信息与跨问题继承\n\n'+q4[1]+'\n\n## 7.2 因果价格预测\n\n'+q4[2]+
         '\n\n## 7.3 规划与结算\n\n共同物理约束沿用Part03，A/B收费公式沿用Part06。Q4-2在0点'+pricebill+
         '\n\n## 7.4 实验与结果\n\n'+q4[4]+'\n\n'+q4[5]+
         f'\n\n## 7.5 PV校正的迁移验证\n\n追加对照只在Q4-3中应用与问题3相同的28天校正，4月1日前仍为原始PV；规划使用既有因果OLS价格，账单使用目标区间实际价。与原始PV策略在相同价格、效率、初态、终态规则和执行器下成对比较。Q4-2仍只用历史PV，不引入附件3预报。迁移后2—12月实际成本为{final_variable["total_cost_yuan"]:,.2f}元，原始PV/OLS基线14,534,062.64元，减少41,783.10元。两者4月前路径相同，增量来自4月启用校正；完整对照见Part08，结论只覆盖该价格解释及执行方式。\n\n## 7.6 图形与指定表格\n\n'+q4[8]+'\n\n完整指定日表见附录A；校正迁移策略另见 results/robustness/variable_w28/table*.csv。', 'q4_draft第1—5、8节；新增variable_raw/w28迁移对照')
    save('part08_validation_sensitivity.md', 'Part08 模型检验、敏感性与收益稳定性',
         '## 8.1 共同验证及逐问分工\n\n'+(WORK/'reports/robustness/test_design_basis.md').read_text()+
         '\n\n## 8.2 问题1的数值检验与效率解释\n\n'+q1[6]+'\n\n'+q1[7]+
         '\n\n## 8.3 预测与滚动模型的既有验证\n\n'+q2[5].split('最优性只针对')[0]+'\n\n'+q3[5].split('| 策略')[0]+ '\n\n'+q4[6].split('| 策略')[0]+
         '\n\n## 8.4 新增连续回放及稳健性结果\n\n'+robust,
         'q1第6—7节，q2第5节，q3第5节，q4第6节；robustness_draft全文与官方检验依据')
    save('part09_evaluation_limits.md', 'Part09 模型评价、失败实验与适用范围', r'''
## 9.1 优点与可支持的结论
统一模型区分承诺、预测计划、实际反馈与账单，使不同问题能够沿同一物理和计费定义比较。给定预测下的MILP有可行性及求解界；全年实际费用从逐段账本重算。信息更新的效果通过同源基线及仅SOC反馈分开解释，PV校正的增量通过成对连续回放与多种假设对照呈现。

## 9.2 失败实验应怎样保留
Q2在1月选中的复杂预测组合，2—12月实际费用比季节基线高955476.04元，不在看到全年结果后改写选型。风险余量在创新评价期仅省约2—5元，不能当作实质创新。软终态门槛α=0.5/0.75相对正常付费更新分别增费2279.99/135578.73元，故保留正常更新。无新信息冻结与有新信息但承诺冻结的两条实际轨迹相同，说明当前执行器在承诺不变时无法利用未来预测。这些是机制边界而非应删除的“不好看结果”。

## 9.3 外推边界与终稿剩余项
MILP最优性只针对给定预测的有限时域，不能提升为全年真实成本最优。补充情景与分块区间仍属于已见数据上的回顾性分析，不证明未知年份盈利，也不覆盖效率×窗口×终态×价格的全部交互。当前不计退化和通信费用，未仿真秒级控制；没有相关数据时收窄结论即可，不必为凑检验盲加参数。

正式提交前仍需确认模板时间、效率及功率侧别、退款/逐次收费、价格可知性与结算时点。确认后应沿指定分支复算、导出Excel并逐项对齐正文。最后统一符号、公式/图表编号、正文页数和引用，补齐AI使用记录、进行最终格式检查。当前是有证据的论文装配初稿，不是完成正式审核的终稿。
''', '各问范围说明及innovation_draft第3—5节；已更新本轮已完成/未完成边界')
    # The full innovation snapshot remains traceable; status text is explicitly historical.
    appendix = (WORK/'papers/innovation_draft.md').read_text()
    save('appendix_B_innovation_archive.md', '附录B 原创新实验完整记录',
         '> 下文是原冻结创新实验的历史快照。其“尚未Q4迁移/未连续全年”等状态已由本轮Part08补充，不代表当前状态。公式与全部成功/失败数值保留，正文只选Part05/06/09明确对应内容。\n\n'+appendix,
         'innovation_draft.md全文原样保留，增加历史说明')
    tables = []
    for q in ['q2','q3','q4']:
        p = WORK/f'reports/{q}_representative_tables.md'
        tables.append(f'## {q.upper()} 题面指定表\n\n'+p.read_text())
    tables.append('## 本轮新增策略的表格入口\n\n下列目录各含完整334日账本/日费用及四个指定日的表1/2/3与合并紧急事件。28天主策略对应 fixed_w28；Q4-3迁移对应variable_w28。正文排版分别置于Part06.6、Part07.6之后，不能改填原始策略的费用。\n\n')
    for name in ['fixed_w28','variable_w28']:
        for p in sorted((WORK/'results/robustness'/name).glob('table*.csv')):
            tables.append(f'- [{name}/{p.name}]({p})\n')
    save('appendix_A_required_tables.md','附录A 指定日期表格与完整策略入口','\n\n'.join(tables), 'reports/q2、q3、q4_representative_tables.md；新增策略CSV')
    save('part10_references_reproduction.md', 'Part10 文献、复现与附件索引', r'''
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
''', '各问复现记录；本轮实际工具/脚本；官方与作者网页')
    mappings = [
        ('q1_draft.md','1→Part04.1；2→Part02；3→Part03；4—5→Part04；6—7→Part08.2；8→Part09/问题2衔接；证据说明→Part10','正文主材料，移出重复假设；指定表保留Part04'),
        ('q2_draft.md','1—4→Part05；5→Part08.3与Part09','保留1月选型失败；不换全年胜出策略；指定表由附录A排回Part05'),
        ('q3_draft.md','1→Part06.1与Part02；2→Part03/06.2；3—4→Part06.3—4；5→Part08.3；6→Part09；7→Part06.6；8及运行→附录A/Part10','删掉历史“尚未做Q4”等过时状态；新增校正放Part06.5，不整篇创新另挂正文'),
        ('q4_draft.md','1—5→Part07.1—4；6→Part08.3；7→Part09；8→Part07.6；9及运行→附录A/Part10','新增迁移放Part07.5；旧结果保留同核基线；验证集中'),
        ('innovation_draft.md','1→Part06.5/08.4实验边界；2的PV公式→Part06.5，风险/门槛公式→附录B；3—4的主PV结论→Part06/08，失败结论→Part05.5/09.2；5→Part08/09；6—7→附录B/Part10；全文历史快照→附录B','成功改进、无效消融分别说明；旧分阶段结果不冒充连续334日'),
        ('robustness_draft.md','全文→Part08.4；其中固定28天最终策略→Part06.5；变价迁移→Part07.5；限界→Part09','本轮新增连续回放/敏感性/分块稳定性；主方案仍28天，不事后选窗口')]
    (OUT/'source_map.json').write_text(json.dumps({'originals_unchanged':True,'source_sha256':before | {'robustness_draft.md':sha(supplement)},
        'mapping':[dict(file=n,parts=p,action=a) for n,p,a in mappings]},ensure_ascii=False,indent=2)+'\n')
    order = sorted(OUT.glob('part*.md')) + sorted(OUT.glob('appendix*.md'))
    index = '# 论文装配顺序与文件归属\n\n**从本文件开始。** 原五份初稿全部保留，以下是新装配副本，已拆分重复内容和更新过时状态。先按Part01—10写正文，附录A中题面指定表应排回对应问题正文；附录B保存完整创新实验供裁剪。摘要在结论核对后写，当前不进行文字精修。\n\n## 阅读/写作顺序\n\n| 顺序 | 文件 | 放什么 |\n|---|---|---|\n'
    for i,p in enumerate(order,1):
        index += f'| {i:02d} | [{p.name}]({p}) | {p.read_text().splitlines()[0].lstrip("# ")} |\n'
    index += '\n## 旧文件逐个放哪里\n\n| 原文件 | 精确归属 | 处理方式 |\n|---|---|---|\n'
    for name,parts,action in mappings:
        index+=f'| [{name}]({WORK/"papers"/name}) | {parts} | {action} |\n'
    index+='\n## 图表取舍\n\n| 图或表源 | 正文位置 | 用法 |\n|---|---|---|\n'
    for source,part,usage in [
        ('modelviz_v3_en/dispatch','Part04.3','保留供需、购电、SOC与电价关系'),
        ('modelviz_v3_en/battery_states','Part08.2','效率口径对照，Part04只交叉引用避免重复'),
        ('modelviz_v3_en/monthly_costs','Part05.4','保留选型失败'),
        ('modelviz_v3_en/representative_execution','Part05.4','计划/实际SOC及紧急量'),
        ('modelviz_q3_v1_en/q3_monthly','Part06.4','更新收益'),
        ('modelviz_q3_v1_en/q3_execution','Part06.6','允许时刻与实际轨迹'),
        ('modelviz_q4_v1_en/q4_monthly','Part07.4','同实际收费下的价格输入对照'),
        ('modelviz_q4_v1_en/q4_prices','Part07.6','因果价格与实际价格'),
        ('modelviz_innovation_v1_en/innovation_monthly','附录B','旧PV/门槛多组结果，正文用新稳健性图替代'),
        ('modelviz_innovation_v1_en/innovation_risk','附录B','风险模型诊断，正文只写无显著实际收益'),
        ('modelviz_robustness_v1_en/robustness_effects','Part08.4','窗口和假设下的配对省费及重抽样区间'),
        ('modelviz_robustness_v1_en/robustness_monthly','Part08.4','28天主方案月度成本和正负省费')]:
        index += f'| [{source}]({WORK/"reports/figures"/source}) | {part} | {usage} |\n'
    index+='\n题面指定表是必须回答的结果，附录A只是装配暂存，不可最终仅以“见附件”替代正文要求。所有可见图内标注为英文。Part编号是写作文件顺序，最终章节/图表/公式编号还需统一。各小节保留部分原局部符号，Part02列出同义对应；本轮不声称已完成终稿格式检查。\n'
    (OUT/'00_README_装配顺序.md').write_text(index)
    (OUT/'assembled_review_draft.md').write_text('# 微网购电策略：正文装配初稿\n\n内部假设版；请先阅读00_README。\n\n'+ '\n\n---\n\n'.join(p.read_text() for p in order))
    assert before == {n:sha(WORK/'papers'/n) for n in ORIGINALS}
    broken=[]
    for p in OUT.glob('*.md'):
        for match in re.findall(r'\]\((/[^)]+)\)',p.read_text()):
            if not Path(match).exists():broken.append([p.name,match])
    (OUT/'assembly_validation.json').write_text(json.dumps({'passed':not broken,'originals_unchanged':True,'mapped_sources':len(mappings),'ordered_parts':len(order),'broken_absolute_links':broken},ensure_ascii=False,indent=2)+'\n')
    if broken:raise AssertionError(broken)
    print(f'Assembly: {len(order)} ordered parts; {len(mappings)} mapped sources; originals unchanged; links passed')

if __name__=='__main__':main()
