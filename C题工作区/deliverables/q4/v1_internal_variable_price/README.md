# Q4 frozen internal variable-price results

Entry: papers/q4_draft.md. Full prescribed-day tables for Q4-2 and Q4-3 A/B:
reports/q4_representative_tables.md. Nine predefined retrospective policies are in
results/q4. Actual prices settle all policies; future actual prices are available
only to the explicitly hypothetical perfect-price controls.

This is NOT a formal submission. Future-price availability, target-price versus
locked-price settlement, A/B refunds, final-volume versus per-revision billing,
efficiency, terminal-state assumptions and template time mapping remain open.
All policies inherit the same Q2 fixed-price January warm-up state. Negative
intraday OLS-price results are preserved. Q1-Q3 source outputs are unchanged.

Use Python 3.12 and install requirements-q3.txt, then run inside a COPY:

    python -B scripts/validate_q4.py
    python -B scripts/audit_q4_lp.py
    python -B -m unittest discover -s tests -p test_q4.py

These commands were executed in this copied package before creating its manifest.
Audit outputs can change diagnostic metadata; preserve this frozen directory.
The 25-test full-workspace evidence is in logs/q4/all_model_tests.log; the five
Q4 tests and all numerical audit dependencies are included here. Full recomputation
requires a fresh work copy without completed results/q4; run scripts/run_q4.py.
All cleaned inputs and inherited forecasts required by that script are included.

Both figures have English labels, 300-dpi PNG and SVG. Each standalone
workspace/adapted_plot.py takes data.csv and an output directory. The full
ModelViz service pipeline requires the installed skill. Its historical absolute
paths are preserved as provenance. verify_q4_artifacts.py is a parent-workspace
preservation check and requires the previous packages and installed template;
it is not one of the portable numerical audit commands above.

The manifest hashes all packaged files except itself. Sibling ZIP/SHA256 files
provide transport integrity. BZD dictionary query logs retain full attribution
and licensing. No unrelated member workspace or previous frozen package is copied.
