"""Post-outcome hourly-energy diagnostics of supplied forecasts; never a predictor."""
import json
import numpy as np
import pandas as pd
from prepare_data import WORK, OUT, naive_time


def evaluate_pv(hourly, derived, actual):
    keys = ['issue_time','target_time']
    # Source key guards: a duplicated interval must not silently become extra energy.
    if hourly.duplicated(keys).any() or derived.duplicated(['issue_time','interval_start']).any() or actual.duplicated('interval_start').any():
        raise ValueError('Duplicated source keys')
    d,a = derived.copy(),actual.copy()
    for frame in [d,a]:
        if not frame.interval_end.eq(frame.interval_start+pd.Timedelta(minutes=10)).all():
            raise ValueError('Expected ten-minute intervals')
        if not frame.interval_start.dt.minute.mod(10).eq(0).all() or not frame.interval_start.dt.second.eq(0).all():
            raise ValueError('Intervals must be aligned to the ten-minute grid')
        frame['target_time'] = frame.interval_start.dt.floor('h')+pd.Timedelta(hours=1)
    forecast_hour = d.groupby(keys).agg(forecast_interval_count=('pv_forecast_kwh','count'),forecast_hour_kwh=('pv_forecast_kwh','sum')).reset_index()
    actual_hour = a.groupby('target_time').agg(actual_interval_count=('pv_actual_kwh','count'),actual_hour_kwh=('pv_actual_kwh','sum')).reset_index()
    result = hourly[['issue_time','target_time','horizon_h','pv_forecast_kw']].merge(
        forecast_hour,on=keys,how='left',validate='one_to_one').merge(actual_hour,on='target_time',how='left',validate='many_to_one')
    for prefix in ['forecast','actual']:
        count = f'{prefix}_interval_count'
        result[count] = result[count].fillna(0).astype(int)
        result[f'{prefix}_hour_kwh'] = result[f'{prefix}_hour_kwh'].where(result[count].eq(6))
    f_ok,a_ok = result.forecast_interval_count.eq(6),result.actual_interval_count.eq(6)
    result['comparison_status'] = np.select([~f_ok&~a_ok,~f_ok,~a_ok],['missing_both','missing_forecast','missing_actual'],default='comparable')
    result['interval_start'] = result.target_time-pd.Timedelta(hours=1)
    result['target_business_date'] = result.interval_start.dt.strftime('%Y-%m-%d')
    result['issue_hour'] = result.issue_time.dt.hour
    result['lead_block'] = (result.horizon_h-1)//6+1
    result['error_kwh'] = result.forecast_hour_kwh-result.actual_hour_kwh
    result['error_available_time'] = result.target_time.where(result.comparison_status.eq('comparable'))
    # Historical outcome-based subset only, not a feature available at issue_time.
    result['actual_positive_pv'] = pd.Series(pd.NA,index=result.index,dtype='boolean')
    result.loc[a_ok,'actual_positive_pv'] = result.loc[a_ok,'actual_hour_kwh'].gt(0)
    return result.sort_values(keys).reset_index(drop=True)


def errors_at(evaluation,decision_time):
    """Only completed, comparable error records; full evaluation CSV is retrospective."""
    t = naive_time(decision_time)
    return evaluation.loc[evaluation.comparison_status.eq('comparable')
        & (pd.to_datetime(evaluation.error_available_time)<=t)
        & (pd.to_datetime(evaluation.issue_time)<=t)].copy()


def summarize(evaluation):
    valid = evaluation.loc[evaluation.comparison_status.eq('comparable')].copy()
    # One target hour has exactly one version from each issue hour and lead block.
    common = valid.groupby('target_time').filter(lambda g:len(g)==4 and g.issue_hour.nunique()==4 and g.lead_block.nunique()==4)
    records = []
    for scope,subset in [('all_comparable',valid),('same_target_four_versions',common)]:
        for population,data in [('all_hours',subset),('actual_pv_positive',subset.loc[subset.actual_positive_pv.fillna(False)])]:
            groupings = [('overall',None),('issue_hour','issue_hour'),('lead_block','lead_block')]
            if scope=='all_comparable':
                groupings += [('horizon_h','horizon_h')]
            for grouping,column in groupings:
                groups = [('all',data)] if column is None else data.groupby(column)
                for value,g in groups:
                    error = g.error_kwh
                    records.append({'scope':scope,'population':population,'grouping':grouping,'group_value':str(value),
                        'n':len(g),'target_hour_count':g.target_time.nunique(),
                        'target_start':g.target_time.min(),'target_end':g.target_time.max(),
                        'bias_kwh':error.mean(),'mae_kwh':error.abs().mean(),'rmse_kwh':np.sqrt(error.pow(2).mean())})
    return pd.DataFrame(records),common


def main():
    hourly = pd.read_csv(OUT/'pv_forecast_hourly.csv',parse_dates=['issue_time','target_time'],float_precision='round_trip')
    derived = pd.read_csv(OUT/'pv_forecast_10min.csv',parse_dates=['issue_time','interval_start','interval_end'],float_precision='round_trip')
    actual = pd.read_csv(OUT/'actual_10min.csv',parse_dates=['interval_start','interval_end'],float_precision='round_trip')
    result = evaluate_pv(hourly,derived,actual)
    result.to_csv(OUT/'pv_forecast_hourly_evaluation.csv',index=False,date_format='%Y-%m-%dT%H:%M:%S')
    summary,common = summarize(result)
    summary.to_csv(WORK/'reports/pv_forecast_error_summary.csv',index=False,date_format='%Y-%m-%dT%H:%M:%S')
    # Save comparison keys explicitly so future comparisons can reproduce exactly the same sample.
    common[['issue_time','target_time','issue_hour','lead_block']].to_csv(WORK/'reports/pv_forecast_common_targets.csv',index=False,date_format='%Y-%m-%dT%H:%M:%S')
    status = result.comparison_status.value_counts().to_dict()
    lines = ['# PV预报数据诊断', '',
        '评估对象是题目提供的预报经已声明线性积分后的一小时电量；未训练模型或校正预报。统计是事后数据诊断，不是调度效果或独立测试集的预测成绩。', '',
        '## 比较口径', '',
        '每行目标为[target_time−1小时,target_time)。预测与实际都必须包含该小时完整6个十分钟区间，分别求和为kWh。原始整点pv_forecast_kw只供追溯，不直接与区间平均实际功率相减。误差=预测小时电量−实际小时电量，正值表示高估。', '',
        f'共保留{len(result)}个原发布版本—目标键：'+ '；'.join(f'{k}={v}' for k,v in status.items())+'。',
        f'四个版本都有有效实际值的共同目标小时数为{common.target_time.nunique()}，共{len(common)}条版本记录。按发布时间或提前量段作版本比较时使用同一目标集合。', '',
        '## 相同目标集合的比较（全部小时）', '',
        '| 分组 | 值 | 样本数 | 偏差(kWh) | MAE(kWh) | RMSE(kWh) |','|---|---|---:|---:|---:|---:|']
    selected = summary.loc[(summary.scope=='same_target_four_versions')&(summary.population=='all_hours')&(summary.grouping!='overall')]
    for r in selected.itertuples():
        lines.append(f'| {r.grouping} | {r.group_value} | {r.n} | {r.bias_kwh:.4f} | {r.mae_kwh:.4f} | {r.rmse_kwh:.4f} |')
    lines += ['', 'lead_block=1/2/3/4分别为提前1—6/7—12/13—18/19—24小时。issue_hour按预报发布时间分组，不自动等同于提前量优劣。精度仅在Markdown展示时取4位，CSV未提前舍入。', '',
        '完整汇总另含全部可比样本的horizon_h=1—24、发布时间、提前量段，以及实际PV小时电量>0子集。后者是事后筛选口径，包含微小非零值，不代表天文学白昼，也不用于生成当时预测特征。不同提前量单独汇总的目标集合可能略有差别；严格版本比较使用same_target_four_versions。', '',
        '## 缺口和信息边界', '',
        '- 第一份0点预报的首小时缺端点，forecast_hour_kwh和error_kwh保持空值，状态missing_forecast。',
        '- 跨年36条版本—目标记录（涉及18个不同目标小时）没有实际数据，actual_hour_kwh和error_kwh为空，状态missing_actual；真实零PV小时仍可评估。',
        '- 错误记录在目标整小时结束后才可用，error_available_time=target_time。没有实际值或不完整的小时始终不进入errors_at筛选。',
        '- 全量evaluation文件含事后实际数据，不可直接作为训练特征；调用errors_at(evaluation,decision_time)只取当时已结束的误差。该接口仅供后续因果校准，不在本轮拟合参数。',
        '- 这些误差依赖区间平均实际功率、点值线性积分、旧版首小时端点等假设，队伍改口径后须重算。误差改善不等于购电费用下降。', '',
        '生成代码：scripts/diagnose_forecasts.py；验证代码：scripts/validate_forecast_diagnostics.py；原始值和五张基础表未被修正。']
    (WORK/'reports/pv_forecast_diagnostics.md').write_text('\n'.join(lines)+'\n')
    print(f'Wrote evaluation rows={len(result)}, status={json.dumps(status)}, common_target_hours={common.target_time.nunique()}')


if __name__=='__main__':
    main()
