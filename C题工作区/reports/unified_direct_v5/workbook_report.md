# Five workbook export report

## Result

Five selected strategy workbooks were written under `outputs/unified_direct_v5` from the official Appendix 5 templates. The final independent readback passed 4,107,481 checks and 2,143,182 numeric comparisons with zero failures. Maximum absolute errors were 7.27595761418e-11 kWh and 1.30385160446e-7 yuan.

Selected strategies:

| Workbook | Strategy |
| --- | --- |
| result1.xlsx | baseline |
| result2.xlsx | Q2_D112 |
| result3.xlsx | q3_raw |
| result4-2.xlsx | q42_fixed |
| result4-3.xlsx | q43_raw_ols |

## Executed commands and status

1. Bundled Python ran `scripts/unified_direct_v5/prepare_workbooks.py`: passed. It read the frozen `selection.json`, generated the Artifact Tool payload, 1,008-entry time mapping, fee summary, policy metadata, and all specified-day CSV/Markdown tables.
2. Bundled Node ran `scripts/unified_direct_v5/build_workbooks.mjs --inspect-templates`: passed. This rendered the official templates before editing.
3. The spreadsheet artifact marker ran once with `--operation-kind create --expected-output-count 5 --output-format xlsx`: passed.
4. Bundled Node ran `scripts/unified_direct_v5/build_workbooks.mjs`: passed. It recalculated, inspected, rendered, and exported all five workbooks with `@oai/artifact-tool`.
5. Bundled Node ran `scripts/unified_direct_v5/build_workbooks.mjs --inspect-saved`: passed. It rendered saved top sections, totals, and year-end tails.
6. Bundled Python ran `scripts/unified_direct_v5/verify_workbooks.py`: final pass. The readback used openpyxl and the original Appendix 1, Appendix 2, and Appendix 4 workbooks. It did not import the preparer or builder and did not read `workbook_payload.json`.

All authoring and verification commands set `TMPDIR`, `TMP`, and `TEMP` to `outputs/unified_direct_v5/runtime`. The dependency link is confined to `scripts/unified_direct_v5/node_modules`.

## Delivered files

- `outputs/unified_direct_v5/result1.xlsx`
- `outputs/unified_direct_v5/result2.xlsx`
- `outputs/unified_direct_v5/result3.xlsx`
- `outputs/unified_direct_v5/result4-2.xlsx`
- `outputs/unified_direct_v5/result4-3.xlsx`
- `outputs/unified_direct_v5/cost_summary.csv`
- `outputs/unified_direct_v5/policy_mapping.json`
- `outputs/unified_direct_v5/template_time_mapping.csv`
- `outputs/unified_direct_v5/specified_days/`: 50 CSV and 50 Markdown files covering both Q1 tables and three tables for each of four specified dates in each year-wide workbook.
- `reports/unified_direct_v5/workbook_readback.json` and `workbook_readback.md`: final independent readback.
- `reports/unified_direct_v5/workbook_readback_first_fail.json` and `workbook_readback_first_fail.md`: preserved first failure caused only by the verifier's initial metadata path base.
- `reports/unified_direct_v5/workbook_previews/`: template, authored, and saved-file layout previews.

## Independent coverage

The final readback covered five workbooks, 192,528 ledger intervals, 288,720 workbook grid cells, 1,336 year-date instances, 1,008 template time mappings, all 100 specified-day table files, every daily amount formula and cached result, all battery blocks and sparse SOC cells, and all 612 merged emergency-event rows. It reconstructed fixed and variable-price bills from the original source workbooks using the original contract, F_A adjustment, and 5p emergency formulas. Q1 reproduced 35,126.94858928963 yuan and D112 reproduced 13,913,892.481868185 yuan within the required absolute cost tolerance.

The metadata verifier checked all 30 recorded source, template, code, configuration, protocol, and ledger hashes. Original template SHA-256 values remained:

| Template | SHA-256 before and after |
| --- | --- |
| result1.xlsx | `28360e0974e7d6065394a8aba4e14a86773ae0036cc7d3ea1b211b515b03d688` |
| result2.xlsx | `1c26494cfc6d754e0bd9bff7e13e1126a73d2d2da6c5336eb251d89b9a1a1a47` |
| result3.xlsx | `c59da470cabd0be23f602c95c8aa9d11ec224a0cdac216b3e1f218e65d006bdc` |
| result4-2.xlsx | `1c26494cfc6d754e0bd9bff7e13e1126a73d2d2da6c5336eb251d89b9a1a1a47` |
| result4-3.xlsx | `c59da470cabd0be23f602c95c8aa9d11ec224a0cdac216b3e1f218e65d006bdc` |

## Layout and precision review

Saved previews show readable Chinese headers, corrected `00:00-00:10` through `23:50-24:00` interval labels, six-decimal numeric displays, complete daily totals and fees, six four-hour battery blocks per date, 00:00/24:00 SOC entries, and adjacent emergency intervals merged within each date. The Q3 and Q4-3 adjusted sheets hold final effective purchases. Q4-2 uses its new-ledger `grid_original_kwh` values on the plan sheet.

The workbooks store source numeric precision but display six decimals. Copying displayed text can therefore lose digits; the stored values and independent calculations remain unrounded. The selected ledgers had no positive emergency tails at or below the 1e-7 kWh event-listing threshold, so omitted event energy and cost are both zero. The working interpretation and assumptions remain those disclosed in the frozen protocol and its export amendment.
