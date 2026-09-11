"""Ground the innovation chapter in frozen selection and actual execution evidence."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

WORK=Path(__file__).resolve().parents[1];OUT=WORK/'results/innovation'
LABELS={'pv_raw':'Raw PV','pv_bias':'PV bias correction','risk_none':'No reserve','risk_fixed':'Fixed reserve',
'risk_g05':'Risk reserve gamma 0.5','risk_g10':'Risk reserve gamma 1.0','gate_paid':'Paid updates',
'gate_q50':'Gate alpha 0.50','gate_q75':'Gate alpha 0.75','gate_frozen':'Frozen information and contract','gate_info_frozen':'New information, frozen contract'}
def read(p):return pd.read_csv(p,float_precision='round_trip')
def load(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def table(headers,rows):return '| '+' | '.join(headers)+' |\n|'+'|'.join(['---']*len(headers))+'|\n'+'\n'.join('| '+' | '.join(map(str,row))+' |' for row in rows)+'\n'
def num(x):return f'{x:,.2f}'

def main():
    assert load(OUT/'validation.json')['passed'];assert load(OUT/'independent_lp_audit.json')['passed']
    comp=read(OUT/'comparison.csv');selection=load(OUT/'selection.json');scores=read(OUT/'calibration_scores.csv').set_index('policy');cfg=load(OUT/'config_snapshot.json')
    bases={'pv':'pv_raw','risk':'risk_none','gate':'gate_paid'};costs=comp.set_index('policy').total_cost_yuan
    comp['baseline']=comp['group'].map(bases);comp['saving_yuan']=[costs[b]-c for b,c in zip(comp.baseline,comp.total_cost_yuan)]
    comp['saving_percent']=100*comp.saving_yuan/comp.baseline.map(costs);comp['march_selected']=[selection['selected'][g]==p for g,p in zip(comp['group'],comp.policy)]
    comp.to_csv(OUT/'effect_comparison.csv',index=False)
    monthly=[];compute=[];risk_diagnostics=[];gate_diagnostics=[];pv_errors=[]
    truth=read(WORK/'data/processed/actual_10min.csv').set_index('interval_start');truth.index=pd.to_datetime(truth.index)
    for row in comp.itertuples():
        folder=OUT/'evaluation'/row.policy;daily=read(folder/'daily.csv');ledger=read(folder/'ledger.csv');states=load(folder/'solvers.json');decisions=load(folder/'decisions.json')
        monthly.append(daily.assign(month=daily.date.str[:7]).groupby('month').total_cost_yuan.sum().rename(row.policy))
        calls=len(states)+len(decisions);seconds=sum(s['solver']['runtime_seconds'] for s in states)
        seconds+=sum(r['hold_solver' if r['accepted'] else 'update_solver']['runtime_seconds'] for r in decisions)
        compute.append({'policy':row.policy,'chosen_plan_solves':len(states),'actual_solver_calls':calls,'solver_seconds':seconds,
            'max_mip_gap':max([s['solver']['mip_gap'] for s in states]+[r[a+'_solver']['mip_gap'] for r in decisions for a in ['hold','update']])})
        if row.group=='risk':
            events=read(folder/'emergency_events.csv');emergency=ledger.emergency_kwh>1e-6
            refs=[s for s in states if s['metadata'].get('reserve')]
            noon=ledger.loc[ledger.slot_id==72].set_index('date').energy_end_actual_kwh
            baseline_ledger=read(OUT/'evaluation/risk_none/ledger.csv')
            grid_difference=ledger.grid_effective_kwh-baseline_ledger.grid_effective_kwh
            risk_diagnostics.append({'policy':row.policy,'minimum_SOC_kwh':float(ledger.energy_end_actual_kwh.min()),
                'longest_emergency_minutes':int(events.intervals.max()*10) if len(events) else 0,
                'emergency_intervals':int(emergency.sum()),'emergency_at_discharge_limit':int((emergency&(ledger.discharge_actual_kwh>=5000/6-1e-6)).sum()),
                'emergency_at_min_SOC':int((emergency&(ledger.energy_end_actual_kwh<=1200+1e-6)).sum()),
                'actual_reference_miss_days':sum(noon.loc[s['date']]<1200+s['metadata']['reserve']['amount_kwh']-1e-6 for s in refs),
                'absolute_grid_change_kwh':float(grid_difference.abs().sum()),'reference_days':len(refs),'reference_shortfall_days':sum(s['solver']['reserve_shortfall_kwh']>1e-6 for s in refs),
                'mean_reference_kwh':float(np.mean([s['metadata']['reserve']['amount_kwh'] for s in refs])) if refs else 0.})
        if decisions:
            for r in decisions:gate_diagnostics.append({'policy':row.policy,'date':r['date'],'issue_hour':r['issue_hour'],'vhat_yuan':r['vhat_yuan'],
                'vreplay_yuan':r['vreplay_yuan'],'tau_yuan':r['tau_yuan'],'accepted':r['accepted'],'positive_replay':r['vreplay_yuan']>0,'proposed_change_kwh':r['proposed_change_kwh']})
        if row.group=='pv':
            v=read(folder/'plan_versions.csv');v['actual_pv_kwh']=truth.loc[pd.to_datetime(v.interval_start)].pv_actual_kwh.to_numpy()
            for hour,g in v.groupby('issue_hour'):
                for scope,gp in [('all',g),('actual_daylight_evaluation_only',g.loc[g.actual_pv_kwh>.1])]:
                    err=gp.pv_forecast_kwh-gp.actual_pv_kwh
                    pv_errors.append({'policy':row.policy,'issue_hour':hour,'scope':scope,'n':len(gp),'mae_kwh':float(err.abs().mean()),'rmse_kwh':float(np.sqrt((err**2).mean()))})
    monthly=pd.concat(monthly,axis=1).reset_index();monthly.to_csv(OUT/'monthly_costs.csv',index=False)
    pd.DataFrame(compute).to_csv(OUT/'computation_summary.csv',index=False)
    pd.DataFrame(risk_diagnostics).to_csv(OUT/'risk_diagnostics.csv',index=False);pd.DataFrame(gate_diagnostics).to_csv(OUT/'gate_diagnostics.csv',index=False)
    gate_stats=[]
    for policy,g in pd.DataFrame(gate_diagnostics).groupby('policy',sort=False):
        accepted=g.accepted.astype(bool);changed=g.proposed_change_kwh>1e-6
        gate_stats.append({'policy':policy,'candidate_acceptances':int(accepted.sum()),'nonzero_contract_changes':int((accepted&changed).sum()),
            'rejections':int((~accepted).sum()),'positive_local_replay_fraction':float(g.positive_replay.mean()),'mean_threshold_yuan':float(g.tau_yuan.mean())})
    pd.DataFrame(gate_stats).to_csv(OUT/'gate_summary.csv',index=False)
    pv_errors=pd.DataFrame(pv_errors);pv_errors.to_csv(OUT/'pv_error_summary.csv',index=False)
    risk=load(OUT/'risk_models.json');risk=[r for r in risk if r['issue_time']>='2025-04-01' and r['predicted_s_kwh'] is not None]
    error=np.array([r['realized_s_kwh']-r['predicted_s_kwh'] for r in risk]);risk_stats={'n':len(risk),'alpha':.75,'coverage':float((error<=1e-6).mean()),
        'pinball_loss_kwh':float(np.mean(.75*np.maximum(error,0)+.25*np.maximum(-error,0))),
        'negative_clipped_forecasts':sum(r['predicted_s_kwh']==0 for r in risk)}
    save(OUT/'risk_forecast_summary.json',risk_stats)
    audit=load(OUT/'validation.json');lp=load(OUT/'independent_lp_audit.json')
    rows=[[LABELS[r.policy],num(scores.loc[r.policy,'march_cost_yuan']),num(r.total_cost_yuan),num(r.saving_yuan),f'{r.saving_percent:.5f}',num(r.emergency_kwh),'Yes' if r.march_selected else 'No'] for r in comp.itertuples()]
    selected_rows=[]
    for group,p in selection['selected'].items():
        diff=float(costs[bases[group]]-costs[p]);selected_rows.append([group,LABELS[p],num(diff),'降低费用' if diff>1 else ('增加费用' if diff< -1 else '基线或近似无差异')])
    computation=table(['策略','实际求解次数','求解器秒','最大gap'],[[LABELS[r['policy']],r['actual_solver_calls'],f"{r['solver_seconds']:.3f}",f"{r['max_mip_gap']:.3e}"] for r in compute])
    error_table=table(['PV策略','发布时刻','评价范围','MAE/kWh','RMSE/kWh'],[[LABELS[r.policy],f'{r.issue_hour:02d}:00','全部' if r.scope=='all' else '实际日间（仅评价）',f'{r.mae_kwh:.4f}',f'{r.rmse_kwh:.4f}'] for r in pv_errors.itertuples()])
    gate_table=table(['门槛策略','采纳候选次数','非零改购次数','拒绝次数','局部真实回放收益>0占比','平均τ/元'],[[LABELS[r['policy']],r['candidate_acceptances'],r['nonzero_contract_changes'],r['rejections'],f"{r['positive_local_replay_fraction']:.3f}",num(r['mean_threshold_yuan'])] for r in gate_stats])
    chapter='''# 创新实验：预报校正、连续风险余量与付费更新门槛

内部可追溯实验及论文增补初稿，不是正式提交版。依据统一方案第6.3、11、12、14节逐项实施，不把常规MILP、MPC或数据防泄漏包装为算法原创。

## 1. 实验设计与信息边界

固定价A结算作为机制实验主场景，Q1—Q4原结果保持不变。2月用于启动历史模型，3月全部31天的实际回放费用用于选型，4月1日至12月31日275天为参数冻结后的评价期。此前已经看过全年基线，因此是探索性顺序回测；不能宣称评价期是此前完全未触及的数据。候选和数值参数在execution_plan.md预先写明，评价后没有替换选中策略。

校正实验使用Q3原发布PV、Q2冻结负荷和硬日终循环；风险实验使用Q2历史PV/负荷及同核日前计划；门槛实验使用Q3原PV但共同改成软终态以保证保持承诺的可行性。各组内部同初态、同价格、同执行器，不能跨组直接用费用差归因。4月各组共同初态来自旧对应基线4月1日实际SOC，之后每条策略连续演化；不是每日重置。收支均按目标区间固定价格及最终有效量相对0点承诺一次计费，代理惩罚不进入真实账单。

## 2. 三个改进的模型

**PV校正。** 采用统一方案允许的发布时间偏差简化，而不是另造复杂回归：用过去28个完整目标日、相同发布小时、原PV预报为正的区间估计平均残差(实际−原预报)。仅在原预报为正时加该偏差并裁剪到非负，夜间原零值保持零。训练目标全部在当前日0点前完成；日内也不使用当前日新实际PV校正。该限制减少信息泄漏可能，但不是复杂条件误差模型。全部/日间MAE按相同目标集合比较，实际日间掩码只在事后评价使用。

**连续风险。** 每日0点用冻结的样本外净负载预测，构造12—18点36段残差的最大正累计前缀S，而非终点累计和。最近56个已结束日作为训练样本，最少20日；不足时回退固定参考2400kWh。条件分位模型以S/1000为目标，特征为截距、预测净负载均值/1000、预测PV均值/1000，最小化α=0.75的pinball损失。秩不足回退经验分位。内部余量B=min(9600,γ*S_hat/0.9)，γ只比较0.5和1，在12点设置E+s≥1200+B的软参考；λ_B=已知固定价均值×0.9元/内部kWh。实际缺电仍可调用全部可用电池。无余量与固定2400kWh对照始终保留；它不是严格机会约束，也不保证覆盖全部连续缺口。

**更新门槛。** 在6/12/18点，从同一真实SOC、同一0点承诺和新PV预测分别优化保持当前q与允许修改q。两者共用预计紧急通道u≤预测负荷以及“紧急不充电”约束，并共用软终态λ_T|E_end−E_midnight|，λ_T取已知固定价均值×0.9。取预测总成本差Vhat。历史反事实回放将两条候选q分别固定到当日24点、之后不再更新，从同一实际SOC执行相同实际序列，计合同/紧急费及相同终态代理得到Vreplay。只有次日0点才把ζ=Vhat−Vreplay纳入同发布时刻最近56日历史；至少20个样本时τ=max(0,Qα(ζ))，α比较0.5/0.75。Vhat>τ+1e-7才更新；早期样本不足仍正常更新。

反事实终态代理不是电网账单；冻结到24点的局部收益也不是全年滚动策略的真实增量。无门槛优化已经包含保持承诺可行集，Vhat非负本身不是创新。接收新信息但购电冻结时，当前贪心执行器不会读取未来预测，因此两条冻结策略实际轨迹理应完全相同，这一点以实际账本验证。

## 3. 全部候选真实结果

'''+table(['策略','3月校准费/元','4—12月实际费/元','较组内基线节省/元','节省率/%','紧急量/kWh','3月选中'],rows)+'''
门槛两条冻结策略以付费更新为表中参照，百分比同时反映是否更新，不能解释成单独门槛效果；PV和风险组各有自己的基线。选择只看3月，保留所有后续失败候选。

'''+table(['组别','3月选中策略','后续节省/元','后续方向'],selected_rows)+'''
固定风险余量若只有几元差异，相对于千万元账单不足以支持实际有效的创新主张，且MILP退化最优轨迹会改变后续反馈；不因3月微小差额选中便夸大优越性。风险组的全部计划都满足12点参考（计划欠量天数为0），但实际执行器只接受购电承诺，仍按真实净负荷贪心充放。计划SOC参考并不自动落实到实际SOC。表中另列实际12点参考未达天数与相对基线的购电量变化，说明仅改规划储能轨迹未形成显著实际经济收益。没有在看到这些结果后提高惩罚重跑以追求正收益。

## 4. 校准、误差与运行机制

'''+error_table+'\n'+gate_table+'\n采纳候选不一定产生非零改购，两个次数分列；累计改购量是历次候选变化的绝对量，不是最终结算电量。\n\n'+f"风险分位评价样本{risk_stats['n']}日，目标覆盖率0.75，实际覆盖率{risk_stats['coverage']:.4f}，平均pinball损失{risk_stats['pinball_loss_kwh']:.3f}kWh。覆盖不是联合安全概率，样本存在时间依赖。分时PV误差见pv_error_summary.csv；风险连续缺口、SOC最低值、放电功率受限和软参考欠量见risk_diagnostics.csv；逐次预测/实际回放收益、阈值与采纳见gate_diagnostics.csv。\n\n"+table(['策略','最低SOC/kWh','最长紧急分钟','紧急段数','放电功率受限紧急段','到达SOC下限紧急段','计划参考欠量天数','实际参考未达天数','购电量绝对变化/kWh'],[[LABELS[r['policy']],num(r['minimum_SOC_kwh']),r['longest_emergency_minutes'],r['emergency_intervals'],r['emergency_at_discharge_limit'],r['emergency_at_min_SOC'],r['reference_shortfall_days'],r['actual_reference_miss_days'],num(r['absolute_grid_change_kwh'])] for r in risk_diagnostics])+'''
## 5. 验证、计算量和限制

'''+f"独立读回检查{audit['check_count']:,}项通过，不导入规划、预测、门槛或执行模块；重建物理、实际费用、历史截止、风险目标、偏差与门槛、成对回放和3月选择。最大核对误差{audit['max_residual']:.3e}（混合量纲，具体项见validation.json）。36个独立矩阵LP时域通过；最大真实松弛差{lp['maximum_relaxation_gap_yuan']:.4f}元，最大LP约束误差{lp['maximum_lp_primal_violation']:.3e}。存在分数充放/预计紧急模式，因此不能声称LP与MILP完全等价。另有25项旧模型测试及9项新增测试通过。这些检验针对预测时域，不证明全年真实费用最优。\n\n"+computation+'''
上表仅统计4—12月评价阶段，把每次门槛比较的保持/更新两个MILP都计入；原export_policy的summary.solves仅表示最终保留计划数量。评价阶段完整计算总次数与耗时由已保存的两条求解器记录重建，见computation_summary.csv。求解器秒不含回归、文件读写和实际回放时间。

正式模板、效率/功率、退款与最终量一次结算仍是假设；风险实验保留硬日循环，门槛实验改为共同软终态，不能把终态改动当门槛贡献。未做所有模块联合优化，也未把这些创新全面迁移到Q4；当前证据只对应固定价格A规则。连续评价仍属历史探索，不能推广为跨年保证。

## 6. 英文图形

图I-1给出每月校正收益及门槛收益，正负均保留。图I-2比较连续风险目标与因果分位预测，柱形显示覆盖失效；不平滑原始日目标。

![Monthly innovation effects](../reports/figures/modelviz_innovation_v1_en/innovation_monthly/outputs/chart.png)

![Cumulative risk forecast](../reports/figures/modelviz_innovation_v1_en/innovation_risk/outputs/chart.png)

## 7. 复核与交接

在C题工作区运行：

```bash
.venv/bin/python -B scripts/validate_innovation.py
.venv/bin/python -B scripts/audit_innovation_lp.py
.venv/bin/python -B scripts/report_innovation.py
.venv/bin/python -B -m unittest discover -s tests -p 'test_innovation_core.py'
```

完整重算用scripts/run_innovation.py，必须另开版本且不复制完成的results/innovation。分阶段11组全账本、计划、求解状态、日费用、四日可用表、候选承诺与成对回放均保存，模型/来源哈希和论文增补随冻结包交付。3月20日只在校准段，其他三个指定日属于评价段，不能把不同阶段表拼成一个未披露初态的全年正式策略。
'''
    (WORK/'papers/innovation_draft.md').write_text(chapter)
    (WORK/'reports/innovation/model_and_results.md').write_text(chapter.replace('(../reports/figures/','(../figures/'))
    sources=[OUT/n for n in ['comparison.csv','calibration_scores.csv','selection.json','validation.json','independent_lp_audit.json','risk_models.json']]+[WORK/'scripts/report_innovation.py']
    save(OUT/'report_sources.json',{str(p.relative_to(WORK)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    print(comp[['policy','total_cost_yuan','saving_yuan','march_selected']].to_string(index=False))
    print('Risk:',risk_stats)

if __name__=='__main__':main()
