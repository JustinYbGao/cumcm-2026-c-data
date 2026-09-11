# Five populated result workbooks — internal review

**Status: REVIEW ONLY. Not an officially confirmed submission.** Original templates and source data remain unchanged. This set adopts the existing interval-end convention and explicitly relabels the copied time headers to `00:00-00:10` through `23:50-24:00`. `template_time_mapping.csv` records every old/new label. Numeric values are matched by physical date/time, never shifted or wrapped.

| Workbook | Policy | Total cost (CNY) |
|---|---|---:|
| result1.xlsx | Q1 baseline | 35,126.948589 |
| result2.xlsx | Q2 January-selected forecast | 16,333,683.392851 |
| result3.xlsx | Q3 continuous 28-day PV correction | 13,726,733.574968 |
| result4-2.xlsx | Q4-2 causal OLS price | 17,030,881.697375 |
| result4-3.xlsx | Q4-3 continuous 28-day PV correction | 14,492,279.546435 |

Q3/Q4-3 use raw PV through March and correction from April, with continuous actual SOC from February. Selection of the correction was retrospective research, not a pre-registered unseen-year test.

## Read the columns correctly

- The original Chinese sheet names/order follow Attachment 5. Original headers other than the explicit time relabeling are retained. All energy values are kWh; fees are CNY. The English-only requirement for plot labels does not change the official workbook sheet names.
- Annual grid sheets have all 334 dates, each with 144 ten-minute values. `EP` sums these values using a formula. Values retain floating-point precision and display six decimals.
- On `计划购电量`, `EQ` is the midnight original commitment fee. On `调整购电量`, `EQ` is the **complete final contract fee** under rule A, including the original fee and revision adjustments. These two fees must NOT be added together.
- All-in cost = final applicable contract fee + emergency purchase fee. The emergency fee is recomputed at each ten-minute actual price times five, including when prices change during one merged emergency event. `cost_summary.csv` lists original, increase, decrease, contract, emergency and total fees.
- `调整购电量` contains the final effective commitment for each interval, not the signed change and not all intermediate versions. The original full `plan_versions.csv` remains the history evidence.
- Annual battery sheets have 2,004 rows: six four-hour blocks for each date, using actual executed charge/discharge. For each day, the first two rows' `E/F` cells independently record SOC at 00:00 and 24:00; the row's four-hour block does not change that time meaning.
- Emergency sheets list every maximal consecutive positive run within each day (threshold 1e-7 kWh), with repeated explicit dates. Days with no emergency purchase have no event row. Date coverage of simulated operation is proved by the grid/battery sheets and independent audit, not by inserting fictional zero events.

Sources and checks: `source_hashes.json`, `cost_summary.csv`, and `../../reports/revision_v1/export_validation.json`. Run instructions: `../../reports/revision_v1/reproduction.md`.

Before formal submission, resolve the time/template convention and adopt the stated physical/settlement/information assumptions, complete the required human AI review and final paper format check. If the physical interpretation changes, rerun affected models before regenerating these files. Do not rename an old frozen archive as the formal support package.
