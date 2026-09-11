# Frozen innovation experiment package

Read papers/innovation_draft.md and reports/innovation/model_and_results.md.
Eleven policies have February-March calibration and April-December evaluation.
March selects PV bias correction, fixed reserve, and paid updates without a gate.
Later PV savings are positive; risk-reserve effects are only a few yuan and both
gates increase actual cost. All candidate results, including failures, remain.

This is exploratory retrospective evaluation, NOT a formal submission or a claim
of original algorithms. Time mapping, settlement, efficiency and terminal-state
assumptions remain explicit. No full Q4 transfer or combined innovation policy is
claimed. Proxy penalties are separate from actual bills.

Use Python 3.12, install requirements-q3.txt, then run inside a COPY:

    python -B scripts/validate_innovation.py
    python -B scripts/audit_innovation_lp.py
    python -B -m unittest discover -s tests -p test_innovation_core.py

All three commands ran in this copied package before its manifest was created.
Audits can rewrite runtime diagnostics, so keep this frozen directory unchanged.
Inputs include the cleaned actual/PV/price files and inherited frozen Q2 forecasts
and Q3 common-state source. Full recomputation uses scripts/run_innovation.py in
a new work copy without completed results/innovation. Source hashes are relative.
The 25 previous-model tests are evidenced in logs/innovation/base_tests.log; the
nine innovation tests are included. No unrelated member workspace is copied.

Figures contain English labels only, PNG at 300 dpi and SVG. The standalone
workspace/adapted_plot.py accepts data.csv and an output directory. Full ModelViz
services need the installed skill; historical template paths are provenance.
verify_innovation_artifacts.py also checks earlier packages in the parent workspace,
so it is not a portable numerical command. Initial render/repair evidence is retained.

manifest.json hashes all package files except itself. Sibling partNN.zip archives
are independent ZIPs containing disjoint paths: extract ALL parts into ONE folder.
Their .sha256 files and archive_index.json provide transport checks. Splitting keeps
individual transport files manageable; no byte concatenation is needed. BZD query
logs preserve full attribution and licensing.
