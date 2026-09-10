
# CELL 1, execution_count=None
# %pip install pandas numpy openpyxl matplotlib ipykernel

# CELL 2, execution_count=None
from pathlib import Path
import datetime as dt
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display

# 若移动了文件夹，只需修改 ROOT。
ROOT = Path.cwd()
if not (ROOT / '附件').is_dir():
    ROOT = Path('/Users/mike/Desktop/国赛')
DATA = ROOT / '附件'
assert DATA.is_dir(), f'找不到附件目录：{DATA}'
pd.set_option('display.max_columns', 12)
print('数据目录：', DATA)


# CELL 4, execution_count=None
raw = {f'附件{i}.xlsx': pd.read_excel(DATA / f'附件{i}.xlsx', sheet_name=None) for i in range(1, 5)}
inventory = pd.DataFrame([
    {'文件': f, '工作表': s, '行数': len(df), '列数': len(df.columns)}
    for f, sheets in raw.items() for s, df in sheets.items()
])
display(inventory)
display(raw['附件1.xlsx']['Sheet1'].head())

# CELL 6, execution_count=None
def minute_of_day(value):
    if isinstance(value, (dt.time, dt.datetime, pd.Timestamp)):
        return value.hour * 60 + value.minute
    text = str(value).strip()
    extra = 1440 if '+1' in text else 0
    parts = text.replace('+1', '').split(':')
    return int(parts[0]) * 60 + int(parts[1]) + extra

def check_slots(values):
    minutes = [minute_of_day(v) for v in values]
    assert minutes == list(range(10, 1441, 10)), '时段不是连续的0:10到24:00'
    return minutes

def numeric_block(frame):
    out = frame.apply(pd.to_numeric, errors='raise')
    assert np.isfinite(out.to_numpy(dtype=float)).all(), '发现缺失或无穷值'
    assert (out >= 0).all().all(), '发现负数，请核查原表'
    return out


# CELL 8, execution_count=None
source = raw['附件1.xlsx']['Sheet1']
minutes = check_slots(source.iloc[:, 0])
values = numeric_block(source.iloc[:, 1:])
q1_day = pd.DataFrame({'slot_id': range(1, 145)})
q1_day['start_time'] = [f'{(m-10)//60:02d}:{(m-10)%60:02d}' for m in minutes]
q1_day['end_time'] = [f'{m//60:02d}:{m%60:02d}' for m in minutes]
q1_day[['price_yuan_per_kwh', 'load_kw', 'pv_forecast_kw']] = values.to_numpy()
q1_day['load_kwh'] = q1_day.load_kw / 6
q1_day['pv_forecast_kwh'] = q1_day.pv_forecast_kw / 6
q1_day['net_load_forecast_kwh'] = q1_day.load_kwh - q1_day.pv_forecast_kwh
fixed_price = q1_day[['slot_id', 'start_time', 'end_time', 'price_yuan_per_kwh']].copy()
display(q1_day.head())

# CELL 10, execution_count=None
def annual_long(frame, value_name):
    minutes = check_slots(frame.columns[1:])
    dates = pd.to_datetime(frame.iloc[:, 0], errors='raise').dt.normalize()
    assert len(dates) == 365 and dates.is_unique
    assert list(dates) == list(pd.date_range('2025-01-01', '2025-12-31'))
    values = numeric_block(frame.iloc[:, 1:])
    result = pd.DataFrame({
        'date': np.repeat(dates.to_numpy(), 144),
        'slot_id': np.tile(np.arange(1, 145), 365),
        value_name: values.to_numpy().reshape(-1),
    })
    result['interval_end'] = result.date + pd.to_timedelta(np.tile(minutes, 365), unit='m')
    result['interval_start'] = result.interval_end - pd.Timedelta(minutes=10)
    assert result.interval_start.is_unique
    return result

load = annual_long(raw['附件2.xlsx']['小区负载'], 'load_actual_kw')
pv = annual_long(raw['附件2.xlsx']['光伏发电实际功率'], 'pv_actual_kw')
price = annual_long(raw['附件4.xlsx']['Sheet1'], 'actual_price_yuan_per_kwh')
keys = ['date', 'slot_id', 'interval_start', 'interval_end']
actual_10min = load.merge(pv, on=keys, validate='one_to_one').merge(price, on=keys, validate='one_to_one')
actual_10min = actual_10min.merge(
    fixed_price[['slot_id', 'price_yuan_per_kwh']].rename(columns={'price_yuan_per_kwh':'fixed_price_yuan_per_kwh'}),
    on='slot_id', validate='many_to_one').sort_values('interval_start').reset_index(drop=True)
actual_10min['load_actual_kwh'] = actual_10min.load_actual_kw / 6
actual_10min['pv_actual_kwh'] = actual_10min.pv_actual_kw / 6
actual_10min['net_load_actual_kwh'] = actual_10min.load_actual_kwh - actual_10min.pv_actual_kwh
assert len(actual_10min) == 52560 and not actual_10min.isna().any().any()
assert actual_10min.interval_end.iloc[-1] == pd.Timestamp('2026-01-01')
display(actual_10min.head())

# CELL 12, execution_count=None
forecast_raw = raw['附件3.xlsx']['Sheet1'].copy()
dates = pd.to_datetime(forecast_raw.iloc[:, 0].replace(r'^\s*$', np.nan, regex=True).ffill())
issue_minutes = forecast_raw.iloc[:, 1].map(minute_of_day)
assert set(issue_minutes) == {0, 360, 720, 1080}
issues = dates + pd.to_timedelta(issue_minutes, unit='m')
assert len(issues) == 1460 and issues.is_unique
assert (issues.groupby(dates).size() == 4).all()
assert list(forecast_raw.columns[2:]) == [f'预报{i}小时' for i in range(1, 25)]
values = numeric_block(forecast_raw.iloc[:, 2:])
pv_forecast_hourly = pd.DataFrame({
    'issue_time': np.repeat(issues.to_numpy(), 24),
    'horizon_h': np.tile(np.arange(1, 25), len(issues)),
    'pv_forecast_kw': values.to_numpy().reshape(-1),
})
pv_forecast_hourly['target_time'] = pv_forecast_hourly.issue_time + pd.to_timedelta(pv_forecast_hourly.horizon_h, unit='h')
assert len(pv_forecast_hourly) == 35040
assert not pv_forecast_hourly.duplicated(['issue_time', 'target_time']).any()
display(pv_forecast_hourly.head())

# CELL 14, execution_count=None
DAY = '2025-03-20'
day_data = actual_10min.loc[actual_10min.date == pd.Timestamp(DAY)].copy()
assert len(day_data) == 144, '日期不在数据范围内'
fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
axes[0].plot(day_data.interval_start, day_data.load_actual_kw, label='Load')
axes[0].plot(day_data.interval_start, day_data.pv_actual_kw, label='PV')
axes[0].set(ylabel='Power (kW)', title=DAY)
axes[0].legend()
axes[1].plot(day_data.interval_start, day_data.actual_price_yuan_per_kwh, label='Actual price')
axes[1].plot(day_data.interval_start, day_data.fixed_price_yuan_per_kwh, label='Fixed price')
axes[1].set(ylabel='Price (yuan/kWh)', xlabel='Time')
axes[1].legend()
plt.tight_layout()
plt.show()

# CELL 16, execution_count=None
def history_at(decision_time):
    t = pd.Timestamp(decision_time)
    return actual_10min.loc[actual_10min.interval_end <= t].copy()

def forecasts_at(decision_time):
    t = pd.Timestamp(decision_time)
    return pv_forecast_hourly.loc[
        (pv_forecast_hourly.issue_time <= t) & (pv_forecast_hourly.target_time > t)
    ].copy()

DECISION_TIME = '2025-02-01 00:00'
history = history_at(DECISION_TIME)
available_forecasts = forecasts_at(DECISION_TIME)
print('可用历史行数：', len(history))
display(available_forecasts.tail())

# CELL 18, execution_count=None
EXPORT = False
if EXPORT:
    from datetime import datetime
    output = ROOT / '处理结果' / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    output.mkdir(parents=True, exist_ok=False)
    tables = {'q1_day': q1_day, 'fixed_price': fixed_price,
              'actual_10min': actual_10min, 'pv_forecast_hourly': pv_forecast_hourly}
    for name, table in tables.items():
        table.to_csv(output / f'{name}.csv', index=False, encoding='utf-8-sig', date_format='%Y-%m-%d %H:%M:%S')
    (output / '处理说明.md').write_text(
        '# 处理说明\n来源：附件1—4。原文件未修改；未删除或填补数值。\n'
        '采用区间平均功率假设，十分钟电量=功率/6。此口径需与建模人员确认。\n'
        '全年实际52560行，小时预报35040行；小时预报未做十分钟插值。\n'
        '已检查时间、缺失、非数值、负数、唯一键和合并行数。\n'
        '尚未完成：异常跳变、预报误差分析、调度优化。\n', encoding='utf-8')
    print('已导出：', output)
else:
    print('暂不导出；将 EXPORT 改为 True 后运行本格即可。')

# CELL 20, execution_count=None
# 例：按日统计实际用电量和光伏电量
daily_energy = actual_10min.groupby("date")[["load_actual_kwh", "pv_actual_kwh"]].sum()
display(daily_energy.head())