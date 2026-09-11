# First workbook readback failure snapshot

- Status: **FAIL**
- Checks: 4,106,606
- Numeric comparisons: 2,142,606
- Failures: 25
- Maximum absolute energy error: 7.275957614183426e-11 kWh
- Maximum absolute cost error: 1.30385160446167e-7 yuan

All 25 failures were `metadata_hash_path` failures. The first verifier resolved C题工作区-relative provenance paths from the repository parent. Workbook values, cached formulas, dates, mappings, raw-price bills, and specified-day tables had no failures. The final readback reruns the entire audit after correcting the path base.
