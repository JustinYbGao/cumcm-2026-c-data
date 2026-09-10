# 数据字典

所有CSV为UTF-8、逗号分隔、不输出行索引。数值为未提前舍入的浮点数，功率kW、电量kWh、电价元/kWh。真实零值与有符号净负载原样保留。日期为YYYY-MM-DD，完整时间为YYYY-MM-DDTHH:MM:SS，无时区。行列定位均为Excel从1开始的坐标。

源目录：`/Users/justingao/Documents/CUMCM/CUMCM2026Problems/C题/附件/`。所有派生口径详见processing_notes.md。

## fixed_price.csv

144行。唯一键：slot_id。来自附件1.xlsx/Sheet1；没有来源业务日期。

| 字段 | 类型/单位 | 定义/来源 |
|---|---|---|
| slot_id | int | 日内编号1—144 |
| raw_time_label | string | 附件1 A列原标签的字符串表示；Excel time统一显示秒，0:00+1保留 |
| start_minute | int/min | 自业务日0点起的区间开始偏移，0—1430 |
| end_minute | int/min | 区间结束偏移，10—1440 |
| start_time | string | 日内HH:MM:SS |
| end_time | string | 日内HH:MM:SS，末值24:00:00；用end_minute运算 |
| price_yuan_per_kwh | float/元每kWh | 附件1 B列，固定日内电价，不乘1/6 |
| source_row | int | 附件1源行2—145 |

## q1_day.csv

144行。唯一键：slot_id。具有fixed_price上述全部字段，增加以下字段。原功率既是源值也是输入值，不另造重复raw数值列。

| 字段 | 类型/单位 | 定义/来源 |
|---|---|---|
| load_kw | float/kW | 附件1 C列给定负载原值 |
| pv_forecast_kw | float/kW | 附件1 D列给定PV预测原值，不是真实PV |
| load_kwh | float/kWh | load_kw/6，采用区间平均功率假设 |
| pv_forecast_kwh | float/kWh | pv_forecast_kw/6 |
| net_load_forecast_kw | float/kW | load_kw-pv_forecast_kw，可负 |
| net_load_forecast_kwh | float/kWh | load_kwh-pv_forecast_kwh，可负 |

Q1无来源日期，因此不添加伪date或完整interval_start。给定任意仿真业务日时，下游可把分钟偏移加到该日，但必须明确该日期是仿真锚点，而非附件来源。

## actual_10min.csv

52560行。唯一键：interval_start，等价键：date+slot_id。由附件2两表与附件4一对一连接，再按slot_id接固定价。

| 字段 | 类型/单位 | 定义/来源 |
|---|---|---|
| date | date | 业务日2025-01-01至2025-12-31 |
| slot_id | int | 当日1—144 |
| interval_start | datetime | 区间起点，全年连续十分钟网格 |
| interval_end | datetime | interval_start+10分钟，末值2026-01-01T00:00:00 |
| available_time | datetime | 默认等于interval_end，决策时刻不早于此值方可用 |
| load_actual_kw | float/kW | 附件2.xlsx/小区负载原功率 |
| pv_actual_kw | float/kW | 附件2.xlsx/光伏发电实际功率原功率 |
| load_actual_kwh | float/kWh | load_actual_kw/6 |
| pv_actual_kwh | float/kWh | pv_actual_kw/6 |
| net_load_actual_kw | float/kW | 实际负载原功率减实际PV原功率，可负 |
| net_load_actual_kwh | float/kWh | 实际负载电量减实际PV电量，可负 |
| fixed_price_yuan_per_kwh | float/元每kWh | 附件1的固定日内价格，以slot_id映射 |
| actual_price_yuan_per_kwh | float/元每kWh | 附件4.xlsx/Sheet1原始实际价格；不代表未来提前可知 |
| load_raw_time_label | string | 附件2小区负载表原列标签 |
| pv_raw_time_label | string | 附件2光伏发电实际功率表原列标签 |
| price_raw_time_label | string | 附件4表原列标签 |
| load_source_row / pv_source_row / price_source_row | int | 对应源工作表行2—366 |
| load_source_column / pv_source_column / price_source_column | string | 对应源列字母B—EO |

源值可用源文件/工作表映射与对应source_row/source_column直接定位。固定价格源行为slot_id+1，列B。

## pv_forecast_hourly.csv

35040行，1460次发布，每次24目标。唯一键：issue_time+target_time，等价键：issue_time+horizon_h。

| 字段 | 类型/单位 | 定义/来源 |
|---|---|---|
| issue_time | datetime | 发布时间，当日0/6/12/18点 |
| horizon_h | int/h | 1—24小时前瞻 |
| target_time | datetime | issue_time+horizon_h小时，跨2026年目标保留 |
| pv_forecast_kw | float/kW | 附件3.xlsx/Sheet1原预测值 |
| source_row | int | 附件3源行2—1461 |
| source_column | string | 附件3源列C—Z，即horizon_h+2 |
| raw_date_label | string，可空 | 附件3 A列原始标签；空字符串仍为空，不等于数值缺失 |
| raw_issue_label | string | 附件3 B列原发布钟点 |
| date_was_filled | bool | 当前行日期是否来自按原行序向下填充 |

日期填充变更日志位于data/interim/transformation_log.csv，列为source_file、source_sheet、source_cell、original_value（JSON表示）、new_value、reason。每个原始空日期单元格只记一条，共1095条。

## pv_forecast_10min.csv

210234行。唯一键：issue_time+interval_start。保留所有发布版本，不去重不同issue_time。该表是有明确假设的派生预测电量，不能当作原始整点测量。

| 字段 | 类型/单位 | 定义/来源 |
|---|---|---|
| issue_time | datetime | 当前预报版本发布时间 |
| interval_start / interval_end | datetime | 目标十分钟区间完整起止时间 |
| horizon_start_min / horizon_end_min | int/min | 相对当前发布时间的起止分钟偏移，范围0—1440 |
| date | date | 目标区间开始所属业务日，可为2026-01-01 |
| slot_id | int | 目标日1—144 |
| pv_forecast_kwh | float/kWh | 线性功率曲线对该十分钟区间的梯形积分 |
| conversion_method | string | piecewise_linear_point_power_trapezoid |
| endpoint_rule | string | 首小时previous_issue_point，其余current_issue_points |
| endpoint_issue_time | datetime，可空 | 仅首小时填写所用旧版发布时间；其余区间不适用，留空 |

对首小时：旧端点通过小时表键(endpoint_issue_time, target_time=issue_time)追溯，右端为当前版h=1。其他区间：令k=floor(horizon_start_min/60)，用当前版h=k和h=k+1进行线性积分。因此不重复储存所有原整点功率。

首份2025-01-01T00:00:00的首小时无旧端点，只生成horizon_start_min=60—1430的138段。不能把缺失6段填零。data/interim/forecast_coverage.csv保存每个issue_time的interval_count、first_interval_start、last_interval_end、missing_first_hour。

## 辅助报告

- numeric_summary.csv：各字段count、missing、nonfinite、zero、negative、min、max。
- daily_energy.csv：以date为键汇总实际负载、PV与净电量（kWh/day）。
- largest_jumps.csv：field、interval_start、previous_value、current_value、change、source_row、source_column、action；单位跟随field。只做排名，不删除数值。
- template_cells.csv：file、sheet、cell、value、python_type，原结果模板所有非空结构的坐标清单，不是填写结果。
- validation_all.json/md：实际执行的检查与结果；111_audit.json/md：朋友文件的来源、逐字段对照和重跑结果。

## pv_forecast_hourly_evaluation.csv（事后评估专用）

35040行，唯一键issue_time+target_time，与原小时预报版本键完全一致。包含实际观测，不能直接当作决策输入。调用diagnose_forecasts.errors_at按决策时间获取当时已结束的可比误差。

| 字段 | 类型/单位 | 定义 |
|---|---|---|
| issue_time、target_time、horizon_h、pv_forecast_kw | 同小时原表 | 原始版本键、提前量与整点预测，仅追溯；pv_forecast_kw不用于直接计算平均功率误差 |
| interval_start | datetime | 目标小时起点target_time−1小时，目标区间到target_time结束 |
| target_business_date | date | 目标小时起点所属日期，跨年末小时仍属2025-12-31 |
| forecast_interval_count | int | 当前版本该小时有效预测十分钟电量数，应为6；没有则为0，计数0不是填补电量 |
| actual_interval_count | int | 该小时有效实际十分钟电量数，应为6；没有则为0 |
| forecast_hour_kwh | float/kWh，可空 | 完整6段预测电量之和；不足6段留空，不求不完整小时总量 |
| actual_hour_kwh | float/kWh，可空 | 完整6段实际PV电量之和；不足6段留空，真实0保留 |
| comparison_status | string | comparable / missing_forecast / missing_actual / missing_both；当前原数据不存在missing_both |
| issue_hour | int | 预报发布时间钟点0、6、12、18 |
| lead_block | int | 1=提前1—6小时，2=7—12，3=13—18，4=19—24 |
| error_kwh | float/kWh，可空 | forecast_hour_kwh−actual_hour_kwh，正值高估 |
| error_available_time | datetime，可空 | 可比较行等于target_time；缺测或缺预测留空，始终不作为有效历史误差 |
| actual_positive_pv | nullable bool | 事后实际小时电量>0；无实际值留空，仅用于诊断子集 |

实际小时电量按区间平均功率口径，预测小时电量按点值线性积分口径，二者比较的是同一小时的电量。错误表不是新模型预测输出。CSV读取建议dtype={'actual_positive_pv':'boolean'}，时间列用parse_dates。

## 预报误差与日历汇总

- pv_forecast_error_summary.csv：scope=all_comparable或same_target_four_versions；population=all_hours或actual_pv_positive；grouping=overall、issue_hour、lead_block或horizon_h；group_value为分组值；n为版本记录数，target_hour_count为不同目标小时数，target_start/target_end为目标小时末时间范围。bias_kwh、mae_kwh、rmse_kwh分别是有符号平均误差、绝对误差均值、均方根误差（单位kWh）。未计算存在零除问题的MAPE。
- pv_forecast_common_targets.csv：issue_time、target_time、issue_hour、lead_block；34968条，8742个共同目标小时，每个目标有4个版本。各发布时间/提前量段比较共享完全相同目标集合。
- actual_calendar_summary.csv：grouping=month或weekday；value为月份1—12或星期0—6（周一=0）；n_days为真实业务日数；mean_daily_load_kwh、mean_daily_pv_kwh、mean_daily_net_load_kwh为观测日总电量均值，单位kWh/day。唯一键grouping+value。只作全样本描述，不作为早期预测参数。
- validation_forecast_diagnostics.json：新增错误表的独立读回、单位、缺失、样本集合与信息时点验证。
