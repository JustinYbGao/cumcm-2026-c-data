# Original attachments required for full input reconstruction

The contest-supplied attachments are not redistributed in this package. Copy the exact original files without editing their contents or worksheet/header labels, using these package filenames:

| Supplied file | Destination | Purpose |
| --- | --- | --- |
| Attachment 1 | raw/attachment_1.xlsx | The undated Q1 day and known fixed tariff |
| Attachment 2 | raw/attachment_2.xlsx | Actual annual load and PV |
| Attachment 3 | raw/attachment_3.xlsx | Four daily hourly PV forecast releases |
| Attachment 4 | raw/attachment_4.xlsx | Actual annual tariff |

`required_files.json` records the expected SHA-256 identities. Renaming files is sufficient; leave original sheet names and headers intact. The parser validates original source-schema literals using equivalent ASCII Unicode escapes. The problem PDF and blank result templates are unnecessary for the numerical preparation command; the five completed English result workbooks are already included separately.

Run `python scripts/prepare_inputs.py` from the package root. This prepares Q1, the 52,560 actual ten-minute records, hourly PV releases, their ten-minute integrals, historical B0 forecasts and the causal OLS price cache. It does not optimize annual purchases. The first release lacks a prior anchor for its first hour, so those six unavailable intervals remain absent rather than zero-filled.
