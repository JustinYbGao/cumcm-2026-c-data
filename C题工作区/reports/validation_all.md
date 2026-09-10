# all 数据验证

验证对象为重新读取的 CSV；任何未通过项均保留。

| 检查 | 结果 | 证据 |
|---|---|---|
| Q1: 144 slots unique and ordered | 通过 |  |
| Q1: complete relative day intervals | 通过 |  |
| Q1: required values nonmissing | 通过 |  |
| fixed_price: 144 slots unique and ordered | 通过 |  |
| fixed_price: complete relative day intervals | 通过 |  |
| fixed_price: required values nonmissing | 通过 |  |
| Q1: all original numeric cells preserved | 通过 |  |
| Q1: energy and signed net load | 通过 |  |
| Q1: fixed price identical | 通过 |  |
| Q1: negative net and zeros preserved | 通过 | negative net=30, PV zero=55 |
| actual_10min: interval_start timezone-naive | 通过 |  |
| actual_10min: interval_end timezone-naive | 通过 |  |
| actual_10min: available_time timezone-naive | 通过 |  |
| pv_forecast_hourly: issue_time timezone-naive | 通过 |  |
| pv_forecast_hourly: target_time timezone-naive | 通过 |  |
| pv_forecast_10min: interval_start timezone-naive | 通过 |  |
| pv_forecast_10min: interval_end timezone-naive | 通过 |  |
| pv_forecast_10min: issue_time timezone-naive | 通过 |  |
| pv_forecast_10min: endpoint_issue_time timezone-naive | 通过 |  |
| Actual: 52560 unique contiguous intervals | 通过 |  |
| Actual: every day 144 slots | 通过 |  |
| Actual: end/start and year-end business date | 通过 |  |
| Actual: no missing data or unexpected join loss | 通过 |  |
| Actual: all load_actual_kw raw cells reconcile | 通过 |  |
| Actual: load source rows reconcile | 通过 |  |
| Actual: load_actual_kw zeros preserved | 通过 |  |
| Actual: all pv_actual_kw raw cells reconcile | 通过 |  |
| Actual: pv source rows reconcile | 通过 |  |
| Actual: pv_actual_kw zeros preserved | 通过 |  |
| Actual: all actual_price_yuan_per_kwh raw cells reconcile | 通过 |  |
| Actual: price source rows reconcile | 通过 |  |
| Actual: actual_price_yuan_per_kwh zeros preserved | 通过 |  |
| Actual: energy and signed net conversion | 通过 |  |
| Actual: negative net preserved | 通过 | negative net=10130 |
| Actual: fixed price mapping | 通过 |  |
| Actual: availability is interval end | 通过 |  |
| Hourly: 35040 unique version-target keys | 通过 |  |
| Hourly: 1460 issue times / 24 horizons | 通过 |  |
| Hourly: target equals issue plus horizon | 通过 |  |
| Hourly: every original power preserved | 通过 |  |
| Hourly: date fills recorded | 通过 |  |
| Hourly: date-fill flags map to exact source rows | 通过 |  |
| Hourly: all 1095 date-fill source cells logged | 通过 |  |
| Hourly: overlapping versions and cross-year retained | 通过 | targets after actual end=36 |
| 10min: 210234 rows and unique version-interval keys | 通过 |  |
| 10min: initial issue 138 intervals, remaining 1459 issues 144 | 通过 |  |
| 10min: all intervals 10min and within 24h | 通过 |  |
| 10min: no internal gaps per version | 通过 |  |
| 10min: missing initial hour not invented | 通过 |  |
| 10min: business date and slot | 通过 |  |
| 10min: endpoint source older by 6h | 通过 |  |
| 10min: every interval independently integrates raw forecast powers | 通过 |  |
| 10min: finite nonnegative derived values | 通过 |  |
| Causal access: 23 decision timestamps, future rows excluded | 通过 |  |
| Causal access: February 1 uses all January and none of February | 通过 |  |
| Synthetic boundary/units/version/isolation tests | 通过 | 9 tests |
| All original workbooks including templates unchanged | 通过 |  |
