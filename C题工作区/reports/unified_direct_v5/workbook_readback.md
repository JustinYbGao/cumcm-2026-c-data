# Workbook independent readback

- Status: **PASS**
- Checks: 4107481
- Numeric comparisons: 2143182
- Errors: 0
- Maximum absolute energy error: 7.27595761418e-11 kWh
- Maximum absolute cost error: 1.30385160446e-07 yuan

Saved workbooks were read independently with openpyxl. Bills were rebuilt from the original Appendix 1 and Appendix 4 prices using the applicable original contract, F_A adjustment, and 5p emergency formulas.

| Workbook | Strategy | Events | Omitted tiny emergency (kWh) | Total cost (yuan) |
| --- | --- | ---: | ---: | ---: |
| result1.xlsx | baseline | 0 | 0 | 35126.948589 |
| result2.xlsx | Q2_D112 | 185 | 0 | 13913892.481868 |
| result3.xlsx | q3_raw | 123 | 0 | 13561833.453414 |
| result4-2.xlsx | q42_fixed | 185 | 0 | 14678539.461690 |
| result4-3.xlsx | q43_raw_ols | 119 | 0 | 14321858.370546 |
