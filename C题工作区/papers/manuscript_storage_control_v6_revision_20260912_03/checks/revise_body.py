"""Apply the recorded body-only edits to the frozen predecessor text."""
from pathlib import Path
import difflib
import hashlib
import json

P = Path(__file__).resolve().parents[1]
O = Path(json.loads((P / 'reports/revision_context.json').read_text())['predecessor'])
before = (O / 'manuscript_EN.md').read_text()
assert (P / 'manuscript_EN.md').read_text() == before
lines = before.splitlines()
edits = {
    245: ("Settlement wording", "Thus $C_{t,k}(q_t)=F_A(q_t;q_t^0,p^{\\mathrm{plan}}_{t\\mid k})$ at a paid update. The negative term implements the adopted net reduction adjustment. Reducing a one-kWh midnight commitment to zero leaves a half-price charge; increasing it to two kWh yields $2.5p_t$. These charges implement the working settlement interpretation in Table 3."),
    429: ("Correction result", "Q3 correction saves CNY 535.62 in the reserve arm and costs an additional CNY 8,925.36 in the greedy arm. This reversal ties the correction's value to the full purchasing and storage procedure. The earlier nominal-MILP correction study uses a different purchasing method (Appendix B)."),
    469: ("Repeated price qualification", "OLS saves CNY 3,079.27 in the reserve family and costs an additional CNY 6,786.91 in the matched greedy family. The selected reserve policy is `q42_ols_reserve`. Its total CNY 14,618,518.98 comprises CNY 13,704,872.50 of ordinary fees and CNY 913,646.48 of emergencies, all at actual variable prices. The selected policy saves CNY 68,043.65 relative to its same-input greedy control."),
    483: ("Resampling scope reference", "The raw-PV OLS-versus-fixed comparison has positive descriptive intervals: [14,140.65, 44,563.84] CNY with 7-day blocks and [11,797.92, 46,451.05] CNY with 14-day blocks. In contrast, both block lengths cross zero for each reserve-family PV-correction comparison, under fixed and OLS planning prices. These intervals distinguish the observed price effect from the smaller correction rankings; Section 8 defines their resampling scope."),
    487: ("Diagnostic figure introduction", "Figure 8 uses the prespecified diagnostic date, 14 July 2025, to show how released planning prices and procurement versions lead to the executed energy and reserve trace. Each version starts at its release and leaves completed intervals fixed. The actual-price trace provides retrospective settlement context."),
    501: ("Verification methods; counts relocated", "Independent verification rebuilt the source inputs and refitted historical forecasts at their own information cutoffs, using implementations separate from the production forecast, execution, billing, and objective functions. It replayed all twenty-two annual paths and checked candidate scores and saved workbooks. Table 9 reports the numerical discrepancies and tolerances; Appendix A records the coverage and reproduction details."),
    513: ("Workbook verification; counts relocated", "The workbook checks read the saved XLSX files directly and reconciled each variable-price emergency event with its independently checked ten-minute ledger allocation. Table 9 reports the energy and fee discrepancies for these saved quantities."),
    517: ("Numerical tie result", "Independent score accumulation gave a different first qualifying index in 2 numerically tied decisions. Each saved choice obeyed the original $10^{-8}$ CNY first-index rule on its saved scores. Recomputed scores stayed within the cash tolerance, and accepted index differences corresponded to purchase and reserve vectors agreeing within $10^{-6}$ kWh. The verification record lists the score gaps."),
    519: ("Information-test methods and outcomes", "Twenty-nine information tests used six preselected decision fixtures on 15 May: eighteen interventions on unavailable information, nine positive controls using permitted inputs, and two PV-access guards. Changing future demand/PV, unreleased PV forecasts, or future actual prices left the available inputs, full purchase/reserve candidates, scores, and selected pairs unchanged. Permitted PV, completed price history, and actual-energy changes produced the expected responses. The tests disabled price caches and kept the B0 archive fixed; its historical reconstruction was checked separately. The Q4-2 guard enforced the working interpretation in Table 3."),
    521: ("Reproduction summary; details relocated", "An isolated reproduction of the selected reserve policies rebuilt the kernel and reproduced the saved trajectories and candidate/input arrays exactly. It used the same host and dependency versions; Appendix A specifies the comparisons and exclusions."),
    523: ("Optimizer stopping and independent billing", "Of 85,504 local searches across twenty-two annual policies, 46,365 ended with non-success stopping records. The logs contain 0 solver exceptions, 0 initializer fallbacks, and 0 invalid-return fallbacks. Selection retained a starting candidate 12 times and the complete keep-current pair 3,047 times. Every finite retained pair was rescored before selection and executed through the hard physical rule. Independent rebilling of the saved ledgers, using separately validated prices, also recomputed all twenty-two summaries and twenty-nine named paired comparisons."),
    525: ("Forecast-error results and scope", "Figure 9 compares midnight forecasts with the latest release permitted by the 00:00/06:00/12:00/18:00 protocol on the selected raw-PV/OLS Q4-3 reserve path. The PV panels share 26,880 intervals with positive actual generation. This subset is chosen retrospectively for evaluation and excludes 21,216 zero-generation intervals, including 1,280 positive forecasts in each version. It leaves forecast-time inputs unchanged. PV MAE falls from 60.77 to 31.83 kWh per ten-minute interval on the subset and from 34.44 to 18.27 kWh over all 48,096 intervals. Price MAE changes from 0.04270 to 0.04240 CNY/kWh. These error summaries cover one retained historical path; Table 15 gives the matched policy comparisons used to assess operating costs."),
    535: ("Daily-distribution introduction", "Figure 10 shows why winning on many days need not reduce the annual bill: the selected Q3 reserve policy saves money on 188 of 334 days but costs CNY 6,206.07 more over the full period. The plotted observations retain both tails; Table 10 gives the annual block intervals."),
    578: ("Consolidated resampling limitations", "Circular block resampling retains neighboring daily differences and wraps at the endpoints [9]. Both block lengths use 2,000 resamples with seed 20260915. The procedure resamples fixed historical cost differences: it neither reruns the battery on new weather nor refits forecasts, and it leaves repeated 2025 selection uncorrected. Its intervals therefore provide no selection-adjusted inference for unseen years or causal effects. The density displays and descriptive clustering summarize observed variation without significance tests. Scenario ordering was preserved; a shuffled-scenario comparison was not performed."),
    598: ("Concrete limitations and next steps", "Interval labels, efficiency and power measurement, interpolation, balancing, and rule-A settlement follow working conventions; official clarification or metering specifications would be needed before recalculating under different conventions. Q4-2's exclusion of Attachment 3 is also an author interpretation. Surplus charging and preissued reserve thresholds restrict the control law, and finite nonsmooth search supplies no global certificate. Richer causal controllers and independently bounded solutions should therefore be compared on the same information set. The fixed terminal proxy omits degradation and network dynamics; estimating these costs and testing a longer horizon require measured battery-aging and network data. Repeated selection on one historical year limits evidence for future savings. Untouched periods, prespecified comparisons, and matched tests of history windows, weights, capacity, and sustained forecast bias remain necessary. None of these additional tests has been performed for the current reserve controller."),
}
# Resolve the settlement paragraph by its literal start, rather than trust a line.
settlement = next(i + 1 for i, line in enumerate(lines) if line.startswith('Thus $C_{t,k}'))
edits[settlement] = edits.pop(245)
records = []
for n, (reason, new) in sorted(edits.items()):
    old = lines[n - 1]
    assert old and not old.startswith(('#', '|', '![', '*Figure', '$$'))
    assert n > 21 and old != new
    lines[n - 1] = new
    records.append({'source_line_before': n, 'reason': reason, 'before': old, 'after': new})

coverage = (
    'Verification coverage comprised the original input workbooks, 364 historical B0 forecast days, '
    '1,460 raw PV releases, and 1,336 causal price releases. Across all annual paths, the checks '
    'covered 1,058,112 actual intervals, 21,376 decisions, 270,540 retained candidate pairs, and '
    '27,544,050 candidate-scenario forward paths. A separate saved-result check replayed the '
    '22 realized trajectories and reread the five workbooks.'
)
workbooks = before.splitlines()[512].split(' It read the saved XLSX files directly.')[0]
reproduction = before.splitlines()[520]
anchor = before.splitlines()[650]
assert lines[650] == anchor
after = '\n'.join(lines) + '\n'
after = after.replace(anchor + '\n', anchor + '\n\n' + coverage + '\n\n' + workbooks + '\n\n' + reproduction + '\n', 1)
abstract = lambda s: s.split('## Abstract\n', 1)[1].split('# 1 Problem')[0]
assert abstract(after) == abstract(before)
new_title = 'A Study of Microgrid Power Scheduling Based on Mixed-Integer Programming and Historical Scenario Optimization'
old_title = before.splitlines()[0][2:]
after = after.replace('# ' + old_title + '\n', '# ' + new_title + '\n', 1)
records.append({'source_line_before': 1, 'reason': 'User-requested English title pattern', 'before': '# ' + old_title, 'after': '# ' + new_title})
main = (P / 'main.tex').read_text()
assert 'pdftitle={' + old_title + '}' in main
main = main.replace('pdftitle={' + old_title + '}', 'pdftitle={' + new_title + '}')
(P / 'main.tex').write_text(main)
assert after.split('# AI tool usage declaration')[1].split('# Appendix A')[0] == before.split('# AI tool usage declaration')[1].split('# Appendix A')[0]
assert after.split('# Appendix B')[1] == before.split('# Appendix B')[1]
(P / 'manuscript_EN.md').write_text(after)
records.append({'source_line_before': 651, 'reason': 'Coverage and reproduction details relocated to Appendix A', 'before': anchor, 'after': anchor + '\n\n' + coverage + '\n\n' + workbooks + '\n\n' + reproduction})
(P / 'reports/editorial_changes.json').write_text(json.dumps(records, indent=2) + '\n')
(P / 'reports/manuscript_changes.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='revision_02/manuscript_EN.md', tofile='revision_03/manuscript_EN.md')))
print(json.dumps({'locations_changed': len(records), 'abstract_and_keywords_sha256': hashlib.sha256(abstract(after).encode()).hexdigest(), 'abstract_and_keywords_unchanged': True, 'title': new_title}, indent=2))
