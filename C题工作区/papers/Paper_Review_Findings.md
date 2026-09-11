# Paper Review Findings

## Evidence reviewed

- Current `main` at commit `861e840`: verified Q1–Q3 drafts, data processing, result ledgers, and validation records.
- `origin/codex/innovation-experiments` at commit `3d5c064`: the friend review guide, Q4 calculations, continuous PV-correction replay, and robustness materials.

## Updates applied

`Problem_Restatement_EN.md` now includes a shared-data/model section, evidence-backed Q1–Q4 result summaries, the Q2 negative comparison, the Q3 continuous correction result, Q4 price-scenario results, validation boundaries, and the remaining deliverable list. Results from the review branch are described as conditional on the stated conventions and are not represented as official Excel submissions.

## Material issues requiring resolution

1. **Q4 and robustness are not on `main`.** The newer review branch is one commit ahead and contains Q4, innovation, and robustness artifacts. Its content has been used as a reviewed source, but it has not been merged into the current working branch.
2. **Official result workbooks are not complete.** Internal CSV/ledger outputs exist, but the review guide states that `result1.xlsx`, `result2.xlsx`, `result3.xlsx`, `result4-2.xlsx`, and `result4-3.xlsx` still require final template mapping and independent read-back verification.
3. **Several task interpretations remain unresolved.** The time-label/template mapping, the meaning and side of the 90% efficiency and 5,000 kW limit, cross-day and terminal SOC conditions, price information availability, and revision-refund/settlement rules can materially change results.
4. **The Q2 selected forecasting combination is a documented failure.** It costs CNY 955,476.04 more than the seasonal baseline on the February–December replay. It should not be promoted as an improvement or silently replaced after observing the result.
5. **The Q3/Q4 correction results are conditional, not guarantees.** The continuous 28-day correction lowers cumulative cost in the tested settings, but it has loss days and months; block-resampling intervals are retrospective descriptions, not future-performance guarantees.
6. **The manuscript is still an assembly draft.** The four specified-date tables must be inserted into the relevant question sections, and the final manuscript still needs unified notation, formulas, table/figure numbering, citations, AI-use disclosure, anonymity, and page-layout review.
